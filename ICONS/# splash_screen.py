# splash_screen.py
import os
import subprocess
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QApplication, QMessageBox
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QGuiApplication
import webbrowser

class SplashScreen(QWidget):
    check_complete = pyqtSignal(dict)  # Emite dicionário de status

    def __init__(self, codyn_dir):
        super().__init__()
        self.codyn_dir = codyn_dir
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Centralizar janela
        screen = QGuiApplication.primaryScreen()
        size = screen.availableGeometry()
        width, height = 400, 350
        self.resize(width, height)
        self.move((size.width()-width)//2, (size.height()-height)//2)

        # Layout principal
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        # Logo
        logo = QLabel()
        logo_path = os.path.join(codyn_dir, "ICONS", "LOGO_CODYN2.png")
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(pix)
        else:
            logo.setText("LOGO NOT FOUND")
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        # Texto
        label = QLabel("Iniciando CODYN...")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 14pt;")
        layout.addWidget(label)

        # Barra de progresso
        self.progress = QProgressBar()
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setFixedHeight(24)
        self.progress.setStyleSheet("QProgressBar { font-size: 10pt; border-radius: 8px; }")
        layout.addWidget(self.progress)

        self.setLayout(layout)

        self.status = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)
        self.current = 0

    def start_checks(self):
        self.progress.setValue(0)
        self.current = 0
        self.status = {
            'folders_ok': True,
            'missing_folders': [],
            'env_cmds': {},
        }
        self.timer.start(45)  # ~5 segundos com 100 steps (100*45ms=4,5s)
        QTimer.singleShot(200, self.run_checks)

    def update_progress(self):
        self.current += 1
        self.progress.setValue(self.current)
        if self.current >= 100:
            self.timer.stop()
            self.check_complete.emit(self.status)

    def run_checks(self):
        # Cria pastas se necessário
        folders_to_create = ["LIGANDS", "TARGET", "RUNS"]
        for folder in folders_to_create:
            path = os.path.join(self.codyn_dir, folder)
            if not os.path.exists(path):
                os.makedirs(path)

        # Checa pastas obrigatórias
        must_exist = ["BASE", "BIN", "ICONS"]
        missing = []
        for folder in must_exist:
            path = os.path.join(self.codyn_dir, folder)
            if not os.path.exists(path):
                missing.append(folder)
        self.status['folders_ok'] = (len(missing) == 0)
        self.status['missing_folders'] = missing

        # Checa comandos no PATH
        required_cmds = ['gmx_MMPBSA', 'gmx', 'obabel']
        for cmd in required_cmds:
            result = subprocess.call(f"command -v {cmd}", shell=True,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.status['env_cmds'][cmd] = (result == 0)
