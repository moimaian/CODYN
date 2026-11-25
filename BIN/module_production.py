# -*- coding: utf-8 -*-
"""STEP 5 — Produção de dinâmica molecular + remoção de PBC da trajetória."""

from BIN.context import RunContext
from BIN.module_mdrun import run_mdrun

STEP = "md"


def run_production(ctx: RunContext):
    cfg = ctx.cfg
    tag = cfg.md_tag
    ctx.log(STEP, f"####### MD PRODUCTION START {ctx.prot_name} {ctx.lig_name} #######", stamp=False)
    ctx.log(STEP, f"Using {cfg.n_threads} CPU threads; {cfg.production_time_ns:g} ns = {cfg.steps_md} steps")
    ctx.log(STEP, "Running GROMPP for MD Production...")
    ctx.gmx_run(STEP, ["grompp", "-f", "md.mdp", "-c", "npt.gro", "-t", "npt.cpt", "-p", "topol.top",
                       "-n", "index.ndx", "-o", f"md_0_{tag}.tpr"], quiet=True)
    ctx.log(STEP, f"Running MD Production in {cfg.production_time_ns:g} ns ... Wait!")
    run_mdrun(ctx, STEP, f"md_0_{tag}", cfg.steps_md)

    ctx.log(STEP, "Removing PBC from trajectory...")
    ctx.gmx_run(STEP, ["trjconv", "-s", f"md_0_{tag}.tpr", "-f", f"md_0_{tag}.xtc", "-o", f"md_0_{tag}_noPBC.xtc",
                       "-pbc", "mol", "-center"], input_text="Protein\nSystem\n", quiet=True)
    ctx.log(STEP, "Molecular Dynamics Finished Successfully!")
