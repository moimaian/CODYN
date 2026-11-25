# -*- coding: utf-8 -*-
"""Splash do CODYN: verifica pastas e ferramentas, garante o atalho do menu e libera a janela principal."""

import os
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QGuiApplication, QPixmap
from PyQt5.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from BIN import tools
from BIN.platform_utils import IS_WINDOWS
from BIN.theme import PALETTE
from BIN.versao import VERSAO

CRITICAL_DIRS = ("BASE", "BIN", "ICONS")
AUTOCREATE_DIRS = ("PROJECTS",)


def _print(msg: str):
    print(msg, flush=True)


def ensure_desktop(app_dir: str) -> str:
    """Cria/atualiza o atalho do menu (Linux: ~/.local/share/applications/CODYN.desktop; Windows: CODYN.lnk
    na Área de Trabalho e no Menu Iniciar). Devolve a mensagem."""
    try:
        from BIN.module_requirements import create_desktop_launcher, venv_paths
        if not os.path.isfile(venv_paths("CODYN")["python"]):
            return "venv not created yet; shortcut skipped"
        ok, msg = create_desktop_launcher()
        return msg
    except Exception as e:  # nunca impede a abertura do programa
        return f"shortcut not updated: {e}"


class SplashScreen(QWidget):
    check_complete = pyqtSignal(dict)

    def __init__(self, codyn_dir: str):
        super().__init__()
        self.codyn_dir = codyn_dir
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SplashScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)
        screen = QGuiApplication.primaryScreen().availableGeometry()
        w, h = 520, 340
        self.resize(w, h)
        self.move((screen.width() - w) // 2 + screen.x(), (screen.height() - h) // 2 + screen.y())

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        card = QWidget()
        card.setObjectName("splash_card")
        card.setStyleSheet(f"#splash_card{{background:#12202E;border:2px solid {PALETTE['border']};border-radius:12px;}}")
        lay.addWidget(card)
        inner = QVBoxLayout(card)
        inner.setAlignment(Qt.AlignCenter)

        logo = QLabel()
        logo.setStyleSheet("background:transparent;")
        logo_path = os.path.join(codyn_dir, "ICONS", "LOGO_CODYN.png")
        if os.path.exists(logo_path):
            logo.setPixmap(QPixmap(logo_path).scaled(170, 170, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("CODYN")
            logo.setStyleSheet(f"font-size:36pt;font-weight:bold;color:{PALETTE['brand']};background:transparent;")
        logo.setAlignment(Qt.AlignCenter)
        inner.addWidget(logo)

        self.label = QLabel(f"CODYN  v{VERSAO}")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(f"font-size:13pt;font-weight:bold;color:{PALETTE['text']};background:transparent;")
        inner.addWidget(self.label)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(20)
        self.progress.setFixedWidth(380)
        self.progress.setAlignment(Qt.AlignCenter)
        inner.addWidget(self.progress, alignment=Qt.AlignCenter)

        self.status = {}
        self._target = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def _set_target(self, value: int, text: str = ""):
        self._target = max(self._target, value)
        if text:
            self.label.setText(text)

    def _tick(self):
        cur = self.progress.value()
        if cur < self._target:
            self.progress.setValue(cur + 1)
        elif cur >= 100:
            self._timer.stop()
            self.check_complete.emit(self.status)

    def start_checks(self):
        self.progress.setValue(0)
        self.status = {"missing_folders": [], "created_folders": [], "tools": {}, "missing_tools": [], "shortcut": ""}
        self._timer.start(12)
        QTimer.singleShot(60, self._run_checks)

    def _run_checks(self):
        root = Path(self.codyn_dir)
        _print(f"[CODYN] v{VERSAO} — checking installation at {root}")
        self._set_target(20, "Checking folders...")
        for name in CRITICAL_DIRS:
            if not (root / name).is_dir():
                self.status["missing_folders"].append(name)
        for name in AUTOCREATE_DIRS:
            d = root / name
            if not d.is_dir():
                try:
                    d.mkdir(parents=True, exist_ok=True)
                    self.status["created_folders"].append(name)
                except OSError:
                    self.status["missing_folders"].append(name)
        self._set_target(45, "Checking tools...")
        tool_paths = {
            "gmx": tools.find_gmx(),
            "obabel": tools.find_obabel(),
            "perl": tools.find_perl(),
        }
        if not IS_WINDOWS:   # o gmx_MMPBSA depende do AmberTools, que não existe para Windows
            tool_paths["gmx_MMPBSA"] = tools.find_executable("gmx_MMPBSA", extra=["/usr/local/bin/gmx_MMPBSA"],
                                                             search_conda=True)
        self.status["tools"] = tool_paths
        self.status["missing_tools"] = [k for k, v in tool_paths.items() if not v]
        for k, v in tool_paths.items():
            _print(f"[CODYN][CHECK] {k:<11}: {v or 'NOT FOUND'}")
        self._set_target(75, "Updating menu shortcut...")
        self.status["shortcut"] = ensure_desktop(self.codyn_dir)
        _print(f"[CODYN] {self.status['shortcut']}")
        self._set_target(100, f"CODYN  v{VERSAO}")
