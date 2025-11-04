#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ========================= BOOTSTRAP CODYN (pip-only) =========================
# venv global por usuário: $HOME/.venv/CODYN
# - Se não existir, cria e reexecuta dentro dele.
# - Garante PyQt5 (fixo) p/ exibir UI.
# - Verifica demais pacotes/versões (fixas) e FERRAMENTAS EXTERNAS (CUDA, GROMACS, gmx_MMPBSA);
#   se faltar algo, abre o Install Requirements.

import os, sys, subprocess, importlib.util, shutil
from pathlib import Path
from typing import Optional

os.environ.setdefault("PYTHONNOUSERSITE", "1")

# Versões EXATAS (Python packages)
PINNED = {
    "numpy": "1.26.4",
    "pandas": "2.1.4",
    "matplotlib": "3.8.4",
    "scipy": "1.13.1",
    "psutil": "5.9.8",
    "rdkit": "2022.09.5",
    "PyQt5": "5.15.10",  # PyQt5 é a única instalada automaticamente aqui
}

ROOT = Path(__file__).resolve().parent
BIN_DIR = ROOT / "BIN"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BIN_DIR))

# ---- helpers gerais ----
def _which(name: str) -> Optional[str]:
    return shutil.which(name)

def _venv_paths():
    venv_dir = Path.home() / ".venv" / "CODYN"
    if os.name == "nt":
        py = venv_dir / "Scripts" / "python.exe"
        pip = venv_dir / "Scripts" / "pip.exe"
    else:
        py = venv_dir / "bin" / "python"
        pip = venv_dir / "bin" / "pip"
    return venv_dir, py, pip

def _run(cmd):
    return subprocess.run(cmd, check=True, text=True)

def _ensure_venv():
    venv_dir, vpy, vpip = _venv_paths()
    if not vpy.exists():
        venv_dir.parent.mkdir(parents=True, exist_ok=True)
        print(f"[CODYN] Criando venv em {venv_dir} ...")
        _run([sys.executable, "-m", "venv", str(venv_dir)])
        _run([str(vpy), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    return venv_dir, vpy, vpip

def _ensure_pyqt5(vpy, vpip):
    try:
        import PyQt5  # noqa
        import PyQt5.QtWidgets  # noqa
        # Força a versão exata se estiver diferente
        from PyQt5 import QtCore
        ver = getattr(QtCore, "__version__", None)
        if ver and ver != PINNED["PyQt5"]:
            print(f"[CODYN] PyQt5 versão {ver} != {PINNED['PyQt5']}. Ajustando...")
            _run([str(vpip), "install", f"PyQt5=={PINNED['PyQt5']}"])
    except Exception:
        print("[CODYN] Instalando PyQt5 (necessário para abrir a interface)...")
        _run([str(vpip), "install", f"PyQt5=={PINNED['PyQt5']}"])

def _reexec_in_venv(vpy):
    if Path(sys.executable).resolve() != Path(vpy).resolve():
        print(f"[CODYN] Reexecutando dentro do venv: {vpy}")
        env = os.environ.copy()
        env["CODYN_BOOTSTRAPPED"] = "1"
        os.execve(str(vpy), [str(vpy), __file__], env)

# ---- checagem de pacotes Python pinados ----
def _missing_or_mismatched_packages():
    missing = []
    mismatched = []
    for mod, ver in PINNED.items():
        if mod == "PyQt5":
            continue  # já tratado separadamente
        try:
            pkg = __import__(mod)
            cur = getattr(pkg, "__version__", None)
            if cur is None or cur != ver:
                mismatched.append((mod, ver, cur))
        except Exception:
            missing.append((mod, ver))
    return missing, mismatched

# ---- checagem de ferramentas externas ----
def _external_tools_status():
    """
    Retorna (missing, details) para:
      - CUDA Toolkit: precisa de 'nvcc'
      - GROMACS: precisa de 'gmx'
      - gmx_MMPBSA: import do módulo Python 'gmx_MMPBSA' OU binário 'gmx_MMPBSA'
    """
    missing = []
    details = []

    # CUDA Toolkit
    nvcc = _which("nvcc")
    if not nvcc:
        missing.append("CUDA Toolkit")
        details.append(" - CUDA Toolkit: 'nvcc' não encontrado no PATH")
    else:
        details.append(f" - CUDA Toolkit: OK ({nvcc})")

    # GROMACS
    gmx = _which("gmx")
    if not gmx:
        # tentar um caminho comum quando instalado via make install
        if Path("/usr/local/gromacs/bin/gmx").exists():
            details.append(" - GROMACS: OK (/usr/local/gromacs/bin/gmx)")
        else:
            missing.append("GROMACS")
            details.append(" - GROMACS: 'gmx' não encontrado no PATH")
    else:
        details.append(f" - GROMACS: OK ({gmx})")

    # gmx_MMPBSA
    mmpbsa_bin = _which("gmx_MMPBSA")
    mmpbsa_mod = importlib.util.find_spec("gmx_MMPBSA")
    if not (mmpbsa_bin or mmpbsa_mod):
        missing.append("gmx_MMPBSA")
        details.append(" - gmx_MMPBSA: nem módulo Python ('gmx_MMPBSA') nem binário 'gmx_MMPBSA' encontrado")
    else:
        where = mmpbsa_bin or ("module:" + str(mmpbsa_mod.origin) if mmpbsa_mod and mmpbsa_mod.origin else "module")
        details.append(f" - gmx_MMPBSA: OK ({where})")

    return missing, details

def _maybe_open_requirements_ui(message: str):
    # Garante um QApplication e abre a UI do instalador
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox
    except Exception as e:
        print("[CODYN] Falha ao importar PyQt5 para exibir UI:", e)
        sys.exit(1)

    app = QApplication.instance() or QApplication(sys.argv)
    reply = QMessageBox.information(None, "Requisitos do CODYN", message, QMessageBox.Ok)

    try:
        from module_requirements import RequirementsInstaller  # BIN/module_requirements.py
        w = RequirementsInstaller()
        w.show()
        app.exec_()
    except Exception as e:
        QMessageBox.critical(None, "Erro",
            f"Não foi possível abrir o instalador de requisitos:\n{e}\n\n"
            f"Verifique o arquivo BIN/module_requirements.py.")
        sys.exit(1)

def _bootstrap():
    # 1) Criar/entrar no venv
    if os.environ.get("CODYN_BOOTSTRAPPED") != "1":
        venv_dir, vpy, vpip = _ensure_venv()
        _reexec_in_venv(vpy)

    # 2) Já dentro do venv
    venv_dir, vpy, vpip = _venv_paths()
    _ensure_pyqt5(vpy, vpip)

    # 3) Checar pacotes Python pinados
    missing_py, mismatched_py = _missing_or_mismatched_packages()

    # 4) Checar ferramentas externas
    missing_ext, ext_details = _external_tools_status()

    if missing_py or mismatched_py or missing_ext:
        msg_lines = []

        if missing_py:
            msg_lines.append("Pacotes Python ausentes:")
            for m, v in missing_py:
                msg_lines.append(f"  - {m}=={v}")

        if mismatched_py:
            msg_lines.append("\nPacotes Python com versão diferente da requerida:")
            for m, want, cur in mismatched_py:
                msg_lines.append(f"  - {m}: instalado={cur!r}, requerido={want}")

        if missing_ext:
            msg_lines.append("\nFerramentas externas ausentes:")
            for name in missing_ext:
                msg_lines.append(f"  - {name}")

        # Detalhes de diagnóstico das externas
        if ext_details:
            msg_lines.append("\nDiagnóstico de ferramentas externas:")
            msg_lines.extend(ext_details)

        msg_lines.append("\nClique em OK para abrir o instalador de requisitos.")
        _maybe_open_requirements_ui("\n".join(msg_lines))

        # Revalida após a janela do instalador
        missing_py2, mismatched_py2 = _missing_or_mismatched_packages()
        missing_ext2, ext_details2 = _external_tools_status()

        if missing_py2 or mismatched_py2 or missing_ext2:
            from PyQt5.QtWidgets import QMessageBox, QApplication
            app = QApplication.instance() or QApplication(sys.argv)
            final_lines = ["Alguns requisitos ainda não estão atendidos. Tente novamente em 'Install Requirements'.\n"]

            if missing_py2:
                final_lines.append("Ainda faltam pacotes Python:")
                for m, v in missing_py2:
                    final_lines.append(f"  - {m}=={v}")
            if mismatched_py2:
                final_lines.append("\nPacotes Python com versão divergente:")
                for m, want, cur in mismatched_py2:
                    final_lines.append(f"  - {m}: instalado={cur!r}, requerido={want}")
            if missing_ext2:
                final_lines.append("\nAinda faltam ferramentas externas:")
                for name in missing_ext2:
                    final_lines.append(f"  - {name}")
            if ext_details2:
                final_lines.append("\nDiagnóstico atual das ferramentas externas:")
                final_lines.extend(ext_details2)

            QMessageBox.warning(None, "CODYN", "\n".join(final_lines))
            sys.exit(1)

_bootstrap()
# ======================= FIM DO BOOTSTRAP CODYN ==============================


# IMPORTANDO AS BIBLIOTECAS PARA CODYN.py:
import sys
import os
import re
import json
import subprocess
import webbrowser
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStyle,
    QTabWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QAction, QMessageBox,
    QFileDialog, QSizePolicy, QSplitter, QTextEdit,
    QCheckBox, QGridLayout, QComboBox, QFormLayout,
    QSpacerItem, QGroupBox, QProgressBar
)
from PyQt5.QtGui import QPixmap, QGuiApplication
from PyQt5.QtCore import (Qt, QTimer, QThread, pyqtSignal, QEventLoop)

from BIN import (module_protein, module_ligands, module_cell, module_equilibration_nvt, module_equilibration_npt, module_production, module_view )
from BIN.splash_screen import SplashScreen
from BIN.config_form import ConfiguracaoDinamica
from BIN.module_requirements import RequirementsInstaller

# CRIANDO A CLASSE PARA EXECUÇÃO DAS ETAPAS EM THREADS:
class RunWorkerThread(QThread):
    update_tab_signal = pyqtSignal(int)
    log_prot_signal = pyqtSignal(str)
    log_cell_signal = pyqtSignal(str)
    log_eq_signal = pyqtSignal(str)
    log_md_signal = pyqtSignal(str)
    log_lig_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)
    alert_signal = pyqtSignal(str, str)
    log_progress_step_signal = pyqtSignal(int)  # Sinal para atualizar a barra de progresso dos steps
    log_progress_stepmax_signal = pyqtSignal(int)  # Sinal para atualizar o valor máximo na barra de progresso dos steps
    log_progress_time_signal = pyqtSignal(int)  # Sinal para atualizar a barra de progresso do tempo
    update_run_folders_signal = pyqtSignal(list) # Sinal para atualizar a lista de pastas em run_folders

    def __init__(self, tabs, tab_config, codyn_dir, run_folders_info, lig_dir, prot_dir):
        super().__init__()
        self.tabs = tabs
        self.tab_config = tab_config
        self.codyn_dir = codyn_dir
        self.run_folders_info = run_folders_info
        self.lig_dir = lig_dir
        self.prot_dir = prot_dir    
        # self.cancel_requested = False

    def request_cancel(self):
        self.cancel_requested = True

    def run(self):
        self.cancel_requested = False  # Reset flag at start
        self.lig_dir = self.tab_config.lig_dir.text()
        self.prot_dir = self.tab_config.prot_dir.text()
        self.update_tab_signal.emit(2) # STEP 1

        # Loop para preparo dos ligantes em cada pasta de execução:
        for info in self.run_folders_info:
            if self.cancel_requested:
                break  # Interrompe o loop se cancelado
            nome_ligante = info["nome_ligante"]
            # Passa para a classe PreparoLigantes em module_ligands.py
            prep_lig = module_ligands.PreparoLigantes(
                self.codyn_dir,
                self.lig_dir
            )
            prep_lig.log_lig_signal.connect(self.log_lig_signal.emit)  # Conecta o sinal de log
            prep_lig.alert_signal.connect(self.alert_signal.emit)  # Conecta o sinal de alerta
            prep_lig.start_preparation(nome_ligante, run_folder=info["run_folder"])

        # QTimer.singleShot(1000, lambda: self.tabs.setCurrentIndex(3))
        self.update_tab_signal.emit(3)  # STEP 2

        if self.cancel_requested:
            return  # Não continua para as próximas etapas

        # PREPARO DA PROTEÍNA:
        # Verifica extensão e prepara nome_proteina
        prot_files = [f for f in os.listdir(self.prot_dir.strip()) if os.path.isfile(os.path.join(self.prot_dir.strip(), f))]
        if len(prot_files) != 1:
            self.log_prot_signal.emit("Attention!", "It is only possible to perform the dynamics with one protein at a time.\nPlace only one file in the proteins folder.")
            self.cancel_requested = True
            return
        prot_file = prot_files[0]
        ext = os.path.splitext(prot_file)[1].lower()
        if ext not in [".pdb", ".pdbqt"]:
            self.log_prot_signal.emit("Attention!", "The protein file must have a .pdb or .pdbqt extension.")
            return
        nome_proteina = os.path.splitext(prot_file)[0]

        # Se for .pdbqt, converte para .pdb usando obabel
        prot_path = os.path.join(self.prot_dir, prot_file)
        if ext == ".pdbqt":
            pdb_path = os.path.join(self.prot_dir.strip(), f"{nome_proteina}.pdb")
            subprocess.run(f'obabel "{prot_path}" -O "{pdb_path}"', shell=True)
            os.remove(prot_path)  # Remove o arquivo .pdbqt original
            msg = f"[{datetime.now().strftime('%H:%M:%S')}] Arquivo {prot_file} convertido para {nome_proteina}.pdb usando Open Babel."
            self.log_prot_signal.emit(msg)
            prot_path = pdb_path  # Atualiza para o .pdb recém-criado

        # PREPARO DO COMPLEXO:
        # Loop para preparo do complexo em cada pasta de execução:
        for info in self.run_folders_info:
            if self.cancel_requested:
                break
            nome_proteina = info["nome_proteina"]
            nome_ligante=info["nome_ligante"]
            run_folder=info["run_folder"]
            config_data = os.path.join(self.codyn_dir, ".form_data.json")
            prep_prot = module_protein.PreparoProteina(
                self.codyn_dir,
                self.prot_dir.strip(),
                self.lig_dir.strip(),
                config_data,
                run_folder,
                prot_path
            )
            prep_prot.log_prot_signal.connect(self.log_prot_signal.emit)  # Conecta o sinal de log
            prep_prot.start_preparation(nome_proteina, nome_ligante)

        if self.cancel_requested:
            return        

        # QTimer.singleShot(1000, lambda: self.tabs.setCurrentIndex(4))
        self.update_tab_signal.emit(4)  # STEP 3

        # Loop para preparo da Célula Unitária e Minimização:
        self.prep_cells = [] # Lista para armazenar instâncias de PreparoCell
        for info in self.run_folders_info:            
            if self.cancel_requested:
                break
            nome_proteina = info["nome_proteina"]
            nome_ligante = info["nome_ligante"]
            run_folder = info["run_folder"]
            config_data = os.path.join(self.codyn_dir, ".form_data.json")
            prep_cell = module_cell.PreparoCell(
                self.codyn_dir,
                config_data,
                run_folder
            )
            prep_cell.log_cell_signal.connect(self.log_cell_signal.emit)
            self.prep_cells.append(prep_cell)  # Salva a referência!
            prep_cell.start_preparation(nome_proteina, nome_ligante)
            if hasattr(prep_cell, 'min_thread'):
                prep_cell.min_thread.wait()  # Espera terminar antes de seguir

        if self.cancel_requested:
            return

        # QTimer.singleShot(1000, lambda: self.tabs.setCurrentIndex(5))
        self.update_tab_signal.emit(5)  # STEP 4
        
        # Loop para equilibração NVT:
        self.prep_nvts = [] # Lista para armazenar instâncias de PrepNVT
        for info in self.run_folders_info:
            if self.cancel_requested:
                break
            nome_proteina = info["nome_proteina"]
            nome_ligante = info["nome_ligante"]
            run_folder = info["run_folder"]
            config_data = os.path.join(self.codyn_dir, ".form_data.json")
            prep_nvt = module_equilibration_nvt.PrepNVT(
                self.codyn_dir,
                config_data,
                run_folder
            )
            prep_nvt.log_eq_signal.connect(self.log_eq_signal.emit)
            self.prep_nvts.append(prep_nvt)  # Salva a referência!
            prep_nvt.start_equilibration(nome_proteina, nome_ligante)
            if hasattr(prep_nvt, 'nvt_thread'):
                prep_nvt.nvt_thread.wait()  # Espera terminar antes de seguir

        if self.cancel_requested:
            return

        # Loop para equilibração NPT:
        self.prep_npts = [] # Lista para armazenar instâncias de PrepNPT
        for info in self.run_folders_info:
            if self.cancel_requested:
                break
            nome_proteina = info["nome_proteina"]
            nome_ligante = info["nome_ligante"]
            run_folder = info["run_folder"]
            config_data = os.path.join(self.codyn_dir, ".form_data.json")
            prep_npt = module_equilibration_npt.PrepNPT(
                self.codyn_dir,
                config_data,
                run_folder
            )
            prep_npt.log_eq_signal.connect(self.log_eq_signal.emit)
            self.prep_npts.append(prep_npt)  # Salva a referência!
            npt_thread = prep_npt.start_equilibration(nome_proteina, nome_ligante)
            if npt_thread is not None:
                npt_thread.wait()
            else:
                self.log_eq_signal.emit("NPT thread não foi criada corretamente.")


        if self.cancel_requested:
            return

        # QTimer.singleShot(1000, lambda: self.tabs.setCurrentIndex(6))
        self.update_tab_signal.emit(6)  # STEP 5
        # Atualiza a lista de pastas RUN na aba de mmpbsa e visualização
        runs_dir = os.path.join(self.codyn_dir, "RUNS")
        all_run_folders = [
            d for d in os.listdir(runs_dir)
            if os.path.isdir(os.path.join(runs_dir, d))
        ]
        self.update_run_folders_signal.emit(all_run_folders)

        # Inicia a produção de dinâmica molecular:
        # Loop para MD Production:
        self.prep_mds = [] # Lista para armazenar instâncias de PrepMD
        for info in self.run_folders_info:
            if self.cancel_requested:
                break
            nome_proteina = info["nome_proteina"]
            nome_ligante = info["nome_ligante"]
            run_folder = info["run_folder"]
            config_data = os.path.join(self.codyn_dir, ".form_data.json")
            prep_md = module_production.PrepMD(
                self.codyn_dir,
                config_data,
                run_folder
            )
            prep_md.log_md_signal.connect(self.log_md_signal.emit)
            prep_md.log_progress_step_signal.connect(self.log_progress_step_signal.emit)
            prep_md.log_progress_stepmax_signal.connect(self.log_progress_stepmax_signal.emit)
            prep_md.log_progress_time_signal.connect(self.log_progress_time_signal.emit)
            self.prep_mds.append(prep_md)  # Salva a referência!
            
            loop = QEventLoop()
            def on_md_finished(_):
                loop.quit()
            # Conecta o sinal de término da thread de produção
            def connect_thread_and_start():
                # Garante que a thread foi criada
                if hasattr(prep_md, 'MD_Thread'):
                    prep_md.MD_Thread.finished_signal.connect(on_md_finished)
                else:
                    # Se a thread ainda não existe, conecta após a criação
                    orig_start = prep_md.start_production
                    def wrapped_start(*args, **kwargs):
                        orig_start(*args, **kwargs)
                        if hasattr(prep_md, 'MD_Thread'):
                            prep_md.MD_Thread.finished_signal.connect(on_md_finished)
                    prep_md.start_production = wrapped_start
            connect_thread_and_start()
            prep_md.start_production(nome_proteina, nome_ligante)
            loop.exec_()  # Espera até a thread terminar

        if self.cancel_requested:
            return
        
         # Muda para a aba de análise e visualização
        self.update_tab_signal.emit(7)  # STEP 6

class MMPBSAWorker(QThread):    
    log_mmpbsa_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)
    alert_signal = pyqtSignal(str, str)
    update_tab_signal = pyqtSignal(int)

    def __init__(self, n_threads, t_ns_md_list, run_folders, params):
        super().__init__()
        self.n_threads = n_threads
        self.t_ns_md_list = t_ns_md_list
        self.run_folders = run_folders
        self.params = params
    
    def request_cancel(self):
        self.cancel_requested = True

    def run(self):
        self.cancel_requested = False  # Reset flag at start
        try:
            self.log_mmpbsa_signal.emit(f"Time production values in runs folders: {self.t_ns_md_list}")
            if not self.t_ns_md_list:
                self.t_ns_md = None
                for run_folder in self.run_folders:
                    for fname in os.listdir(run_folder):
                        match = re.search(r"md_0_([\d\.]+)\.xtc", fname)
                        if match:
                            self.t_ns_md = match.group(1)
                            break
                    if self.t_ns_md:
                        break
                if not self.t_ns_md:
                    self.alert_signal.emit("Erro", "Não foi possível determinar t_ns_md automaticamente.")
                    self.finished_signal.emit(False)
                    return
            else:                
                for run_folder, t_ns_md in zip(self.run_folders, self.t_ns_md_list):
                    self.t_ns_md = t_ns_md
                    if self.cancel_requested:
                        break
                    self.log_mmpbsa_signal.emit(f"N_THREADS: {self.n_threads}, T_NS_MD: {self.t_ns_md}")
                    required_files = [
                        "mmpbsa.in",
                        f"md_0_{self.t_ns_md}.tpr",
                        "index.ndx",
                        f"md_0_{self.t_ns_md}_noPBC.xtc",
                        "topol.top"
                    ]
                    # Verifica se todos os arquivos necessários estão presentes:
                    for fname in required_files:
                        if not os.path.exists(os.path.join(run_folder, fname)):
                            self.log_mmpbsa_signal.emit(f"Arquivo faltando: {fname}")
                        else:
                            self.log_mmpbsa_signal.emit(f"Found required file: {fname}")
                    cmd = [f"mpirun -np {self.n_threads} gmx_MMPBSA MPI -O -i mmpbsa.in -cs md_0_{self.t_ns_md}.tpr -ci index.ndx -cg 1 13 -ct md_0_{self.t_ns_md}_noPBC.xtc -cp topol.top"]
                    self.log_mmpbsa_signal.emit("comando: " + " ".join(cmd))
                    process = subprocess.Popen(
                        cmd,
                        cwd=run_folder,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True
                    )
                    self.log_mmpbsa_signal.emit(f"Executando gmx_MMPBSA em {run_folder}")
                    for line in process.stdout:
                        self.log_mmpbsa_signal.emit(line.strip())
                    process.wait()
                    self.log_mmpbsa_signal.emit(f"Subprocesso finalizado com código {process.returncode}")
                    if process.returncode == 0:
                        self.log_mmpbsa_signal.emit("MMPBSA/MMGBSA finalizado com sucesso!")                    
                    else:
                        self.alert_signal.emit("Erro", f"Execução falhou com código {process.returncode}")
                        self.finished_signal.emit(False)
                # Sinaliza finalização
                self.update_tab_signal.emit(8)
                self.finished_signal.emit(True)
        except Exception as e:
            self.alert_signal.emit("Erro", str(e))
            self.finished_signal.emit(False)


# CRIANDO A CLASSE PRINCIPAL DA APLICAÇÃO:
class MainWindow(QMainWindow):   
    # Inicializando a janela principal:
    def __init__(self):        
        super().__init__()
        self.cancel_requested = False
        self.mmpbsa_workers = []        

        # Diretórios do projeto
        self.codyn_dir = os.path.abspath(os.path.dirname(__file__))
        self.run_folder = None
        self.lig_dir = None
        self.prot_dir = None
        
        # Diretórios de corridas anteriores:
        runs_dir = os.path.join(self.codyn_dir, "RUNS")
        self.old_run_folders = [f for f in os.listdir(runs_dir) if os.path.isdir(os.path.join(runs_dir, f))]

        # Título da janela
        self.setWindowTitle("CODYN - Computational Methods for Molecular Dynamics")

        # Obter o tamanho da tela
        screen = QGuiApplication.primaryScreen()
        size = screen.availableGeometry()
        width = size.width() // 2
        height = size.height() // 2

        # Redimensionar e centralizar a janela
        self.resize(width, height)
        x = (size.width() - width) // 2
        y = (size.height() - height) // 2
        self.move(x, y)
       
        # Codyn Menu Bar        
        menu_bar = self.menuBar()  
        codyn_menu = menu_bar.addMenu("Menu")        
        new_action = QAction("Configure New Run", self)
        new_action.triggered.connect(lambda: self.tabs.setCurrentIndex(1))  # Configuration tab
        codyn_menu.addAction(new_action)
        step1_action = QAction("Step 1 - Ligands Preparation", self)
        step1_action.triggered.connect(lambda: self.tabs.setCurrentIndex(2))  # Step 1
        codyn_menu.addAction(step1_action)
        step2_action = QAction("Step 2 - Complex Preparation", self)
        step2_action.triggered.connect(lambda: self.tabs.setCurrentIndex(3))  # Step 2
        codyn_menu.addAction(step2_action)
        step3_action = QAction("Step 3 - Cell Unit Preparation", self)
        step3_action.triggered.connect(lambda: self.tabs.setCurrentIndex(4))  # Step 3
        codyn_menu.addAction(step3_action)
        step4_action = QAction("Step 4 - System Equilibration", self)
        step4_action.triggered.connect(lambda: self.tabs.setCurrentIndex(5))  # Step 4
        codyn_menu.addAction(step4_action)
        step5_action = QAction("Step 5 - Molecular Dynamics Production", self)
        step5_action.triggered.connect(lambda: self.tabs.setCurrentIndex(6))  # Step 5
        codyn_menu.addAction(step5_action)
        step6_action = QAction("Step 6 - Calculate MMPBSA/MMGBSA", self)
        step6_action.triggered.connect(lambda: self.tabs.setCurrentIndex(7))  # Step 6
        codyn_menu.addAction(step6_action)
        step7_action = QAction("Results Visualization", self)
        step7_action.triggered.connect(lambda: self.tabs.setCurrentIndex(8))  # Step 7
        codyn_menu.addAction(step7_action)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        codyn_menu.addAction(exit_action)
        
        # Help Menu        
        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About Us", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.tabBar().setExpanding(True)
        self.setCentralWidget(self.tabs)

        # Tabs
        self.tab_home = QWidget()
        self.tab_config = ConfiguracaoDinamica(self.codyn_dir, self.tabs)
        self.tab1 = QWidget() # Preparo Ligantes
        self.tab2 = QWidget() # Preparo do Complexo
        self.tab3 = QWidget() # Preparo Célula Unitária
        self.tab4 = QWidget() # Equilíbrio do Sistema
        self.tab5 = QWidget() # Produção
        self.tab6 = QWidget() # Cálculo do MMPBSA/MMGBSA
        self.tab7 = QWidget() # Análise e Visualização

        # Add tabs to the tab widget
        self.tabs.addTab(self.tab_home, "HOME")
        self.tabs.addTab(self.tab_config, "CONFIG")
        self.tabs.addTab(self.tab1, "STEP 1")
        self.tabs.addTab(self.tab2, "STEP 2")
        self.tabs.addTab(self.tab3, "STEP 3")
        self.tabs.addTab(self.tab4, "STEP 4")
        self.tabs.addTab(self.tab5, "STEP 5")
        self.tabs.addTab(self.tab6, "STEP 6")
        self.tabs.addTab(self.tab7, "RESULTS")

        # Initialize tabs
        self.init_tab_home()
        self.tab_config.saved.connect(self.start_config_run_thread)
        self.init_tab1()
        self.init_tab2()
        self.init_tab3()
        self.init_tab4()
        self.init_tab5()
        self.init_tab6()
        self.init_tab7()

    def init_tab_home(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        layout.addStretch()  # Espaço flexível no topo para centralização vertical
        
        # Logo
        logo_label = QLabel()
        logo_path = os.path.join(self.codyn_dir, "ICONS", "LOGO_CODYN2.png")
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pix)
        else:
            logo_label.setText("Logo not found")
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)        
        layout.addSpacing(10)  # Pequeno espaço fixo entre logo e título
        
        # Título
        title1 = QLabel("Computational Methods for Molecular Dynamics")
        title1.setAlignment(Qt.AlignCenter)
        title1.setStyleSheet("font-size:14pt;font-weight:bold;")
        layout.addWidget(title1)

        title2 = QLabel("Current version limited to protein/multi-ligand systems")
        title2.setAlignment(Qt.AlignCenter)
        title2.setStyleSheet("font-size:10pt;font-style:italic;")
        layout.addWidget(title2)

        # Botão Start abaixo do splitter
        layout.addStretch()
        layout.addSpacing(100)
        start_btn = QPushButton("START")
        start_btn.setFixedWidth(120)
        start_btn.setStyleSheet("""
QPushButton {
    background-color: #FFFFFF;   /* Cinza claro */
    color: #333333;              /* Cinza escuro */
    font-size: 14pt;
    font-weight: bold;
    border: 1px solid #333333;   /* Borda cinza escuro */
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #CCCCCC;   /* Cinza médio ao passar o mouse */
    color: #000000;
}
QPushButton:pressed {
    background-color: #666666;   /* Cinza escuro ao clicar */
    color: #000000;
}
""")
        start_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        layout.addWidget(start_btn, alignment=Qt.AlignCenter)

        # Botão Exit centralizado logo abaixo do botão Start
        layout.addStretch()
        layout.addSpacing(100)
        install_btn = QPushButton("Install requirements")
        install_btn.setFixedWidth(200)
        install_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #cccccc;
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton:hover, QPushButton:pressed {
                color: #000000;
                background: transparent;
                border: none;
            }
        """)
        install_btn.clicked.connect(self.show_requirements_installer)
        layout.addWidget(install_btn, alignment=Qt.AlignCenter)

        layout.addStretch()  # Espaço flexível em baixo para centralização vertical

        self.tab_home.setLayout(layout)

    def init_tab1(self):
        main_layout = QVBoxLayout()
        label = QLabel("Step 1 - Ligands Preparation")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size:14pt;font-weight:bold;")
        main_layout.addWidget(label)
        main_layout.addSpacing(10)  # Espaço fixo entre o título e o status

        # Status do preparo dos ligantes
        status_lig = QTextEdit()
        status_lig.setReadOnly(True)
        status_lig.setStyleSheet("background-color: #333333; font-family: monospace; color: #FFFFFF;")
        self.status_lig = status_lig
        main_layout.addWidget(status_lig)

        # Botão Cancelar
        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setFixedWidth(150)
        btn_cancel.setStyleSheet("""
        QPushButton {
            background-color: #FFA07A;   /* Vermelho salmão claro */
            color: #333333;              /* Cinza escuro */
            font-size: 12pt;
            font-weight: bold;
            border: 1px solid #333333; /* Borda cinza escuro */
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #E9967A;   /* Vermelho salmão médio ao passar o mouse */
            color: #000000;  /* Preto */
        }
        QPushButton:pressed {
            background-color: #CD7054;   /* Vermelho salmão escuro ao clicar */
            color: #000000;  /* Preto */
        }
        """)
        btn_cancel.clicked.connect(self.cancel_all_processes)
        main_layout.addWidget(btn_cancel, alignment=Qt.AlignCenter)
        main_layout.addSpacing(10)
        self.tab1.setLayout(main_layout)

    def init_tab2(self):
        main_layout = QVBoxLayout()
        label = QLabel("Step 2 - Complex Preparation")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size:14pt;font-weight:bold;")
        main_layout.addWidget(label)
        main_layout.addSpacing(10)  # Espaço fixo entre o título e o status

        # Status do preparo do complexo
        status_prot = QTextEdit()
        status_prot.setReadOnly(True)
        status_prot.setStyleSheet("background-color: #333333; font-family: monospace; color: #FFFFFF;")
        self.status_prot = status_prot
        main_layout.addWidget(status_prot)

        # Botão Cancelar
        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setFixedWidth(150)
        btn_cancel.setStyleSheet("""
        QPushButton {
            background-color: #FFA07A;   /* Vermelho salmão claro */
            color: #333333;              /* Cinza escuro */
            font-size: 12pt;
            font-weight: bold;
            border: 1px solid #333333; /* Borda cinza escuro */
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #E9967A;   /* Vermelho salmão médio ao passar o mouse */
            color: #000000;  /* Preto */
        }
        QPushButton:pressed {
            background-color: #CD7054;   /* Vermelho salmão escuro ao clicar */
            color: #000000;  /* Preto */
        }
        """)
        btn_cancel.clicked.connect(self.cancel_all_processes)
        main_layout.addWidget(btn_cancel, alignment=Qt.AlignCenter)
        main_layout.addSpacing(10)
        self.tab2.setLayout(main_layout)
    
    def init_tab3(self):
        main_layout = QVBoxLayout()
        label = QLabel("Step 3 - Unit Cell Preparation and Minimization")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size:14pt;font-weight:bold;")
        main_layout.addWidget(label)
        main_layout.addSpacing(10)  # Espaço fixo entre o título e o status

        # Status do preparo da célula unitária
        status_cell = QTextEdit()
        status_cell.setReadOnly(True)
        status_cell.setStyleSheet("background-color: #333333; font-family: monospace; color: #FFFFFF;")
        self.status_cell = status_cell
        main_layout.addWidget(status_cell)

        # Botão Cancelar
        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setFixedWidth(150)
        btn_cancel.setStyleSheet("""
        QPushButton {
            background-color: #FFA07A;   /* Vermelho salmão claro */
            color: #333333;              /* Cinza escuro */
            font-size: 12pt;
            font-weight: bold;
            border: 1px solid #333333; /* Borda cinza escuro */
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #E9967A;   /* Vermelho salmão médio ao passar o mouse */
            color: #000000;  /* Preto */
        }
        QPushButton:pressed {
            background-color: #CD7054;   /* Vermelho salmão escuro ao clicar */
            color: #000000;  /* Preto */
        }
        """)
        btn_cancel.clicked.connect(self.cancel_all_processes)
        main_layout.addWidget(btn_cancel, alignment=Qt.AlignCenter)
        main_layout.addSpacing(10)
        self.tab3.setLayout(main_layout)

    def init_tab4(self):
        main_layout = QVBoxLayout()
        label = QLabel("Step 4 - System Equilibration")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size:14pt;font-weight:bold;")
        main_layout.addWidget(label)
        main_layout.addSpacing(10)  # Espaço fixo entre o título e o status

        # Status do equilíbrio do sistema
        status_eq = QTextEdit()
        status_eq.setReadOnly(True)
        status_eq.setStyleSheet("background-color: #333333; font-family: monospace; color: #FFFFFF;")
        self.status_eq = status_eq
        main_layout.addWidget(status_eq)

        # Botão Cancelar
        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setFixedWidth(150)
        btn_cancel.setStyleSheet("""
QPushButton {
    background-color: #FFA07A;   /* Vermelho salmão claro */
    color: #333333;              /* Cinza escuro */
    font-size: 12pt;
    font-weight: bold;
    border: 1px solid #333333; /* Borda cinza escuro */
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #E9967A;   /* Vermelho salmão médio ao passar o mouse */
    color: #000000;  /* Preto */
}
QPushButton:pressed {
    background-color: #CD7054;   /* Vermelho salmão escuro ao clicar */
    color: #000000;  /* Preto */
}
""")
        btn_cancel.clicked.connect(self.cancel_all_processes)
        main_layout.addWidget(btn_cancel, alignment=Qt.AlignCenter)
        main_layout.addSpacing(10)
        self.tab4.setLayout(main_layout)

    def init_tab5(self):
        main_layout = QVBoxLayout()
        label = QLabel("Step 5 - Molecular Dynamics Production")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size:14pt;font-weight:bold;")
        main_layout.addWidget(label)
        main_layout.addSpacing(10)  # Espaço fixo entre o título e o status

        # Status da produção
        status_prod = QTextEdit()
        status_prod.setReadOnly(True)
        status_prod.setStyleSheet("background-color: #333333; font-family: monospace; color: #FFFFFF;")
        self.status_prod = status_prod
        main_layout.addWidget(status_prod)

        # Duas colunas de opções
        col_layout = QHBoxLayout()

        # Barra de progresso para Steps
        self.progress_step = QProgressBar()
        self.progress_step.setFormat("Step: %v")
        self.progress_step.setStyleSheet("font-size:10pt;font-weight:bold;")
        self.progress_step.setMinimum(0)
        self.progress_step.setMaximum(1)
        self.progress_step.setValue(0)
        col_layout.addWidget(self.progress_step)

        # ---- Coluna Direita ----
        right_col = QVBoxLayout()

        # Barra de progresso para tempo restante
        self.progress_time = QProgressBar()
        self.progress_time.setFormat("Remaining Time:  --:--:-- ")
        self.progress_time.setStyleSheet("font-size:10pt;font-weight:bold;")
        self.progress_time.setMinimum(0)
        # self.progress_time.setMaximum(60)
        self.progress_time.setValue(0)

        col_layout.addWidget(self.progress_time)

        # Definindo os fatores de expansão
        col_layout.setStretch(0, 3)  # self.progress_step ocupa 3 partes
        col_layout.setStretch(1, 1)  # self.progress_time 
        main_layout.addLayout(col_layout)

        # Botão Cancelar
        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setFixedWidth(150)
        btn_cancel.setStyleSheet("""
QPushButton {
    background-color: #FFA07A;   /* Vermelho salmão claro */
    color: #333333;              /* Cinza escuro */
    font-size: 12pt;
    font-weight: bold;
    border: 1px solid #333333; /* Borda cinza escuro */
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #E9967A;   /* Vermelho salmão médio ao passar o mouse */
    color: #000000;  /* Preto */
}
QPushButton:pressed {
    background-color: #CD7054;   /* Vermelho salmão escuro ao clicar */
    color: #000000;  /* Preto */
}
""")
        btn_cancel.clicked.connect(self.cancel_all_processes)
        main_layout.addWidget(btn_cancel, alignment=Qt.AlignCenter)
        main_layout.addSpacing(10)
        self.tab5.setLayout(main_layout)

    def init_tab6(self):
        # Layout principal
        main_layout = QVBoxLayout()
        self.form_widget = QWidget()
        form_layout = QFormLayout(self.form_widget)

        # Label centralizada no topo:
        label = QLabel("Step 6 - Calculate MMPBSA/MMGBSA")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size:14pt;font-weight:bold;")
        main_layout.addWidget(label)
        main_layout.addSpacing(10)
        
        # -------- Seleção da pasta para execução --------   
        self.combo_run_folder_mmpbsa = QComboBox()
        self.combo_run_folder_mmpbsa.addItems(self.old_run_folders)
        form_layout.addRow("Select Run Folder:", self.combo_run_folder_mmpbsa)

        # -------- Campo de Força como ComboBox --------
        self.ff = QComboBox()
        self.ff.addItems([
            "1 - Charmm36_2021",
            "6 - AMBER99SB",
            "9 - Charmm27",
            "15 - GROMOS96_54a7",
            "16 - OPLS_AA/L"
        ])
        form_layout.addRow("Force Field:", self.ff)

        # -------- Presets para preenchimento dos campos de texto--------
        self.n_threads = QLineEdit(str((os.cpu_count())//2))  # Número de threads
        self.frame_start = QLineEdit("1")
        self.frame_end = QLineEdit("2000")
        self.interval = QLineEdit("1")
        self.verbose = QLineEdit("2")
        self.igb = QLineEdit("5")
        self.sltcon = QLineEdit("0.15")
        self.probe_radius = QLineEdit("1.4")
        self.istrng = QLineEdit("0.15")
        self.fill_ratio = QLineEdit("4.0")
        self.idecomp = QLineEdit("2")
        self.dec_verbose = QLineEdit("3")


        # -------- Adicionando campos ao formulário --------
        form_layout.addRow("n_threads:", self.n_threads)  # Número de threads
        form_layout.addRow("Start Frame:", self.frame_start)
        form_layout.addRow("End Frame:", self.frame_end)
        form_layout.addRow("Interval:", self.interval)
        form_layout.addRow("verbose:", self.verbose)
        form_layout.addRow("GBSA-igb:", self.igb)
        form_layout.addRow("GBSA-saltcon:", self.sltcon)
        form_layout.addRow("GBSA-probe:", self.probe_radius)
        form_layout.addRow("PBSA-istrng:", self.istrng)
        form_layout.addRow("PBSA-fillratio:", self.fill_ratio)
        form_layout.addRow("Decomp-idecomp:", self.idecomp)
        form_layout.addRow("Decomp-verbose:", self.dec_verbose)


        # Adicionando o layout do formulário ao layout principal
        main_layout.addWidget(self.form_widget)

        # Caixa de status para logs do MMPBSA (inicialmente oculta)
        self.status_mmpbsa = QTextEdit()
        self.status_mmpbsa.setReadOnly(True)
        self.status_mmpbsa.setStyleSheet("background-color: #333333; font-family: monospace; color: #FFFFFF;")
        self.status_mmpbsa.hide()  # Oculta inicialmente
        main_layout.addWidget(self.status_mmpbsa)

        # Botões
        # Layout horizontal para os botões
        button_layout = QHBoxLayout()

        # Botão Cancelar
        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setFixedWidth(150)
        btn_cancel.setStyleSheet("""
QPushButton {
    background-color: #FFA07A;   /* Vermelho salmão claro */
    color: #333333;              /* Cinza escuro */
    font-size: 12pt;
    font-weight: bold;
    border: 1px solid #333333; /* Borda cinza escuro */
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #E9967A;   /* Vermelho salmão médio ao passar o mouse */
    color: #000000;  /* Preto */
}
QPushButton:pressed {
    background-color: #CD7054;   /* Vermelho salmão escuro ao clicar */
    color: #000000;  /* Preto */
}
""")
        btn_cancel.clicked.connect(self.cancel_all_processes)
        button_layout.addWidget(btn_cancel, alignment=Qt.AlignCenter)

        # Botão RUN centralizado
        run_btn_single = QPushButton("SINGLE RUN")
        run_btn_single.setFixedWidth(150)
        run_btn_single.setStyleSheet("""
QPushButton {
    background-color: #B7E4C7;   /* Verde pastel claro */
    color: #333333;              /* Cinza escuro */
    font-size: 12pt;
    font-weight: bold;
    border: 1px solid #222;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #74C69D;   /* Verde pastel médio ao passar o mouse */
    color: #000000;  /* Preto */
}
QPushButton:pressed {
    background-color: #40916C;   /* Verde pastel escuro ao clicar */
    color: #000000;  /* Preto */
}
""")
        run_btn_single.clicked.connect(self.salvar_mmpbsa_single)
        button_layout.addWidget(run_btn_single, alignment=Qt.AlignCenter)

        # Botão RUN centralizado
        run_btn_all = QPushButton("RUN ALL")
        run_btn_all.setFixedWidth(150)
        run_btn_all.setStyleSheet("""
QPushButton {
    background-color: #B7E4C7;   /* Verde pastel claro */
    color: #333333;              /* Cinza escuro */
    font-size: 12pt;
    font-weight: bold;
    border: 1px solid #222;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #74C69D;   /* Verde pastel médio ao passar o mouse */
    color: #000000;  /* Preto */
}
QPushButton:pressed {
    background-color: #40916C;   /* Verde pastel escuro ao clicar */
    color: #000000;  /* Preto */
}
""")
        run_btn_all.clicked.connect(self.salvar_mmpbsa_all)
        button_layout.addWidget(run_btn_all, alignment=Qt.AlignCenter)
        main_layout.addLayout(button_layout)

        back_form_btn = QPushButton("SHOW FORM")
        back_form_btn.setFixedWidth(150)
        back_form_btn.setStyleSheet("""
QPushButton {
    background-color: #FFFFFF;   /* Cinza claro */
    color: #333333;              /* Cinza escuro */
    font-size: 12pt;
    font-weight: bold;
    border: 1px solid #333333;   /* Borda cinza escuro */
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #CCCCCC;   /* Cinza médio ao passar o mouse */
    color: #000000;
}
QPushButton:pressed {
    background-color: #666666;   /* Cinza escuro ao clicar */
    color: #000000;
}
""")
        back_form_btn.clicked.connect(self.back_form_mmpbsa)
        button_layout.addWidget(back_form_btn, alignment=Qt.AlignCenter)

        back_status_btn = QPushButton("SHOW STATUS")
        back_status_btn.setFixedWidth(150)
        back_status_btn.setStyleSheet("""
QPushButton {
    background-color: #FFFFFF;   /* Cinza claro */
    color: #333333;              /* Cinza escuro */
    font-size: 12pt;
    font-weight: bold;
    border: 1px solid #333333;   /* Borda cinza escuro */
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #CCCCCC;   /* Cinza médio ao passar o mouse */
    color: #000000;
}
QPushButton:pressed {
    background-color: #666666;   /* Cinza escuro ao clicar */
    color: #000000;
}
""")
        back_status_btn.clicked.connect(self.back_status_mmpbsa)
        button_layout.addWidget(back_status_btn, alignment=Qt.AlignCenter)

        main_layout.addSpacing(10)
        self.tab6.setLayout(main_layout)
        
    def init_tab7(self):
        layout = QVBoxLayout()
        
        # Label centralizada
        label_title = QLabel("Results Visualization")
        label_title.setAlignment(Qt.AlignCenter)
        label_title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(label_title)
        layout.addSpacing(20)

        # Duas colunas de opções
        col_layout = QHBoxLayout()

        # ---- Coluna Esquerda ----
        left_col = QVBoxLayout()
        
        # Label e ComboBox de pasta RUN
        label_run_folder = QLabel("Choose Run Folder")
        left_col.addWidget(label_run_folder)        
        self.combo_run_folder = QComboBox()
        self.combo_run_folder.addItems(self.old_run_folders)
        left_col.addWidget(self.combo_run_folder)

        # Label e ComboBox Step
        label_step = QLabel("Choose the Step:")
        left_col.addWidget(label_step)
        self.combo_step = QComboBox()
        self.combo_step.addItems(["Pre-production", "Post-production"])
        left_col.addWidget(self.combo_step)

        # Label e ComboBox de gráficos
        label_chart = QLabel("Choose the result parameter:")
        left_col.addWidget(label_chart)
        self.combo_chart = QComboBox()
        # Opções para pré-produção:
        self.pre_prod_charts = [
            "Potential Energy-Minimization", "Temperature-NVT", "Pressure-NPT", "Density-NPT"
        ]
        # Opções para pós-produção:
        self.post_prod_charts = [
            "RMSD", "RMSD Dist", "RMSF", "SASA", "HBONDs", "Center Of Mass"
        ]
        self.combo_chart.addItems(self.pre_prod_charts)        
        left_col.addWidget(self.combo_chart)       
       
        # ---- Coluna Direita ----
        right_col = QVBoxLayout()
        # Label e ComboBox de grupo (apenas para pós-produção)
        self.label_group = QLabel("Choose the index group:")
        self.label_group1 = QLabel("Group 1:")
        self.combo_group1 = QComboBox()
        self.label_group2 = QLabel("Group 2:")
        self.combo_group2 = QComboBox()
        self.label_group.setEnabled(False)
        self.label_group1.setEnabled(False)
        self.label_group2.setEnabled(False)
        self.combo_group1.setEnabled(False)
        self.combo_group2.setEnabled(False)
        right_col.addWidget(self.label_group)
        right_col.addWidget(self.label_group1)
        right_col.addWidget(self.combo_group1)
        right_col.addWidget(self.label_group2)
        right_col.addWidget(self.combo_group2)

        # Caixas de seleção para legenda e média móvel e a caixa de texto ao lado
        moving_avg_layout = QHBoxLayout()
        self.check_legend = QCheckBox("Show Legend")
        self.check_moving_avg = QCheckBox("Moving Average")
        self.moving_avg_value = QLineEdit("20")
        self.moving_avg_value.setPlaceholderText("Moving Average Value")
        self.moving_avg_value.setFixedWidth(80)
        self.check_legend.setChecked(False)
        self.moving_avg_value.setEnabled(False)  # Inicialmente inativa
        moving_avg_layout.addWidget(self.check_legend)
        moving_avg_layout.addWidget(self.check_moving_avg)
        moving_avg_layout.addWidget(self.moving_avg_value)
        right_col.addLayout(moving_avg_layout)

        col_layout.addLayout(left_col)
        col_layout.setStretch(0, 1)  # left_col ocupa 1 parte
        col_layout.addLayout(right_col)
        col_layout.setStretch(1, 1)  # right_col ocupa 1 parte
        
        # Conecta o sinal para ativar/desativar a caixa de texto
        self.check_moving_avg.stateChanged.connect(
            lambda state: self.moving_avg_value.setEnabled(state == Qt.Checked)
        )
        
        layout.addLayout(col_layout)
        layout.addSpacing(15)

        # ---- Status Viewer ----
        self.status_view = QTextEdit()
        self.status_view.setReadOnly(True)
        self.status_view.setStyleSheet("background-color: #333; color: #fff; font-family: monospace;")
        layout.addWidget(self.status_view)

        # ---- Botões ----
        button_row = QHBoxLayout()
        btn_cancel = QPushButton("CANCELAR")
        btn_view = QPushButton("VIEW")
        btn_cancel.setFixedWidth(150)
        btn_view.setFixedWidth(150)
        btn_cancel.setStyleSheet("""
        QPushButton {
            background-color: #FFA07A;   /* Vermelho salmão claro */
            color: #333333;              /* Cinza escuro */
            font-size: 12pt;
            font-weight: bold;
            border: 1px solid #333333; /* Borda cinza escuro */
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #E9967A;   /* Vermelho salmão médio ao passar o mouse */
            color: #000000;  /* Preto */
        }
        QPushButton:pressed {
            background-color: #CD7054;   /* Vermelho salmão escuro ao clicar */
            color: #000000;  /* Preto */
        }
        """)
        btn_view.setStyleSheet("""
QPushButton {
    background-color: #B7E4C7;   /* Verde pastel claro */
    color: #333333;              /* Cinza escuro */
    font-size: 12pt;
    font-weight: bold;
    border: 1px solid #222;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #74C69D;   /* Verde pastel médio ao passar o mouse */
    color: #000000;  /* Preto */
}
QPushButton:pressed {
    background-color: #40916C;   /* Verde pastel escuro ao clicar */
    color: #000000;  /* Preto */
}
""")
        button_row.addWidget(btn_cancel, alignment=Qt.AlignLeft)
        button_row.addStretch()
        button_row.addWidget(btn_view, alignment=Qt.AlignRight)
        layout.addLayout(button_row)

        self.tab7.setLayout(layout)

        # ---- LÓGICA DE ATUALIZAÇÃO DINÂMICA ----

        # Quando o Step mudar, atualize as opções de chart e combo_group
        def on_step_change(idx):
            if idx == 0:  # Pre-production
                self.combo_chart.clear()
                self.combo_chart.addItems(self.pre_prod_charts)
                self.label_group.setEnabled(False)
                self.label_group1.setEnabled(False)
                self.label_group2.setEnabled(False)
                self.combo_group1.setEnabled(False)
                self.combo_group2.setEnabled(False)
            else:  # Post-production
                self.combo_chart.clear()
                self.combo_chart.addItems(self.post_prod_charts)
                self.label_group.setEnabled(True)
                self.label_group1.setEnabled(True)
                self.label_group2.setEnabled(True)
                self.combo_group1.setEnabled(True)
                self.combo_group2.setEnabled(True)
                # Carregar os grupos do arquivo index.ndx da pasta selecionada
                self.update_group_combo()

        self.combo_step.currentIndexChanged.connect(on_step_change)

        def on_chart_change(idx):
            chart_text = self.combo_chart.currentText()
            if chart_text == "RMSD Dist" or chart_text == "RMSF" or chart_text == "Center Of Mass" or chart_text == "SASA":
                self.label_group2.setEnabled(False)
                self.combo_group2.setEnabled(False)
                self.label_group1.setEnabled(True)
                self.combo_group1.setEnabled(True)
            elif self.combo_step.currentIndex() == 1:  # Post-production
                self.label_group1.setEnabled(True)
                self.combo_group1.setEnabled(True)
                self.label_group2.setEnabled(True)
                self.combo_group2.setEnabled(True)
            else:
                self.label_group1.setEnabled(False)
                self.combo_group1.setEnabled(False)
                self.label_group2.setEnabled(False)
                self.combo_group2.setEnabled(False)

        self.combo_chart.currentIndexChanged.connect(on_chart_change)

        # Atualizar grupos quando Run Folder muda
        def on_run_folder_change(idx):
            if self.combo_step.currentIndex() == 1:  # Só recarrega se for pós-produção
                self.update_group_combo()
        self.combo_run_folder.currentIndexChanged.connect(on_run_folder_change)

        # Função para ler index.ndx e atualizar combo_group
        def update_group_combo():
            self.combo_group1.clear()
            self.combo_group2.clear()
            run_folder = self.combo_run_folder.currentText()
            if not run_folder:
                return
            ndx_path = os.path.join(self.codyn_dir, "RUNS", run_folder, "index.ndx")
            if os.path.exists(ndx_path):
                with open(ndx_path) as f:
                    lines = f.readlines()
                groups = []
                for line in lines:
                    line = line.strip()
                    if line.startswith('[') and line.endswith(']'):
                        groups.append(line)
                for idx, name in enumerate(groups):
                    self.combo_group1.addItem(f"{idx} - {name}")
                    self.combo_group2.addItem(f"{idx} - {name}")
            else:
                self.combo_group1.addItem("No index.ndx found")
                self.combo_group2.addItem("No index.ndx found")
        self.update_group_combo = update_group_combo

        # STATUS e BOTÕES
        btn_cancel.clicked.connect(lambda: self.status_view.clear())
        btn_cancel.clicked.connect(self.cancel_all_processes)
        btn_view.clicked.connect(self.view_results)

    def view_results(self):
        run_folder = self.combo_run_folder.currentText()
        step = self.combo_step.currentText()
        chart = self.combo_chart.currentText()
        group_index1 = None
        group_index2 = None
        if step == "Post-production" and self.combo_group1.isEnabled():
            group_index1 = self.combo_group1.currentIndex()
        if step == "Post-production" and self.combo_group2.isEnabled():
            group_index2 = self.combo_group2.currentIndex()
        use_moving_avg = self.check_moving_avg.isChecked()
        use_legend = self.check_legend.isChecked()
        try:
            moving_avg_value = int(self.moving_avg_value.text())
        except ValueError:
            moving_avg_value = 20  # valor padrão se não for inteiro

        from BIN.module_view import ViewWorker
        self.view_worker = ViewWorker(
            self.codyn_dir, run_folder, step, chart,
            group_index1, group_index2,
            use_moving_avg, moving_avg_value, use_legend
        )
        self.view_worker.log_view_signal.connect(self.log_status_view)
        self.view_worker.run()
        
    #Método para instalar dependências:
    def show_requirements_installer(self):
        self.req_win = RequirementsInstaller(None)
        self.req_win.setWindowModality(Qt.ApplicationModal)
        self.req_win.show()
        self.req_win.activateWindow()
        self.req_win.raise_()
    
    def update_progress_time(self, secs: int):
        if secs is None or secs < 0:
            # fallback para casos estranhos
            self.progress_time.setFormat("Remaining Time: --:--:--")
            return
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        # mantém o valor, mas exibimos no texto formatado
        self.progress_time.setValue(secs)
        self.progress_time.setFormat(f"Remaining Time: {h:02d}:{m:02d}:{s:02d}")

    def update_run_folders(self, all_run_folders):
        self.combo_run_folder_mmpbsa.clear()
        self.combo_run_folder_mmpbsa.addItems(all_run_folders)
        self.combo_run_folder.clear()
        self.combo_run_folder.addItems(all_run_folders)
        # if all_run_folders:
        #     self.combo_run_folder.setCurrentIndex(0)
    # Método para cancelar todos os processos e voltar para a aba HOME
    def cancel_all_processes(self):
        reply = QMessageBox.question(
            self,
            "Attention",
            "Do you really want to cancel all processes\n and return to the HOME tab?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if hasattr(self, 'worker'):
                self.worker.request_cancel()
            self.tabs.setCurrentIndex(0)
            # Mata todos os processos que começam com "gmx"
            subprocess.run("pkill -9 -f '^gmx'", shell=True)
            
    def salvar_mmpbsa_single(self):
        n_threads = int(self.n_threads.text())
        run_folder = self.combo_run_folder_mmpbsa.currentText()        
        if not run_folder:
            QMessageBox.warning(self, "Attention!", "Please select a Run Folder.")
            self.tabs.setCurrentIndex(6)
            return

        # Para cada pasta, obter o tempo de produção (t_ns_md) do arquivo md_0_*.xtc
        run_folders = [os.path.join(self.codyn_dir, "RUNS", run_folder)]
        t_ns_md_list = []
        for run_folder in run_folders:
            xtc_files = [f for f in os.listdir(run_folder) if f.startswith("md_0_") and f.endswith(".xtc")]
            if xtc_files:
                # Extrai o número entre md_0_ e .xtc
                match = re.search(r"md_0_(\d+)\.xtc", xtc_files[0])
                if match:
                    t_ns_md = match.group(1)
                    t_ns_md_list.append(t_ns_md)
                else:
                    t_ns_md_list.append("100")  # Valor padrão se não encontrar
            else:
                t_ns_md_list.append("100")  # Valor padrão se não encontrar
        print(f"t_ns_md_list detectados: {t_ns_md_list}")

        config_mmpbsa = {
            "Run_Folder": self.combo_run_folder_mmpbsa.currentText(),
            "force_field": self.ff.currentText().split('-')[0].strip(),
            "n_threads": self.n_threads.text(),
            "frame_start": self.frame_start.text(),
            "frame_end": self.frame_end.text(),
            "interval": self.interval.text(),
            "verbose": self.verbose.text(),
            "igb": self.igb.text(),
            "sltcon": self.sltcon.text(),
            "probe_radius": self.probe_radius.text(),
            "istrng": self.istrng.text(),
            "fill_ratio": self.fill_ratio.text(),
            "idecomp": self.idecomp.text(),
            "dec_verbose": self.dec_verbose.text(),
        }

        # Verifica se todos os campos estão preenchidos
        if any(not item for item in config_mmpbsa.values()):
            QMessageBox.warning(self, "Attention!", "There are empty MMPBSA configuration fields.")
            self.tabs.setCurrentIndex(7)
            return

        # Formato do arquivo mmpbsa.in:
        mmpbsa_in_content = f"""\
# General namelist variables
&general
  # System name
  sys_name             = "{config_mmpbsa['Run_Folder']}",
  # First frame to analyze
  startframe={config_mmpbsa['frame_start']},
  # Last frame to analyze
  endframe={config_mmpbsa['frame_end']},
  interval={config_mmpbsa['interval']},
  # How many energy terms to print in the final output
  verbose={config_mmpbsa['verbose']},
/
# Generalized-Born namelist variables
&gb
  # GB model to use
  igb={config_mmpbsa['igb']},
  saltcon={config_mmpbsa['sltcon']},
/
#&pb
#  istrng={config_mmpbsa['istrng']}, fillratio={config_mmpbsa['fill_ratio']},
/
&decomp
idecomp={config_mmpbsa['idecomp']}, dec_verbose={config_mmpbsa['dec_verbose']},
# This will print all residues that are less than 4 Å between
# the receptor and the ligand
#  print_res='Within 4',
/
"""

        # Salva em cada run_folder
        for run_folder in run_folders:
            file_path = os.path.join(run_folder, "mmpbsa.in")
            with open(file_path, "w") as f:
                f.write(mmpbsa_in_content)

        self.form_widget.hide()
        self.status_mmpbsa.clear()
        self.status_mmpbsa.show()
        # 6. Executa MMPBSAWorker para cada pasta, usando o t_ns_md correspondente
        # for worker in self.mmpbsa_workers:
        #     worker.wait()
        self.mmpbsa_workers.clear()  # Limpa lista antes de iniciar novos cálculos
        worker = MMPBSAWorker(n_threads, t_ns_md_list, run_folders, params=config_mmpbsa)
        worker.log_mmpbsa_signal.connect(self.log_status_mmpbsa)
        worker.start()
        self.mmpbsa_workers = [worker]
        # self.mmpbsa_workers.append(worker)  # <-- GUARDA REFERÊNCIA!

    def salvar_mmpbsa_all(self):
        n_threads = int(self.n_threads.text())

        # Obter subpastas em RUNS que NÃO possuem FINAL_RESULTS_MMPBSA.dat
        runs_dir = os.path.join(self.codyn_dir, "RUNS")
        run_folders = [
            os.path.join(runs_dir, d)
            for d in os.listdir(runs_dir)
            if os.path.isdir(os.path.join(runs_dir, d)) and
            not os.path.exists(os.path.join(runs_dir, d, "FINAL_RESULTS_MMPBSA.dat"))
        ]
        print(f"run_folders detectadas: {run_folders}")

        # Para cada pasta, obter o tempo de produção (t_ns_md) do arquivo md_0_*.xtc
        t_ns_md_list = []
        for run_folder in run_folders:
            xtc_files = [f for f in os.listdir(run_folder) if f.startswith("md_0_") and f.endswith(".xtc")]
            if xtc_files:
                # Extrai o número entre md_0_ e .xtc
                match = re.search(r"md_0_(\d+)\.xtc", xtc_files[0])
                if match:
                    t_ns_md = match.group(1)
                    t_ns_md_list.append(t_ns_md)
                else:
                    t_ns_md_list.append("100")  # Valor padrão se não encontrar
            else:
                t_ns_md_list.append("100")  # Valor padrão se não encontrar
        print(f"t_ns_md_list detectados: {t_ns_md_list}")

        config_mmpbsa = {
            "force_field": self.ff.currentText().split('-')[0].strip(),
            "n_threads": self.n_threads.text(),
            "frame_start": self.frame_start.text(),
            "frame_end": self.frame_end.text(),
            "interval": self.interval.text(),
            "verbose": self.verbose.text(),
            "igb": self.igb.text(),
            "sltcon": self.sltcon.text(),
            "probe_radius": self.probe_radius.text(),
            "istrng": self.istrng.text(),
            "fill_ratio": self.fill_ratio.text(),
            "idecomp": self.idecomp.text(),
            "dec_verbose": self.dec_verbose.text(),
        }

        # Verifica se todos os campos estão preenchidos
        if any(not item for item in config_mmpbsa.values()):
            QMessageBox.warning(self, "Attention!", "There are empty MMPBSA configuration fields.")
            self.tabs.setCurrentIndex(7)
            return

        # Formato do arquivo mmpbsa.in:
        mmpbsa_in_content = f"""\
# General namelist variables
&general
  # System name
  sys_name             = "Proteina-ligante"
  # First frame to analyze
  startframe={config_mmpbsa['frame_start']},
  # Last frame to analyze
  endframe={config_mmpbsa['frame_end']},
  interval={config_mmpbsa['interval']},
  # How many energy terms to print in the final output
  verbose={config_mmpbsa['verbose']},
/
# Generalized-Born namelist variables
&gb
  # GB model to use
  igb={config_mmpbsa['igb']},
  saltcon={config_mmpbsa['sltcon']},
/
#&pb
#  istrng={config_mmpbsa['istrng']}, fillratio={config_mmpbsa['fill_ratio']},
/
&decomp
idecomp={config_mmpbsa['idecomp']}, dec_verbose={config_mmpbsa['dec_verbose']},
# This will print all residues that are less than 4 Å between
# the receptor and the ligand
#  print_res='Within 4',
/
"""

        # Salva em cada run_folder
        for run_folder in run_folders:
            file_path = os.path.join(run_folder, "mmpbsa.in")
            with open(file_path, "w") as f:
                f.write(mmpbsa_in_content)

        self.form_widget.hide()
        self.status_mmpbsa.clear()
        self.status_mmpbsa.show()
        # 6. Executa MMPBSAWorker para cada pasta, usando o t_ns_md correspondente
        # for worker in self.mmpbsa_workers:
        #     worker.wait()
        self.mmpbsa_workers.clear()  # Limpa lista antes de iniciar novos cálculos
        worker = MMPBSAWorker(n_threads, t_ns_md_list, run_folders, params=config_mmpbsa)
        worker.log_mmpbsa_signal.connect(self.log_status_mmpbsa)
        worker.start()
        self.mmpbsa_workers = [worker]
        # self.mmpbsa_workers.append(worker)  # <-- GUARDA REFERÊNCIA!

    def back_form_mmpbsa(self):
        self.status_mmpbsa.hide()
        self.form_widget.show()

    def back_status_mmpbsa(self):
        self.form_widget.hide()
        self.status_mmpbsa.show()

    def show_alert(self, title, message):
        QMessageBox.information(self, title, message)

    def log_status_lig(self, message):
        self.status_lig.append(message)
        self.status_lig.verticalScrollBar().setValue(self.status_lig.verticalScrollBar().maximum())

    def log_status_prot(self, message):
        # Exibe no QTextEdit ou, se necessário, chama QMessageBox
        if message.startswith("Attention!"):
            QMessageBox.warning(self, "Attention!", message[9:])
        else:
            self.status_prot.append(message)
            self.status_prot.verticalScrollBar().setValue(self.status_prot.verticalScrollBar().maximum())

    def log_status_cell(self, message):
        self.status_cell.append(message)
        self.status_cell.verticalScrollBar().setValue(self.status_cell.verticalScrollBar().maximum())

    def log_status_eq(self, message):
        self.status_eq.append(message)
        self.status_eq.verticalScrollBar().setValue(self.status_eq.verticalScrollBar().maximum())

    def log_status_md(self, message):
        self.status_prod.append(message)
        self.status_prod.verticalScrollBar().setValue(self.status_prod.verticalScrollBar().maximum())

    def log_status_mmpbsa(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        self.status_mmpbsa.append(f"{ts} {message}")
        self.status_mmpbsa.verticalScrollBar().setValue(self.status_mmpbsa.verticalScrollBar().maximum())
    
    def log_status_view(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        self.status_view.append(f"{ts} {message}")
        self.status_view.verticalScrollBar().setValue(self.status_view.verticalScrollBar().maximum())

    def start_config_run_thread(self, run_folders_info):
        self.worker = RunWorkerThread(
            self.tabs,
            self.tab_config,
            self.codyn_dir,
            run_folders_info,
            self.tab_config.lig_dir.text(),
            self.tab_config.prot_dir.text()
        )
        self.worker.alert_signal.connect(self.show_alert, Qt.BlockingQueuedConnection)
        self.worker.log_prot_signal.connect(self.log_status_prot)
        self.worker.log_cell_signal.connect(self.log_status_cell)
        self.worker.log_eq_signal.connect(self.log_status_eq)
        self.worker.log_md_signal.connect(self.log_status_md)
        self.worker.log_progress_step_signal.connect(self.progress_step.setValue)
        self.worker.log_progress_stepmax_signal.connect(self.progress_step.setMaximum)
        self.worker.log_progress_time_signal.connect(self.update_progress_time)
        self.worker.update_run_folders_signal.connect(self.update_run_folders)
        self.worker.log_lig_signal.connect(self.log_status_lig)
        self.worker.update_tab_signal.connect(self.tabs.setCurrentIndex)
        self.worker.finished_signal.connect(lambda _: QMessageBox.information(self, "Concluído", "Dinâmica finalizada!"))
        self.worker.start()

    def closeEvent(self, event):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.request_cancel()
            self.worker.wait()
        event.accept()

    def show_about(self):
        QMessageBox.about(
            self,
            "ABOUT US",
            "                          An Open Source\n   Automated Molecular Dynamics Tool\n   \nDeveloped by:\n   Moisés Maia Neto and Gustavo Scheiffer\n   Universidade Federal do Paraná (UFPR)\n   Brazil\n \nContact:\n   moimaian@gmail.com   \n\n           Version 1.0   © July-2025\n   "
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    codyn_dir = os.path.abspath(os.path.dirname(__file__))

    splash = SplashScreen(codyn_dir)
    splash.show()
    splash.start_checks()

    def start_mainwindow(status):
        splash.close()

        # Pastas "críticas" → manter aviso + abrir GitHub
        critical_set = {"BASE", "BIN", "ICONS", "TEST"}
        # Pastas "auto-criáveis" → apenas criar e avisar (sem abrir GitHub)
        autocreate_set = {"RUNS", "TARGET", "LIGANDS"}

        missing = set(status.get("missing_folders", []))

        if missing:
            crit_missing = sorted([f for f in missing if f in critical_set])
            auto_missing = sorted([f for f in missing if f in autocreate_set])

            if crit_missing:
                QMessageBox.warning(
                    None,
                    "Missing required folders",
                    "The following mandatory folders were not found: "
                    + ", ".join(crit_missing)
                    + "\nPlease download the complete project structure from GitHub."
                )
                webbrowser.open("https://github.com/moimaian/CODYN")

            if auto_missing:
                # Cria as pastas diretamente no diretório do projeto
                for name in auto_missing:
                    os.makedirs(os.path.join(codyn_dir, name), exist_ok=True)
                QMessageBox.information(
                    None,
                    "Folders created",
                    "The following folders were created automatically: "
                    + ", ".join(auto_missing)
                )

        window = MainWindow()
        window.show()

        # Alertas para comandos ausentes no PATH
        missing_tools = [cmd for cmd, ok in status['env_cmds'].items() if not ok]
        if missing_tools:
            QMessageBox.critical(
                window,
                "Dependencies not installed",
                "The following commands are not available in the PATH:\n"
                + "\n".join(missing_tools) +
                "\n\nPlease install the requirements. (Or use the button on the Home tab to install later.)"
            )

    splash.check_complete.connect(start_mainwindow)
    sys.exit(app.exec_())
