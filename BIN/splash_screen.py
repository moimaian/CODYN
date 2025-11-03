# splash_screen.py (com logs e chaves compatíveis com CODYN.py)
import os
import sys
import shutil
from pathlib import Path
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QApplication
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QGuiApplication


def _print(msg: str):
    print(msg, flush=True)


class SplashScreen(QWidget):
    check_complete = pyqtSignal(dict)  # Emite dicionário de status

    def __init__(self, codyn_dir: str):
        super().__init__()
        self.codyn_dir = codyn_dir
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Centralizar janela
        screen = QGuiApplication.primaryScreen()
        size = screen.availableGeometry()
        width, height = 400, 350
        self.resize(width, height)
        self.move((size.width() - width) // 2, (size.height() - height) // 2)

        # Layout principal
        layout_ss = QVBoxLayout()
        layout_ss.setAlignment(Qt.AlignCenter)

        # Logo
        logo = QLabel()
        logo_path = os.path.join(codyn_dir, "ICONS", "LOGO_CODYN.png")
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(pix)
        else:
            logo.setText("LOGO NOT FOUND")
        logo.setAlignment(Qt.AlignCenter)
        layout_ss.addWidget(logo)

        # Texto
        label = QLabel("Loading CODYN...")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #333333;")
        layout_ss.addWidget(label)

        # Barra de progresso
        self.progress = QProgressBar()
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setFixedHeight(24)
        self.progress.setStyleSheet(
            "QProgressBar { font-size: 10pt; border-radius: 4px; font-weight: bold; color: #333333; }"
        )
        layout_ss.addWidget(self.progress)

        self.setLayout(layout_ss)

        self.status = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_progress)
        self.current = 0

    def start_checks(self):
        """Inicia checagens e mostra progresso."""
        self.progress.setValue(0)
        self.current = 0

        # Estrutura de status compatível com CODYN.py
        self.status = {
            # Compatibilidade (o CODYN.py usa essas três chaves):
            "folders_ok": True,
            "missing_folders": [],
            "env_cmds": {},   # dict[str, bool] — True se encontrado, False se ausente

            # Extras informativos (não usados por CODYN.py, mas úteis no debug):
            "folders": {},        # nome -> caminho
            "venv": {},           # dir/python paths
            "tools_paths": {},    # nome -> caminho (ou None)
        }

        self.timer.start(30)
        QTimer.singleShot(150, self._run_checks)

    def _update_progress(self):
        self.current += 1
        self.progress.setValue(self.current)
        if self.current >= 100:
            self.timer.stop()
            self.check_complete.emit(self.status)

    # ------------------ checagens ------------------

    def _check_folder(self, name: str, path: Path):
        exists = path.exists() and path.is_dir()
        self.status["folders"][name] = str(path)
        if not exists:
            self.status["folders_ok"] = False
            self.status["missing_folders"].append(str(path))
        _print(f"[CODYN][CHECK] DIR {name:>8}: {path}  ->  {'OK' if exists else 'MISSING'}")
        return exists

    def _check_folders(self):
        root = Path(self.codyn_dir)
        pairs = [
            ("BASE",    root / "BASE"),
            ("BIN",     root / "BIN"),
            ("RUNS",    root / "RUNS"),
            ("TARGET",  root / "TARGET"),
            ("LIGANDS", root / "LIGANDS"),
            ("ICONS",   root / "ICONS"),
            ("TEST",    root / "TEST"),
        ]
        _print("[CODYN] ===== Verificando diretórios importantes =====")
        for name, path in pairs:
            self._check_folder(name, path)

    def _check_venv(self):
        venv_dir = Path.home() / ".venv" / "CODYN"
        if os.name == "nt":
            vpy = venv_dir / "Scripts" / "python.exe"
        else:
            vpy = venv_dir / "bin" / "python"

        exists_dir = venv_dir.exists()
        exists_py = vpy.exists()

        self.status["venv"]["dir"] = str(venv_dir)
        self.status["venv"]["python"] = str(vpy) if exists_py else None

        _print("\n[CODYN] ===== Verificando ambiente ~/.venv/CODYN =====")
        _print(f"[CODYN][CHECK] VENV DIR : {venv_dir}  ->  {'OK' if exists_dir else 'MISSING'}")
        _print(f"[CODYN][CHECK] VENV PY  : {vpy}  ->  {'OK' if exists_py else 'MISSING'}")

    def _which(self, name: str) -> str | None:
        return shutil.which(name)

    def _check_tools(self):
        _print("\n[CODYN] ===== Verificando programas externos =====")

        # GROMACS (gmx)
        gmx_path = self._which("gmx")
        if not gmx_path and Path("/usr/local/gromacs/bin/gmx").exists():
            gmx_path = "/usr/local/gromacs/bin/gmx"
        self.status["tools_paths"]["gmx"] = gmx_path
        self.status["env_cmds"]["gmx"] = bool(gmx_path)
        _print(f"[CODYN][CHECK] GROMACS (gmx): {gmx_path if gmx_path else 'NOT FOUND'}  ->  {'OK' if gmx_path else 'MISSING'}")

        # gmx_MMPBSA: vale tanto binário quanto módulo Python
        mmpbsa_path = self._which("gmx_MMPBSA")
        if not mmpbsa_path:
            try:
                import importlib.util
                spec = importlib.util.find_spec("gmx_MMPBSA")
                if spec and getattr(spec, 'origin', None):
                    mmpbsa_path = f"module:{spec.origin}"
            except Exception:
                pass
        self.status["tools_paths"]["gmx_MMPBSA"] = mmpbsa_path
        self.status["env_cmds"]["gmx_MMPBSA"] = bool(mmpbsa_path)
        _print(f"[CODYN][CHECK] gmx_MMPBSA  : {mmpbsa_path if mmpbsa_path else 'NOT FOUND'}  ->  {'OK' if mmpbsa_path else 'MISSING'}")

    def _run_checks(self):
        self._check_folders()
        self._check_venv()
        self._check_tools()
