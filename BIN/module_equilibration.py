# -*- coding: utf-8 -*-
"""STEP 4 — Equilibração do sistema (NVT e NPT)."""

from BIN.context import RunContext, StepError
from BIN.mdp_tools import read_ndx_groups
from BIN.module_mdrun import energy_xvg, run_mdrun
from BIN.runconfig import LIG_RESNAME

STEP = "eq"
TC_GROUP_1 = f"Protein_{LIG_RESNAME}"
TC_GROUP_2 = "Water_and_ions"


def make_index(ctx: RunContext):
    """index.ndx com Protein_LIG e Water_and_ions (= tudo o que não é proteína/ligante: água, íons...)
    para o acoplamento de temperatura."""
    ctx.log(STEP, "Creating tc-groups (Protein_LIG / Water_and_ions)...")
    ctx.gmx_run(STEP, ["make_ndx", "-f", "em.gro", "-o", "index.ndx"],
                input_text=f'"Protein" | "{LIG_RESNAME}"\n! "{TC_GROUP_1}"\nq\n', quiet=True)
    ndx = ctx.path("index.ndx")
    with open(ndx, "r", encoding="utf-8") as f:
        text = f.read()
    if f"[ !{TC_GROUP_1} ]" not in text:
        raise StepError(f"Could not create the solvent/ions index group (groups: {', '.join(read_ndx_groups(ndx)[:24])}).")
    with open(ndx, "w", encoding="utf-8", newline="\n") as f:
        f.write(text.replace(f"[ !{TC_GROUP_1} ]", f"[ {TC_GROUP_2} ]"))
    groups = read_ndx_groups(ndx)
    for needed in (TC_GROUP_1, TC_GROUP_2):
        if needed not in groups:
            raise StepError(f"Index group '{needed}' was not created.")


def run_nvt(ctx: RunContext):
    ctx.log(STEP, f"####### EQUILIBRATION NVT START {ctx.prot_name} {ctx.lig_name} #######", stamp=False)
    ctx.log(STEP, f"Using {ctx.cfg.n_threads} CPU threads")
    make_index(ctx)
    ctx.log(STEP, "Starting NVT...")
    ctx.gmx_run(STEP, ["grompp", "-f", "nvt.mdp", "-c", "em.gro", "-r", "em.gro", "-p", "topol.top",
                       "-n", "index.ndx", "-o", "nvt.tpr"], quiet=True)
    run_mdrun(ctx, STEP, "nvt", ctx.cfg.steps_eq)
    ctx.log(STEP, "NVT equilibration completed successfully.")
    ctx.log(STEP, "Calculating temperature variation...")
    energy_xvg(ctx, STEP, "nvt.edr", "temperature.xvg", "Temperature")


def run_npt(ctx: RunContext):
    ctx.log(STEP, f"####### EQUILIBRATION NPT START {ctx.prot_name} {ctx.lig_name} #######", stamp=False)
    ctx.log(STEP, "Starting NPT...")
    ctx.gmx_run(STEP, ["grompp", "-f", "npt.mdp", "-c", "nvt.gro", "-t", "nvt.cpt", "-r", "nvt.gro",
                       "-p", "topol.top", "-n", "index.ndx", "-o", "npt.tpr"], quiet=True)
    run_mdrun(ctx, STEP, "npt", ctx.cfg.steps_eq)
    ctx.log(STEP, "NPT equilibration completed successfully.")
    ctx.log(STEP, "Calculating pressure variation...")
    energy_xvg(ctx, STEP, "npt.edr", "pressure.xvg", "Pressure")
    ctx.log(STEP, "Calculating density variation...")
    energy_xvg(ctx, STEP, "npt.edr", "density.xvg", "Density")
