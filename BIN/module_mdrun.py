# -*- coding: utf-8 -*-
"""Execução do `gmx mdrun` com progresso, tempo restante e recuo automático GPU -> CPU."""

import re
from datetime import datetime
from typing import Optional

from BIN.context import RunContext, StepError
from BIN.tools import gmx_has_gpu, tail

_STEP_RE = re.compile(r"\bstep\s+(\d+)")
_FINISH_RE = re.compile(r"will finish\s+(.+?)\s*$")
_REMAIN_RE = re.compile(r"remaining wall clock time:\s*(\d+)\s*s", re.I)
_FINISH_FMT = "%a %b %d %H:%M:%S %Y"

GPU_LEVELS = [
    ("full GPU", ["-nb", "gpu", "-bonded", "gpu", "-pme", "gpu", "-pmefft", "gpu", "-update", "gpu"]),
    ("GPU non-bonded + PME", ["-nb", "gpu", "-pme", "gpu"]),
    ("CPU only", ["-nb", "cpu", "-pme", "cpu", "-bonded", "cpu", "-update", "cpu"]),
]


def _levels(ctx: RunContext, allow_gpu: bool):
    if allow_gpu and ctx.cfg.use_gpu and gmx_has_gpu(ctx.gmx):
        return GPU_LEVELS
    return [("CPU", [])]


def run_mdrun(ctx: RunContext, step: str, deffnm: str, total_steps: int, allow_gpu: bool = True,
              threads: Optional[int] = None) -> None:
    """Roda `gmx mdrun -deffnm <deffnm>` na pasta da execução.

    Se uma configuração de GPU falhar, tenta a próxima menos agressiva antes de desistir
    (um mdrun interrompido retoma sozinho do .cpt)."""
    nthreads = threads or ctx.cfg.n_threads
    levels = _levels(ctx, allow_gpu)
    last_out = ""
    for idx, (label, flags) in enumerate(levels):
        ctx.check_cancel()
        ctx.log(step, f"mdrun {deffnm}: {label} ({nthreads} threads)...")
        state = {"step": 0}

        def on_line(line, _state=state):
            m = _STEP_RE.search(line)
            if not m:
                return
            cur = int(m.group(1))
            _state["step"] = cur
            remaining = None
            fm = _FINISH_RE.search(line)
            if fm:
                try:
                    remaining = max(0, int((datetime.strptime(" ".join(fm.group(1).split()), _FINISH_FMT)
                                            - datetime.now()).total_seconds()))
                except ValueError:
                    remaining = None
            else:
                rm = _REMAIN_RE.search(line)
                if rm:
                    remaining = int(rm.group(1))
            if ctx.on_progress:
                ctx.on_progress(step, cur, total_steps, remaining)

        rc, out = ctx.run(
            step, [ctx.gmx, "mdrun", "-deffnm", deffnm, "-ntmpi", "1", "-ntomp", str(nthreads), *flags, "-v"],
            check=False, on_line=on_line, log_every=30.0, what=f"gmx mdrun {deffnm}",
        )
        last_out = out
        if rc == 0:
            if ctx.on_progress:
                ctx.on_progress(step, total_steps, total_steps, 0)
            return
        if idx + 1 < len(levels):
            ctx.log(step, f"mdrun ({label}) failed; retrying with a less aggressive setup...\n{tail(out, 6)}", stamp=False)
    raise StepError(f"mdrun {deffnm} failed:\n{tail(last_out, 12)}")


def energy_xvg(ctx: RunContext, step: str, edr: str, out_xvg: str, term: str):
    """Extrai uma propriedade do .edr (Potential, Temperature, Pressure, Density) para .xvg."""
    rc, out = ctx.gmx_run(step, ["energy", "-f", edr, "-o", out_xvg], input_text=f"{term}\n0\n", check=False, quiet=True)
    if rc != 0:
        ctx.log(step, f"Warning: could not extract {term} from {edr}:\n{tail(out, 4)}", stamp=False)
        return
    for line in out.splitlines():
        if line.strip().startswith(term):
            ctx.log(step, line.strip(), stamp=False)
