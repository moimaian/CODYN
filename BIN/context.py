# -*- coding: utf-8 -*-
"""Contexto de execução compartilhado pelas etapas do pipeline (sem Qt)."""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

from BIN.runconfig import RunConfig
from BIN.tools import CancelToken, PipelineCancelled, run_cmd, tail


class StepError(Exception):
    """Falha de uma etapa para UMA execução (proteína+ligante); as demais execuções continuam."""


@dataclass
class RunContext:
    codyn_dir: str
    run_folder: str
    prot_name: str
    lig_name: str
    cfg: RunConfig
    gmx: str
    token: CancelToken
    # logger(step, message): step in {"lig","prot","cell","eq","md"}
    logger: Callable[[str, str], None] = lambda step, msg: None
    # pedido de arquivo ao usuário (ex.: .str do CGenFF); devolve caminho ou None. Roda na GUI.
    request_file: Optional[Callable[[dict], Optional[str]]] = None
    # progresso do mdrun: (passo_atual, passo_total, segundos_restantes|None)
    on_progress: Optional[Callable[[int, int, Optional[int]], None]] = None
    state: Dict[str, object] = field(default_factory=dict)

    # ---- caminhos ----
    @property
    def base_dir(self) -> str:
        return os.path.join(self.codyn_dir, "BASE")

    def path(self, name: str) -> str:
        return os.path.join(self.run_folder, name)

    # ---- log ----
    def log(self, step: str, msg: str, stamp: bool = True):
        for line in str(msg).splitlines() or [""]:
            if stamp and line.strip():
                line = f"[{datetime.now().strftime('%H:%M:%S')}] {line}"
            self.logger(step, line)

    def check_cancel(self):
        if self.token.is_set():
            raise PipelineCancelled()

    # ---- execução ----
    def run(self, step: str, args: List[str], input_text: Optional[str] = None, check: bool = True,
            what: str = "", log_every: float = 0.0, on_line=None, quiet: bool = False,
            env: Optional[Dict[str, str]] = None):
        """Roda um comando na pasta da execução. Levanta StepError se rc != 0 e check=True."""
        self.check_cancel()
        name = what or " ".join(os.path.basename(str(a)) if i == 0 else str(a) for i, a in enumerate(args[:3]))
        rc, out = run_cmd(
            args, cwd=self.run_folder, input_text=input_text, token=self.token, on_line=on_line,
            log=None if quiet else (lambda line: self.log(step, line, stamp=False)),
            log_every=log_every, env=env,
        )
        if rc != 0 and check:
            raise StepError(f"{name} failed (exit code {rc}):\n{tail(out, 10)}")
        return rc, out

    def gmx_run(self, step: str, sub: List[str], **kw):
        return self.run(step, [self.gmx] + sub, what=kw.pop("what", f"gmx {sub[0]}"), **kw)


_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.+-]+")


def safe_name(name: str) -> str:
    """Nome de arquivo seguro para compor nomes de pastas e arquivos."""
    return _SAFE_NAME.sub("_", name).strip("_") or "x"
