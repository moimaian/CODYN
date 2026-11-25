# -*- coding: utf-8 -*-
"""Diálogos do CODYN. Hoje: importação do arquivo de parâmetros do CGenFF (.str) sem sair da interface."""

import glob
import os
import shutil
import time
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices, QGuiApplication
from PyQt5.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

from BIN.i18n import Translator
from BIN.module_ligands import parse_cgenff_str, validate_cgenff_str
from BIN.theme import PALETTE, ensure_button_fits, set_role

CGENFF_URL = "https://cgenff.silcsbio.com/"


class CgenffDialog(QDialog):
    """Guia o usuário no CGenFF: abre o site, mostra o MOL2 pronto para envio, monitora a pasta
    Downloads e importa/valida o .str — o pipeline continua automaticamente depois."""

    def __init__(self, req: dict, tr_: Translator, parent=None):
        super().__init__(parent)
        self.tr_ = tr_
        self.req = req
        self.result_path: Optional[str] = None
        self._opened_at = time.time()
        self._detected: Optional[str] = None
        self.setWindowTitle(tr_.t("cgenff_title"))
        self.setModal(True)
        self.setMinimumWidth(620)

        lay = QVBoxLayout(self)
        intro = QLabel(tr_.t("cgenff_intro", lig=req["lig_name"], charge=f"{req['net_charge']:+d}"))
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.RichText)
        lay.addWidget(intro)

        self.lbl_mol2 = QLabel(f"<b>MOL2:</b> <code>{req['mol2']}</code>")
        self.lbl_mol2.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_mol2.setWordWrap(True)
        lay.addWidget(self.lbl_mol2)

        row = QHBoxLayout()
        self.btn_site = QPushButton(tr_.t("cgenff_btn_site")); set_role(self.btn_site, "select")
        self.btn_folder = QPushButton(tr_.t("cgenff_btn_folder")); set_role(self.btn_folder, "secondary")
        self.btn_copy = QPushButton(tr_.t("cgenff_btn_copy")); set_role(self.btn_copy, "secondary")
        for b in (self.btn_site, self.btn_folder, self.btn_copy):
            row.addWidget(b)
        lay.addLayout(row)

        self.lbl_detect = QLabel(tr_.t("cgenff_waiting"))
        self.lbl_detect.setStyleSheet(f"color:{PALETTE['muted']};")
        self.lbl_detect.setWordWrap(True)
        lay.addWidget(self.lbl_detect)

        row2 = QHBoxLayout()
        self.btn_use = QPushButton(tr_.t("cgenff_btn_use")); set_role(self.btn_use, "primary"); self.btn_use.setEnabled(False)
        self.btn_import = QPushButton(tr_.t("cgenff_btn_import")); set_role(self.btn_import, "primary")
        self.btn_skip = QPushButton(tr_.t("cgenff_btn_skip")); set_role(self.btn_skip, "danger")
        row2.addWidget(self.btn_use)
        row2.addWidget(self.btn_import)
        row2.addStretch()
        row2.addWidget(self.btn_skip)
        lay.addLayout(row2)

        self.btn_site.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(CGENFF_URL)))
        self.btn_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(req["mol2"]))))
        self.btn_copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(req["mol2"]))
        self.btn_import.clicked.connect(self._import)
        self.btn_use.clicked.connect(lambda: self._accept_file(self._detected))
        self.btn_skip.clicked.connect(self.reject)

        for b in self.findChildren(QPushButton):
            ensure_button_fits(b)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._scan)
        self._timer.start(1500)

    def _scan(self):
        """Procura um .str novo (modificado após a abertura do diálogo) em Downloads e na pasta da execução."""
        dirs = [os.path.join(os.path.expanduser("~"), "Downloads"), os.path.expanduser("~/Transferências"),
                self.req["run_folder"]]
        best = None
        for d in dirs:
            for f in glob.glob(os.path.join(d, "*.str")):
                try:
                    m = os.path.getmtime(f)
                except OSError:
                    continue
                if m >= self._opened_at - 1 and (best is None or m > best[0]):
                    best = (m, f)
        if best and best[1] != self._detected and validate_cgenff_str(best[1])[0]:
            self._detected = best[1]
            self.lbl_detect.setText(self.tr_.t("cgenff_detected", name=os.path.basename(best[1])))
            self.lbl_detect.setStyleSheet(f"color:{PALETTE['accent']};font-weight:bold;")
            self.btn_use.setEnabled(True)

    def _import(self):
        start = os.path.join(os.path.expanduser("~"), "Downloads")
        path, _ = QFileDialog.getOpenFileName(self, self.tr_.t("cgenff_btn_import"),
                                              start if os.path.isdir(start) else os.path.expanduser("~"),
                                              "CGenFF stream (*.str);;All files (*)")
        if path:
            self._accept_file(path)

    def _accept_file(self, path: Optional[str]):
        if not path:
            return
        ok, why = validate_cgenff_str(path)
        if not ok:
            QMessageBox.warning(self, self.tr_.t("msg_attention"), self.tr_.t("cgenff_invalid", why=why))
            return
        info = parse_cgenff_str(path)
        pen = (info["param_penalty"] or 0, info["charge_penalty"] or 0)
        if max(pen) > 50:
            ans = QMessageBox.question(self, self.tr_.t("msg_attention"),
                                       self.tr_.t("cgenff_high_penalty", pp=pen[0], cp=pen[1]),
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ans != QMessageBox.Yes:
                return
        dst = os.path.join(self.req["run_folder"], os.path.basename(path))
        try:
            if os.path.abspath(dst) != os.path.abspath(path):
                shutil.copy2(path, dst)
        except OSError:
            dst = path
        self.result_path = dst
        self._timer.stop()
        self.accept()

    def done(self, r):
        self._timer.stop()
        super().done(r)
