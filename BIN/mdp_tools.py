# -*- coding: utf-8 -*-
"""Edição de arquivos .mdp por CHAVE (não por número de linha).

As versões antigas do CODYN usavam `sed -i '33s/.*/.../'`: qualquer linha a mais ou a menos no
template quebrava silenciosamente o .mdp. Aqui cada parâmetro é localizado pelo nome (GROMACS trata
'-' e '_' como equivalentes e ignora maiúsculas) e, se não existir, é acrescentado ao final.
"""

import os
import re
import shutil
from typing import Dict, Optional

from BIN.runconfig import RunConfig, WATER_MODELS


def _norm(key: str) -> str:
    return key.strip().lower().replace("_", "-")


def mdp_set(path: str, params: Dict[str, object]):
    """Define parâmetros no .mdp, preservando comentários e a ordem das demais linhas."""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    todo = {_norm(k): (k, v) for k, v in params.items()}
    out = []
    for line in lines:
        body = line.split(";", 1)[0]
        if "=" in body and not line.lstrip().startswith(";"):
            key = _norm(body.split("=", 1)[0])
            if key in todo:
                orig, val = todo.pop(key)
                comment = ""
                if isinstance(val, tuple):          # (valor, comentário novo)
                    val, new_comment = val
                    comment = f" ; {new_comment}" if new_comment else ""
                elif ";" in line:
                    comment = " ;" + line.split(";", 1)[1]
                out.append(f"{orig:<24}= {val}{comment}")
                continue
        out.append(line)
    for orig, val in todo.values():
        if isinstance(val, tuple):
            val = val[0]
        out.append(f"{orig:<24}= {val}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


def mdp_get(path: str, key: str) -> Optional[str]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            body = line.split(";", 1)[0]
            if "=" in body and _norm(body.split("=", 1)[0]) == _norm(key):
                return body.split("=", 1)[1].strip()
    return None


# ajustes específicos de campo de força (o template de BASE/ é o do CHARMM36)
_AMBER_NONBONDED = {
    "vdwtype": "cutoff",
    "vdw-modifier": "potential-shift",
    "rvdw": 1.0,
    "rcoulomb": 1.0,
    "rlist": 1.0,
    "DispCorr": "EnerPres",
}


def prepare_mdps(base_dir: str, run_folder: str, cfg: RunConfig, tc_group_1: str = "Protein_LIG",
                 tc_group_2: str = "Water_and_ions") -> Dict[str, str]:
    """Copia os templates de BASE/ para a pasta da execução e ajusta pelos valores de `cfg`.

    Devolve {nome: caminho} dos .mdp gerados (em.mdp, ions.mdp, nvt.mdp, npt.mdp, md.mdp)."""
    made = {}
    temp = f"{cfg.temperature_K:g}"
    for name in ("ions.mdp", "em.mdp", "nvt.mdp", "npt.mdp", "md.mdp"):
        src = os.path.join(base_dir, name)
        dst = os.path.join(run_folder, name)
        if not os.path.isfile(src):
            raise FileNotFoundError(f"Template not found: {src}")
        shutil.copy2(src, dst)
        params: Dict[str, object] = {}
        if cfg.family == "amber" and name != "ions.mdp":
            params.update(_AMBER_NONBONDED)
            params["rvdw-switch"] = 0  # sem efeito com potential-shift, evita aviso de configuração mista
        if name in ("nvt.mdp", "npt.mdp", "md.mdp"):
            steps = cfg.steps_md if name == "md.mdp" else cfg.steps_eq
            ns = cfg.production_time_ns if name == "md.mdp" else cfg.equilibration_time_ns
            params.update({
                "nsteps": (steps, f"{steps} x {cfg.integration_time_fs:g} fs = {ns:g} ns"),
                "dt": (f"{cfg.dt_ps:g}", f"{cfg.integration_time_fs:g} fs"),
                "tc-grps": f"{tc_group_1} {tc_group_2}",
                "tau_t": "0.1   0.1",
                "ref_t": f"{temp}   {temp}",
            })
            if name == "nvt.mdp":
                params["gen_temp"] = temp
        mdp_set(dst, params)
        made[name] = dst
    if cfg.family == "amber":
        # sem modificador de força, o corte vdW de 1.0 nm precisa de rlist >= rvdw
        mdp_set(made["ions.mdp"], {"rlist": 1.0})
    return made


def solvent_box_file(water_key: str) -> str:
    return WATER_MODELS.get(water_key, WATER_MODELS["tip3p"])[1]


_GROUP_RE = re.compile(r"^\s*\[\s*(.+?)\s*\]\s*$")


def read_ndx_groups(ndx_path: str):
    """Lista ordenada com os nomes dos grupos de um index.ndx (índice = posição)."""
    groups = []
    if not os.path.isfile(ndx_path):
        return groups
    with open(ndx_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = _GROUP_RE.match(line)
            if m:
                groups.append(m.group(1))
    return groups


def ndx_group_index(ndx_path: str, name: str) -> Optional[int]:
    for i, g in enumerate(read_ndx_groups(ndx_path)):
        if g == name:
            return i
    return None
