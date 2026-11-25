#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
#
# CODYN – Computational Platform for Molecular Dynamics
# Copyright (C) 2025–2026 Moisés Maia
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import os
import sys

os.environ.setdefault("PYTHONNOUSERSITE", "1")
CODYN_DIR = os.path.dirname(os.path.abspath(__file__))
if CODYN_DIR not in sys.path:
    sys.path.insert(0, CODYN_DIR)

from BIN import platform_utils as _pu  # noqa: E402  (só biblioteca padrão)

_IS_WINDOWS = _pu.IS_WINDOWS
if _IS_WINDOWS:
    # Todo subprocesso nasce sem janela de console (o atalho usa pythonw.exe, que não tem console).
    _pu.install_subprocess_defaults()


def _bootstrap_codyn_venv():
    """Garante ~/.venv/CODYN + PyQt5 e reexecuta o programa dentro do venv (ver BIN/module_requirements.py)."""
    if os.environ.get("CODYN_VENV_ACTIVE") == "1":
        return
    from BIN.module_requirements import bootstrap_pyqt5
    if not bootstrap_pyqt5(interactive=True, reexec=True, env_name="CODYN"):
        sys.exit(1)


# Saída do programa (prints, erros, subprocessos) num log por sessão, exibido por Help > Terminal.
CODYN_TERMINAL_LOG_DIR = _pu.terminal_log_dir()   # Linux: ~/.cache/codyn ; Windows: %LOCALAPPDATA%\\CODYN
CODYN_TERMINAL_LOG = os.path.join(CODYN_TERMINAL_LOG_DIR, f"terminal_{os.getpid()}.log")
_codyn_tee_proc = None


class _TeeStream:
    """Windows (sem o comando `tee` nem dup2): copia o que o CODYN imprime para o console, se houver, e
    para o log da sessão. Aberto pelo atalho (pythonw.exe) não há console e tudo vai só para o log."""

    def __init__(self, console, log_file):
        self._console, self._log = console, log_file

    def write(self, text):
        for stream in (self._console, self._log):
            if stream is None:
                continue
            try:
                stream.write(text)
            except Exception:   # console com codificação limitada (cp1252) e emoji/acento no texto
                try:
                    stream.write(text.encode("ascii", "replace").decode("ascii"))
                except Exception:
                    pass
        return len(text)

    def flush(self):
        for stream in (self._console, self._log):
            try:
                if stream is not None:
                    stream.flush()
            except Exception:
                pass

    def isatty(self):
        return False

    encoding = "utf-8"
    errors = "replace"

    def writable(self):
        return True

    def fileno(self):
        return self._log.fileno()   # quem pedir um descritor (subprocesso, faulthandler) recebe o log


def _setup_terminal_log():
    global _codyn_tee_proc
    import glob
    import subprocess
    try:
        os.makedirs(CODYN_TERMINAL_LOG_DIR, exist_ok=True)
        for old in glob.glob(os.path.join(CODYN_TERMINAL_LOG_DIR, "terminal_*.log")):
            try:
                old_pid = int(os.path.basename(old)[len("terminal_"):-len(".log")])
                if old_pid != os.getpid() and not _pu.pid_alive(old_pid):
                    os.remove(old)
            except ValueError:
                os.remove(old)
            except Exception:
                pass
        log_fd = os.open(CODYN_TERMINAL_LOG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    except OSError:
        return
    if _IS_WINDOWS:
        # Sem fork/tee/dup2 de console: troca sys.stdout/sys.stderr. Aberto pelo atalho (pythonw.exe) não
        # há console (sys.stdout é None) e tudo vai só para o log; rodando num terminal, a saída continua
        # nele e é copiada para o log (Help > Terminal).
        try:
            log_file = os.fdopen(log_fd, "w", encoding="utf-8", errors="replace", buffering=1)
            console = sys.stdout if (sys.stdout is not None and sys.stdout.isatty()) else None
            sys.stdout = sys.stderr = _TeeStream(console, log_file)
        except Exception:
            pass
        return
    try:
        sys.stdout.flush()
        sys.stderr.flush()
        if os.isatty(1):
            os.close(log_fd)
            _codyn_tee_proc = subprocess.Popen(["tee", "-i", "-a", CODYN_TERMINAL_LOG], stdin=subprocess.PIPE)
            out_fd = _codyn_tee_proc.stdin.fileno()
        else:
            out_fd = log_fd
        os.dup2(out_fd, 1)
        os.dup2(out_fd, 2)
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass


if __name__ == "__main__":
    _bootstrap_codyn_venv()
    _setup_terminal_log()

import shlex
import shutil
import subprocess
import webbrowser

from PyQt5.QtCore import QSettings, QSize, Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices, QGuiApplication, QIcon
from PyQt5.QtWidgets import (
    QAction, QApplication, QComboBox, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget, QAbstractItemView,
)

from BIN import i18n
from BIN.config_form import ConfigForm
from BIN.dialogs import CgenffDialog
from BIN.module_home import HomeTab
from BIN.module_requirements import RequirementsInstaller, missing_required_python
from BIN.module_results import ResultsTab, list_run_folders
from BIN.projects import ProjectManager, migrate_legacy
from BIN.pipeline import MMPBSAWorker, PipelineWorker, find_production_tag
from BIN.runconfig import RunConfig
from BIN.splash_screen import SplashScreen
from BIN.theme import PALETTE, SS_MAIN, ensure_button_fits, set_role
from BIN.tools import CancelToken
from BIN.versao import VERSAO
from BIN.widgets import CollapsibleGroupBox, LogConsole, make_progress, make_title

GITHUB_URL = "https://github.com/moimaian/CODYN"

# (índice da aba, chave do passo, chave i18n do título, com barra de progresso)
STEP_TABS = [
    (2, "lig", "step1_title", False),
    (3, "prot", "step2_title", False),
    (4, "cell", "step3_title", True),
    (5, "eq", "step4_title", True),
    (6, "md", "step5_title", True),
]


class MainWindow(QMainWindow):
    def __init__(self, status=None):
        super().__init__()
        self.codyn_dir = CODYN_DIR
        self.status = status or {}
        self.settings = QSettings("CODYN", "CODYN")
        self.project = ProjectManager(self.codyn_dir, self)
        try:  # estrutura antiga (RUNS/ na raiz) -> projeto PROJECTS/<data>_RUNS_ANTERIORES
            self._migration = migrate_legacy(self.codyn_dir)
        except OSError as e:
            self._migration = None
            print(f"[CODYN] legacy RUNS migration failed: {e}", flush=True)
        lang = self.settings.value("language", "") or i18n.detect_system_language()
        self.tr_ = i18n.Translator(lang if lang in i18n.LANGUAGES else i18n.DEFAULT_LANGUAGE)
        self.worker = None
        self.mmpbsa_worker = None
        self.token = CancelToken()
        self.consoles = {}
        self.bars = {}
        self.remaining = {}
        self._req_dialog = None
        self._runs_status = {}

        self.tr_.on_change(lambda _l: self._update_title())
        self._update_title()
        self.setWindowIcon(QIcon(os.path.join(self.codyn_dir, "ICONS", "LOGO_CODYN.png")))
        screen = QGuiApplication.primaryScreen().availableGeometry()
        w, h = min(1180, int(screen.width() * 0.8)), min(860, int(screen.height() * 0.9))
        self.resize(w, h)
        self.move(screen.x() + (screen.width() - w) // 2, screen.y() + (screen.height() - h) // 2)

        self._build_menu()
        self._build_corner()
        self._build_tabs()
        self.tr_.on_change(lambda _l: self._after_language_change())

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._fit_to_home)  # caso os dados da HOME tenham chegado antes da janela aparecer

    def _fit_to_home(self, attempt=0):
        """Na primeira carga da HOME, ajusta a janela para que todo o conteúdo apareça sem rolagem
        (limitado à área útil da tela). Atualizações posteriores não mexem no tamanho escolhido pelo usuário.
        Mede de novo após o layout assentar (até 3 passadas), pois os dados chegam de forma assíncrona."""
        if getattr(self, "_home_fitted", False) or not self.isVisible() or not self.home._info:
            return
        if attempt == 0:
            QTimer.singleShot(150, lambda: self._fit_to_home(1))
            return
        dw, dh = self.home.extra_size()
        if (dw or dh) and attempt <= 3:
            screen = QGuiApplication.primaryScreen().availableGeometry()
            w = min(self.width() + dw, screen.width())
            h = min(self.height() + dh, screen.height())
            if (w, h) != (self.width(), self.height()):
                self.resize(w, h)
                fg = self.frameGeometry()
                x = min(max(screen.x(), fg.x()), screen.right() - fg.width() + 1)
                y = min(max(screen.y(), fg.y()), screen.bottom() - fg.height() + 1)
                self.move(x, y)
                QTimer.singleShot(150, lambda: self._fit_to_home(attempt + 1))
                return
        self._home_fitted = True

    # ------------------------------------------------------------------ menus ------------------------------------------------------------------
    def _action(self, menu, key, slot):
        act = QAction(self)
        self.tr_.tr(key, act.setText)
        act.triggered.connect(slot)
        menu.addAction(act)
        return act

    def _build_menu(self):
        bar = self.menuBar()
        m = bar.addMenu("Menu")
        self._action(m, "menu_new_run", lambda: self.tabs.setCurrentIndex(1))
        for idx, key in ((2, "menu_step1"), (3, "menu_step2"), (4, "menu_step3"), (5, "menu_step4"),
                         (6, "menu_step5"), (7, "menu_step6"), (8, "menu_results")):
            self._action(m, key, lambda _=False, i=idx: self.tabs.setCurrentIndex(i))
        m.addSeparator()
        self._action(m, "menu_exit", self.close)
        h = bar.addMenu("")
        self.tr_.tr("menu_help", h.setTitle)
        self._action(h, "menu_install", self.show_requirements_installer)
        self._action(h, "menu_terminal", self.open_terminal_window)
        self._action(h, "menu_docs", lambda: webbrowser.open(GITHUB_URL))
        self._action(bar, "menu_about", self.show_about)  # direto na barra, fora do menu Ajuda

    def _build_corner(self):
        box = QWidget()
        box.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(6)
        flag_style = ("QPushButton{border:none;background:transparent;padding:0;}"
                      "QPushButton:hover{background:#16283B;border-radius:4px;}")
        self.flags = {}
        for lang, svg, tip in (("pt", "flag_br.svg", "tooltip_flag_pt"), ("en", "flag_gb.svg", "tooltip_flag_en")):
            b = QPushButton()
            b.setIcon(QIcon(os.path.join(self.codyn_dir, "ICONS", svg)))
            b.setIconSize(QSize(24, 16))
            b.setFlat(True)
            b.setFixedSize(30, 22)
            b.setStyleSheet(flag_style)
            self.tr_.tr(tip, b.setToolTip)
            b.clicked.connect(lambda _=False, l=lang: self.set_language(l))
            lay.addWidget(b)
            self.flags[lang] = b
        self.btn_monitor = QPushButton()
        self.tr_.tr("btn_monitor", self.btn_monitor.setText)
        self.btn_monitor.setStyleSheet(
            f"QPushButton{{padding:4px 12px;border:2px solid {PALETTE['muted']};border-radius:6px;background:{PALETTE['bg']};"
            f"color:{PALETTE['muted']};font-weight:bold;font-size:9pt;}}QPushButton:hover{{background:#16283B;}}")
        self.btn_monitor.clicked.connect(self.open_hw_monitor_window)
        lay.addWidget(self.btn_monitor)
        self.menuBar().setCornerWidget(box, Qt.TopRightCorner)
        self._refresh_flags()

    def _refresh_flags(self):
        for lang, b in self.flags.items():
            on = lang == self.tr_.lang
            b.setStyleSheet(
                "QPushButton{border:none;background:%s;padding:0;border-radius:4px;}"
                "QPushButton:hover{background:#16283B;border-radius:4px;}" % ("#1C3249" if on else "transparent"))

    def set_language(self, lang: str):
        self.settings.setValue("language", lang)
        self.tr_.set_language(lang)

    def _after_language_change(self):
        self._refresh_flags()
        for w in self.findChildren(QPushButton):
            ensure_button_fits(w)
        for i, key in enumerate(("tab_home", "tab_config", "tab_step1", "tab_step2", "tab_step3", "tab_step4",
                                 "tab_step5", "tab_step6", "tab_results")):
            self.tabs.setTabText(i, self.tr_.t(key))
        self.tabs.tabBar().updateGeometry()

    # ------------------------------------------------------------------ abas ------------------------------------------------------------------
    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.tabs.setObjectName("main_tabs")
        self.tabs.tabBar().setExpanding(True)
        _f = self.tabs.tabBar().font(); _f.setBold(True)   # o QSS usa negrito: sem isto o tamanho das abas é medido sem negrito e "RESULTADOS" é cortado
        self.tabs.tabBar().setFont(_f)
        self.setCentralWidget(self.tabs)

        self.home = HomeTab(self.codyn_dir, self.tr_)
        self.home.start_requested.connect(lambda: self.tabs.setCurrentIndex(1))
        self.home.install_requested.connect(self.show_requirements_installer)
        self.home.content_ready.connect(self._fit_to_home)
        self.config = ConfigForm(self.codyn_dir, self.tr_, self.project)
        self.config.cancel_requested.connect(lambda: self.tabs.setCurrentIndex(0))
        self.config.install_requested.connect(self.show_requirements_installer)
        self.config.run_requested.connect(self.start_run)
        self.tabs.addTab(self.home, "")
        self.tabs.addTab(self.config, "")
        for idx, key, title_key, with_progress in STEP_TABS:
            self.tabs.addTab(self._make_step_tab(key, title_key, with_progress), "")
        self.tabs.addTab(self._make_mmpbsa_tab(), "")
        self.results = ResultsTab(self.project, self.tr_)
        self.results.install_requested.connect(self.show_requirements_installer)
        self.tabs.addTab(self.results, "")
        self.project.changed.connect(self._on_project_changed)
        self._after_language_change()
        self._restore_project()

    def _restore_project(self):
        """Reabre o último projeto usado; logo após uma migração abre o projeto migrado (histórico antigo)."""
        name = self.settings.value("last_project", "") or ""
        path = os.path.join(self.codyn_dir, "PROJECTS", name) if name else ""
        if self._migration and not os.path.isdir(path):
            path = self._migration[0]
        if path and os.path.isdir(path):
            self.project.open(path)

    def _on_project_changed(self, path: str):
        if path:
            self.settings.setValue("last_project", os.path.basename(path))
        self.results.refresh_runs()
        self.refresh_mmpbsa_runs()
        self._update_title()

    def _update_title(self):
        title = self.tr_.t("app_title")
        self.setWindowTitle(f"{title}  —  {self.project.name}" if self.project.is_open else title)

    def _version_label(self):
        lbl = QLabel(f"v{VERSAO}")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"font-size:8pt;color:{PALETTE['muted']};")
        return lbl

    def _make_step_tab(self, key: str, title_key: str, with_progress: bool) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 12, 16, 12)
        title = make_title()
        self.tr_.tr(title_key, title.setText)
        lay.addWidget(title)

        if key == "lig":
            self.runs_table = QTableWidget(0, 3)
            self.runs_table.setMaximumHeight(150)
            self.runs_table.verticalHeader().setVisible(False)
            self.runs_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.runs_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.runs_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.runs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            self.runs_table.cellDoubleClicked.connect(self._open_run_row)
            self.tr_.on_change(lambda _l: self._retitle_runs_table())
            self._retitle_runs_table()
            lay.addWidget(self.runs_table)

        console = LogConsole()
        self.consoles[key] = console
        lay.addWidget(console, 1)

        if with_progress:
            row = QHBoxLayout()
            bar = make_progress("%v / %m")
            lbl = QLabel()
            lbl.setMinimumWidth(240)
            self.tr_.tr("lbl_remaining_unknown", lbl.setText)
            self.bars[key] = bar
            self.remaining[key] = lbl
            row.addWidget(bar, 4)
            row.addWidget(lbl, 1)
            lay.addLayout(row)

        row = QHBoxLayout()
        btn_cancel = QPushButton(); set_role(btn_cancel, "danger"); btn_cancel.setFixedWidth(160)
        self.tr_.tr("btn_cancel", btn_cancel.setText)
        btn_cancel.clicked.connect(self.cancel_all)
        row.addStretch()
        row.addWidget(btn_cancel)
        row.addStretch()
        lay.addLayout(row)
        lay.addWidget(self._version_label())
        return tab

    def _retitle_runs_table(self):
        self.runs_table.setHorizontalHeaderLabels([self.tr_.t("runs_col_folder"), self.tr_.t("runs_col_ligand"),
                                                   self.tr_.t("runs_col_status")])

    def _open_run_row(self, row, _col):
        item = self.runs_table.item(row, 0)
        if item:
            QDesktopServices.openUrl(QUrl.fromLocalFile(item.data(Qt.UserRole)))

    def _set_run_status(self, folder: str, text: str):
        for r in range(self.runs_table.rowCount()):
            if self.runs_table.item(r, 0).data(Qt.UserRole) == folder:
                self.runs_table.setItem(r, 2, QTableWidgetItem(text))
                return

    # ------------------------------------------------------------------ STEP 6 (MM/PBSA) ------------------------------------------------------------------
    def _make_mmpbsa_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 12, 16, 12)
        title = make_title()
        self.tr_.tr("step6_title", title.setText)
        lay.addWidget(title)

        grp = CollapsibleGroupBox()
        self.tr_.tr("mm_grp_params", grp.setTitle)
        grid = QGridLayout(grp)
        grid.setContentsMargins(14, 18, 14, 12)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)
        self.mm_run = QComboBox()
        self.mm_refresh = QPushButton("⟳"); self.mm_refresh.setFixedWidth(36); set_role(self.mm_refresh, "secondary")
        row = QHBoxLayout(); row.addWidget(self.mm_run, 1); row.addWidget(self.mm_refresh)
        self.mm_fields = {
            "n_threads": QSpinBox(), "frame_start": QSpinBox(), "frame_end": QSpinBox(), "interval": QSpinBox(),
            "verbose": QSpinBox(), "igb": QSpinBox(), "sltcon": QLineEdit("0.15"),
            "idecomp": QSpinBox(), "dec_verbose": QSpinBox(),
        }
        f = self.mm_fields
        f["n_threads"].setRange(1, 256); f["n_threads"].setValue(max(1, (os.cpu_count() or 2) // 2))
        f["frame_start"].setRange(1, 10_000_000); f["frame_start"].setValue(1)
        f["frame_end"].setRange(1, 10_000_000); f["frame_end"].setValue(2000)
        f["interval"].setRange(1, 100000); f["interval"].setValue(1)
        f["verbose"].setRange(0, 3); f["verbose"].setValue(2)
        f["igb"].setRange(1, 8); f["igb"].setValue(5)
        f["idecomp"].setRange(0, 4); f["idecomp"].setValue(2)
        f["dec_verbose"].setRange(0, 3); f["dec_verbose"].setValue(3)
        # linha 0: pasta da execução (largura toda); abaixo, os 9 parâmetros em 3 colunas × 3 linhas,
        # cada par rótulo+campo ocupando um terço da largura
        lbl = QLabel(); self.tr_.tr("mm_run", lbl.setText)
        top = QHBoxLayout(); top.setSpacing(10); top.addWidget(lbl); top.addLayout(row, 1)
        grid.addLayout(top, 0, 0, 1, 3)
        for i, (key, w) in enumerate(f.items()):
            l = QLabel(); self.tr_.tr(f"mm_{key}", l.setText)
            cell = QHBoxLayout(); cell.setSpacing(8)
            cell.addWidget(l); cell.addWidget(w, 1)
            grid.addLayout(cell, 1 + i // 3, i % 3)
        for c in range(3):
            grid.setColumnStretch(c, 1)
            grid.setColumnMinimumWidth(c, 0)
        lay.addWidget(grp)

        self.mm_console = LogConsole()
        lay.addWidget(self.mm_console, 1)

        btns = QHBoxLayout()
        self.mm_cancel = QPushButton(); set_role(self.mm_cancel, "danger"); self.mm_cancel.setFixedWidth(150)
        self.mm_single = QPushButton(); set_role(self.mm_single, "primary"); self.mm_single.setFixedWidth(170)
        self.mm_all = QPushButton(); set_role(self.mm_all, "primary"); self.mm_all.setFixedWidth(190)
        self.tr_.tr("btn_cancel", self.mm_cancel.setText)
        self.tr_.tr("mm_btn_single", self.mm_single.setText)
        self.tr_.tr("mm_btn_all", self.mm_all.setText)
        btns.addWidget(self.mm_cancel); btns.addStretch(); btns.addWidget(self.mm_single); btns.addWidget(self.mm_all)
        lay.addLayout(btns)
        lay.addWidget(self._version_label())
        self.mm_cancel.clicked.connect(self.cancel_mmpbsa)
        self.mm_single.clicked.connect(lambda: self.run_mmpbsa(all_pending=False))
        self.mm_all.clicked.connect(lambda: self.run_mmpbsa(all_pending=True))
        self.mm_refresh.clicked.connect(self.refresh_mmpbsa_runs)
        self.refresh_mmpbsa_runs()
        return tab

    def refresh_mmpbsa_runs(self):
        cur = self.mm_run.currentText()
        self.mm_run.clear()
        runs_dir = self.project.runs_dir
        self.mm_run.addItems([d for d in list_run_folders(runs_dir)
                              if find_production_tag(os.path.join(runs_dir, d))])
        i = self.mm_run.findText(cur)
        if i >= 0:
            self.mm_run.setCurrentIndex(i)

    def run_mmpbsa(self, all_pending: bool):
        if self.mmpbsa_worker is not None and self.mmpbsa_worker.isRunning():
            return
        runs_dir = self.project.runs_dir
        if all_pending:
            folders = [os.path.join(runs_dir, d) for d in list_run_folders(runs_dir)
                       if find_production_tag(os.path.join(runs_dir, d))
                       and not os.path.exists(os.path.join(runs_dir, d, "FINAL_RESULTS_MMPBSA.dat"))]
        else:
            name = self.mm_run.currentText()
            folders = [os.path.join(runs_dir, name)] if name else []
        if not folders:
            QMessageBox.information(self, self.tr_.t("msg_attention"), self.tr_.t("mm_nothing"))
            return
        f = self.mm_fields
        params = {
            "frame_start": f["frame_start"].value(), "frame_end": f["frame_end"].value(),
            "interval": f["interval"].value(), "verbose": f["verbose"].value(), "igb": f["igb"].value(),
            "sltcon": f["sltcon"].text().strip() or "0.15", "istrng": 0.15, "fill_ratio": 4.0,
            "idecomp": f["idecomp"].value(), "dec_verbose": f["dec_verbose"].value(),
        }
        self.token = CancelToken()
        self.mm_console.clear()
        self.mm_console.log(self.tr_.t("mm_starting", n=len(folders)), stamp=True)
        self.mmpbsa_worker = MMPBSAWorker(folders, params, f["n_threads"].value(), self.token, self)
        self.mmpbsa_worker.log_signal.connect(lambda m: self.mm_console.log(m, stamp=True))
        self.mmpbsa_worker.finished_signal.connect(self._mmpbsa_finished)
        self.mm_single.setEnabled(False)
        self.mm_all.setEnabled(False)
        self.mmpbsa_worker.start()

    def _mmpbsa_finished(self, ok: bool):
        self.mm_single.setEnabled(True)
        self.mm_all.setEnabled(True)
        self.mm_console.log(self.tr_.t("mm_done_ok" if ok else "mm_done_fail"), stamp=True)
        if ok:
            self.tabs.setCurrentIndex(8)

    def cancel_mmpbsa(self):
        if self.mmpbsa_worker is not None and self.mmpbsa_worker.isRunning():
            self.token.cancel()

    # ------------------------------------------------------------------ execução do pipeline ------------------------------------------------------------------
    def start_run(self, cfg: RunConfig, infos: list):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, self.tr_.t("msg_attention"), self.tr_.t("run_busy"))
            return
        for c in self.consoles.values():
            c.clear()
        for key in self.bars:
            self.bars[key].setMaximum(1)
            self.bars[key].setValue(0)
            self.tr_.tr("lbl_remaining_unknown", self.remaining[key].setText)
        self.runs_table.setRowCount(len(infos))
        for r, info in enumerate(infos):
            it = QTableWidgetItem(os.path.basename(info["run_folder"]))
            it.setData(Qt.UserRole, info["run_folder"])
            self.runs_table.setItem(r, 0, it)
            self.runs_table.setItem(r, 1, QTableWidgetItem(info["lig_name"]))
            self.runs_table.setItem(r, 2, QTableWidgetItem(self.tr_.t("runs_status_waiting")))
        self._runs_status = {i["run_folder"]: "run" for i in infos}
        self.token = CancelToken()
        self.worker = PipelineWorker(self.codyn_dir, cfg, infos, self.token, self)
        self.worker.log_signal.connect(self._on_log)
        self.worker.stage_signal.connect(self._on_stage)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.request_file_signal.connect(self._on_request_file)
        self.worker.run_done_signal.connect(self._on_run_done)
        self.worker.finished_signal.connect(self._on_finished)
        self.config.btn_run.setEnabled(False)
        self.tabs.setCurrentIndex(2)
        self.worker.start()

    def _on_log(self, step: str, msg: str):
        c = self.consoles.get(step)
        if c is not None:
            c.log(msg)

    def _on_stage(self, idx: int):
        if idx <= 7:
            self.tabs.setCurrentIndex(idx)
        label_key = {2: "runs_status_lig", 3: "runs_status_prot", 4: "runs_status_cell", 5: "runs_status_eq",
                     6: "runs_status_md"}.get(idx)
        if label_key:
            for folder, st in self._runs_status.items():
                if st == "run":
                    self._set_run_status(folder, self.tr_.t(label_key))

    def _on_progress(self, step: str, cur: int, total: int, remaining: int):
        bar = self.bars.get(step)
        if bar is None:
            return
        bar.setMaximum(max(total, 1))
        bar.setValue(min(cur, max(total, 1)))
        if remaining >= 0:
            h, rem = divmod(remaining, 3600)
            m, s = divmod(rem, 60)
            self.remaining[step].setText(self.tr_.t("lbl_remaining", t=f"{h:02d}:{m:02d}:{s:02d}"))

    def _on_request_file(self, req: dict):
        """Chamado na thread da GUI: o pipeline fica bloqueado até o usuário responder."""
        try:
            if req.get("kind") == "cgenff_str":
                self.tabs.setCurrentIndex(2)
                dlg = CgenffDialog(req, self.tr_, self)
                dlg.exec_()
                req["result"]["path"] = dlg.result_path
        finally:
            req["event"].set()

    def _on_run_done(self, folder: str, ok: bool, msg: str):
        self._runs_status[folder] = "ok" if ok else "failed"
        self._set_run_status(folder, self.tr_.t("runs_status_done") if ok else self.tr_.t("runs_status_failed", msg=msg))

    def _on_finished(self, ok: bool, failed: list):
        self.config.btn_run.setEnabled(True)
        self.results.refresh_runs()
        self.refresh_mmpbsa_runs()
        if self.token.is_set():
            for folder, st in self._runs_status.items():
                if st == "run":
                    self._set_run_status(folder, self.tr_.t("runs_status_cancelled"))
            QMessageBox.information(self, "CODYN", self.tr_.t("run_cancelled"))
        elif ok:
            QMessageBox.information(self, "CODYN", self.tr_.t("run_finished_ok"))
        else:
            QMessageBox.warning(self, "CODYN", self.tr_.t("run_finished_failed", n=len(failed)))

    def cancel_all(self):
        running = (self.worker is not None and self.worker.isRunning()) or \
                  (self.mmpbsa_worker is not None and self.mmpbsa_worker.isRunning())
        if not running:
            self.tabs.setCurrentIndex(0)
            return
        ans = QMessageBox.question(self, self.tr_.t("msg_attention"), self.tr_.t("run_cancel_confirm"),
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans == QMessageBox.Yes:
            self.token.cancel()
            self.tabs.setCurrentIndex(0)

    # ------------------------------------------------------------------ utilitários ------------------------------------------------------------------
    def show_requirements_installer(self):
        self.req_win = RequirementsInstaller(None, self.tr_)
        self.req_win.setWindowModality(Qt.ApplicationModal)
        self.req_win.show()
        self.req_win.raise_()
        self.req_win.activateWindow()
        self.req_win.destroyed.connect(lambda: self.home.refresh())

    def open_hw_monitor_window(self):
        script = os.path.join(self.codyn_dir, "BIN", "hw_monitor_window.py")
        if not os.path.isfile(script):
            QMessageBox.warning(self, "CODYN", self.tr_.t("msg_monitor_missing", path=script))
            return
        try:
            subprocess.Popen([sys.executable, script])
        except Exception as e:
            QMessageBox.critical(self, "CODYN", f"{e}")

    def open_terminal_window(self):
        title = "CODYN - Terminal"
        if _IS_WINDOWS:
            # Windows: PowerShell numa janela de console própria acompanhando o log ao vivo (equivalente do
            # `tail -F`). Fechar a janela não afeta o CODYN.
            log_ps = CODYN_TERMINAL_LOG.replace("'", "''")
            command = (f"$Host.UI.RawUI.WindowTitle = '{title}'; "
                       f"Get-Content -LiteralPath '{log_ps}' -Wait -Encoding UTF8")
            try:
                subprocess.Popen(["powershell", "-NoLogo", "-NoProfile", "-NoExit", "-Command", command],
                                 stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NEW_CONSOLE)
            except Exception:
                QMessageBox.warning(self, "CODYN", self.tr_.t("msg_terminal_missing", path=CODYN_TERMINAL_LOG))
            return
        tail = ["tail", "-n", "+1", "-F", CODYN_TERMINAL_LOG]
        candidates = [
            ("gnome-terminal", [f"--title={title}", "--"] + tail),
            ("x-terminal-emulator", ["-e", shlex.join(tail)]),
            ("xfce4-terminal", ["-T", title, "-e", shlex.join(tail)]),
            ("mate-terminal", ["-t", title, "-e", shlex.join(tail)]),
            ("konsole", ["-e"] + tail),
            ("xterm", ["-T", title, "-e"] + tail),
        ]
        for exe, args in candidates:
            path = shutil.which(exe)
            if path:
                try:
                    subprocess.Popen([path] + args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True)
                    return
                except Exception:
                    continue
        QMessageBox.warning(self, "CODYN", self.tr_.t("msg_terminal_missing", path=CODYN_TERMINAL_LOG))

    def show_about(self):
        QMessageBox.about(self, self.tr_.t("menu_about").replace("&", ""), self.tr_.t("about_text", versao=VERSAO))

    def closeEvent(self, event):
        busy = (self.worker is not None and self.worker.isRunning()) or \
               (self.mmpbsa_worker is not None and self.mmpbsa_worker.isRunning())
        if busy:
            ans = QMessageBox.question(self, self.tr_.t("msg_attention"), self.tr_.t("run_close_confirm"),
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ans != QMessageBox.Yes:
                event.ignore()
                return
            self.token.cancel()
            for w in (self.worker, self.mmpbsa_worker):
                if w is not None and w.isRunning():
                    w.wait(8000)
        event.accept()

    # ------------------------------------------------------------------ verificações iniciais ------------------------------------------------------------------
    def post_start_checks(self):
        st = self.status
        if self._migration:
            path, moved, copied = self._migration
            QMessageBox.information(self, "CODYN", self.tr_.t("msg_migrated", path=path, moved=moved, copied=copied))
        if st.get("missing_folders"):
            QMessageBox.warning(self, "CODYN", self.tr_.t("msg_missing_folders", folders=", ".join(st["missing_folders"]), url=GITHUB_URL))
        problems = list(st.get("missing_tools", []))
        problems += missing_required_python()
        if problems:
            box = QMessageBox(QMessageBox.Warning, "CODYN", self.tr_.t("msg_missing_requirements", items=", ".join(problems)),
                              QMessageBox.NoButton, self)
            b_inst = box.addButton(self.tr_.t("btn_open_installer"), QMessageBox.AcceptRole)
            box.addButton(self.tr_.t("btn_close"), QMessageBox.RejectRole)
            box.exec_()
            if box.clickedButton() is b_inst:
                self.show_requirements_installer()


def main():
    if _IS_WINDOWS:
        # identidade própria na barra de tarefas (senão o Windows agrupa a janela sob o ícone do Python)
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MoisesMaia.CODYN")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("CODYN")
    app.setStyleSheet(SS_MAIN)
    splash = SplashScreen(CODYN_DIR)
    splash.show()
    splash.start_checks()
    holder = {}

    def start_mainwindow(status):
        splash.close()
        win = MainWindow(status)
        holder["win"] = win
        win.show()
        QTimer.singleShot(300, win.post_start_checks)

    splash.check_complete.connect(start_mainwindow)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
