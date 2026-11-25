# -*- coding: utf-8 -*-
"""STEP 3 — Célula unitária: caixa, solvatação, íons e minimização de energia."""

from BIN.context import RunContext
from BIN.mdp_tools import solvent_box_file
from BIN.module_mdrun import energy_xvg, run_mdrun

STEP = "cell"


def prepare_cell(ctx: RunContext):
    cfg = ctx.cfg
    ctx.log(STEP, f"####### CELL PREPARATION START {ctx.prot_name} {ctx.lig_name} #######", stamp=False)
    ctx.log(STEP, f"Using ion conc: {cfg.ion_concentration_M} M, positive ion: {cfg.positive_ion}, "
                  f"negative ion: {cfg.negative_ion}, box: {cfg.box_type} ({cfg.box_distance_nm} nm)")

    ctx.log(STEP, "Creating unit cell...")
    ctx.gmx_run(STEP, ["editconf", "-f", "complex.gro", "-o", "newbox.gro", "-bt", cfg.box_type, "-c",
                       "-d", f"{cfg.box_distance_nm:g}"], quiet=True)

    ctx.log(STEP, "Filling unit cell with solvent...")
    ctx.gmx_run(STEP, ["solvate", "-cp", "newbox.gro", "-cs", solvent_box_file(cfg.solvent_model),
                       "-p", "topol.top", "-o", "solv.gro"], quiet=True)

    ctx.log(STEP, "Preparing ion topology...")
    ctx.gmx_run(STEP, ["grompp", "-f", "ions.mdp", "-c", "solv.gro", "-p", "topol.top", "-o", "ions.tpr"], quiet=True)

    ctx.log(STEP, f"Adding ions {cfg.positive_ion} and {cfg.negative_ion} ...")
    rc, out = ctx.gmx_run(STEP, ["genion", "-s", "ions.tpr", "-o", "solv_ions.gro", "-p", "topol.top",
                                 "-pname", cfg.positive_ion, "-nname", cfg.negative_ion,
                                 "-conc", f"{cfg.ion_concentration_M:g}", "-neutral"],
                          input_text="SOL\n", quiet=True)
    for line in out.splitlines():
        if "Will try to add" in line:
            ctx.log(STEP, line.strip())
    ctx.log(STEP, "Cell preparation completed successfully.")

    ctx.log(STEP, "Starting energy minimization...")
    ctx.gmx_run(STEP, ["grompp", "-f", "em.mdp", "-c", "solv_ions.gro", "-p", "topol.top", "-o", "em.tpr"], quiet=True)
    em_steps = 100000
    run_mdrun(ctx, STEP, "em", em_steps, allow_gpu=False)
    log_text = ""
    try:
        with open(ctx.path("em.log"), "r", encoding="utf-8", errors="ignore") as f:
            log_text = f.read()
    except OSError:
        pass
    for line in log_text.splitlines():
        s = line.strip()
        if s.startswith(("Potential Energy", "Maximum force", "Steepest Descents converged", "Steepest Descents did not converge")):
            ctx.log(STEP, s, stamp=False)
    if "did not converge" in log_text:
        ctx.log(STEP, "Warning: energy minimization did not reach the force tolerance; check the structure/topology.", stamp=False)
    ctx.log(STEP, "Energy Minimization completed successfully!")
    ctx.log(STEP, "Calculating potential energy...")
    energy_xvg(ctx, STEP, "em.edr", "potential.xvg", "Potential")
