# -*- coding: utf-8 -*-
"""STEP 1 — Preparo e parametrização dos ligantes.

Fluxo (por ligante, tudo dentro da pasta <projeto>/RUNS/<execução>/):
  1. converte o ligante (pdbqt/pdb/mol2/sdf) em MOL2 com hidrogênios e cargas de Gasteiger (Open Babel);
  2. padroniza o nome do resíduo para LIG (cabe no .gro, igual em todos os arquivos) e calcula a
     carga líquida;
  3. parametriza:
       - CHARMM36 -> CGenFF: usa um .str já existente (pasta do ligante/RUNS do projeto) ou pede ao usuário que
         importe o arquivo pela própria interface (ver `request_file`); valida penalidades e converte;
       - AMBER    -> GAFF/GAFF2 (AM1-BCC ou Gasteiger) com acpype/antechamber, totalmente automático;
  4. gera LIG.gro, LIG.itp (+ LIG.prm no CHARMM) e as restrições de posição do ligante.
"""

import os
import re
import shutil
from typing import Dict, List, Optional, Tuple

from BIN.context import RunContext, StepError
from BIN.mdp_tools import read_ndx_groups
from BIN.runconfig import LIG_RESNAME, LIGAND_METHOD_LABELS
from BIN.platform_utils import python_exe
from BIN.tools import find_executable, find_obabel, find_perl

STEP = "lig"
LIG_FILE_EXTS = (".pdbqt", ".pdb", ".mol2", ".sdf", ".mol")


# ------------------------------- utilidades -------------------------------

def find_ligand_file(ligands_dir: str, lig_name: str) -> Optional[str]:
    for ext in LIG_FILE_EXTS:
        p = os.path.join(ligands_dir, lig_name + ext)
        if os.path.isfile(p):
            return p
    return None


def list_ligands(ligands_dir: str) -> List[str]:
    """Nomes (sem extensão) dos ligantes suportados em `ligands_dir`."""
    if not os.path.isdir(ligands_dir):
        return []
    names = []
    for f in sorted(os.listdir(ligands_dir)):
        base, ext = os.path.splitext(f)
        if ext.lower() in LIG_FILE_EXTS and os.path.isfile(os.path.join(ligands_dir, f)):
            names.append(base)
    return names


def mol2_net_charge(mol2_path: str) -> int:
    """Carga líquida = soma das cargas parciais de Gasteiger (conserva a carga formal)."""
    total, in_atoms = 0.0, False
    with open(mol2_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("@<TRIPOS>"):
                in_atoms = line.startswith("@<TRIPOS>ATOM")
                continue
            if in_atoms:
                parts = line.split()
                if len(parts) >= 9:
                    try:
                        total += float(parts[8])
                    except ValueError:
                        pass
    return int(round(total))


def normalize_mol2_resname(mol2_path: str, resname: str = LIG_RESNAME):
    """Define o nome da molécula (linha 2) e o nome do resíduo (coluna 8 dos átomos) como `resname`."""
    with open(mol2_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.read().splitlines()
    out, section, mol_line = [], "", -1
    for line in lines:
        if line.startswith("@<TRIPOS>"):
            section = line.strip()
            mol_line = 0
            out.append(line)
            continue
        if section == "@<TRIPOS>MOLECULE":
            mol_line += 1
            if mol_line == 1:
                line = resname
        elif section == "@<TRIPOS>ATOM":
            parts = line.split()
            if len(parts) >= 8:
                # colunas: id name x y z type subst_id subst_name charge
                head = line.split(None, 7)
                if len(head) >= 8:
                    rest = head[7].split(None, 1)
                    tail = (" " + rest[1]) if len(rest) > 1 else ""
                    line = "{:>7} {:<8} {:>10} {:>10} {:>10} {:<8} {:>3} {:<8}{}".format(
                        head[0], head[1], head[2], head[3], head[4], head[5], head[6], resname, tail)
        elif section == "@<TRIPOS>SUBSTRUCTURE":
            parts = line.split()
            if len(parts) >= 2:
                parts[1] = resname
                line = " ".join(parts)
        out.append(line)
    with open(mol2_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


def itp_total_charge(itp_path: str) -> Optional[float]:
    """Soma das cargas da seção [ atoms ] de um .itp (para conferência da parametrização)."""
    total, in_atoms, found = 0.0, False, False
    with open(itp_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.split(";", 1)[0].strip()
            if not line:
                continue
            if line.startswith("["):
                in_atoms = re.match(r"\[\s*atoms\s*\]", line, re.I) is not None
                continue
            if in_atoms:
                parts = line.split()
                if len(parts) >= 7:
                    try:
                        total += float(parts[6])
                        found = True
                    except ValueError:
                        pass
    return total if found else None


# ------------------------------- CGenFF -------------------------------

_RESI_RE = re.compile(r"^(RESI\s+)(\S+)(\s+)(-?\d+\.\d+)?(.*)$")
_PEN_RE = re.compile(r"param\s+penalty\s*=\s*([\d.]+)\s*;\s*charge\s+penalty\s*=\s*([\d.]+)", re.I)


def parse_cgenff_str(path: str) -> Dict[str, object]:
    """Lê o .str do CGenFF: nome do resíduo, carga e penalidades (parâmetros e cargas)."""
    info: Dict[str, object] = {"resname": None, "charge": None, "param_penalty": None, "charge_penalty": None}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = _RESI_RE.match(line.strip())
            if m and info["resname"] is None:
                info["resname"] = m.group(2)
                if m.group(4) is not None:
                    info["charge"] = float(m.group(4))
                pm = _PEN_RE.search(m.group(5) or "")
                if pm:
                    info["param_penalty"] = float(pm.group(1))
                    info["charge_penalty"] = float(pm.group(2))
    return info


def validate_cgenff_str(path: str) -> Tuple[bool, str]:
    """Verifica se o arquivo parece um .str do CGenFF (para recusar importações erradas na GUI)."""
    try:
        text = open(path, "r", encoding="utf-8", errors="ignore").read()
    except OSError as e:
        return False, str(e)
    if "read rtf card append" not in text.lower() or not re.search(r"^RESI\s+\S+", text, re.M):
        return False, "not a CGenFF stream file (.str): missing 'read rtf card append' / 'RESI'"
    if not re.search(r"^read\s+param", text, re.I | re.M):
        return False, "the .str has no parameter section ('read param card')"
    return True, ""


def rewrite_resname_in_str(src: str, dst: str, resname: str = LIG_RESNAME) -> Optional[str]:
    """Copia o .str trocando 'RESI <qualquer>' por 'RESI LIG'. Devolve o nome antigo."""
    old = None
    out = []
    with open(src, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = _RESI_RE.match(line.rstrip("\n"))
            if m and old is None:
                old = m.group(2)
                rest = (m.group(4) or "") and f"{m.group(3)}{m.group(4)}"
                line = f"{m.group(1)}{resname}{rest or m.group(3)}{m.group(5)}\n"
            out.append(line)
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(out)
    return old


def find_existing_str(ctx: RunContext, ligands_dir: str) -> Optional[str]:
    n = ctx.lig_name
    runs_dir = os.path.dirname(os.path.abspath(ctx.run_folder))
    candidates = [
        ctx.path(f"{LIG_RESNAME}.str"),
        ctx.path(f"{n}_fix.str"), ctx.path(f"{n}.str"),
        os.path.join(ligands_dir, f"{n}_fix.str"), os.path.join(ligands_dir, f"{n}.str"),
        # .str soltos na pasta RUNS do projeto (a pasta da execução é <projeto>/RUNS/<execução>)
        os.path.join(runs_dir, f"{n}_fix.str"), os.path.join(runs_dir, f"{n}.str"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


# ------------------------------- etapas -------------------------------

def _convert_to_mol2(ctx: RunContext, lig_file: str) -> str:
    obabel = find_obabel()
    if not obabel:
        raise StepError("Open Babel ('obabel') not found. Use 'Install requirements' (OpenBabel).")
    ext = os.path.splitext(lig_file)[1].lower()
    ctx.log(STEP, f"Processing ligand {os.path.basename(lig_file)} with Open Babel...")
    src = ctx.path("ligand_input" + ext)
    shutil.copy2(lig_file, src)
    fmt = {"pdbqt": "pdbqt", "pdb": "pdb", "mol2": "mol2", "sdf": "sdf", "mol": "mol"}[ext[1:]]
    # 1) coordenadas + hidrogênios ausentes; 2) cargas de Gasteiger no MOL2
    ctx.run(STEP, [obabel, f"-i{fmt}", src, "-opdb", "-O", ctx.path("ligand_raw.pdb")], what="obabel (-> pdb)", quiet=True)
    ctx.log(STEP, "Converted to PDB.")
    ctx.run(STEP, [obabel, "-ipdb", ctx.path("ligand_raw.pdb"), "-h", "-opdb", "-O", ctx.path("ligand_h.pdb")],
            what="obabel (+H)", quiet=True)
    ctx.log(STEP, "Added hydrogens.")
    out_mol2 = ctx.path(f"{LIG_RESNAME}.mol2")
    ctx.run(STEP, [obabel, "-ipdb", ctx.path("ligand_h.pdb"), "--partialcharge", "gasteiger", "-omol2", "-O", out_mol2],
            what="obabel (-> mol2)", quiet=True)
    if not os.path.isfile(out_mol2) or os.path.getsize(out_mol2) == 0:
        raise StepError("Open Babel did not produce the MOL2 file.")
    normalize_mol2_resname(out_mol2)
    ctx.log(STEP, f"Generated {LIG_RESNAME}.mol2 with Gasteiger charges (residue name set to {LIG_RESNAME}).")
    return out_mol2


def _parametrize_cgenff(ctx: RunContext, mol2: str, net_charge: int, ligands_dir: str):
    perl = find_perl()
    script = os.path.join(ctx.base_dir, "sort_mol2_bonds.pl")
    fix_mol2 = ctx.path(f"{LIG_RESNAME}_fix.mol2")
    if not perl or not os.path.isfile(script):
        raise StepError("perl or BASE/sort_mol2_bonds.pl not found (required to prepare the MOL2 for CGenFF).")
    ctx.log(STEP, "Correcting bonds in MOL2 (sort_mol2_bonds.pl)...")
    ctx.run(STEP, [perl, script, mol2, fix_mol2], what="sort_mol2_bonds.pl", quiet=True)

    str_src = find_existing_str(ctx, ligands_dir)
    if str_src:
        ctx.log(STEP, f"Using existing CGenFF stream file: {str_src}")
    else:
        ctx.log(STEP, "CGenFF stream (.str) not found. Waiting for the file to be provided in the interface...")
        if ctx.request_file is None:
            raise StepError("CGenFF .str file is required and no interactive handler is available.")
        str_src = ctx.request_file({
            "kind": "cgenff_str", "lig_name": ctx.lig_name, "mol2": fix_mol2,
            "run_folder": ctx.run_folder, "net_charge": net_charge,
        })
        ctx.check_cancel()
        if not str_src:
            raise StepError("CGenFF .str was not provided; ligand skipped.")
    ok, why = validate_cgenff_str(str_src)
    if not ok:
        raise StepError(f"Invalid CGenFF file '{os.path.basename(str_src)}': {why}")
    str_dst = ctx.path(f"{LIG_RESNAME}.str")
    old = rewrite_resname_in_str(str_src, str_dst)
    info = parse_cgenff_str(str_dst)
    ctx.log(STEP, f"CGenFF residue '{old}' -> {LIG_RESNAME}; charge {info['charge']}, "
                  f"param penalty {info['param_penalty']}, charge penalty {info['charge_penalty']}.")
    pp, cp = info["param_penalty"], info["charge_penalty"]
    if (pp is not None and pp > 50) or (cp is not None and cp > 50):
        ctx.log(STEP, "Warning: CGenFF penalties above 50 — parameters/charges need validation (consider refining them).", stamp=False)
    elif (pp is not None and pp > 10) or (cp is not None and cp > 10):
        ctx.log(STEP, "Attention: CGenFF penalties between 10 and 50 — check the highlighted parameters.", stamp=False)
    if info["charge"] is not None and abs(info["charge"] - net_charge) > 0.01:
        ctx.log(STEP, f"Warning: CGenFF net charge ({info['charge']}) differs from the MOL2-derived charge ({net_charge}).", stamp=False)

    script_py = os.path.join(ctx.base_dir, "cgenff_charmm2gmx_py3_nx2.py")
    ctx.log(STEP, "Converting CGenFF -> GROMACS...")
    ctx.run(STEP, [python_exe(), script_py, LIG_RESNAME, fix_mol2, str_dst, ctx.cfg.gmx_ff + ".ff"],
            what="cgenff_charmm2gmx", quiet=False)
    low = LIG_RESNAME.lower()
    for need in (f"{low}.itp", f"{low}.prm", f"{low}_ini.pdb"):
        if not os.path.isfile(ctx.path(need)):
            raise StepError(f"CGenFF conversion did not produce {need}.")
    shutil.copy2(ctx.path(f"{low}.itp"), ctx.path(f"{LIG_RESNAME}.itp"))
    shutil.copy2(ctx.path(f"{low}.prm"), ctx.path(f"{LIG_RESNAME}.prm"))
    ctx.gmx_run(STEP, ["editconf", "-f", f"{low}_ini.pdb", "-o", f"{LIG_RESNAME}.gro"], quiet=True)
    for dup in (f"{low}.itp", f"{low}.prm", f"{low}.top"):   # o conversor grava em minúsculas
        try:
            os.remove(ctx.path(dup))
        except OSError:
            pass
    ctx.state["lig_prm"] = f"{LIG_RESNAME}.prm"
    ctx.log(STEP, "CHARMM/CGenFF parametrization completed.")


def amber_env() -> Dict[str, str]:
    """PATH/AMBERHOME para que o acpype encontre antechamber, parmchk2, tleap e sqm."""
    ante = find_executable("antechamber", search_conda=True)
    env: Dict[str, str] = {}
    if ante:
        bindir = os.path.dirname(ante)
        env["PATH"] = bindir + os.pathsep + os.environ.get("PATH", "")
        if not os.environ.get("AMBERHOME"):
            home = os.path.dirname(bindir)
            if os.path.isdir(os.path.join(home, "dat")):
                env["AMBERHOME"] = home
    return env


def _parametrize_amber(ctx: RunContext, mol2: str, net_charge: int):
    cfg = ctx.cfg
    acpype = find_executable("acpype", search_conda=True)
    if not acpype:
        raise StepError("acpype not found. Use 'Install requirements' (acpype + AmberTools).")
    env = amber_env()
    if "PATH" not in env and not find_executable("antechamber"):
        raise StepError("AmberTools (antechamber) not found. Use 'Install requirements' (AmberTools).")
    atom_type = "gaff2" if cfg.ligand_method == "gaff2" else "gaff"
    cm = cfg.ligand_charge_model
    q = cfg.ligand_charges.get(ctx.lig_name, net_charge)
    ctx.log(STEP, f"Running acpype: {atom_type.upper()} atom types, "
                  f"{'AM1-BCC' if cm == 'bcc' else 'Gasteiger'} charges, net charge {q:+d}...")
    out_dir = ctx.path(f"{LIG_RESNAME}.acpype")
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    ctx.run(STEP, [acpype, "-i", os.path.basename(mol2), "-b", LIG_RESNAME, "-c", cm, "-n", str(q),
                   "-a", atom_type, "-o", "gmx", "-f"], what="acpype", env=env, log_every=0.5)
    itp = os.path.join(out_dir, f"{LIG_RESNAME}_GMX.itp")
    gro = os.path.join(out_dir, f"{LIG_RESNAME}_GMX.gro")
    if not (os.path.isfile(itp) and os.path.isfile(gro)):
        raise StepError("acpype did not produce the GROMACS files (…_GMX.itp/.gro). Check antechamber/sqm output above.")
    shutil.copy2(itp, ctx.path(f"{LIG_RESNAME}.itp"))
    shutil.copy2(gro, ctx.path(f"{LIG_RESNAME}.gro"))
    ctx.state["lig_prm"] = None
    ctx.log(STEP, f"AMBER/{atom_type.upper()} parametrization completed.")


def _make_ligand_restraints(ctx: RunContext):
    """posre_lig.itp (átomos pesados) e inclusão condicional (#ifdef POSRES) no final de LIG.itp."""
    gro = f"{LIG_RESNAME}.gro"
    ctx.gmx_run(STEP, ["make_ndx", "-f", gro, "-o", "index_lig.ndx"], input_text="0 & ! a H*\nq\n", quiet=True)
    groups = read_ndx_groups(ctx.path("index_lig.ndx"))
    if len(groups) < 2:
        raise StepError("Could not create the ligand heavy-atom index group.")
    ctx.gmx_run(STEP, ["genrestr", "-f", gro, "-n", "index_lig.ndx", "-o", "posre_lig.itp", "-fc", "1000", "1000", "1000"],
                input_text=f"{len(groups) - 1}\n", quiet=True)
    itp = ctx.path(f"{LIG_RESNAME}.itp")
    with open(itp, "r", encoding="utf-8") as f:
        text = f.read()
    if "posre_lig.itp" not in text:
        with open(itp, "a", encoding="utf-8", newline="\n") as f:
            f.write('\n; Ligand position restraints\n#ifdef POSRES\n#include "posre_lig.itp"\n#endif\n')
    ctx.log(STEP, "Created ligand position restraints (heavy atoms).")


def prepare_ligand(ctx: RunContext, ligands_dir: str):
    """Executa a STEP 1 completa para uma execução."""
    cfg = ctx.cfg
    ctx.log(STEP, f"######### INITIALIZING {ctx.lig_name} PREPARATION #########", stamp=False)
    ctx.log(STEP, f"Force field: {cfg.force_field}; ligand method: {LIGAND_METHOD_LABELS.get(cfg.ligand_method, cfg.ligand_method)}")
    lig_file = find_ligand_file(ligands_dir, ctx.lig_name)
    if not lig_file:
        raise StepError(f"Ligand file for '{ctx.lig_name}' not found in {ligands_dir}")

    if cfg.family == "charmm":
        ff_src = os.path.join(ctx.base_dir, cfg.gmx_ff + ".ff")
        ff_dst = ctx.path(cfg.gmx_ff + ".ff")
        if not os.path.isdir(ff_src):
            raise StepError(f"Force field folder not found: {ff_src}")
        if not os.path.isdir(ff_dst):
            shutil.copytree(ff_src, ff_dst)
            ctx.log(STEP, f"Copied {cfg.gmx_ff}.ff into the run folder.")

    mol2 = _convert_to_mol2(ctx, lig_file)
    net_charge = mol2_net_charge(mol2)
    if ctx.lig_name in cfg.ligand_charges:
        ctx.log(STEP, f"Ligand net charge detected: {net_charge:+d}; using the value set in the interface: {cfg.ligand_charges[ctx.lig_name]:+d}")
        net_charge = cfg.ligand_charges[ctx.lig_name]
    else:
        ctx.log(STEP, f"Ligand net charge (from Gasteiger charges): {net_charge:+d}")
    ctx.state["net_charge"] = net_charge

    ctx.check_cancel()
    if cfg.ligand_method == "cgenff":
        _parametrize_cgenff(ctx, mol2, net_charge, ligands_dir)
    else:
        _parametrize_amber(ctx, mol2, net_charge)

    q_itp = itp_total_charge(ctx.path(f"{LIG_RESNAME}.itp"))
    expected = cfg.ligand_charges.get(ctx.lig_name, net_charge)
    if q_itp is not None:
        q_itp = round(q_itp, 5)
        ctx.log(STEP, f"Topology net charge: {q_itp + 0.0:+.4f}")
        if abs(q_itp - round(q_itp)) > 0.01 or abs(round(q_itp) - expected) > 0:
            ctx.log(STEP, f"Warning: topology charge {q_itp:+.4f} is not the expected integer {expected:+d}.", stamp=False)

    _make_ligand_restraints(ctx)
    ctx.log(STEP, f"Ligand {ctx.lig_name} preparation completed successfully.")
