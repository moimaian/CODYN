# -*- coding: utf-8 -*-
"""STEP 2 — Preparo do complexo proteína-ligante.

pdb2gmx (campo de força e água por NOME, não por índice de menu) + fusão das coordenadas do ligante
+ inclusão do ligante na topologia + geração dos .mdp da execução.
"""

import os
import re
import shutil
from typing import List, Optional

from BIN.context import RunContext, StepError
from BIN.mdp_tools import prepare_mdps
from BIN.runconfig import LIG_RESNAME
from BIN.tools import find_obabel

STEP = "prot"
PROT_EXTS = (".pdb", ".pdbqt")


def list_proteins(protein_dir: str) -> List[str]:
    if not os.path.isdir(protein_dir):
        return []
    return sorted(f for f in os.listdir(protein_dir)
                  if os.path.isfile(os.path.join(protein_dir, f)) and os.path.splitext(f)[1].lower() in PROT_EXTS)


def merge_gro(protein_gro: str, ligand_gro: str, out_gro: str, title: str, lig_resnr: Optional[int] = None):
    """Concatena as coordenadas (átomos) de dois .gro usando a caixa do primeiro."""
    def read(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        n = int(lines[1].strip())
        return lines[2:2 + n], lines[2 + n] if len(lines) > 2 + n else ""

    p_atoms, box = read(protein_gro)
    l_atoms, _ = read(ligand_gro)
    if lig_resnr is None:
        lig_resnr = int(p_atoms[-1][:5]) + 1 if p_atoms else 1
    l_atoms = [f"{lig_resnr % 100000:>5}" + line[5:] for line in l_atoms]
    with open(out_gro, "w", encoding="utf-8", newline="\n") as f:
        f.write(title + "\n")
        f.write(f"{len(p_atoms) + len(l_atoms)}\n")
        f.write("\n".join(p_atoms + l_atoms) + "\n")
        f.write(box + "\n")


def add_ligand_to_topology(top_path: str, has_prm: bool, resname: str = LIG_RESNAME):
    """Inclui LIG.prm/LIG.itp antes do primeiro [ moleculetype ] e LIG 1 em [ molecules ]."""
    with open(top_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    out, done = [], False
    for line in lines:
        if not done and re.match(r"\s*\[\s*moleculetype\s*\]", line):
            if has_prm:
                out += ["; Include ligand parameters", f'#include "{resname}.prm"', ""]
            out += ["; Include ligand topology", f'#include "{resname}.itp"', ""]
            done = True
        out.append(line)
    if not done:
        raise StepError("No [ moleculetype ] found in topol.top.")
    while out and not out[-1].strip():
        out.pop()
    out.append(f"{resname:<20}1")
    with open(top_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


def _prepare_protein_pdb(ctx: RunContext, protein_dir: str) -> str:
    files = list_proteins(protein_dir)
    named = [f for f in files if os.path.splitext(f)[0] == ctx.prot_name]
    if not named:
        raise StepError(f"Protein '{ctx.prot_name}' not found in {protein_dir}")
    src = os.path.join(protein_dir, named[0])
    dst = ctx.path("protein.pdb")
    if src.lower().endswith(".pdbqt"):
        obabel = find_obabel()
        if not obabel:
            raise StepError("Open Babel ('obabel') not found; required to convert a .pdbqt protein.")
        ctx.run(STEP, [obabel, "-ipdbqt", src, "-opdb", "-O", dst], what="obabel (protein pdbqt -> pdb)", quiet=True)
        ctx.log(STEP, f"Converted {named[0]} to PDB with Open Babel (the original file was kept).")
    else:
        shutil.copy2(src, dst)
        ctx.log(STEP, "Copied protein into run folder.")
    return dst


def prepare_complex(ctx: RunContext, protein_dir: str):
    cfg = ctx.cfg
    ctx.log(STEP, f"####### COMPLEX PREPARATION START {ctx.prot_name} {ctx.lig_name} #######", stamp=False)
    _prepare_protein_pdb(ctx, protein_dir)
    ctx.log(STEP, f"Running pdb2gmx: force field {cfg.gmx_ff}, water model {cfg.solvent_model}")
    args = ["pdb2gmx", "-f", "protein.pdb", "-o", "protein.gro", "-p", "topol.top", "-i", "posre.itp",
            "-ff", cfg.gmx_ff, "-water", cfg.solvent_model]
    if cfg.ignore_hydrogens:
        args.append("-ignh")
    ctx.gmx_run(STEP, args, quiet=True, what="gmx pdb2gmx")
    ctx.log(STEP, "Generated protein.gro successfully.")

    ctx.log(STEP, f"Bringing {LIG_RESNAME} ({ctx.lig_name}) and {ctx.prot_name} together in complex.gro")
    merge_gro(ctx.path("protein.gro"), ctx.path(f"{LIG_RESNAME}.gro"), ctx.path("complex.gro"),
              f"CODYN {ctx.lig_name} {ctx.prot_name}")
    add_ligand_to_topology(ctx.path("topol.top"), has_prm=bool(ctx.state.get("lig_prm")))
    ctx.log(STEP, "Ligand included in topol.top.")

    prepare_mdps(ctx.base_dir, ctx.run_folder, cfg)
    ctx.log(STEP, f"Generated .mdp files (dt={cfg.dt_ps:g} ps, eq steps={cfg.steps_eq}, production steps={cfg.steps_md}).")
    if cfg.integration_time_fs > 2.0:
        ctx.log(STEP, "Warning: integration step > 2 fs normally requires heavy-hydrogen/virtual-site topologies.", stamp=False)
    ctx.log(STEP, "Complex preparation completed successfully.")
