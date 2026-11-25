# -*- coding: utf-8 -*-
"""Executor do pipeline (STEPs 1-5) em uma QThread, e do cálculo MM/PBSA (STEP 6).

Diferenças em relação às versões antigas do CODYN:
  - um único executor sequencial (sem QWidgets criados fora da thread da GUI);
  - cada execução (proteína+ligante) é independente: se uma falha, as demais continuam;
  - cancelamento real: mata os processos gmx/acpype/mpirun (grupo de processos), não só uma flag;
  - o retorno de cada comando é verificado — nada de seguir adiante após um erro.
"""

import json
import os
import re
import threading
from datetime import datetime
from typing import Dict, List, Optional

from PyQt5.QtCore import QThread, pyqtSignal

from BIN import module_cell, module_equilibration, module_ligands, module_production, module_protein
from BIN.context import RunContext, StepError
from BIN.mdp_tools import ndx_group_index
from BIN.platform_utils import IS_WINDOWS
from BIN.runconfig import LIG_RESNAME, RunConfig
from BIN.tools import CancelToken, PipelineCancelled, find_executable, find_gmx, run_cmd
from BIN.versao import VERSAO

# (índice da aba, passo, função, rótulo)
STAGES = [
    (2, "lig"),
    (3, "prot"),
    (4, "cell"),
    (5, "eq"),
    (6, "md"),
]


def create_run_folders(runs_dir: str, cfg: RunConfig, prot_names: List[str], lig_names: List[str]) -> List[dict]:
    """Cria <projeto>/RUNS/<data>_<proteína>_<ligante>/ e grava run_config.json em cada uma."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    os.makedirs(runs_dir, exist_ok=True)
    infos = []
    for prot in prot_names:
        for lig in lig_names:
            base = os.path.join(runs_dir, f"{stamp}_{prot}_{lig}")
            folder, n = base, 1
            while os.path.exists(folder):          # nunca reaproveita uma pasta de execução anterior
                n += 1
                folder = f"{base}-{n}"
            os.makedirs(folder)
            data = cfg.to_dict()
            data.update({"protein": prot, "ligand": lig, "codyn_version": VERSAO, "created": stamp})
            with open(os.path.join(folder, "run_config.json"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            infos.append({"run_folder": folder, "prot_name": prot, "lig_name": lig})
    return infos


class PipelineWorker(QThread):
    log_signal = pyqtSignal(str, str)            # passo, mensagem
    stage_signal = pyqtSignal(int)               # índice da aba a exibir
    progress_signal = pyqtSignal(str, int, int, int)  # passo, atual, total, restante(s) (-1 = desconhecido)
    request_file_signal = pyqtSignal(object)     # pedido de arquivo (dict) -> GUI
    run_done_signal = pyqtSignal(str, bool, str)  # pasta, ok, mensagem
    finished_signal = pyqtSignal(bool, list)     # tudo ok?, pastas que falharam

    def __init__(self, codyn_dir: str, cfg: RunConfig, run_infos: List[dict], token: CancelToken, parent=None):
        super().__init__(parent)
        self.codyn_dir = codyn_dir
        self.cfg = cfg
        self.run_infos = run_infos
        self.token = token

    # --- pedido de arquivo ao usuário (bloqueia ESTA thread até a GUI responder) ---
    def _request_file(self, req: dict) -> Optional[str]:
        ev = threading.Event()
        req = dict(req, event=ev, result={"path": None})
        self.request_file_signal.emit(req)
        while not ev.wait(0.2):
            if self.token.is_set():
                return None
        return req["result"]["path"]

    def _on_progress(self, step: str, cur: int, total: int, remaining: Optional[int]):
        self.progress_signal.emit(step, int(cur), int(total), -1 if remaining is None else int(remaining))

    def run(self):
        gmx = find_gmx()
        failed: List[str] = []
        try:
            if not gmx:
                raise StepError("GROMACS ('gmx') not found. Use 'Install requirements'.")
            ctxs: List[RunContext] = []
            for info in self.run_infos:
                ctxs.append(RunContext(
                    codyn_dir=self.codyn_dir, run_folder=info["run_folder"], prot_name=info["prot_name"],
                    lig_name=info["lig_name"], cfg=self.cfg, gmx=gmx, token=self.token,
                    logger=lambda step, msg: self.log_signal.emit(step, msg),
                    request_file=self._request_file, on_progress=self._on_progress,
                ))
            alive = list(ctxs)

            def stage(step_key, fn):
                for ctx in list(alive):
                    if self.token.is_set():
                        raise PipelineCancelled()
                    try:
                        fn(ctx)
                    except PipelineCancelled:
                        raise
                    except StepError as e:
                        ctx.log(step_key, f"ERROR: {e}", stamp=False)
                        alive.remove(ctx)
                        failed.append(ctx.run_folder)
                        self.run_done_signal.emit(ctx.run_folder, False, str(e).splitlines()[0])
                    except Exception as e:  # erro inesperado: registra e segue com as demais execuções
                        ctx.log(step_key, f"ERROR (unexpected): {type(e).__name__}: {e}", stamp=False)
                        alive.remove(ctx)
                        failed.append(ctx.run_folder)
                        self.run_done_signal.emit(ctx.run_folder, False, f"{type(e).__name__}: {e}")

            lig_dir, prot_dir = self.cfg.ligands_dir, self.cfg.protein_dir
            self.stage_signal.emit(2)
            stage("lig", lambda c: module_ligands.prepare_ligand(c, lig_dir))
            self.stage_signal.emit(3)
            stage("prot", lambda c: module_protein.prepare_complex(c, prot_dir))
            self.stage_signal.emit(4)
            stage("cell", module_cell.prepare_cell)
            self.stage_signal.emit(5)
            stage("eq", lambda c: (module_equilibration.run_nvt(c), module_equilibration.run_npt(c)))
            self.stage_signal.emit(6)
            stage("md", module_production.run_production)
            for c in alive:
                self.run_done_signal.emit(c.run_folder, True, "")
            self.stage_signal.emit(7)
            self.finished_signal.emit(not failed, failed)
        except PipelineCancelled:
            self.log_signal.emit("md", "Cancelled by the user.")
            self.finished_signal.emit(False, failed)
        except StepError as e:
            self.log_signal.emit("lig", f"ERROR: {e}")
            self.finished_signal.emit(False, [i["run_folder"] for i in self.run_infos])
        except Exception as e:
            self.log_signal.emit("lig", f"ERROR (unexpected): {type(e).__name__}: {e}")
            self.finished_signal.emit(False, [i["run_folder"] for i in self.run_infos])


# =============================== MM/PBSA ===============================

MMPBSA_TEMPLATE = """\
# General namelist variables
&general
  # System name
  sys_name             = "{sys_name}",
  # First frame to analyze
  startframe={frame_start},
  # Last frame to analyze
  endframe={frame_end},
  interval={interval},
  # How many energy terms to print in the final output
  verbose={verbose},
/
# Generalized-Born namelist variables
&gb
  # GB model to use
  igb={igb},
  saltcon={sltcon},
/
#&pb
#  istrng={istrng}, fillratio={fill_ratio},
#/
&decomp
idecomp={idecomp}, dec_verbose={dec_verbose},
# This will print all residues that are less than 4 Å between
# the receptor and the ligand
#  print_res='Within 4',
/
"""


def find_production_tag(run_folder: str) -> Optional[str]:
    """Rótulo de tempo (100, 0.5...) do arquivo md_0_<tag>.tpr/.xtc da pasta, se existir."""
    for fname in sorted(os.listdir(run_folder)):
        m = re.fullmatch(r"md_0_([0-9]+(?:\.[0-9]+)?)\.xtc", fname)
        if m:
            return m.group(1)
    return None


def write_mmpbsa_input(run_folder: str, params: Dict[str, str]):
    sys_name = os.path.basename(os.path.normpath(run_folder))
    with open(os.path.join(run_folder, "mmpbsa.in"), "w", encoding="utf-8", newline="\n") as f:
        f.write(MMPBSA_TEMPLATE.format(sys_name=sys_name, **params))


class MMPBSAWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)
    run_done_signal = pyqtSignal(str, bool)

    def __init__(self, run_folders: List[str], params: Dict[str, str], n_threads: int, token: CancelToken, parent=None):
        super().__init__(parent)
        self.run_folders = run_folders
        self.params = params
        self.n_threads = int(n_threads)
        self.token = token

    def run(self):
        ok_all = True
        try:
            exe = find_executable("gmx_MMPBSA", extra=["/usr/local/bin/gmx_MMPBSA"], search_conda=True)
            mpirun = find_executable("mpirun")
            if not exe:
                if IS_WINDOWS:   # gmx_MMPBSA depende do AmberTools (sander/MMPBSA.py), que não existe para Windows
                    self.log_signal.emit("ERROR: gmx_MMPBSA needs AmberTools, which has no Windows build. "
                                         "STEP 6 (MM/GBSA) is available on Linux only; the other steps and the "
                                         "analyses of the RESULTS tab work normally on Windows.")
                else:
                    self.log_signal.emit("ERROR: gmx_MMPBSA not found. Use 'Install requirements'.")
                self.finished_signal.emit(False)
                return
            gmx = find_gmx()
            env = {"PATH": (os.path.dirname(gmx) + os.pathsep + os.environ.get("PATH", "")) if gmx else os.environ.get("PATH", "")}
            for folder in self.run_folders:
                if self.token.is_set():
                    raise PipelineCancelled()
                name = os.path.basename(folder)
                tag = find_production_tag(folder)
                if not tag:
                    self.log_signal.emit(f"[{name}] ERROR: production trajectory (md_0_*.xtc) not found.")
                    ok_all = False
                    self.run_done_signal.emit(folder, False)
                    continue
                ndx = os.path.join(folder, "index.ndx")
                ig_p, ig_l = ndx_group_index(ndx, "Protein"), ndx_group_index(ndx, LIG_RESNAME)
                needed = [f"md_0_{tag}.tpr", f"md_0_{tag}_noPBC.xtc", "index.ndx", "topol.top"]
                missing = [n for n in needed if not os.path.exists(os.path.join(folder, n))]
                if missing or ig_p is None or ig_l is None:
                    self.log_signal.emit(f"[{name}] ERROR: missing {', '.join(missing) or 'index groups Protein/' + LIG_RESNAME}.")
                    ok_all = False
                    self.run_done_signal.emit(folder, False)
                    continue
                write_mmpbsa_input(folder, self.params)
                base = [exe, "MPI"] if mpirun else [exe]
                # nunca mais processos MPI do que quadros a analisar (o gmx_MMPBSA falha nesse caso)
                nframes = max(1, (int(self.params["frame_end"]) - int(self.params["frame_start"])) // max(1, int(self.params["interval"])) + 1)
                nproc = max(1, min(self.n_threads, nframes))
                cmd = ([mpirun, "-np", str(nproc)] if mpirun else []) + base + [
                    "-O", "-nogui", "-i", "mmpbsa.in", "-cs", f"md_0_{tag}.tpr", "-ci", "index.ndx",
                    "-cg", str(ig_p), str(ig_l), "-ct", f"md_0_{tag}_noPBC.xtc", "-cp", "topol.top",
                    "-o", "FINAL_RESULTS_MMPBSA.dat", "-eo", "FINAL_RESULTS_MMPBSA.csv"]
                self.log_signal.emit(f"[{name}] command: {' '.join(cmd)}")
                rc, out = run_cmd(cmd, cwd=folder, token=self.token, env=env,
                                  log=lambda l, n=name: self.log_signal.emit(f"[{n}] {l}"), log_every=0.2)
                if rc == 0:
                    self.log_signal.emit(f"[{name}] MMPBSA/MMGBSA finished successfully!")
                else:
                    self.log_signal.emit(f"[{name}] ERROR: gmx_MMPBSA failed (exit code {rc}).")
                    ok_all = False
                self.run_done_signal.emit(folder, rc == 0)
            self.finished_signal.emit(ok_all)
        except PipelineCancelled:
            self.log_signal.emit("Cancelled by the user.")
            self.finished_signal.emit(False)
        except Exception as e:
            self.log_signal.emit(f"ERROR: {type(e).__name__}: {e}")
            self.finished_signal.emit(False)
