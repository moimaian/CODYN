# -*- coding: utf-8 -*-
"""HOME — logo, hardware (CPU/GPU), software (bibliotecas e ferramentas) e pipeline do CODYN."""

import os
from typing import List, Tuple

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QFormLayout, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from BIN import hw_info
from BIN.i18n import Translator
from BIN.theme import PALETTE, set_role
from BIN.versao import VERSAO
from BIN.widgets import CollapsibleGroupBox, make_kv_label, make_separator

# (aba de destino, chave i18n do nome, chave i18n da descrição)
PIPELINE_STEPS: List[Tuple[int, str, str]] = [
    (1, "home_step0", "home_step0_desc"),
    (2, "home_step1", "home_step1_desc"),
    (3, "home_step2", "home_step2_desc"),
    (4, "home_step3", "home_step3_desc"),
    (5, "home_step4", "home_step4_desc"),
    (6, "home_step5", "home_step5_desc"),
    (7, "home_step6", "home_step6_desc"),
    (8, "home_step7", "home_step7_desc"),
]


class HomeInfoWorker(QThread):
    """Coleta hardware/software fora da thread da GUI (lscpu, nvidia-smi, gmx --version...)."""
    done = pyqtSignal(object)

    def run(self):
        info = {"cpu": [], "gpu": [], "sw": [], "tools": []}
        try:
            info["cpu"] = hw_info.cpu_info()
        except Exception:
            pass
        try:
            info["gpu"] = hw_info.gpu_info()
        except Exception:
            pass
        try:
            for name, mod, attr in hw_info.PY_LIBS:
                info["sw"].append((name, hw_info.python_lib_version(mod, attr)))
            info["tools"] = hw_info.external_tools()
        except Exception:
            pass
        self.done.emit(info)


class HomeTab(QWidget):
    start_requested = pyqtSignal()
    install_requested = pyqtSignal()
    content_ready = pyqtSignal()  # dados de hardware/software carregados e exibidos

    def __init__(self, codyn_dir: str, tr_: Translator, parent=None):
        super().__init__(parent)
        self.codyn_dir = codyn_dir
        self.tr_ = tr_
        self._worker = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(scroll)
        self.inner = inner = QWidget()
        scroll.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(30, 12, 30, 8)
        lay.setSpacing(8)

        # cabeçalho compacto: logo ao lado do título (economiza altura para não precisar de rolagem)
        head = QHBoxLayout()
        head.setSpacing(22)
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo_path = os.path.join(codyn_dir, "ICONS", "LOGO_CODYN2.png")
        if os.path.exists(logo_path):
            logo.setPixmap(QPixmap(logo_path).scaledToWidth(96, Qt.SmoothTransformation))
        else:
            logo.setText("CODYN")
            logo.setStyleSheet(f"font-size:30pt;font-weight:bold;color:{PALETTE['brand']};")
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addStretch()
        t1 = QLabel()
        t1.setStyleSheet("font-size:14pt;font-weight:bold;")
        self.tr_.tr("home_title", t1.setText)
        t2 = QLabel()
        t2.setStyleSheet(f"font-size:10pt;font-style:italic;color:{PALETTE['muted']};")
        self.tr_.tr("home_subtitle", t2.setText)
        titles.addWidget(t1)
        titles.addWidget(t2)
        titles.addStretch()
        head.addStretch()
        head.addWidget(logo)
        head.addLayout(titles)
        head.addStretch()
        lay.addLayout(head)
        lay.addWidget(make_separator())

        # --- hardware ---
        hw_row = QHBoxLayout()
        self.cpu_grp, self.cpu_form = self._kv_group("home_grp_cpu")
        self.gpu_grp, self.gpu_form = self._kv_group("home_grp_gpu")
        hw_row.addWidget(self.cpu_grp)
        hw_row.addWidget(self.gpu_grp)
        lay.addLayout(hw_row)

        # --- software ---
        self.sw_grp = CollapsibleGroupBox()
        self.tr_.tr("home_grp_sw", self.sw_grp.setTitle)
        self.sw_grid = QGridLayout(self.sw_grp)
        self.sw_grid.setContentsMargins(14, 18, 14, 10)
        self.sw_grid.setHorizontalSpacing(24)
        self.sw_grid.setVerticalSpacing(4)
        lay.addWidget(self.sw_grp)

        # --- pipeline ---
        pipe = CollapsibleGroupBox()
        self.tr_.tr("home_grp_pipeline", pipe.setTitle)
        grid = QGridLayout(pipe)
        grid.setContentsMargins(14, 18, 14, 10)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)
        for row, (_tab, name_key, desc_key) in enumerate(PIPELINE_STEPS):
            name = QLabel()
            name.setStyleSheet(f"font-weight:bold;color:{PALETTE['accent']};")
            self.tr_.tr(name_key, lambda txt, w=name: w.setText(txt))
            desc = QLabel()
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color:{PALETTE['text']};")
            self.tr_.tr(desc_key, desc.setText)
            grid.addWidget(name, row, 0, Qt.AlignTop)
            grid.addWidget(desc, row, 1)
        grid.setColumnStretch(1, 1)
        lay.addWidget(pipe)

        lay.addWidget(make_separator())
        btns = QHBoxLayout()
        btns.addStretch()
        self.btn_start = QPushButton(); self.btn_start.setFixedSize(170, 38); set_role(self.btn_start, "primary")
        self.btn_install = QPushButton(); self.btn_install.setFixedSize(210, 38); set_role(self.btn_install, "select")
        self.btn_refresh = QPushButton(); self.btn_refresh.setFixedSize(150, 38); set_role(self.btn_refresh, "secondary")
        self.tr_.tr("home_btn_start", self.btn_start.setText)
        self.tr_.tr("home_btn_install", self.btn_install.setText)
        self.tr_.tr("home_btn_refresh", self.btn_refresh.setText)
        btns.addWidget(self.btn_start)
        btns.addSpacing(12)
        btns.addWidget(self.btn_install)
        btns.addSpacing(12)
        btns.addWidget(self.btn_refresh)
        btns.addStretch()
        lay.addLayout(btns)
        foot = QLabel(f"v{VERSAO}  ·  © 2025–2026 CEB/UFPR  ·  GPL-3.0")
        foot.setAlignment(Qt.AlignCenter)
        foot.setStyleSheet(f"color:{PALETTE['muted']};font-size:8pt;")
        lay.addWidget(foot)

        self.btn_start.clicked.connect(self.start_requested.emit)
        self.btn_install.clicked.connect(self.install_requested.emit)
        self.btn_refresh.clicked.connect(self.refresh)
        self.tr_.on_change(lambda _l: self._rerender())
        self._info = None
        self.refresh()

    def _kv_group(self, title_key: str):
        grp = CollapsibleGroupBox()
        self.tr_.tr(title_key, grp.setTitle)
        form = QFormLayout(grp)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(4)
        form.setContentsMargins(14, 18, 14, 10)
        return grp, form

    # ------------------------------------------------------------------ dados ------------------------------------------------------------------
    def extra_size(self):
        """Quanto falta (largura, altura) para o conteúdo caber sem barras de rolagem.
        A altura considera a quebra de linha dos textos na largura que a janela terá."""
        lay = self.inner.layout()
        lay.activate()
        vp = self.scroll.viewport().size()
        dw = max(0, lay.minimumSize().width() - vp.width())
        width = vp.width() + dw
        need_h = lay.totalHeightForWidth(width) if lay.hasHeightForWidth() else lay.sizeHint().height()
        return dw, max(0, need_h - vp.height())

    def refresh(self):
        if self._worker is not None and self._worker.isRunning():
            return
        self.btn_refresh.setEnabled(False)
        self._worker = HomeInfoWorker(self)
        self._worker.done.connect(self._on_info)
        self._worker.start()

    def _on_info(self, info):
        self._info = info
        self.btn_refresh.setEnabled(True)
        self._rerender()
        self.content_ready.emit()

    @staticmethod
    def _clear(layout):
        """Remove os widgets na hora (sem esperar o event loop), evitando sobreposição ao retraduzir."""
        if isinstance(layout, QFormLayout):
            while layout.rowCount():
                layout.removeRow(0)
            return
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _rerender(self):
        if not self._info:
            return
        for form, rows in ((self.cpu_form, self._info["cpu"]), (self.gpu_form, self._info["gpu"])):
            self._clear(form)
            for key, value in rows:
                form.addRow(make_kv_label(self.tr_.t(key)), make_kv_label(str(value), muted=False))
        self._clear(self.sw_grid)
        entries: List[Tuple[str, str, str]] = []  # (nome, versão|'', dica)
        for name, ver in self._info["sw"]:
            entries.append((name, ver, ""))
        for name, path, ver in self._info["tools"]:
            entries.append((name, (ver or "OK") if path else "", path))
        cols = 4
        for i, (name, ver, tip) in enumerate(entries):
            r, c = divmod(i, cols)
            lbl = QLabel(f"{name}")
            lbl.setStyleSheet(f"color:{PALETTE['muted']};font-size:9pt;")
            ok = bool(ver)
            val = QLabel(ver if ok else self.tr_.t("home_not_installed"))
            val.setStyleSheet(f"font-weight:bold;font-size:9pt;color:{PALETTE['ok'] if ok else PALETTE['danger']};")
            val.setToolTip(tip or ver)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            cell = QHBoxLayout()
            cell.addWidget(lbl)
            cell.addWidget(val)
            cell.addStretch()
            wrap = QWidget()
            wrap.setLayout(cell)
            cell.setContentsMargins(0, 0, 0, 0)
            self.sw_grid.addWidget(wrap, r, c)
