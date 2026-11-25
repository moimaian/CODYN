# -*- coding: utf-8 -*-
"""Descoberta de executáveis externos e execução de subprocessos com cancelamento real.

Sem dependência de Qt (usado também pelo bootstrap e pelos testes).

- find_executable / find_gmx: acham o binário no PATH ou em locais conhecidos (GROMACS em
  /usr/local/gromacs, ambientes conda como o AmberTools...);
- CancelToken: sinalizador de cancelamento compartilhado por todas as etapas do pipeline;
- run_cmd: roda um comando (lista de argumentos, sem shell) transmitindo a saída linha a linha,
  em um grupo de processos próprio, para que o cancelamento mate o gmx de verdade;
- terminate_all: encerra todos os processos filhos ainda em execução.
"""

import glob
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from BIN import platform_utils as pu
from BIN.platform_utils import find_obabel, find_perl  # noqa: F401  (reexportados: usados por vários módulos)

GMX_CANDIDATES = pu.gmx_candidates()

_CONDA_ROOTS = pu.conda_roots()

_gmx_cache: Optional[str] = None


def _conda_bins(name: str) -> List[str]:
    found: List[str] = []
    # Windows: executáveis em <raiz>\Scripts e <raiz>\Library\bin; Linux: <raiz>/bin
    subdirs = ("Scripts", os.path.join("Library", "bin"), "bin") if pu.IS_WINDOWS else ("bin",)
    for root in _CONDA_ROOTS:
        r = os.path.expanduser(root)
        for exe in pu.exe_names(name):
            for sub in subdirs:
                for pat in (os.path.join(r, sub, exe), os.path.join(r, "envs", "*", sub, exe)):
                    found.extend(sorted(glob.glob(pat)))
    return found


def find_executable(name: str, extra: Sequence[str] = (), search_conda: bool = False) -> Optional[str]:
    """Primeiro PATH, depois caminhos extras, o venv do CODYN, ~/.local/bin e (opcional) ambientes conda.
    No Windows aceita .exe/.bat/.cmd."""
    path = shutil.which(name)
    if path:
        return path
    candidates = list(extra)
    in_venv = pu.find_in_venv(name)
    if in_venv:
        candidates.append(in_venv)
    for exe in pu.exe_names(name):
        candidates.append(str(Path.home() / ".local" / "bin" / exe))
    if search_conda:
        candidates += _conda_bins(name)
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def find_gmx(refresh: bool = False) -> Optional[str]:
    """Localiza o GROMACS: $CODYN_GMX, 'gmx' no PATH e instalações comuns."""
    global _gmx_cache
    if _gmx_cache and not refresh and os.path.exists(_gmx_cache):
        return _gmx_cache
    env = os.environ.get("CODYN_GMX")
    if env and os.path.isfile(env):
        _gmx_cache = env
        return env
    _gmx_cache = find_executable("gmx", extra=pu.gmx_candidates())
    return _gmx_cache


def gmx_info(gmx: Optional[str] = None) -> Dict[str, str]:
    """Versão e recursos do GROMACS (GPU, SIMD, MPI) lidos de `gmx --version`."""
    gmx = gmx or find_gmx()
    info: Dict[str, str] = {"path": gmx or "", "version": "", "gpu": "", "simd": "", "mpi": ""}
    if not gmx:
        return info
    try:
        out = subprocess.run([gmx, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=15).stdout
    except Exception:
        return info
    for key, rx in (
        ("version", r"GROMACS version:\s*(.+)"),
        ("gpu", r"GPU support:\s*(.+)"),
        ("simd", r"SIMD instructions:\s*(.+)"),
        ("mpi", r"MPI library:\s*(.+)"),
    ):
        m = re.search(rx, out)
        if m:
            info[key] = m.group(1).strip()
    return info


def gmx_has_gpu(gmx: Optional[str] = None) -> bool:
    g = gmx_info(gmx).get("gpu", "").lower()
    return g not in ("", "disabled", "none") and shutil.which("nvidia-smi") is not None


# ------------------------------- cancelamento -------------------------------

class CancelToken:
    def __init__(self):
        self._ev = threading.Event()

    def cancel(self):
        self._ev.set()
        terminate_all()

    def reset(self):
        self._ev.clear()

    def is_set(self) -> bool:
        return self._ev.is_set()

    __bool__ = is_set


class PipelineCancelled(Exception):
    pass


_procs_lock = threading.Lock()
_procs: "set[subprocess.Popen]" = set()


def terminate_all(grace: float = 2.0):
    """Envia SIGTERM (e depois SIGKILL) ao grupo de processo de tudo que o CODYN iniciou
    (Windows: `taskkill /T` da árvore de processos, primeiro educado e depois forçado)."""
    with _procs_lock:
        procs = list(_procs)
    for p in procs:
        pu.kill_tree(p.pid)
    deadline = time.time() + grace
    for p in procs:
        while p.poll() is None and time.time() < deadline:
            time.sleep(0.05)
        if p.poll() is None:
            pu.kill_tree(p.pid, force=True)


def run_cmd(
    args: Sequence[str],
    cwd: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
    input_text: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    token: Optional[CancelToken] = None,
    on_line: Optional[Callable[[str], None]] = None,
    log_every: float = 0.0,
    timeout: Optional[float] = None,
) -> Tuple[int, str]:
    """Executa `args` (sem shell) e devolve (returncode, saída). stderr é mesclado ao stdout.

    - log(linha): recebe cada linha (a saída do gmx vai toda para stderr, então NÃO é erro);
    - on_line(linha): vê TODAS as linhas (usado para ler progresso do mdrun);
    - log_every: se > 0, só repassa ao log uma linha por esse intervalo (mdrun -v emite milhares);
    - token: se cancelado, o processo é encerrado e PipelineCancelled é levantada.
    """
    if token is not None and token.is_set():
        raise PipelineCancelled()
    full_env = os.environ.copy()
    full_env.setdefault("GMX_MAXBACKUP", "-1")  # nunca criar #arquivo.1# ao reexecutar
    for k, v in pu.child_env_defaults().items():  # Windows: filhos Python em UTF-8
        full_env.setdefault(k, v)
    if env:
        full_env.update(env)
    proc = subprocess.Popen(
        [str(a) for a in args],
        cwd=cwd,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=full_env,
        **pu.popen_group_kwargs(),
    )
    with _procs_lock:
        _procs.add(proc)
    if input_text is not None:
        try:
            # bytes: o stdin em modo texto converteria "\n" em "\r\n" no Windows (o gmx leria "H*\r")
            proc.stdin.buffer.write(input_text.encode("utf-8"))
            proc.stdin.close()
        except Exception:
            pass
    lines: List[str] = []
    last_emit = 0.0
    started = time.time()
    try:
        for raw in proc.stdout:
            line = raw.rstrip("\n").rstrip("\r")
            lines.append(line)
            if len(lines) > 4000:
                del lines[:1000]
            if on_line:
                on_line(line)
            if log and line.strip():
                now = time.time()
                if log_every <= 0 or now - last_emit >= log_every:
                    log(line)
                    last_emit = now
            if token is not None and token.is_set():
                terminate_all()
                raise PipelineCancelled()
            if timeout and time.time() - started > timeout:
                terminate_all()
                lines.append(f"timeout after {timeout}s")
                break
        proc.wait()
    finally:
        with _procs_lock:
            _procs.discard(proc)
        if proc.poll() is None:
            pu.kill_tree(proc.pid, force=True)
    return proc.returncode, "\n".join(lines)


def tail(text: str, n: int = 12) -> str:
    return "\n".join(text.strip().splitlines()[-n:])
