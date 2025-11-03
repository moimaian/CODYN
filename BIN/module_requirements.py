# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shutil
import urllib.request
import threading
from pathlib import Path
from typing import Optional, List, Tuple

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox, QPushButton, QTextEdit, QApplication,
    QHBoxLayout, QMessageBox, QProgressBar, QLineEdit, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal


# ============================ helpers (pip-only / system) ============================

def _run(cmd: List[str], check: bool = False) -> subprocess.CompletedProcess:
    """Executa um comando e retorna CompletedProcess (stdout + stderr unificados)."""
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=check)

def _which(name: str) -> Optional[str]:
    return shutil.which(name)

def venv_paths(env_name: str = "CODYN") -> dict:
    """
    Define o local do venv do CODYN e retorna caminhos úteis.
    venv: ~/.venv/CODYN
    """
    home = str(Path.home())
    project_root = Path(__file__).resolve().parent.parent  # .../CODYN
    venv_dir = os.path.join(home, ".venv", env_name)
    if os.name == "nt":
        py = os.path.join(venv_dir, "Scripts", "python.exe")
        pip = os.path.join(venv_dir, "Scripts", "pip.exe")
    else:
        py = os.path.join(venv_dir, "bin", "python")
        pip = os.path.join(venv_dir, "bin", "pip")
    return {
        "home": home,
        "project_root": str(project_root),
        "venv_dir": venv_dir,
        "python": py,
        "pip": pip,
    }

def _pick_python_for_venv() -> str:
    """
    Escolhe um Python >=3.10 para criar o venv:
      - usa o Python atual se >=3.10
      - senão tenta 'python3.10', depois 'python3'
    """
    if sys.version_info >= (3, 10):
        return sys.executable
    return _which("python3.10") or _which("python3") or sys.executable

def ensure_venv(env_name: str = "CODYN") -> dict:
    """
    Garante a existência do venv em ~/.venv/CODYN e pip/setuptools/wheel atualizados.
    """
    p = venv_paths(env_name)
    need_create = (not os.path.isdir(p["venv_dir"])) or (not os.path.isfile(p["python"]))
    if need_create:
        py_for_venv = _pick_python_for_venv()
        res = _run([py_for_venv, "-m", "venv", p["venv_dir"]])
        if res.returncode != 0:
            raise RuntimeError(f"Falha ao criar venv:\n{res.stdout}")
        _run([p["python"], "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    return p

def _pip_install(python_bin: str, specs: List[str]) -> subprocess.CompletedProcess:
    """
    Executa pip install no venv (python -m pip install ...).
    """
    cmd = [python_bin, "-m", "pip", "install", "--upgrade"] + specs
    return _run(cmd)

def _apt_install(pkgs: List[str]) -> bool:
    """
    Instala pacotes via apt (requer sudo). Retorna True/False.
    """
    try:
        ret = os.system("sudo apt-get update")
        if ret != 0:
            return False
        cmd = "sudo apt-get install -y " + " ".join(pkgs)
        ret = os.system(cmd)
        return ret == 0
    except Exception:
        return False


# ================================== UI =====================================

class RequirementsInstaller(QWidget):
    """
    Instalador de requisitos do CODYN (venv + pip) e ferramentas externas:
      - Stack Python (versões escolhidas, via pip dentro do venv)
      - CUDA Toolkit (sistema, via apt)
      - GROMACS 2024.5 com CUDA (build a partir do source, via cmake)
      - Open Babel (pip openbabel-wheel; fallback apt openbabel)
      - gmx_MMPBSA (pip + deps sistema openmpi; clone e pip install .)
      - Atalho (.desktop): apenas um checkbox para criar/atualizar o lançador padrão
    """
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    enable_install_signal = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CODYN – Install Requirements")
        self.setMinimumWidth(820)

        self.paths = venv_paths("CODYN")
        self.project_root = Path(self.paths["project_root"])
        self.codyn_py = str(self.project_root / "CODYN.py")
        self.default_icon = str(self.project_root / "ICONS" / "LOGO_CODYN.png")
        self.desktop_dir = Path.home() / ".local" / "share" / "applications"
        self.desktop_file = self.desktop_dir / "CODYN.desktop"

        layout_mr = QVBoxLayout()
        layout_mr.addWidget(QLabel(
            "Selected items will be installed into the CODYN Python environment (~/.venv/CODYN) "
            "or system-wide when required. This installer prefers pip into the venv; when not available, it uses apt (requires sudo)."
        ))

        # -------- Stack Python (versões editáveis) --------
        self.pyqt5_version       = "5.15.10"
        self.psutil_version      = "5.9.8"
        self.numpy_version       = "1.26.4"
        self.pandas_version      = "2.1.4"
        self.matplotlib_version  = "3.8.4"
        self.scipy_version       = "1.13.1"

        # Opcionais comuns
        self.mdanalysis_version  = "2.6.1"
        self.mdtraj_version      = "1.9.9"
        self.seaborn_version     = "0.13.2"
        self.joblib_version      = "1.3.2"

        # NOVO: RDKit (via rdkit-pypi)
        self.rdkit_version       = "2022.9.5"

        # Grid de seleção
        grid_widget = QWidget(); gL = QGridLayout(grid_widget); gL.setContentsMargins(0,0,0,0)

        # Venv
        self.check_venv = QCheckBox("Create/repair CODYN Python environment (venv at ~/.venv/CODYN)")
        self.ed_python_info = QLineEdit(f"Using: {self.paths['python']}")
        self.ed_python_info.setReadOnly(True)
        gL.addWidget(self.check_venv, 0, 0, 1, 1); gL.addWidget(self.ed_python_info, 0, 1, 1, 1)

        r = 1
        # Base stack
        self.check_pyqt5 = QCheckBox("Install PyQt5"); self.ed_pyqt5 = QLineEdit(self.pyqt5_version)
        gL.addWidget(self.check_pyqt5, r, 0); gL.addWidget(self.ed_pyqt5, r, 1); r += 1

        self.check_psutil = QCheckBox("Install psutil"); self.ed_psutil = QLineEdit(self.psutil_version)
        gL.addWidget(self.check_psutil, r, 0); gL.addWidget(self.ed_psutil, r, 1); r += 1

        self.check_numpy = QCheckBox("Install numpy"); self.ed_numpy = QLineEdit(self.numpy_version)
        gL.addWidget(self.check_numpy, r, 0); gL.addWidget(self.ed_numpy, r, 1); r += 1

        self.check_pandas = QCheckBox("Install pandas"); self.ed_pandas = QLineEdit(self.pandas_version)
        gL.addWidget(self.check_pandas, r, 0); gL.addWidget(self.ed_pandas, r, 1); r += 1

        self.check_matplotlib = QCheckBox("Install matplotlib"); self.ed_matplotlib = QLineEdit(self.matplotlib_version)
        gL.addWidget(self.check_matplotlib, r, 0); gL.addWidget(self.ed_matplotlib, r, 1); r += 1

        self.check_scipy = QCheckBox("Install scipy"); self.ed_scipy = QLineEdit(self.scipy_version)
        gL.addWidget(self.check_scipy, r, 0); gL.addWidget(self.ed_scipy, r, 1); r += 1

        # Opcionais úteis em dinâmica molecular
        self.check_mdanalysis = QCheckBox("Install MDAnalysis"); self.ed_mdanalysis = QLineEdit(self.mdanalysis_version)
        gL.addWidget(self.check_mdanalysis, r, 0); gL.addWidget(self.ed_mdanalysis, r, 1); r += 1

        self.check_mdtraj = QCheckBox("Install MDTraj"); self.ed_mdtraj = QLineEdit(self.mdtraj_version)
        gL.addWidget(self.check_mdtraj, r, 0); gL.addWidget(self.ed_mdtraj, r, 1); r += 1

        self.check_seaborn = QCheckBox("Install seaborn"); self.ed_seaborn = QLineEdit(self.seaborn_version)
        gL.addWidget(self.check_seaborn, r, 0); gL.addWidget(self.ed_seaborn, r, 1); r += 1

        self.check_joblib = QCheckBox("Install joblib"); self.ed_joblib = QLineEdit(self.joblib_version)
        gL.addWidget(self.check_joblib, r, 0); gL.addWidget(self.ed_joblib, r, 1); r += 1

        # NOVO: RDKit (rdkit-pypi)
        self.check_rdkit = QCheckBox("Install RDKit (rdkit-pypi)")
        self.ed_rdkit = QLineEdit(self.rdkit_version)
        gL.addWidget(self.check_rdkit, r, 0); gL.addWidget(self.ed_rdkit, r, 1); r += 1

        gL.setColumnStretch(0, 2); gL.setColumnStretch(1, 1)
        layout_mr.addWidget(grid_widget)

        # -------- Extras de sistema/projetos externos --------
        layout_mr.addWidget(QLabel("System/External Tools"))

        self.check_cuda = QCheckBox("Install CUDA Toolkit (system via apt if needed)")
        layout_mr.addWidget(self.check_cuda)

        self.check_gromacs = QCheckBox("Install GROMACS 2024.5 (CUDA build, system-wide)")
        layout_mr.addWidget(self.check_gromacs)

        self.check_openbabel = QCheckBox("Install OpenBabel (pip openbabel-wheel → fallback apt)")
        layout_mr.addWidget(self.check_openbabel)

        self.check_gmxmmpbsa = QCheckBox("Install gmx_MMPBSA (pip + openmpi via apt)")
        layout_mr.addWidget(self.check_gmxmmpbsa)

        # -------- Launcher (.desktop) — SIMPLES --------
        self.check_launcher = QCheckBox("Install the CODYN shortcut in the menu")
        layout_mr.addWidget(self.check_launcher)

        # Barra de progresso e log
        self.progress = QProgressBar(); self.progress.setValue(0)
        layout_mr.addWidget(self.progress)
        self.log = QTextEdit(); self.log.setReadOnly(True)
        layout_mr.addWidget(self.log)

        # Botões
        btns = QHBoxLayout()
        self.btn_install = QPushButton("Install Selected"); self.btn_install.clicked.connect(self.start_installation)
        btns.addWidget(self.btn_install)
        self.btn_close = QPushButton("Close"); self.btn_close.clicked.connect(self.close)
        btns.addWidget(self.btn_close)
        layout_mr.addLayout(btns)

        self.setLayout(layout_mr)

        # Sinais/estado
        self.thread = None
        self.log_signal.connect(self._log)
        self.progress_signal.connect(self._set_progress)
        self.enable_install_signal.connect(self._set_install_enabled)

    # ------------------------------ UI helpers ------------------------------

    def _log(self, msg: str):
        self.log.append(msg)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _set_progress(self, value: int):
        self.progress.setValue(value)

    def _set_install_enabled(self, enabled: bool):
        self.btn_install.setEnabled(enabled)

    # ------------------------------ actions ------------------------------

    def start_installation(self):
        self.btn_install.setEnabled(False)
        self.progress.setValue(0)

        # Atualiza versões
        self.pyqt5_version       = self._text(self.pyqt5_version, self.pyqt5_version)
        self.psutil_version      = self._text(self.psutil_version, self.psutil_version)
        self.numpy_version       = self._text(self.numpy_version, self.numpy_version)
        self.pandas_version      = self._text(self.pandas_version, self.pandas_version)
        self.matplotlib_version  = self._text(self.matplotlib_version, self.matplotlib_version)
        self.scipy_version       = self._text(self.scipy_version, self.scipy_version)

        self.mdanalysis_version  = self._text(self.mdanalysis_version, self.mdanalysis_version)
        self.mdtraj_version      = self._text(self.mdtraj_version, self.mdtraj_version)
        self.seaborn_version     = self._text(self.seaborn_version, self.seaborn_version)
        self.joblib_version      = self._text(self.joblib_version, self.joblib_version)

        self.rdkit_version       = self._text(self.rdkit_version, self.rdkit_version)

        steps = sum([
            self.check_venv.isChecked(),
            self.check_pyqt5.isChecked(),
            self.check_psutil.isChecked(),
            self.check_numpy.isChecked(),
            self.check_pandas.isChecked(),
            self.check_matplotlib.isChecked(),
            self.check_scipy.isChecked(),
            self.check_mdanalysis.isChecked(),
            self.check_mdtraj.isChecked(),
            self.check_seaborn.isChecked(),
            self.check_joblib.isChecked(),
            self.check_rdkit.isChecked(),
            self.check_cuda.isChecked(),
            self.check_gromacs.isChecked(),
            self.check_openbabel.isChecked(),
            self.check_gmxmmpbsa.isChecked(),
            self.check_launcher.isChecked(),
        ])
        if steps == 0:
            QMessageBox.information(self, "No Selection", "Please select at least one action.")
            self.btn_install.setEnabled(True)
            return

        self.progress.setMaximum(steps)
        self.log.clear()

        self.thread = threading.Thread(target=self._run_selected, daemon=True)
        self.thread.start()

    def _text(self, value: str, default: str) -> str:
        v = (value or "").strip()
        return v or default

    def _run_selected(self):
        step = 0
        try:
            # 1) venv
            if self.check_venv.isChecked():
                self.log_signal.emit("Ensuring Python venv at ~/.venv/CODYN ...\n")
                p = ensure_venv("CODYN")
                self.log_signal.emit(f"Using Python: {p['python']}\n")
                step += 1; self.progress_signal.emit(step)
            else:
                p = ensure_venv("CODYN")  # sempre garante o venv

            pybin = p["python"]

            # 2) Stack Python (pip no venv)
            if self.check_pyqt5.isChecked():
                if not self.install_pkg(pybin, f"PyQt5=={self.pyqt5_version}"): return self._abort("PyQt5")
                step += 1; self.progress_signal.emit(step)
            if self.check_psutil.isChecked():
                if not self.install_pkg(pybin, f"psutil=={self.psutil_version}"): return self._abort("psutil")
                step += 1; self.progress_signal.emit(step)
            if self.check_numpy.isChecked():
                if not self.install_pkg(pybin, f"numpy=={self.numpy_version}"): return self._abort("numpy")
                step += 1; self.progress_signal.emit(step)
            if self.check_pandas.isChecked():
                if not self.install_pkg(pybin, f"pandas=={self.pandas_version}"): return self._abort("pandas")
                step += 1; self.progress_signal.emit(step)
            if self.check_matplotlib.isChecked():
                if not self.install_pkg(pybin, f"matplotlib=={self.matplotlib_version}"): return self._abort("matplotlib")
                step += 1; self.progress_signal.emit(step)
            if self.check_scipy.isChecked():
                if not self.install_pkg(pybin, f"scipy=={self.scipy_version}"): return self._abort("scipy")
                step += 1; self.progress_signal.emit(step)

            if self.check_mdanalysis.isChecked():
                if not self.install_pkg(pybin, f"MDAnalysis=={self.mdanalysis_version}"): return self._abort("MDAnalysis")
                step += 1; self.progress_signal.emit(step)
            if self.check_mdtraj.isChecked():
                if not self.install_pkg(pybin, f"mdtraj=={self.mdtraj_version}"): return self._abort("MDTraj")
                step += 1; self.progress_signal.emit(step)
            if self.check_seaborn.isChecked():
                if not self.install_pkg(pybin, f"seaborn=={self.seaborn_version}"): return self._abort("seaborn")
                step += 1; self.progress_signal.emit(step)
            if self.check_joblib.isChecked():
                if not self.install_pkg(pybin, f"joblib=={self.joblib_version}"): return self._abort("joblib")
                step += 1; self.progress_signal.emit(step)

            # NOVO: RDKit
            if self.check_rdkit.isChecked():
                if not self.install_pkg(pybin, f"rdkit-pypi=={self.rdkit_version}"): return self._abort("RDKit")
                step += 1; self.progress_signal.emit(step)

            # 3) Sistema/externos
            if self.check_cuda.isChecked():
                if not self.install_cuda_toolkit(): return self._abort("CUDA Toolkit")
                step += 1; self.progress_signal.emit(step)

            if self.check_gromacs.isChecked():
                if not self.install_gromacs(): return self._abort("GROMACS")
                step += 1; self.progress_signal.emit(step)

            if self.check_openbabel.isChecked():
                if not self.install_openbabel(pybin): return self._abort("OpenBabel")
                step += 1; self.progress_signal.emit(step)

            if self.check_gmxmmpbsa.isChecked():
                if not self.install_gmxmmpbsa(pybin): return self._abort("gmx_MMPBSA")
                step += 1; self.progress_signal.emit(step)

            # 4) Launcher (simples)
            if self.check_launcher.isChecked():
                ok, msg = self._create_or_update_launcher_simple()
                self.log_signal.emit(msg + "\n")
                if not ok: return self._abort("Launcher")
                step += 1; self.progress_signal.emit(step)

            self.log_signal.emit("\nAll selected actions completed!\n")
        finally:
            self.enable_install_signal.emit(True)

    # ------------------------------ installers (pip) ------------------------------

    def install_pkg(self, pybin: str, spec: str) -> bool:
        res = _pip_install(pybin, [spec])
        if res.returncode != 0:
            self.log_signal.emit(res.stdout + "\n")
            return False
        self.log_signal.emit(f"{spec} installed.\n")
        return True

    # ------------------------------ installers (system/external) -------------------

    def install_cuda_toolkit(self) -> bool:
        """Instala CUDA Toolkit (se nvcc ausente) via apt; se já houver CUDA, informa."""
        try:
            if _which("nvcc"):
                self.log_signal.emit("CUDA Toolkit already present (nvcc found).\n")
                return True
            self.log_signal.emit("Installing CUDA Toolkit via apt (requires sudo)...\n")
            ok = _apt_install(["nvidia-cuda-toolkit"])
            if not ok:
                self.log_signal.emit("Failed to install CUDA via apt.\n")
                return False
            if not _which("nvcc"):
                self.log_signal.emit("CUDA installed but 'nvcc' not found in PATH; check your system configuration.\n")
            else:
                self.log_signal.emit("CUDA Toolkit installed (apt).\n")
            return True
        except Exception as e:
            self.log_signal.emit(f"CUDA Toolkit installation failed: {e}\n")
            return False

    def install_gromacs(self) -> bool:
        """
        Compila e instala GROMACS 2024.5 com CUDA quando disponível.
        Requer: build-essential, cmake, FFTW, OpenMPI, GSL.
        """
        try:
            # Dependências de build
            self.log_signal.emit("Installing build dependencies (requires sudo)...\n")
            ok = _apt_install([
                "build-essential", "git", "wget", "cmake", "libfftw3-dev",
                "libopenmpi-dev", "openmpi-bin", "libgsl0-dev"
            ])
            if not ok:
                self.log_signal.emit("Failed to install build dependencies.\n")
                return False

            have_nvcc = _which("nvcc") is not None

            # Baixar e compilar
            gmx_url = "https://ftp.gromacs.org/gromacs/gromacs-2024.5.tar.gz"
            workdir = "/tmp/gromacs_build"
            os.makedirs(workdir, exist_ok=True)
            tarfile = os.path.join(workdir, "gromacs-2024.5.tar.gz")

            if not os.path.exists(tarfile):
                self.log_signal.emit("Downloading GROMACS 2024.5 source ...\n")
                urllib.request.urlretrieve(gmx_url, tarfile)

            os.system(f"tar -xzf {tarfile} -C {workdir}")
            src_dir = os.path.join(workdir, "gromacs-2024.5")
            build_dir = os.path.join(src_dir, "build")
            os.makedirs(build_dir, exist_ok=True)

            gpu_flag = "-DGMX_GPU=CUDA" if have_nvcc else "-DGMX_GPU=OFF"
            simd_flag = "-DGMX_SIMD=AVX2_256"
            opts = [
                "-DGMX_BUILD_OWN_FFTW=ON",
                "-DREGRESSIONTEST_DOWNLOAD=ON",
                simd_flag,
                "-DGMX_THREAD_MPI=ON",
                "-DGMX_OPENMP=ON",
                "-DGMX_OPENMP_MAX_THREADS=64",
                "-DGMX_USE_RDTSCP=ON",
                gpu_flag
            ]
            cmake_cmd = f"cd {build_dir} && cmake .. " + " ".join(opts)
            self.log_signal.emit(f"Configuring with: {gpu_flag}\n")
            if os.system(cmake_cmd) != 0:
                self.log_signal.emit("CMake configuration failed.\n")
                return False

            self.log_signal.emit("Building GROMACS (make -j)... this may take a while.\n")
            if os.system(f"cd {build_dir} && make -j$(nproc)") != 0:
                self.log_signal.emit("Make failed.\n")
                return False

            self.log_signal.emit("Installing GROMACS (sudo make install)...\n")
            if os.system(f"cd {build_dir} && sudo make install") != 0:
                self.log_signal.emit("sudo make install failed.\n")
                return False

            # Config no bashrc
            bashrc = os.path.join(os.path.expanduser("~"), ".bashrc")
            with open(bashrc, "a", encoding="utf-8") as f:
                f.write("\n# GROMACS setup\n")
                f.write("source /usr/local/gromacs/bin/GMXRC\n")
                f.write('alias gmx="/usr/local/gromacs/bin/gmx"\n')
            self.log_signal.emit("GROMACS installed and configured in .bashrc.\n")
            return True

        except Exception as e:
            self.log_signal.emit(f"GROMACS installation failed: {e}\n")
            return False

    def install_openbabel(self, pybin: str) -> bool:
        """
        Instala Open Babel:
          1) tenta 'pip install openbabel-wheel' (wheels pré-compilados)
          2) fallback: 'sudo apt install openbabel'
        """
        self.log_signal.emit("Trying pip install 'openbabel-wheel'...\n")
        res = _pip_install(pybin, ["openbabel-wheel"])
        if res.returncode == 0:
            self.log_signal.emit("OpenBabel installed via pip (openbabel-wheel).\n")
            return True

        self.log_signal.emit("pip wheel not available for this platform. Trying apt (requires sudo)...\n")
        ok = _apt_install(["openbabel"])
        if not ok:
            self.log_signal.emit("Failed to install OpenBabel via apt.\n")
            return False
        self.log_signal.emit("OpenBabel installed via apt.\n")
        return True

    def install_gmxmmpbsa(self, pybin: str) -> bool:
        """
        Instala gmx_MMPBSA:
          - deps Python no venv: numpy, scipy, matplotlib, pandas, seaborn, tqdm, PyYAML, Cython
          - MPI: instala openmpi (apt) e mpi4py (pip)
          - clona repositório e 'pip install .'
        """
        try:
            self.log_signal.emit("Ensuring basic Python deps for gmx_MMPBSA...\n")
            base = ["numpy", "scipy", "matplotlib", "pandas", "seaborn", "tqdm", "PyYAML", "Cython"]
            res = _pip_install(pybin, base)
            if res.returncode != 0:
                self.log_signal.emit(res.stdout + "\n")
                return False

            self.log_signal.emit("Ensuring MPI (openmpi via apt) ...\n")
            ok = _apt_install(["openmpi-bin", "libopenmpi-dev"])
            if not ok:
                self.log_signal.emit("Failed to install OpenMPI via apt.\n")
                return False

            self.log_signal.emit("Installing mpi4py in the CODYN venv...\n")
            res = _pip_install(pybin, ["mpi4py"])
            if res.returncode != 0:
                self.log_signal.emit(res.stdout + "\n")
                return False

            workdir = os.path.join(str(Path.home()), "gmx_MMPBSA_install")
            os.makedirs(workdir, exist_ok=True)
            repo_dir = os.path.join(workdir, "gmx_MMPBSA")

            if not os.path.exists(repo_dir):
                self.log_signal.emit("Cloning gmx_MMPBSA repository...\n")
                if os.system(f"git clone https://github.com/Valdes-Tresanco-MS/gmx_MMPBSA.git {repo_dir}") != 0:
                    self.log_signal.emit("git clone failed.\n")
                    return False

            self.log_signal.emit("Installing gmx_MMPBSA into the CODYN venv (pip install .)...\n")
            if os.system(f"cd {repo_dir} && '{pybin}' -m pip install .") != 0:
                self.log_signal.emit("pip install . failed for gmx_MMPBSA.\n")
                return False

            self.log_signal.emit("gmx_MMPBSA installed in the CODYN venv.\n")
            self.log_signal.emit(
                "NOTE: Some gmx_MMPBSA workflows may require AmberTools for certain energy terms. "
                "If needed, we can add a separate installer to build AmberTools from source (no conda)."
            )
            return True

        except Exception as e:
            self.log_signal.emit(f"gmx_MMPBSA installation failed: {e}\n")
            return False

    # ------------------------------ launcher (simples) -------------------------------

    def _create_or_update_launcher_simple(self) -> Tuple[bool, str]:
        """
        Cria/atualiza ~/.local/share/applications/CODYN.desktop com valores padrão.
        """
        try:
            self.desktop_dir.mkdir(parents=True, exist_ok=True)
            exec_cmd = f"bash -i -c \"env PYTHONNOUSERSITE=1 '{self.paths['python']}' '{self.codyn_py}'\""
            content = (
                "[Desktop Entry]\n"
                "Version=2025.1\n"
                "Name=CODYN\n"
                "Comment=AUTOMATIZED MOLECULAR DYNAMICS TOOL\n"
                f"Exec={exec_cmd}\n"
                f"Icon={self.default_icon}\n"
                "Terminal=true\n"
                "Type=Application\n"
                "Categories=Qt;Science;Chemistry;Physics;Education;\n"
                "StartupNotify=false\n"
                "MimeType=chemical/x-cml;chemical/x-xyz;\n"
            )
            self.desktop_file.write_text(content, encoding="utf-8")
            os.chmod(self.desktop_file, 0o755)
            try:
                _run(["update-desktop-database"])
            except Exception:
                pass
            return True, f"Launcher created/updated at: {self.desktop_file}"
        except Exception as e:
            return False, f"Failed to create/update launcher:\n{e}"

    # ------------------------------ misc ------------------------------

    def _abort(self, name: str):
        self.log_signal.emit(f"Aborted on {name}.\n")

# Execução direta para teste manual
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = RequirementsInstaller()
    w.show()
    sys.exit(app.exec_())
