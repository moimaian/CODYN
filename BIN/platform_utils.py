# -*- coding: utf-8 -*-
"""O que muda entre Linux e Windows no CODYN, num só lugar (só biblioteca padrão, sem Qt).

Os demais módulos perguntam aqui em que sistema estão rodando e onde ficam as ferramentas externas
(Open Babel, Perl, GROMACS, AmberTools...), em vez de cada um repetir o seu `if`. No Linux nada muda:
tudo continua nos mesmos caminhos de antes.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

IS_WINDOWS = sys.platform.startswith("win")

# Versão exata do Python do venv no Windows: a 3.10.11 é a última 3.10 que o python.org distribui com
# instalador binário (da 3.10.12 em diante só há código-fonte). No Linux o CODYN aceita qualquer 3.10+.
PYTHON_WINDOWS_VERSION = "3.10.11"


# ----------------------------------------------------------------------------- processos filhos
def install_subprocess_defaults() -> None:
    """Windows: faz todo processo filho nascer sem janela de console e com um stdin válido.

    O CODYN aberto pelo atalho roda em `pythonw.exe` (sem console): sem isso cada `pip`, `obabel`,
    `gmx` ou `nvidia-smi` abriria uma janela preta e, sem stdin, o subprocess falharia com "handle
    inválido". Também decodifica a saída das ferramentas com `errors="replace"`, para um byte fora da
    página de código do Windows não derrubar a leitura do log. No Linux não faz nada."""
    if not IS_WINDOWS or getattr(subprocess.Popen, "_codyn_patched", False):
        return
    original_init = subprocess.Popen.__init__
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    def patched_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not kwargs.get("creationflags"):
            kwargs["creationflags"] = no_window
        if kwargs.get("stdin") is None and (sys.stdin is None or not sys.stdin.isatty()):
            kwargs["stdin"] = subprocess.DEVNULL
        text_mode = kwargs.get("text") or kwargs.get("universal_newlines") or kwargs.get("encoding") or kwargs.get("errors")
        if text_mode and kwargs.get("errors") is None:
            kwargs["errors"] = "replace"
        original_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = patched_init  # type: ignore[method-assign]
    subprocess.Popen._codyn_patched = True    # type: ignore[attr-defined]


def popen_group_kwargs() -> dict:
    """Argumentos do Popen para o filho ficar num grupo de processos próprio (o cancelamento encerra o
    gmx de verdade): sessão nova no Linux; grupo novo, sem janela de console, no Windows."""
    if IS_WINDOWS:
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {"start_new_session": True}


def child_env_defaults() -> dict:
    """Variáveis para os filhos Python (conversor CGenFF, acpype...) lerem/gravarem UTF-8 também no
    Windows, onde o padrão é a página de código da região (cp1252)."""
    return {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"} if IS_WINDOWS else {}


def kill_tree(pid: int, force: bool = False) -> None:
    """Encerra o processo `pid` e os seus filhos (o gmx, o gmx_MMPBSA e o mpirun que ele abre).
    Linux: sinal ao grupo de processos. Windows: `taskkill /T` (árvore inteira)."""
    if IS_WINDOWS:
        try:
            cmd = ["taskkill", "/PID", str(pid), "/T"] + (["/F"] if force else [])
            subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000), timeout=15)
        except Exception:
            pass
        return
    import signal
    try:
        os.killpg(pid, signal.SIGKILL if force else signal.SIGTERM)
    except Exception:
        pass


def pid_alive(pid: int) -> bool:
    """True se o processo existe. No Windows NÃO usar os.kill(pid, 0): lá qualquer sinal diferente de
    CTRL_C/CTRL_BREAK encerra o processo (TerminateProcess)."""
    if IS_WINDOWS:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except Exception:
        return True


def python_exe() -> str:
    """Python para rodar scripts filhos cuja saída o CODYN lê (conversor CGenFF): no Windows aberto pelo
    atalho o processo é o pythonw.exe (sem console); o filho usa o python.exe do mesmo venv."""
    exe = sys.executable
    if IS_WINDOWS and os.path.basename(exe).lower() == "pythonw.exe":
        sibling = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.isfile(sibling):
            return sibling
    return exe


# ----------------------------------------------------------------------------- pastas
def terminal_log_dir() -> str:
    """Onde fica o log por sessão exibido em Help > Terminal."""
    if IS_WINDOWS:
        return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.join(str(Path.home()), "AppData", "Local"), "CODYN")
    return os.path.join(os.path.expanduser("~"), ".cache", "codyn")


def venv_dir(env_name: str = "CODYN") -> str:
    return os.path.join(str(Path.home()), ".venv", env_name)


def venv_scripts_dir(env_dir: str) -> str:
    """Pasta dos executáveis do venv: Scripts\\ no Windows, bin/ no Linux."""
    return os.path.join(env_dir, "Scripts" if IS_WINDOWS else "bin")


def exe_names(name: str) -> List[str]:
    """Nomes possíveis de um executável: no Windows `name.exe`, `name.bat`, `name.cmd` e `name`."""
    return [name + ".exe", name + ".bat", name + ".cmd", name] if IS_WINDOWS else [name]


def program_dirs() -> List[str]:
    """Windows: Program Files (x64/x86) e %LOCALAPPDATA%\\Programs, onde os instaladores comuns gravam."""
    folders: List[str] = []
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        value = os.environ.get(variable)
        if value and value not in folders:
            folders.append(value)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        folders.append(os.path.join(local, "Programs"))
    return folders


def conda_roots() -> List[str]:
    """Instalações do conda/mamba/miniforge procuradas pelo CODYN (AmberTools, gmx_MMPBSA)."""
    names = ["anaconda3", "miniconda3", "miniforge3", "mambaforge", "micromamba"]
    roots = [os.path.join(str(Path.home()), n) for n in names]
    if IS_WINDOWS:
        for var in ("LOCALAPPDATA", "ProgramData"):
            base = os.environ.get(var)
            if base:
                roots += [os.path.join(base, n) for n in names]
    else:
        roots.append("/opt/conda")
    return roots


# ----------------------------------------------------------------------------- ferramentas
def find_in_venv(name: str, env_name: str = "CODYN") -> Optional[str]:
    scripts = venv_scripts_dir(venv_dir(env_name))
    for exe in exe_names(name):
        candidate = os.path.join(scripts, exe)
        if os.path.isfile(candidate):
            return candidate
    return None


def find_obabel() -> Optional[str]:
    """O `obabel`: no PATH, no venv do CODYN (no Windows o pacote pip openbabel-wheel o traz dentro do
    pacote Python) e, no Windows, nas pastas de instalação do Open Babel."""
    found = shutil.which("obabel")
    if found:
        return found
    if IS_WINDOWS:
        # openbabel-wheel: o obabel.exe verdadeiro fica dentro do pacote; Scripts\obabel.exe só inicia o Python
        # para chamá-lo, o que custaria uma partida do Python por ligante.
        real = os.path.join(venv_dir(), "Lib", "site-packages", "openbabel", "bin", "obabel.exe")
        if os.path.isfile(real):
            return real
    in_venv = find_in_venv("obabel")
    if in_venv:
        return in_venv
    if IS_WINDOWS:
        for base in program_dirs():
            for pattern in ("OpenBabel*", "Open Babel*"):
                for folder in sorted(glob.glob(os.path.join(base, pattern)), reverse=True):
                    candidate = os.path.join(folder, "obabel.exe")
                    if os.path.isfile(candidate):
                        return candidate
    else:
        for candidate in ("/usr/local/bin/obabel", "/usr/bin/obabel"):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None


def find_perl() -> Optional[str]:
    """O `perl` (corrige o MOL2 para o CGenFF). No Windows vem do Strawberry Perl (winget) ou do Git for
    Windows; logo depois de instalar pelo winget o PATH deste processo ainda é o antigo, daí a procura."""
    found = shutil.which("perl")
    if found:
        return found
    if IS_WINDOWS:
        candidates = [r"C:\Strawberry\perl\bin\perl.exe"]
        for base in program_dirs():
            candidates += [os.path.join(base, "Git", "usr", "bin", "perl.exe"),
                           os.path.join(base, "Strawberry", "perl", "bin", "perl.exe")]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
    return None


def gmx_candidates() -> List[str]:
    """Locais conhecidos do GROMACS (além do PATH)."""
    if IS_WINDOWS:
        found: List[str] = []
        home = str(Path.home())
        for root in [os.path.join(home, "GROMACS"), os.path.join(home, "gromacs")]:
            found += [os.path.join(root, "bin", "gmx.exe"), os.path.join(root, "bin", "gmx_mpi.exe")]
        for base in program_dirs() + ["C:\\"]:
            for pattern in ("GROMACS*", "gromacs*"):
                for folder in sorted(glob.glob(os.path.join(base, pattern)), reverse=True):
                    found += [os.path.join(folder, "bin", "gmx.exe"), os.path.join(folder, "bin", "gmx_mpi.exe")]
        return found
    return ["/usr/local/gromacs/bin/gmx", "/usr/local/gromacs/bin/gmx_mpi", "/opt/gromacs/bin/gmx", "/usr/bin/gmx"]


def gromacs_install_dir() -> str:
    """Onde o instalador do CODYN grava o GROMACS no Windows (sem administrador)."""
    return os.path.join(str(Path.home()), "GROMACS")


def nvcc_path() -> Optional[str]:
    """O `nvcc` do CUDA Toolkit (PATH, CUDA_PATH no Windows, /usr/local/cuda no Linux)."""
    found = shutil.which("nvcc")
    if found:
        return found
    if IS_WINDOWS:
        roots = [os.environ.get("CUDA_PATH", "")]
        for base in program_dirs():
            roots += sorted(glob.glob(os.path.join(base, "NVIDIA GPU Computing Toolkit", "CUDA", "v*")), reverse=True)
        for root in roots:
            candidate = os.path.join(root, "bin", "nvcc.exe") if root else ""
            if candidate and os.path.isfile(candidate):
                return candidate
        return None
    candidate = "/usr/local/cuda/bin/nvcc"
    return candidate if os.path.exists(candidate) else None


# ----------------------------------------------------------------------------- abrir pastas
def open_path(path: str) -> None:
    """Abre um arquivo ou pasta no programa padrão do sistema (gerenciador de arquivos)."""
    if IS_WINDOWS:
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
