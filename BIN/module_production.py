import glob
import os
import re
import json
import subprocess
import shutil
from datetime import datetime
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QWidget, QTextEdit

from PyQt5.QtCore import QThread, pyqtSignal
import subprocess

class MD_Thread(QThread):
    log_md_signal = pyqtSignal(str)
    log_progress_step_signal = pyqtSignal(int)
    log_progress_stepmax_signal = pyqtSignal(int)
    log_progress_time_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool)

    def __init__(self, gmx, run_folder, n_threads, t_ns_md, t_int):
        super().__init__()
        self.gmx = gmx
        self.run_folder = run_folder
        self.n_threads = n_threads
        self.t_ns_md = t_ns_md
        self.t_int = t_int

    def run(self):
        t_fs_md = int(1_000_000 * self.t_ns_md)
        n_steps = int(t_fs_md / self.t_int)
        self.log_progress_stepmax_signal.emit(n_steps)  # Emitindo o valor máximo para a barra de progresso dos steps
        # MD Production
        try:
            # Monta e roda o grompp para MD Production
            self.log_md_signal.emit("Running GROMPP for MD Production...")
            result = subprocess.run(
                f"{self.gmx} grompp -f md.mdp -c npt.gro -t npt.cpt -p topol.top -n index.ndx -o md_0_'{self.t_ns_md}'.tpr",
                shell=True, cwd=self.run_folder, capture_output=True, text=True
            )
            if result.stdout:
                self.log_md_signal.emit(result.stdout.strip())
            if result.stderr:
                self.log_md_signal.emit("Erro: " + result.stderr.strip())

            # Roda MD Production (mdrun):
            self.log_md_signal.emit(f"Running MD Production in {self.t_ns_md} ns ... Wait!")
            process = subprocess.Popen(
                f"{self.gmx} mdrun -deffnm md_0_{self.t_ns_md} -ntmpi 1 -ntomp '{self.n_threads}' -nb gpu -bonded gpu -pme gpu -pmefft gpu -update gpu -v",
                shell=True, cwd=self.run_folder,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            for line in process.stdout:
                # self.log_md_signal.emit(line.rstrip()) # Exibe no status_prot
                # Atualiza barra de progresso dos steps
                m_step = re.search(r"step\s+(\d+)", line)
                if m_step:
                    step = int(m_step.group(1))
                    self.log_progress_step_signal.emit(step)
                # Atualiza barra de progresso do tempo restante
                m_time = re.search(r"remaining wall clock time:\s+(\d+)\s", line, re.IGNORECASE)
                if m_time:
                    time_remaining = int(m_time.group(1))
                    self.log_progress_time_signal.emit(time_remaining)
            process.wait()
            # Remove PBC (Periodic Boundary Conditions) from the trajectory
            self.log_md_signal.emit("Removing PBC from trajectory...")
            result = subprocess.run(
                f"{self.gmx} trjconv -s md_0_{self.t_ns_md}.tpr -f md_0_{self.t_ns_md}.xtc -o md_0_{self.t_ns_md}_noPBC.xtc -pbc mol -center",
                shell=True, cwd=self.run_folder, capture_output=True, text=True, input="1\n0\n"
            )
            if result.stdout:
                self.log_md_signal.emit(result.stdout.strip())            
            if result.stderr:
                self.log_md_signal.emit("Erro: " + result.stderr.strip())                
            self.finished_signal.emit(True)
            
        except Exception as e:
            self.log_md_signal.emit(f"Error during MD Production: {e}")
            self.finished_signal.emit(False)


class PrepMD(QWidget):
    log_md_signal = pyqtSignal(str)
    log_progress_step_signal = pyqtSignal(int)
    log_progress_stepmax_signal = pyqtSignal(int)
    log_progress_time_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool)
    def __init__(self, codyn_dir: str, config_data: dict, run_folder: str):
        super().__init__()
        self.codyn_dir = codyn_dir
        self.config_data = config_data
        self.run_folder = run_folder

    def log(self, message: str):
        """Adiciona mensagem no status_prot com timestamp e faz auto-scroll."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_md_signal.emit(f"[{ts}] {message}")

    def on_MD_finished(self, success):
        if success:
            self.log("Molecular Dynamics Finished Successfully!")

    def start_production(self, nome_proteina: str, nome_ligante: str):
        try:
            self.log(f"\n####### MD PRODUCTION START {nome_proteina} {nome_ligante} #######")

            # Carregar dados de configuração
            self.config_data = os.path.join(self.codyn_dir, ".form_data.json")
            with open(self.config_data, 'r') as f:
                self.config = json.load(f)
                self.t_ns_md = float(self.config["production_time_ns"])
                self.n_threads = int(self.config["n_threads"])
                self.t_int = float(self.config["integration_time_fs"])
            self.log(f"Using {self.n_threads} Threads in CPU for production")

            # GROMACS preprocessing commands
            gmx = "/usr/local/gromacs/bin/gmx"  

            # MD Production:
            self.log("Starting MD Production...")
            try:
                # Criando a thread de minimização
                self.MD_Thread = MD_Thread(gmx, self.run_folder, self.n_threads, self.t_ns_md, self.t_int)
                self.MD_Thread.log_progress_step_signal.connect(self.log_progress_step_signal.emit)
                self.MD_Thread.log_progress_stepmax_signal.connect(self.log_progress_stepmax_signal.emit)
                self.MD_Thread.log_progress_time_signal.connect(self.log_progress_time_signal.emit)
                self.MD_Thread.log_md_signal.connect(self.log)
                self.MD_Thread.finished_signal.connect(self.on_MD_finished)
                self.MD_Thread.start()

            except Exception as e:
                self.log(f"Error during {nome_ligante} MD Production: {e}")

        except Exception as e:
            self.log(f"Error during MD Production: {e}")
