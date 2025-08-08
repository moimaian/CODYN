import os
import sys
import subprocess
import shutil
import urllib.request
import threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox, QPushButton,
    QTextEdit, QApplication, QHBoxLayout, QMessageBox, QProgressBar
)
from PyQt5.QtCore import Qt

class RequirementsInstaller(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install Requirements")
        self.setMinimumWidth(540)
        layout = QVBoxLayout()

        label = QLabel("Select requirements to install:")
        layout.addWidget(label)

        self.check_conda = QCheckBox("Create Conda environment (AmberTools21)")
        self.check_cuda = QCheckBox("Install CUDA Toolkit (for GPU support)")
        self.check_gromacs = QCheckBox("Install GROMACS 2024.5 (with CUDA GPU and all options)")
        self.check_openbabel = QCheckBox("Install OpenBabel (latest stable)")
        self.check_gmxmmpbsa = QCheckBox("Install gmx_MMPBSA (with dependencies)")
        layout.addWidget(self.check_conda)
        layout.addWidget(self.check_cuda)
        layout.addWidget(self.check_gromacs)
        layout.addWidget(self.check_openbabel)
        layout.addWidget(self.check_gmxmmpbsa)

        # Progress & log
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        btns = QHBoxLayout()
        self.btn_install = QPushButton("Install Selected")
        self.btn_install.clicked.connect(self.start_installation)
        btns.addWidget(self.btn_install)
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)

        self.setLayout(layout)
        self.thread = None

    def start_installation(self):
        self.btn_install.setEnabled(False)
        self.progress.setValue(0)
        steps = sum([
            self.check_conda.isChecked(),
            self.check_cuda.isChecked(),
            self.check_gromacs.isChecked(),
            self.check_openbabel.isChecked(),
            self.check_gmxmmpbsa.isChecked()
        ])
        if steps == 0:
            QMessageBox.information(self, "No Selection", "Please select at least one requirement.")
            self.btn_install.setEnabled(True)
            return
        self.progress.setMaximum(steps)
        self.log.clear()
        self.thread = threading.Thread(target=self._install_selected, daemon=True)
        self.thread.start()

    def _install_selected(self):
        step = 0
        if self.check_conda.isChecked():
            self._log("Installing Miniconda3 & AmberTools21 environment...\n")
            success = self.install_conda_env()
            step += 1
            self.progress.setValue(step)
            if not success:
                self._log("Aborted on Conda install failure.\n")
                self.btn_install.setEnabled(True)
                return
        if self.check_cuda.isChecked():
            self._log("Installing CUDA Toolkit ...\n")
            success = self.install_cuda_toolkit()
            step += 1
            self.progress.setValue(step)
            if not success:
                self._log("Aborted on CUDA install failure.\n")
                self.btn_install.setEnabled(True)
                return
        if self.check_gromacs.isChecked():
            self._log("Installing GROMACS 2024.5 ...\n")
            success = self.install_gromacs()
            step += 1
            self.progress.setValue(step)
            if not success:
                self._log("Aborted on GROMACS install failure.\n")
                self.btn_install.setEnabled(True)
                return
        if self.check_openbabel.isChecked():
            self._log("Installing OpenBabel ...\n")
            success = self.install_openbabel()
            step += 1
            self.progress.setValue(step)
            if not success:
                self._log("Aborted on OpenBabel install failure.\n")
                self.btn_install.setEnabled(True)
                return
        if self.check_gmxmmpbsa.isChecked():
            self._log("Installing gmx_MMPBSA ...\n")
            success = self.install_gmxmmpbsa()
            step += 1
            self.progress.setValue(step)
            if not success:
                self._log("Aborted on gmx_MMPBSA install failure.\n")
                self.btn_install.setEnabled(True)
                return
        self._log("\nAll selected requirements installed!\n")
        self.btn_install.setEnabled(True)

    def _log(self, msg):
        def append():
            self.log.append(msg)
            self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        QApplication.instance().postEvent(self.log, type('append', (QApplication,), {})())
        self.log.append(msg)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def install_conda_env(self):
        import urllib.request
        home = os.path.expanduser("~")
        conda_dir = os.path.join(home, "miniconda3")
        env_name = "AmberTools21"
        env_exists = False

        # Check if conda already installed
        conda_bin = shutil.which("conda")
        if not conda_bin:
            self._log("Miniconda3 not found. Downloading installer...")
            miniconda_url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
            miniconda_sh = os.path.join(home, "Miniconda3-latest-Linux-x86_64.sh")
            try:
                urllib.request.urlretrieve(miniconda_url, miniconda_sh)
                os.chmod(miniconda_sh, 0o755)
                self._log(f"Running installer: {miniconda_sh} ... (may prompt for input)\n")
                ret = os.system(f"bash {miniconda_sh} -b -p {conda_dir}")
                if ret != 0:
                    self._log("Miniconda installation failed.")
                    return False
                self._log("Miniconda installed successfully.\n")
                os.environ["PATH"] = f"{conda_dir}/bin:" + os.environ["PATH"]
            except Exception as e:
                self._log(f"Failed to download/install Miniconda: {e}")
                return False
        else:
            self._log("Conda already installed. Using existing installation.\n")
            conda_dir = os.path.dirname(os.path.dirname(conda_bin))

        # Create/activate AmberTools21 environment
        try:
            out = subprocess.check_output([f"{conda_dir}/bin/conda", "env", "list"]).decode()
            if env_name in out:
                self._log("AmberTools21 environment already exists. Skipping creation.\n")
                env_exists = True
            if not env_exists:
                # Instala AmberTools21 e Python 3.11
                ret = os.system(
                    f'"{conda_dir}/bin/conda" create -y -n {env_name} -c conda-forge python=3.11 ambertools'
                )
                if ret != 0:
                    self._log("Failed to create AmberTools21 environment.")
                    return False
                self._log("AmberTools21 environment created!\n")
        except Exception as e:
            self._log(f"Error checking/creating environment: {e}")
            return False
        return True

    def install_cuda_toolkit(self):
        # Instala o CUDA Toolkit via conda ou apt
        try:
            conda_bin = shutil.which("conda")
            if conda_bin:
                self._log("Installing CUDA Toolkit via conda (nvidia channel)...")
                ret = os.system(f"{conda_bin} install -y -c nvidia cuda-toolkit")
                if ret != 0:
                    self._log("Failed to install CUDA Toolkit via conda.")
                    return False
                self._log("CUDA Toolkit installed (conda).\n")
                return True
            else:
                self._log("Installing CUDA Toolkit via apt (requires sudo)...")
                ret = os.system("sudo apt-get update && sudo apt-get install -y nvidia-cuda-toolkit")
                if ret != 0:
                    self._log("Failed to install CUDA Toolkit via apt.")
                    return False
                self._log("CUDA Toolkit installed (apt).\n")
                return True
        except Exception as e:
            self._log(f"CUDA Toolkit installation failed: {e}")
            return False

    def install_gromacs(self):
        # Verifica se o cmake já está instalado, senão instala
        try:
            cmake_bin = shutil.which("cmake")
            if not cmake_bin:
                self._log("CMake not found. Installing via apt (requires sudo)...")
                ret = os.system("sudo apt-get update && sudo apt-get install -y cmake")
                if ret != 0:
                    self._log("Failed to install CMake.")
                    return False
                self._log("CMake installed successfully.\n")
            else:
                self._log("CMake already installed.\n")
        except Exception as e:
            self._log(f"Error checking/installing CMake: {e}")
            return False
        # Instala dependências básicas para compilação
        try:
            self._log("Installing build-essential, git, wget, OpenMP, and MPI dependencies...")
            ret = os.system("sudo apt-get install -y build-essential git wget libfftw3-dev libopenmpi-dev openmpi-bin libgsl0-dev")
            if ret != 0:
                self._log("Failed to install build dependencies.")
                return False
        except Exception as e:
            self._log(f"Error installing dependencies: {e}")
            return False
        try:
            gmx_url = "https://ftp.gromacs.org/gromacs/gromacs-2024.5.tar.gz"
            workdir = "/tmp/gromacs_build"
            os.makedirs(workdir, exist_ok=True)
            tarfile = os.path.join(workdir, "gromacs-2024.5.tar.gz")
            self._log("Downloading GROMACS 2024.5 source ...")
            urllib.request.urlretrieve(gmx_url, tarfile)
            os.system(f"tar -xzf {tarfile} -C {workdir}")
            build_dir = os.path.join(workdir, "gromacs-2024.5", "build")
            os.makedirs(build_dir, exist_ok=True)
            # Compilando com as flags solicitadas
            self._log("Configuring GROMACS with CUDA and custom flags...")
            cmake_cmd = (
                f"cd {build_dir} && "
                f"cmake .. "
                f"-DGMX_BUILD_OWN_FFTW=ON "
                f"-DREGRESSIONTEST_DOWNLOAD=ON "
                f"-DGMX_GPU=CUDA "
                f"-DGMX_SIMD=AVX2_256 "
                f"-DGMX_THREAD_MPI=ON "
                f"-DGMX_OPENMP=ON "
                f"-DGMX_OPENMP_MAX_THREADS=64 "
                f"-DGMX_USE_RDTSCP=ON"
            )
            if os.system(cmake_cmd) != 0:
                self._log("CMake configuration failed.")
                return False
            self._log("Building GROMACS (make)... This may take a while.")
            if os.system(f"cd {build_dir} && make -j$(nproc)") != 0:
                self._log("Make failed.")
                return False
            self._log("Running make check (tests)...")
            if os.system(f"cd {build_dir} && make check") != 0:
                self._log("make check reported errors (some may be expected, check log for details).")
                # Não aborta na checagem
            self._log("Installing GROMACS (sudo make install)...")
            if os.system(f"cd {build_dir} && sudo make install") != 0:
                self._log("sudo make install failed.")
                return False
            # Adiciona ao .bashrc
            bashrc = os.path.join(os.path.expanduser("~"), ".bashrc")
            with open(bashrc, "a") as f:
                f.write("\n# GROMACS setup\n")
                f.write("source /usr/local/gromacs/bin/GMXRC\n")
                f.write('alias gmx="/usr/local/gromacs/bin/gmx"\n')
            self._log("GROMACS installed and configured in .bashrc.\n")
            # Executa source GMXRC para ativar no ambiente atual
            os.system("source /usr/local/gromacs/bin/GMXRC")
            return True
        except Exception as e:
            self._log(f"GROMACS installation failed: {e}")
            return False

    def install_openbabel(self):
        # Instala o OpenBabel via conda ou apt
        try:
            conda_bin = shutil.which("conda")
            if conda_bin:
                self._log("Installing OpenBabel via conda...")
                ret = os.system(f"{conda_bin} install -y -c conda-forge openbabel")
                if ret != 0:
                    self._log("Failed to install OpenBabel via conda.")
                    return False
                self._log("OpenBabel installed (conda).\n")
                return True
            else:
                self._log("Installing OpenBabel via apt (requires sudo)...")
                ret = os.system("sudo apt-get update && sudo apt-get install -y openbabel")
                if ret != 0:
                    self._log("Failed to install OpenBabel via apt.")
                    return False
                self._log("OpenBabel installed (apt).\n")
                return True
        except Exception as e:
            self._log(f"OpenBabel installation failed: {e}")
            return False

    def install_gmxmmpbsa(self):
        # Instala dependências, AmberTools21, ParmEd, pip, depois baixa e instala o gmx_MMPBSA
        try:
            home = os.path.expanduser("~")
            workdir = os.path.join(home, "gmx_MMPBSA_install")
            os.makedirs(workdir, exist_ok=True)
            # Instalar dependências se necessário
            self._log("Installing Python requirements: numpy, scipy, matplotlib, pandas, seaborn, tqdm, PyYAML, Cython, mpi4py ...")
            # Instalar dependências dentro do AmberTools21
            python_amber = os.path.join(home, "miniconda3", "envs", "AmberTools21", "bin", "python")
            pip_amber = os.path.join(home, "miniconda3", "envs", "AmberTools21", "bin", "pip")
            os.system(f"{pip_amber} install numpy scipy matplotlib pandas seaborn tqdm PyYAML Cython mpi4py openmpi-bin libopenmpi-dev openssh-client")
            # Clonar repositório
            url = "https://github.com/Valdes-Tresanco-MS/gmx_MMPBSA.git"
            repo_dir = os.path.join(workdir, "gmx_MMPBSA")
            if not os.path.exists(repo_dir):
                self._log("Cloning gmx_MMPBSA repository...")
                if os.system(f"git clone {url} {repo_dir}") != 0:
                    self._log("git clone failed.")
                    return False
            self._log("Installing gmx_MMPBSA in AmberTools21 environment...")
            if os.system(f"cd {repo_dir} && {python_amber} setup.py install") != 0:
                self._log("setup.py install failed.")
                return False
            self._log("gmx_MMPBSA installed successfully in AmberTools21!\n")
            return True
        except Exception as e:
            self._log(f"gmx_MMPBSA installation failed: {e}")
            return False


# Para teste direto:
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = RequirementsInstaller()
    w.show()
    sys.exit(app.exec_())
