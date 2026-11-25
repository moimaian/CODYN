# -*- coding: utf-8 -*-
"""Informações de hardware e software exibidas na HOME e usadas pelo instalador (sem Qt)."""

import importlib
import os
import platform
import re
import shutil
import subprocess
from typing import Dict, List, Tuple

from BIN import platform_utils as pu
from BIN import tools

try:
    import psutil
except Exception:  # psutil ainda não instalado (primeira execução)
    psutil = None


def _psutil():
    """psutil, tentando importar de novo se ele foi instalado depois de o programa abrir."""
    global psutil
    if psutil is None:
        try:
            importlib.invalidate_caches()
            import psutil as _p
            psutil = _p
        except Exception:
            pass
    return psutil


def _out(cmd: List[str], timeout: float = 4.0) -> str:
    # LC_ALL=C: lscpu/nvcc/obabel traduzem os rótulos conforme o locale e quebrariam o parsing
    try:
        env = dict(os.environ, LC_ALL="C", LANG="C")
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, env=env).stdout
    except Exception:
        return ""


# ------------------------------- CPU / RAM / disco -------------------------------

def cpu_info() -> List[Tuple[str, str]]:
    """[(rótulo_i18n_key, valor)] — as chaves são traduzidas pela HOME."""
    rows: List[Tuple[str, str]] = [("hw_arch", platform.machine() or "?")]
    lscpu = _out(["lscpu"]) if not pu.IS_WINDOWS else ""   # o Windows não tem lscpu
    fields = {}
    for line in lscpu.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    if pu.IS_WINDOWS:
        win_model = _windows_cpu_name()
        if win_model:
            fields["Model name"] = win_model
        ps = _psutil()
        try:
            freq = ps.cpu_freq() if ps is not None else None
            if freq and freq.max:
                fields["CPU max MHz"] = str(freq.max)
        except Exception:
            pass
    model = fields.get("Model name") or platform.processor() or "?"
    rows.append(("hw_model", model))
    if fields.get("CPU max MHz"):
        try:
            rows.append(("hw_max_clock", f"{float(fields['CPU max MHz']) / 1000:.2f} GHz"))
        except ValueError:
            pass
    phys = None
    try:
        sockets = int(fields.get("Socket(s)", "1") or 1)
        phys = sockets * int(fields.get("Core(s) per socket", "0") or 0)
    except ValueError:
        pass
    if _psutil() is not None and not phys:
        phys = psutil.cpu_count(logical=False)
    rows.append(("hw_cores", str(phys or "?")))
    rows.append(("hw_threads", str(os.cpu_count() or "?")))
    for key, label in (("L2 cache", "hw_l2"), ("L3 cache", "hw_l3")):
        if fields.get(key):
            rows.append((label, fields[key]))
    if _psutil() is not None:
        mem = psutil.virtual_memory()
        rows.append(("hw_ram", f"{mem.total / 1073741824:.1f} GB ({mem.available / 1073741824:.1f} GB free)"))
    return rows


def _windows_cpu_name() -> str:
    """Nome do processador no Windows (registro: HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            return " ".join(str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).split())
    except Exception:
        return ""


def disk_free_gb(path: str) -> float:
    try:
        return shutil.disk_usage(path).free / 1073741824
    except Exception:
        return 0.0


# ------------------------------- GPU / CUDA -------------------------------

def gpu_info() -> List[Tuple[str, str]]:
    if not shutil.which("nvidia-smi"):
        return [("hw_gpu", "nvidia-smi not found")]
    raw = _out(["nvidia-smi", "--query-gpu=name,memory.total,clocks.max.sm,power.limit,driver_version",
                "--format=csv,noheader,nounits"]).strip()
    if not raw:
        return [("hw_gpu", "NVIDIA GPU not responding")]
    rows: List[Tuple[str, str]] = []
    first = raw.splitlines()[0]
    parts = [p.strip() for p in first.split(",")]
    name = parts[0]
    rows.append(("hw_gpu", name + (f"  (+{len(raw.splitlines()) - 1})" if len(raw.splitlines()) > 1 else "")))
    if len(parts) > 1:
        rows.append(("hw_vram", f"{float(parts[1]) / 1024:.1f} GB"))
    if len(parts) > 2 and parts[2] not in ("", "[N/A]"):
        rows.append(("hw_gpu_clock", f"{parts[2]} MHz"))
    if len(parts) > 3 and parts[3] not in ("", "[N/A]"):
        rows.append(("hw_gpu_power", f"{float(parts[3]):.0f} W"))
    if len(parts) > 4:
        rows.append(("hw_driver", parts[4]))
    cuda = cuda_version()
    if cuda:
        rows.append(("hw_cuda", cuda))
    return rows


def cuda_version() -> str:
    """CUDA do toolkit (nvcc) ou, na falta dele, a versão máxima suportada pelo driver."""
    nvcc = pu.nvcc_path()
    if nvcc:
        m = re.search(r"release\s+([\d.]+)", _out([nvcc, "--version"]))
        if m:
            return m.group(1)
    m = re.search(r"CUDA Version:\s*([\d.]+)", _out(["nvidia-smi"]))
    return f"{m.group(1)} (driver)" if m else ""


def has_nvidia() -> bool:
    return bool(shutil.which("nvidia-smi")) and bool(_out(["nvidia-smi", "-L"]).strip())


# ------------------------------- software -------------------------------

# (nome exibido, módulo, atributo)
PY_LIBS = [
    ("PyQt5", "PyQt5.QtCore", "PYQT_VERSION_STR"),
    ("NumPy", "numpy", "__version__"),
    ("Pandas", "pandas", "__version__"),
    ("Matplotlib", "matplotlib", "__version__"),
    ("SciPy", "scipy", "__version__"),
    ("psutil", "psutil", "__version__"),
    ("NetworkX", "networkx", "__version__"),
    ("MDAnalysis", "MDAnalysis", "__version__"),
    ("RDKit", "rdkit", "__version__"),
    ("python-docx", "docx", "__version__"),
]


def python_lib_version(module: str, attr: str) -> str:
    try:
        mod = importlib.import_module(module)
        v = getattr(mod, attr, None)
        if v is None:
            from importlib import metadata
            v = metadata.version(module.split(".")[0])
        return str(v)
    except Exception:
        return ""


def external_tools() -> List[Tuple[str, str, str]]:
    """[(nome, caminho|'', versão)] das ferramentas externas usadas pelo pipeline."""
    rows: List[Tuple[str, str, str]] = []
    gmx = tools.find_gmx()
    info = tools.gmx_info(gmx) if gmx else {}
    ver = info.get("version", "")
    if info.get("gpu") and info["gpu"].lower() != "disabled":
        ver += f" [{info['gpu']}]"
    rows.append(("GROMACS", gmx or "", ver))
    obabel = tools.find_obabel()
    ob_ver = ""
    if obabel:
        m = re.search(r"Open Babel\s+([\d.]+)", _out([obabel, "-V"]))
        ob_ver = m.group(1) if m else ""
    rows.append(("Open Babel", obabel or "", ob_ver))
    rows.append(("Perl", tools.find_perl() or "", ""))
    ante = tools.find_executable("antechamber", search_conda=True)
    rows.append(("AmberTools (antechamber)", ante or "", ""))
    rows.append(("acpype", tools.find_executable("acpype", search_conda=True) or "", python_lib_version("acpype", "__version__")))
    mm = tools.find_executable("gmx_MMPBSA", extra=["/usr/local/bin/gmx_MMPBSA"], search_conda=True)
    rows.append(("gmx_MMPBSA", mm or "", ""))
    if not pu.IS_WINDOWS:   # o GROMACS do Windows usa thread-MPI: não precisa de mpirun
        rows.append(("MPI (mpirun)", shutil.which("mpirun") or "", ""))
    nvcc = pu.nvcc_path() or ""
    rows.append(("CUDA Toolkit (nvcc)", nvcc, cuda_version() if nvcc else ""))
    return rows


def software_versions() -> List[Tuple[str, str]]:
    """[(nome, versão|'')] — versão vazia = não instalado."""
    rows = [("Python", platform.python_version())]
    for name, mod, attr in PY_LIBS:
        rows.append((name, python_lib_version(mod, attr)))
    for name, path, ver in external_tools():
        rows.append((name, (ver or "OK") if path else ""))
    return rows


def detect_hardware() -> Dict[str, object]:
    return {
        "cpu_threads": os.cpu_count() or 1,
        "ram_gb": (psutil.virtual_memory().total / 1073741824) if _psutil() else 0.0,
        "has_nvidia": has_nvidia(),
        "cuda": cuda_version(),
        "disk_free_gb": disk_free_gb(os.path.expanduser("~")),
    }
