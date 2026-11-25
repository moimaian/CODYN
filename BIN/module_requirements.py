# -*- coding: utf-8 -*-
"""Requisitos do CODYN: bootstrap do venv (sem Qt) e janela "Install requirements".

Parte 1 (sem Qt, usada antes de qualquer import científico):
  venv_paths, ensure_venv, bootstrap_pyqt5 — cria ~/.venv/CODYN, instala o PyQt5 e reexecuta o
  programa dentro do venv.

Parte 2 (GUI): RequirementsInstaller — mostra o que está instalado/ausente (Python, parametrização de
ligantes, simulação) e instala o que o usuário marcar: pip no venv, apt/pkexec para pacotes do
sistema, compilação do GROMACS, gmx_MMPBSA, AmberTools (conda) e o atalho do menu.
"""

import os
import shutil
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from BIN import platform_utils as pu  # noqa: E402  (só biblioteca padrão: seguro antes do venv)

IS_WINDOWS = pu.IS_WINDOWS

# Versões recomendadas (fixas) dos pacotes Python instalados no venv.
PINNED: Dict[str, str] = {
    "PyQt5": "5.15.10",
    "numpy": "1.26.4",
    "pandas": "2.1.4",
    "matplotlib": "3.8.4",
    "scipy": "1.13.1",
    "psutil": "5.9.8",
    "networkx": "2.8.8",       # o conversor CGenFF usa a API do networkx 2.x
    "MDAnalysis": "2.6.1",
    "rdkit": "2023.9.6",
    "acpype": "2023.10.27",
    "python-docx": "1.1.2",    # relatório final (.docx)
    "openbabel-wheel": "",     # sem fixação: depende da plataforma
}

# Necessários para o programa abrir e rodar o pipeline (sem eles o instalador é oferecido).
REQUIRED_PY = [("PyQt5", "PyQt5"), ("numpy", "numpy"), ("pandas", "pandas"),
               ("matplotlib", "matplotlib"), ("psutil", "psutil"), ("networkx", "networkx")]

GROMACS_VERSION = "2024.5"
MIN_PYTHON = (3, 10)

# --- Windows ---
# Python exato do venv: 3.10.11 é a última 3.10 que o python.org distribui com instalador binário.
TARGET_VENV_PYTHON_WINDOWS = pu.PYTHON_WINDOWS_VERSION
PYTHON_WINGET_ID = "Python.Python.3.10"
PYTHON_WINDOWS_INSTALLER_URL = (f"https://www.python.org/ftp/python/{TARGET_VENV_PYTHON_WINDOWS}/"
                                f"python-{TARGET_VENV_PYTHON_WINDOWS}-amd64.exe")
# Runtime Visual C++ que as DLLs do Qt5 (PyQt5) e do NumPy/RDKit exigem.
VCREDIST_WINGET_ID = "Microsoft.VCRedist.2015+.x64"
VCREDIST_DOWNLOAD_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
PERL_WINGET_ID = "StrawberryPerl.StrawberryPerl"
CMAKE_WINGET_ID = "Kitware.CMake"
CUDA_WINGET_ID = "Nvidia.CUDA"
VS_BUILDTOOLS_WINGET_ID = "Microsoft.VisualStudio.2022.BuildTools"
# Códigos de saída do winget que também significam "já está instalado" (PACKAGE_ALREADY_INSTALLED e
# UPDATE_NOT_APPLICABLE); quem chama ainda confere o resultado depois.
_WINGET_ALREADY_OK = {0, 0x8A150061 - (1 << 32), 0x8A15010D - (1 << 32)}


# =============================== bootstrap (sem Qt) ===============================

def _run(cmd: List[str], check: bool = False, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    kwargs: dict = {}
    if IS_WINDOWS:
        # Aberto pelo atalho (pythonw.exe) não há stdin/console: sem isso o subprocess falha com "handle
        # inválido" e cada pip abriria uma janela de console.
        kwargs["stdin"] = subprocess.DEVNULL
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=check, env=env,
                          encoding="utf-8", errors="replace", **kwargs)


def _run_interactive(cmd: List[str]) -> int:
    """Roda `cmd` mostrando a saída no console (instaladores do winget, que pedem o UAC do Windows)."""
    kwargs: dict = {}
    if IS_WINDOWS:
        kwargs["stdin"] = subprocess.DEVNULL
    try:
        return subprocess.call(cmd, **kwargs)
    except OSError as e:
        print(f"[CODYN] {e}")
        return 1


def _assume_yes() -> bool:
    """CODYN_ASSUME_YES=1 (definida pelo CODYN_Windows.bat): responde "S" sozinho às confirmações do
    bootstrap, para o usuário do Windows não precisar digitar nada no terminal."""
    return os.environ.get("CODYN_ASSUME_YES") == "1"


def _prompt_yes_no(message: str, default_yes: bool = True) -> bool:
    if _assume_yes():
        print(f"{message} -> Y")
        return True
    try:
        resp = input(f"{message} {'[Y/n]' if default_yes else '[y/N]'}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return default_yes
    if not resp:
        return default_yes
    return resp in ("y", "yes", "s", "sim")


def _which(name: str) -> Optional[str]:
    return shutil.which(name)


def venv_paths(env_name: str = "CODYN") -> dict:
    home = str(Path.home())
    venv_dir = os.path.join(home, ".venv", env_name)
    scripts = pu.venv_scripts_dir(venv_dir)    # Windows: Scripts\ ; Linux: bin/
    ext = ".exe" if IS_WINDOWS else ""
    return {
        "home": home,
        "app_dir": str(Path(__file__).resolve().parent.parent),
        "venv_dir": venv_dir,
        "python": os.path.join(scripts, "python" + ext),
        "pythonw": os.path.join(scripts, "pythonw.exe") if IS_WINDOWS else os.path.join(scripts, "python"),
        "pip": os.path.join(scripts, "pip" + ext),
    }


# =============================== Windows ===============================

def _winget_available() -> bool:
    return IS_WINDOWS and _which("winget") is not None


def _winget_install(pkg_id: str, extra: Optional[List[str]] = None, log=print) -> bool:
    """winget install -e --id <pkg_id> ...; True se instalou ou se já estava instalado."""
    cmd = ["winget", "install", "--id", pkg_id, "-e", "--silent",
           "--accept-package-agreements", "--accept-source-agreements"] + list(extra or [])
    log("[CODYN] " + " ".join(cmd))
    rc = _run_interactive(cmd)
    if rc > 0x7FFFFFFF:
        rc -= 1 << 32
    return rc in _WINGET_ALREADY_OK


def _download_file(url: str, dest: str, log=print) -> bool:
    try:
        log(f"[CODYN] Downloading {url}")
        urllib.request.urlretrieve(url, dest)
        return os.path.isfile(dest) and os.path.getsize(dest) > 0
    except Exception as exc:
        log(f"[CODYN] Download failed for {url}: {exc}")
        return False


def _vcredist_installed() -> bool:
    """True se o runtime Visual C++ 2015-2022 (x64) está instalado (chave de registro do instalador)."""
    if not IS_WINDOWS:
        return True
    try:
        import winreg
    except ImportError:
        return True
    for key in (r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
                r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
                if int(winreg.QueryValueEx(handle, "Installed")[0]) == 1:
                    return True
        except OSError:
            continue
    return False


def ensure_vcredist_windows() -> bool:
    """Garante o runtime Visual C++ (x64) que as DLLs do Qt5 exigem: sem ele o import do PyQt5 falha com
    "DLL load failed". Usa o winget e, sem ele, o instalador oficial da Microsoft (o Windows pede o UAC)."""
    if not IS_WINDOWS or _vcredist_installed():
        return True
    print("[CODYN] Visual C++ runtime (x64) not found - it is required by Qt5. Installing...")
    ok = False
    if _winget_available():
        ok = _winget_install(VCREDIST_WINGET_ID)
    if not ok and not _vcredist_installed():
        import tempfile
        installer = os.path.join(tempfile.gettempdir(), "codyn_vc_redist.x64.exe")
        if _download_file(VCREDIST_DOWNLOAD_URL, installer):
            ok = _run_interactive([installer, "/install", "/quiet", "/norestart"]) in (0, 1638, 3010)
    if _vcredist_installed() or ok:
        print("[CODYN] Visual C++ runtime available.")
        return True
    print("[CODYN] Could not install the Visual C++ runtime. Install it manually:\n"
          f"        winget install --id {VCREDIST_WINGET_ID} -e\n        or {VCREDIST_DOWNLOAD_URL}")
    return False


def _python_version_string(py: str) -> Optional[str]:
    res = _run([py, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"])
    if res.returncode != 0:
        return None
    lines = res.stdout.strip().splitlines()
    return lines[-1].strip() if lines else None


def _windows_python_candidates() -> List[str]:
    """Pythons 3.10 prováveis no Windows (py launcher, pastas padrão dos instaladores, PATH)."""
    found: List[str] = []
    if _which("py"):
        res = _run(["py", "-3.10", "-c", "import sys; print(sys.executable)"])
        if res.returncode == 0 and res.stdout.strip():
            found.append(res.stdout.strip().splitlines()[-1])
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        found.append(os.path.join(local, "Programs", "Python", "Python310", "python.exe"))
    for var in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(var, "")
        if base:
            found.append(os.path.join(base, "Python310", "python.exe"))
    for name in ("python", "python3"):
        path = _which(name)
        if path:
            found.append(path)
    found.append(sys.executable)
    seen, unique = set(), []
    for path in found:
        key = os.path.normcase(os.path.abspath(path))
        if key not in seen and os.path.isfile(path):
            seen.add(key)
            unique.append(path)
    return unique


def _find_windows_python(version: str) -> Optional[str]:
    for path in _windows_python_candidates():
        if _python_version_string(path) == version:
            return path
    return None


def ensure_python310_windows(version: str = TARGET_VENV_PYTHON_WINDOWS) -> str:
    """Windows: devolve o python.exe da versão exata (3.10.11). Se não existir, instala pelo winget
    (Python.Python.3.10 --version 3.10.11) ou, sem winget, pelo instalador oficial do python.org
    (instalação por usuário, sem administrador e sem alterar o PATH)."""
    found = _find_windows_python(version)
    if found:
        return found
    print(f"[CODYN] Python {version} not found on this Windows.")
    if not _prompt_yes_no(f"[CODYN] Install Python {version} now?", default_yes=True):
        raise RuntimeError(f"Python {version} is required to create the CODYN environment.")
    if _winget_available():
        _winget_install(PYTHON_WINGET_ID, ["--version", version, "--scope", "user"])
        found = _find_windows_python(version)
        if found:
            return found
    import tempfile
    installer = os.path.join(tempfile.gettempdir(), f"python-{version}-amd64.exe")
    if _download_file(PYTHON_WINDOWS_INSTALLER_URL, installer):
        _run_interactive([installer, "/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_launcher=0",
                          "Include_test=0", "Include_pip=1"])
        found = _find_windows_python(version)
        if found:
            return found
    raise RuntimeError(
        f"Could not install Python {version}. Install it manually and start CODYN again:\n"
        f"  winget install --id {PYTHON_WINGET_ID} -e --version {version}\n"
        f"  or {PYTHON_WINDOWS_INSTALLER_URL}")


def _windows_known_folder(csidl: int) -> str:
    """Pasta especial do Windows (Desktop, Menu Iniciar > Programas), mesmo redirecionada pelo OneDrive."""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf) == 0 and buf.value:  # type: ignore[attr-defined]
            return buf.value
    except Exception:
        pass
    return ""


_LNK_POWERSHELL = r"""
$ErrorActionPreference = 'Stop'
$ws = New-Object -ComObject WScript.Shell
foreach ($lnk in ($env:CODYN_LNK_PATHS -split '\|')) {
  if (-not $lnk) { continue }
  $s = $ws.CreateShortcut($lnk)
  $s.TargetPath = $env:CODYN_LNK_TARGET
  $q = [char]34
  $s.Arguments = $q + $env:CODYN_LNK_SCRIPT + $q
  $s.WorkingDirectory = $env:CODYN_LNK_WORKDIR
  $s.Description = 'CODYN - Computational Platform for Molecular Dynamics'
  if ($env:CODYN_LNK_ICON -and (Test-Path $env:CODYN_LNK_ICON)) { $s.IconLocation = $env:CODYN_LNK_ICON }
  $s.Save()
}
"""


def windows_shortcut_paths() -> List[str]:
    """Onde ficam os atalhos CODYN.lnk: Área de Trabalho e Menu Iniciar."""
    paths = []
    for csidl in (0x10, 0x02):  # CSIDL_DESKTOPDIRECTORY, CSIDL_PROGRAMS (Menu Iniciar > Programas)
        folder = _windows_known_folder(csidl)
        if folder:
            paths.append(os.path.join(folder, "CODYN.lnk"))
    return paths


def ensure_windows_shortcuts(script_path: Optional[str] = None, env_name: str = "CODYN", force: bool = False) -> bool:
    """Cria/atualiza CODYN.lnk na Área de Trabalho e no Menu Iniciar. O atalho abre o CODYN.py com o
    pythonw.exe do venv (Scripts\\pythonw.exe: sem janela de console; a saída vai para Help > Terminal).
    Só recria quando falta um atalho ou o destino mudou. Retorna True se os atalhos existem."""
    if not IS_WINDOWS:
        return False
    p = venv_paths(env_name)
    target = p["pythonw"] if os.path.isfile(p["pythonw"]) else p["python"]
    if not os.path.isfile(target):
        return False
    script = os.path.abspath(script_path or os.path.join(p["app_dir"], "CODYN.py"))
    app_dir = os.path.dirname(script)
    icon = os.path.join(app_dir, "ICONS", "CODYN.ico")
    lnk_paths = windows_shortcut_paths()
    if not lnk_paths:
        return False
    signature = "\n".join([target, script, icon if os.path.isfile(icon) else ""] + lnk_paths)
    marker = os.path.join(p["venv_dir"], ".codyn_shortcuts")
    try:
        current = Path(marker).read_text(encoding="utf-8")
    except Exception:
        current = ""
    if not force and current == signature and all(os.path.isfile(x) for x in lnk_paths):
        return True
    env = os.environ.copy()
    env.update({"CODYN_LNK_PATHS": "|".join(lnk_paths), "CODYN_LNK_TARGET": target, "CODYN_LNK_SCRIPT": script,
                "CODYN_LNK_WORKDIR": app_dir, "CODYN_LNK_ICON": icon if os.path.isfile(icon) else ""})
    try:
        res = _run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-Command", _LNK_POWERSHELL], env=env)
    except Exception as exc:
        print(f"[CODYN] Could not create the shortcuts: {exc}")
        return False
    if res.returncode != 0:
        print(f"[CODYN] Failed to create the CODYN.lnk shortcuts:\n{res.stdout}")
        return False
    try:
        Path(marker).write_text(signature, encoding="utf-8")
    except Exception:
        pass
    print("[CODYN] CODYN.lnk shortcuts created on the Desktop and in the Start Menu.")
    return all(os.path.isfile(x) for x in lnk_paths)


def _py_ok(py: str) -> bool:
    try:
        out = _run([py, "-c", "import sys;print(sys.version_info[0], sys.version_info[1])"]).stdout.split()
        return (int(out[0]), int(out[1])) >= MIN_PYTHON
    except Exception:
        return False


def _pick_python_for_venv() -> str:
    if IS_WINDOWS:   # no Windows o venv usa exatamente o Python 3.10.11
        if _python_version_string(sys.executable) == TARGET_VENV_PYTHON_WINDOWS:
            return sys.executable
        return ensure_python310_windows(TARGET_VENV_PYTHON_WINDOWS)
    if sys.version_info >= MIN_PYTHON:
        return sys.executable
    for cand in ("python3.12", "python3.11", "python3.10", "python3"):
        p = _which(cand)
        if p and _py_ok(p):
            return p
    return sys.executable


def ensure_venv(env_name: str = "CODYN") -> dict:
    p = venv_paths(env_name)
    if IS_WINDOWS:
        ensure_vcredist_windows()  # as DLLs do Qt5 precisam do runtime Visual C++
        if os.path.isfile(p["python"]) and _python_version_string(p["python"]) != TARGET_VENV_PYTHON_WINDOWS:
            shutil.rmtree(p["venv_dir"], ignore_errors=True)   # venv com outra versão: refaz com a 3.10.11
    if not os.path.isfile(p["python"]):
        os.makedirs(os.path.dirname(p["venv_dir"]), exist_ok=True)
        res = _run([_pick_python_for_venv(), "-m", "venv", p["venv_dir"]])
        if res.returncode != 0:
            raise RuntimeError(f"Failed to create venv (is 'python3-venv' installed?):\n{res.stdout}")
        _run([p["python"], "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    return p


def _has_module(py: str, module: str) -> bool:
    return _run([py, "-c", f"import {module}"]).returncode == 0


def _running_in_target_venv(env_name: str = "CODYN") -> bool:
    try:
        paths = venv_paths(env_name)
        if IS_WINDOWS:
            # O atalho abre o CODYN com pythonw.exe (sem console) - mesmo venv que python.exe.
            allowed = {os.path.normcase(os.path.abspath(paths["python"])),
                       os.path.normcase(os.path.abspath(paths["pythonw"]))}
            return os.path.normcase(os.path.abspath(sys.executable)) in allowed
        return Path(sys.executable).resolve() == Path(paths["python"]).resolve()
    except Exception:
        return False


def _stdin_is_tty() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def bootstrap_pyqt5(interactive: bool = True, reexec: bool = True, env_name: str = "CODYN") -> bool:
    """Garante venv + PyQt5 e (opcionalmente) reexecuta o programa dentro do venv.

    Retorna True se o PyQt5 está disponível no interpretador ATUAL (ou se houve reexecução)."""
    if os.environ.get("CODYN_VENV_ACTIVE") == "1" and _running_in_target_venv(env_name):
        return True
    if IS_WINDOWS and _running_in_target_venv(env_name) and _has_module(sys.executable, "PyQt5.QtWidgets"):
        os.environ["CODYN_VENV_ACTIVE"] = "1"   # já dentro do venv (atalho/pythonw): sem novo bootstrap
        return True
    p = venv_paths(env_name)
    have_venv = os.path.isfile(p["python"])
    if not have_venv and not _stdin_is_tty() and not _assume_yes():
        print("[CODYN] First run needs a terminal to create the Python environment.", file=sys.stderr)
        return False
    if interactive and (_stdin_is_tty() or _assume_yes()) and not have_venv:
        print("=" * 70)
        print("CODYN - first run")
        print(f"  The Python environment will be created at: {p['venv_dir']}")
        if IS_WINDOWS:
            print(f"  It uses Python {TARGET_VENV_PYTHON_WINDOWS}.")
        print("  PyQt5 will be installed so the interface can open; the rest is installed")
        print("  from the 'Install requirements' window.")
        print("=" * 70)
        if _assume_yes():
            print("Continue? [Y/n] Y")
        else:
            try:
                ans = input("Continue? [Y/n] ").strip().lower()
            except EOFError:
                ans = "y"
            if ans in ("n", "no", "nao", "não"):
                return False
    try:
        p = ensure_venv(env_name)
    except Exception as e:
        print(f"[CODYN] {e}", file=sys.stderr)
        return False
    installed = False
    if not _has_module(p["python"], "PyQt5.QtWidgets"):
        print("[CODYN] Installing PyQt5 (required to open the interface)...")
        res = _run([p["python"], "-m", "pip", "install", f"PyQt5=={PINNED['PyQt5']}"])
        if res.returncode != 0:
            print(res.stdout, file=sys.stderr)
            return False
        installed = True
    if reexec and (not _running_in_target_venv(env_name) or installed):
        env = os.environ.copy()
        env["CODYN_VENV_ACTIVE"] = "1"
        env["PYTHONNOUSERSITE"] = "1"
        if IS_WINDOWS:
            # O Windows não tem exec(): os.execve criaria um processo novo e encerraria este logo em
            # seguida, soltando o terminal. Executa o filho e espera o resultado (pythonw sem terminal).
            exe = p["python"] if _stdin_is_tty() or not os.path.isfile(p["pythonw"]) else p["pythonw"]
            sys.exit(subprocess.call([exe] + sys.argv, env=env))
        os.execve(p["python"], [p["python"]] + sys.argv, env)
    return _has_module(sys.executable, "PyQt5.QtWidgets")


def missing_required_python(py: Optional[str] = None) -> List[str]:
    py = py or sys.executable
    return [name for name, mod in REQUIRED_PY if not _has_module(py, mod)]


# =============================== GUI ===============================
try:
    from PyQt5.QtCore import pyqtSignal
    from PyQt5.QtWidgets import (
        QApplication, QCheckBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
        QPushButton, QScrollArea, QVBoxLayout, QWidget,
    )
    _HAVE_QT = True
except Exception:  # pragma: no cover - PyQt5 ainda não instalado
    _HAVE_QT = False

if _HAVE_QT:
    from BIN import hw_info, tools
    from BIN.i18n import Translator, detect_system_language
    from BIN.theme import PALETTE, ensure_button_fits, set_role
    from BIN.widgets import CollapsibleGroupBox, LogConsole

    class RequirementsInstaller(QWidget):
        log_signal = pyqtSignal(str)
        progress_signal = pyqtSignal(int)
        busy_signal = pyqtSignal(bool)
        done_signal = pyqtSignal()

        def __init__(self, parent=None, translator: Optional[Translator] = None):
            super().__init__(parent)
            self.tr_ = translator or Translator(detect_system_language())
            self.paths = venv_paths("CODYN")
            self.app_dir = Path(self.paths["app_dir"])
            self.rows: Dict[str, dict] = {}
            self._thread: Optional[threading.Thread] = None
            self.setMinimumWidth(780)
            self.resize(860, 760)

            root = QVBoxLayout(self)
            self.lbl_intro = QLabel()
            self.lbl_intro.setWordWrap(True)
            root.addWidget(self.lbl_intro)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            holder = QWidget()
            self.items_layout = QVBoxLayout(holder)
            scroll.setWidget(holder)
            scroll.setMinimumHeight(300)
            root.addWidget(scroll, 4)

            self._build_groups()
            self.items_layout.addStretch()

            self.progress = QProgressBar()
            root.addWidget(self.progress)
            self.log = LogConsole()
            self.log.setMinimumHeight(140)
            root.addWidget(self.log, 1)

            btns = QHBoxLayout()
            self.btn_missing = QPushButton(); set_role(self.btn_missing, "select")
            self.btn_all = QPushButton(); set_role(self.btn_all, "secondary")
            self.btn_refresh = QPushButton(); set_role(self.btn_refresh, "secondary")
            self.btn_install = QPushButton(); set_role(self.btn_install, "primary")
            self.btn_close = QPushButton(); set_role(self.btn_close, "danger")
            for b in (self.btn_missing, self.btn_all, self.btn_refresh):
                btns.addWidget(b)
            btns.addStretch()
            btns.addWidget(self.btn_install)
            btns.addWidget(self.btn_close)
            root.addLayout(btns)

            tr = self.tr_.tr
            tr("req_intro_win" if IS_WINDOWS else "req_intro", self.lbl_intro.setText, venv=self.paths["venv_dir"])
            tr("req_btn_select_missing", self.btn_missing.setText)
            tr("req_btn_select_all", self.btn_all.setText)
            tr("req_btn_refresh", self.btn_refresh.setText)
            tr("req_btn_install", self.btn_install.setText)
            tr("btn_close", self.btn_close.setText)
            self.btn_missing.clicked.connect(self.select_missing)
            self.btn_all.clicked.connect(self.toggle_all)
            self.btn_refresh.clicked.connect(self.refresh_status)
            self.btn_install.clicked.connect(self.start_installation)
            self.btn_close.clicked.connect(self.close)
            self.log_signal.connect(self.log.log)
            self.progress_signal.connect(self.progress.setValue)
            self.busy_signal.connect(self._set_busy)
            self.done_signal.connect(self.refresh_status)
            self.tr_.tr("req_title", self.setWindowTitle)
            for b in (self.btn_missing, self.btn_all, self.btn_refresh, self.btn_install, self.btn_close):
                ensure_button_fits(b)
            self.refresh_status()
            self.select_missing()

        # ------------------------- construção da lista -------------------------
        def _add_group(self, title_key: str) -> QVBoxLayout:
            grp = CollapsibleGroupBox()
            self.tr_.tr(title_key, grp.setTitle)
            lay = QVBoxLayout(grp)
            self.items_layout.addWidget(grp)
            return lay

        def _add_item(self, lay: QVBoxLayout, key: str, label_key: str, kind: str,
                      version: Optional[str] = None, hint_key: Optional[str] = None):
            row = QHBoxLayout()
            chk = QCheckBox()
            self.tr_.tr(label_key, chk.setText)
            status = QLabel()
            status.setMinimumWidth(190)
            row.addWidget(chk, 3)
            ed = None
            if version is not None:
                ed = QLineEdit(version)
                ed.setMaximumWidth(120)
                row.addWidget(ed)
            row.addWidget(status, 2)
            lay.addLayout(row)
            if hint_key:
                hint = QLabel()
                hint.setWordWrap(True)
                hint.setStyleSheet(f"color:{PALETTE['muted']};font-size:8pt;margin-left:24px;")
                self.tr_.tr(hint_key, hint.setText)
                lay.addWidget(hint)
            self.rows[key] = {"check": chk, "status": status, "edit": ed, "kind": kind}

        def _add_note(self, lay: QVBoxLayout, hint_key: str):
            """Texto explicativo solto (sem caixa de seleção) dentro de um grupo."""
            note = QLabel()
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{PALETTE['muted']};font-size:8pt;")
            self.tr_.tr(hint_key, note.setText)
            lay.addWidget(note)

        def _build_groups(self):
            g = self._add_group("req_grp_python")
            self._add_item(g, "venv", "req_venv", "venv")
            for name in ("PyQt5", "numpy", "pandas", "matplotlib", "scipy", "psutil", "networkx", "MDAnalysis", "rdkit", "python-docx"):
                self._add_item(g, name, f"req_pkg_{name.lower()}", "pip", PINNED[name])
            g = self._add_group("req_grp_ligand")
            if IS_WINDOWS:
                # Windows: Open Babel pelo pip (openbabel-wheel), Perl pelo winget (Strawberry Perl). O AmberTools
                # (antechamber/acpype, método AMBER/GAFF) e o gmx_MMPBSA não existem para Windows.
                self._add_item(g, "openbabel", "req_openbabel", "openbabel", hint_key="req_hint_openbabel_win")
                self._add_item(g, "perl", "req_perl", "winget_perl", hint_key="req_hint_perl_win")
                self._add_note(g, "req_hint_win_amber")
                g = self._add_group("req_grp_sim")
                self._add_item(g, "cuda", "req_cuda", "cuda", hint_key="req_hint_cuda_win")
                self._add_item(g, "gromacs", "req_gromacs", "gromacs", GROMACS_VERSION, hint_key="req_hint_gromacs_win")
                self._add_note(g, "req_hint_win_mmpbsa")
            else:
                self._add_item(g, "openbabel", "req_openbabel", "openbabel", hint_key="req_hint_openbabel")
                self._add_item(g, "perl", "req_perl", "apt", hint_key="req_hint_perl")
                self._add_item(g, "acpype", "req_acpype", "pip", PINNED["acpype"], hint_key="req_hint_acpype")
                self._add_item(g, "ambertools", "req_ambertools", "ambertools", hint_key="req_hint_ambertools")
                g = self._add_group("req_grp_sim")
                self._add_item(g, "cuda", "req_cuda", "cuda", hint_key="req_hint_cuda")
                self._add_item(g, "gromacs", "req_gromacs", "gromacs", GROMACS_VERSION, hint_key="req_hint_gromacs")
                self._add_item(g, "mpi", "req_mpi", "apt", hint_key="req_hint_mpi")
                self._add_item(g, "gmxmmpbsa", "req_gmxmmpbsa", "gmxmmpbsa", hint_key="req_hint_gmxmmpbsa")
            g = self._add_group("req_grp_launcher")
            self._add_item(g, "launcher", "req_launcher_win" if IS_WINDOWS else "req_launcher", "launcher")

        # ------------------------- estado -------------------------
        def _status_of(self, key: str) -> str:
            """'' = não instalado; texto = versão/caminho."""
            py = self.paths["python"] if os.path.isfile(self.paths["python"]) else sys.executable
            if key == "venv":
                return str(self.paths["venv_dir"]) if os.path.isfile(self.paths["python"]) else ""
            if key in PINNED and self.rows[key]["kind"] == "pip":
                mod = {"PyQt5": "PyQt5.QtCore", "MDAnalysis": "MDAnalysis", "python-docx": "docx"}.get(key, key)
                attr = "PYQT_VERSION_STR" if key == "PyQt5" else "__version__"
                if py == sys.executable:
                    return hw_info.python_lib_version(mod, attr)
                out = _run([py, "-c", f"import {mod} as m; print(getattr(m,'{attr}','ok'))"])
                return out.stdout.strip().splitlines()[-1] if out.returncode == 0 and out.stdout.strip() else ""
            if key == "openbabel":
                return tools.find_obabel() or ""
            if key == "perl":
                return tools.find_perl() or ""
            if key == "ambertools":
                return tools.find_executable("antechamber", search_conda=True) or ""
            if key == "cuda":
                return pu.nvcc_path() or ""
            if key == "gromacs":
                gmx = tools.find_gmx(refresh=True)
                return (tools.gmx_info(gmx).get("version") or gmx) if gmx else ""
            if key == "mpi":
                return shutil.which("mpirun") or ""
            if key == "gmxmmpbsa":
                return tools.find_executable("gmx_MMPBSA", extra=["/usr/local/bin/gmx_MMPBSA"], search_conda=True) or ""
            if key == "launcher":
                if IS_WINDOWS:
                    lnk = [x for x in windows_shortcut_paths() if os.path.isfile(x)]
                    return lnk[0] if lnk else ""
                f = Path.home() / ".local" / "share" / "applications" / "CODYN.desktop"
                return str(f) if f.exists() else ""
            return ""

        def refresh_status(self):
            for key, row in self.rows.items():
                s = self._status_of(key)
                row["installed"] = bool(s)
                lbl = row["status"]
                if s:
                    lbl.setText(("✔ " + s)[:44])
                    lbl.setToolTip(s)
                    lbl.setStyleSheet(f"color:{PALETTE['accent_dark']};font-weight:bold;")
                else:
                    lbl.setText("✖ " + self.tr_.t("req_not_installed"))
                    lbl.setToolTip("")
                    lbl.setStyleSheet(f"color:{PALETTE['danger']};font-weight:bold;")

        def select_missing(self):
            for key, row in self.rows.items():
                row["check"].setChecked(not row.get("installed", False)
                                        and key not in ("rdkit", "MDAnalysis", "scipy", "launcher", "cuda", "ambertools"))
            # CUDA/AmberTools/launcher só quando o usuário pedir (instalações pesadas ou opcionais)
            if not self.rows["launcher"].get("installed"):
                self.rows["launcher"]["check"].setChecked(True)

        def toggle_all(self):
            new = not all(r["check"].isChecked() for r in self.rows.values())
            for r in self.rows.values():
                r["check"].setChecked(new)

        def _set_busy(self, busy: bool):
            self.btn_install.setEnabled(not busy)
            for r in self.rows.values():
                r["check"].setEnabled(not busy)

        # ------------------------- instalação -------------------------
        def start_installation(self):
            chosen = [k for k, r in self.rows.items() if r["check"].isChecked()]
            if not chosen:
                QMessageBox.information(self, self.tr_.t("req_title"), self.tr_.t("req_none_selected"))
                return
            self.busy_signal.emit(True)
            self.progress.setMaximum(len(chosen))
            self.progress.setValue(0)
            self.log.clear()
            versions = {k: (r["edit"].text().strip() if r["edit"] else "") for k, r in self.rows.items()}
            self._thread = threading.Thread(target=self._run_selected, args=(chosen, versions), daemon=True)
            self._thread.start()

        def _emit(self, msg: str):
            self.log_signal.emit(msg)

        def _cmd(self, cmd: List[str], cwd: Optional[str] = None) -> bool:
            self._emit("$ " + " ".join(cmd))
            try:
                rc, _ = tools.run_cmd(cmd, cwd=cwd, log=self._emit, log_every=0.2)
            except Exception as e:
                self._emit(f"ERROR: {e}")
                return False
            return rc == 0

        def _privileged(self, cmd: List[str]) -> bool:
            """Comando de administrador: pkexec (janela de senha) ou sudo no terminal."""
            if shutil.which("pkexec") and os.environ.get("DISPLAY"):
                return self._cmd(["pkexec"] + cmd)
            self._emit("$ sudo " + " ".join(cmd) + "   (password prompt appears in the terminal)")
            return subprocess.run(["sudo"] + cmd).returncode == 0

        def _apt(self, pkgs: List[str]) -> bool:
            if not shutil.which("apt-get"):
                self._emit("apt-get not available on this system; install manually: " + " ".join(pkgs))
                return False
            return self._privileged(["apt-get", "install", "-y"] + pkgs)

        def _pip(self, spec: str) -> bool:
            return self._cmd([self.paths["python"], "-m", "pip", "install", spec])

        def _run_selected(self, chosen: List[str], versions: Dict[str, str]):
            step = 0
            try:
                if not os.path.isfile(self.paths["python"]):
                    ensure_venv("CODYN")
                for key in chosen:
                    kind = self.rows[key]["kind"]
                    self._emit(f"\n=== {self.tr_.t('req_installing', item=key)} ===")
                    ok = True
                    if kind == "venv":
                        ensure_venv("CODYN")
                    elif kind == "pip":
                        ver = versions.get(key, "")
                        ok = self._pip(f"{key}=={ver}" if ver else key)
                    elif kind == "openbabel":
                        ok = self._pip("openbabel-wheel") or (not IS_WINDOWS and self._apt(["openbabel"]))
                    elif kind == "winget_perl":
                        ok = self._install_perl_windows()
                    elif kind == "apt":
                        ok = self._apt({"perl": ["perl"], "mpi": ["openmpi-bin", "libopenmpi-dev"]}[key])
                    elif kind == "cuda":
                        ok = self._install_cuda()
                    elif kind == "gromacs":
                        ok = self._install_gromacs(versions.get("gromacs") or GROMACS_VERSION)
                    elif kind == "ambertools":
                        ok = self._install_ambertools()
                    elif kind == "gmxmmpbsa":
                        ok = self._install_gmxmmpbsa()
                    elif kind == "launcher":
                        ok, msg = create_desktop_launcher()
                        self._emit(msg)
                    if not ok:
                        self._emit(f"\n✖ {self.tr_.t('req_failed', item=key)}")
                        return
                    step += 1
                    self.progress_signal.emit(step)
                self._emit("\n✔ " + self.tr_.t("req_all_done"))
            except Exception as e:
                self._emit(f"ERROR: {type(e).__name__}: {e}")
            finally:
                self.busy_signal.emit(False)
                self.done_signal.emit()

        def _winget(self, pkg_id: str, extra: Optional[List[str]] = None) -> bool:
            """winget no Windows: a saída do instalador vai para o terminal (Help > Terminal)."""
            if not _winget_available():
                self._emit("winget was not found (it comes with Windows 10/11 'App Installer'). Install "
                           f"manually: winget install --id {pkg_id} -e")
                return False
            self._emit(f"$ winget install --id {pkg_id} -e   (Windows may ask for confirmation)")
            return _winget_install(pkg_id, extra, log=self._emit)

        def _install_perl_windows(self) -> bool:
            if tools.find_perl():
                self._emit("Perl already present.")
                return True
            if not self._winget(PERL_WINGET_ID):
                return False
            return bool(tools.find_perl()) or self._ok_after_path_refresh("Perl")

        def _ok_after_path_refresh(self, what: str) -> bool:
            self._emit(f"{what} was installed, but this session does not see it yet; restart CODYN.")
            return True

        def _install_cuda(self) -> bool:
            if pu.nvcc_path():
                self._emit("CUDA Toolkit already present.")
                return True
            if IS_WINDOWS:
                return self._winget(CUDA_WINGET_ID)
            return self._apt(["nvidia-cuda-toolkit"])

        def _install_ambertools(self) -> bool:
            if tools.find_executable("antechamber", search_conda=True):
                self._emit("AmberTools already present.")
                return True
            conda = shutil.which("mamba") or shutil.which("conda") or tools.find_executable("conda", search_conda=True)
            if not conda:
                self._emit(self.tr_.t("req_no_conda"))
                return False
            return self._cmd([conda, "create", "-y", "-n", "AmberTools", "-c", "conda-forge", "ambertools"])

        def _install_gmxmmpbsa(self) -> bool:
            py = self.paths["python"]
            if not self._cmd([py, "-m", "pip", "install", "numpy", "scipy", "matplotlib", "pandas", "seaborn",
                              "tqdm", "PyYAML", "Cython"]):
                return False
            if not shutil.which("mpirun") and not self._apt(["openmpi-bin", "libopenmpi-dev"]):
                return False
            if not self._cmd([py, "-m", "pip", "install", "mpi4py"]):
                return False
            work = os.path.join(str(Path.home()), "gmx_MMPBSA_install")
            repo = os.path.join(work, "gmx_MMPBSA")
            os.makedirs(work, exist_ok=True)
            if not os.path.isdir(repo):
                if not self._cmd(["git", "clone", "https://github.com/Valdes-Tresanco-MS/gmx_MMPBSA.git", repo]):
                    return False
            if not self._cmd([py, "-m", "pip", "install", "."], cwd=repo):
                return False
            self._emit(self.tr_.t("req_mmpbsa_note"))
            return True

        # ---- GROMACS no Windows: compilado do código-fonte com CMake + Visual Studio Build Tools ----
        def _find_cmake_windows(self) -> Optional[str]:
            found = shutil.which("cmake")
            if found:
                return found
            for base in pu.program_dirs():
                candidate = os.path.join(base, "CMake", "bin", "cmake.exe")
                if os.path.isfile(candidate):
                    return candidate
            return None

        def _has_msvc_windows(self) -> bool:
            """True se há o Visual Studio (ou Build Tools) com o compilador C++ (vswhere, da Microsoft)."""
            vswhere = os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                                   "Microsoft Visual Studio", "Installer", "vswhere.exe")
            if not os.path.isfile(vswhere):
                return False
            res = _run([vswhere, "-latest", "-products", "*", "-requires",
                        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"])
            return res.returncode == 0 and bool(res.stdout.strip())

        def _install_gromacs_windows(self, ver: str) -> bool:
            import tarfile
            if tools.find_gmx(refresh=True):
                self._emit("GROMACS already present.")
                return True
            cmake = self._find_cmake_windows()
            if not cmake:
                if not self._winget(CMAKE_WINGET_ID):
                    return False
                cmake = self._find_cmake_windows()
                if not cmake:
                    self._emit("CMake was installed, but this session does not see it yet; restart CODYN and install GROMACS again.")
                    return False
            if not self._has_msvc_windows():
                self._emit("Installing Visual Studio Build Tools (C++ compiler, several GB; this takes a while)...")
                override = ("--wait --quiet --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended")
                if not self._winget(VS_BUILDTOOLS_WINGET_ID, ["--override", override]) or not self._has_msvc_windows():
                    self._emit("The C++ compiler is not available. Install 'Visual Studio Build Tools' with the "
                               "'Desktop development with C++' workload and try again.")
                    return False
            work = os.path.join(str(Path.home()), "gromacs_build")
            os.makedirs(work, exist_ok=True)
            tarball = os.path.join(work, f"gromacs-{ver}.tar.gz")
            if not os.path.exists(tarball):
                self._emit(f"Downloading GROMACS {ver} source...")
                if not _download_file(f"https://ftp.gromacs.org/gromacs/gromacs-{ver}.tar.gz", tarball, log=self._emit):
                    return False
            src = os.path.join(work, f"gromacs-{ver}")
            if not os.path.isdir(src):
                self._emit("Extracting the source...")
                with tarfile.open(tarball) as tf:
                    tf.extractall(work)
            build = os.path.join(src, "build")
            prefix = pu.gromacs_install_dir()
            os.makedirs(build, exist_ok=True)
            nvcc = pu.nvcc_path()
            base_opts = ["-A", "x64", f"-DCMAKE_INSTALL_PREFIX={prefix}", "-DREGRESSIONTEST_DOWNLOAD=OFF",
                         "-DGMX_THREAD_MPI=ON", "-DGMX_OPENMP=ON", "-DBUILD_TESTING=OFF", "-DGMXAPI=OFF",
                         "-DGMX_INSTALL_NBLIB_API=OFF"]
            attempts = []
            if nvcc:
                attempts.append(("CUDA", base_opts + ["-DGMX_BUILD_OWN_FFTW=ON", "-DGMX_GPU=CUDA"]))
            attempts.append(("CPU only", base_opts + ["-DGMX_BUILD_OWN_FFTW=ON", "-DGMX_GPU=OFF"]))
            attempts.append(("CPU only, built-in FFT", base_opts + ["-DGMX_FFT_LIBRARY=fftpack", "-DGMX_GPU=OFF"]))
            configured = False
            for label, opts in attempts:
                self._emit(f"Configuring ({label})...")
                if os.path.isfile(os.path.join(build, "CMakeCache.txt")):
                    os.remove(os.path.join(build, "CMakeCache.txt"))
                if self._cmd([cmake, "-S", src, "-B", build] + opts):
                    configured = True
                    break
                self._emit(f"Configuration '{label}' failed; trying the next option...")
            if not configured:
                return False
            self._emit("Building GROMACS (this takes a long time)...")
            if not self._cmd([cmake, "--build", build, "--config", "Release", "--target", "install", "--", "/m"]):
                return False
            gmx = tools.find_gmx(refresh=True)
            if not gmx:
                self._emit(f"The build finished, but gmx.exe was not found in {prefix}\\bin.")
                return False
            self._emit(f"GROMACS installed at {prefix}")
            return True

        def _install_gromacs(self, ver: str) -> bool:
            if IS_WINDOWS:
                return self._install_gromacs_windows(ver)
            deps = ["build-essential", "git", "wget", "cmake", "libfftw3-dev", "libopenmpi-dev", "openmpi-bin", "libgsl-dev"]
            if not self._apt(deps):
                return False
            nvcc = shutil.which("nvcc") or ("/usr/local/cuda/bin/nvcc" if os.path.exists("/usr/local/cuda/bin/nvcc") else None)
            work = os.path.join(str(Path.home()), "gromacs_build")
            os.makedirs(work, exist_ok=True)
            tarball = os.path.join(work, f"gromacs-{ver}.tar.gz")
            if not os.path.exists(tarball):
                self._emit(f"Downloading GROMACS {ver} source...")
                urllib.request.urlretrieve(f"https://ftp.gromacs.org/gromacs/gromacs-{ver}.tar.gz", tarball)
            if not self._cmd(["tar", "-xzf", tarball, "-C", work]):
                return False
            build = os.path.join(work, f"gromacs-{ver}", "build")
            os.makedirs(build, exist_ok=True)
            opts = ["-DGMX_BUILD_OWN_FFTW=ON", "-DREGRESSIONTEST_DOWNLOAD=OFF", "-DGMX_THREAD_MPI=ON",
                    "-DGMX_OPENMP=ON", "-DGMX_USE_RDTSCP=ON",
                    "-DGMX_GPU=CUDA" if nvcc else "-DGMX_GPU=OFF"]
            if nvcc:
                opts.append(f"-DCMAKE_CUDA_COMPILER={nvcc}")
            self._emit(f"Configuring ({'CUDA' if nvcc else 'CPU only'})...")
            if not self._cmd(["cmake", ".."] + opts, cwd=build):
                return False
            self._emit("Building GROMACS (this takes a while)...")
            if not self._cmd(["make", f"-j{os.cpu_count() or 4}"], cwd=build):
                return False
            if not self._privileged(["make", "-C", build, "install"]):
                return False
            bashrc = Path.home() / ".bashrc"
            line = "source /usr/local/gromacs/bin/GMXRC"
            try:
                if not bashrc.exists() or line not in bashrc.read_text(encoding="utf-8", errors="ignore"):
                    with open(bashrc, "a", encoding="utf-8") as f:
                        f.write(f"\n# GROMACS (CODYN)\n{line}\n")
            except OSError:
                pass
            tools.find_gmx(refresh=True)
            return True

        def closeEvent(self, event):
            if self._thread is not None and self._thread.is_alive():
                QMessageBox.information(self, self.tr_.t("req_title"), self.tr_.t("req_busy"))
                event.ignore()
                return
            event.accept()


def create_desktop_launcher(icon: Optional[str] = None) -> tuple:
    """Cria/atualiza o atalho do programa: Linux, ~/.local/share/applications/CODYN.desktop; Windows, os
    atalhos CODYN.lnk na Área de Trabalho e no Menu Iniciar (apontando para o venv do usuário)."""
    if IS_WINDOWS:
        ok = ensure_windows_shortcuts()
        return ok, ("Shortcuts created/updated: " + ", ".join(windows_shortcut_paths())) if ok else \
            "Failed to create the CODYN shortcuts (is the Python environment created?)."
    try:
        p = venv_paths("CODYN")
        app_dir = Path(p["app_dir"])
        icon = icon or str(app_dir / "ICONS" / "LOGO_CODYN.png")
        d = Path.home() / ".local" / "share" / "applications"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "CODYN.desktop"
        exec_cmd = f"bash -i -c \"env PYTHONNOUSERSITE=1 '{p['python']}' '{app_dir / 'CODYN.py'}'\""
        content = (
            "[Desktop Entry]\n"
            "Version=1.0\n"
            "Name=CODYN\n"
            "Comment=Automated protein-ligand molecular dynamics (GROMACS)\n"
            f"Exec={exec_cmd}\n"
            f"Icon={icon}\n"
            "Terminal=false\n"
            "Type=Application\n"
            "Categories=Qt;Science;Chemistry;Education;\n"
            "StartupNotify=false\n"
        )
        if not f.exists() or f.read_text(encoding="utf-8") != content:
            f.write_text(content, encoding="utf-8")
        os.chmod(f, 0o755)
        if shutil.which("update-desktop-database"):
            subprocess.run(["update-desktop-database", str(d)], capture_output=True)
        return True, f"Launcher created/updated at: {f}"
    except Exception as e:
        return False, f"Failed to create/update launcher: {e}"


if __name__ == "__main__" and _HAVE_QT:
    app = QApplication(sys.argv)
    from BIN.theme import SS_MAIN
    app.setStyleSheet(SS_MAIN)
    w = RequirementsInstaller()
    w.show()
    sys.exit(app.exec_())
