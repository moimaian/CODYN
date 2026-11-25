# -*- coding: utf-8 -*-
"""RESULTS — visualização dos resultados (pré e pós-produção) e gráficos combinados."""

import os
from datetime import datetime
from typing import List

from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import Qt, QThread, QUrl, pyqtSignal

from BIN.i18n import Translator
from BIN.mdp_tools import read_ndx_groups
from BIN.theme import ensure_button_fits, set_role
from BIN.tools import CancelToken, PipelineCancelled
from BIN.widgets import CollapsibleGroupBox, LogConsole, make_title

PRE_CHARTS = ["Potential Energy-Minimization", "Temperature-NVT", "Pressure-NPT", "Density-NPT"]
POST_CHARTS = ["RMSD", "RMSD Dist", "RMSF", "SASA", "HBONDs", "Center Of Mass", "Rgyration"]
ONE_GROUP = {"RMSD Dist", "RMSF", "Center Of Mass", "SASA", "Rgyration"}


def list_run_folders(runs: str) -> List[str]:
    """Pastas de execução dentro de <projeto>/RUNS."""
    if not os.path.isdir(runs):
        return []
    return sorted((d for d in os.listdir(runs) if os.path.isdir(os.path.join(runs, d))), reverse=True)


def parse_xvg_columns(path: str):
    """Colunas numéricas de um .xvg: (xs, ys) das duas primeiras colunas."""
    xs, ys = [], []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith(("#", "@")):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    xs.append(float(parts[0]))
                    ys.append(float(parts[1]))
                except ValueError:
                    continue
    return xs, ys


class ReportWorker(QThread):
    """Gera o relatório final em segundo plano (as análises do gmx podem demorar)."""
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(str)     # caminho do .docx
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, project_dir: str, lang: str, token: CancelToken, parent=None):
        super().__init__(parent)
        self.project_dir, self.lang, self.token = project_dir, lang, token

    def run(self):
        try:
            from BIN import module_report
            self.finished_ok.emit(module_report.generate_final_report(
                self.project_dir, self.lang, progress=self.progress.emit, token=self.token))
        except PipelineCancelled:
            self.cancelled.emit()
        except Exception as e:  # noqa: BLE001 - qualquer falha vira mensagem para o usuário
            self.failed.emit(f"{type(e).__name__}: {e}")


class ResultsTab(QWidget):
    install_requested = pyqtSignal()

    def __init__(self, project, tr_: Translator, parent=None):
        super().__init__(parent)
        self.project = project
        self.tr_ = tr_
        self.merge_state = {"base_file": None, "base_x": None, "base_label": None, "y_series": []}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        title = make_title()
        self.tr_.tr("res_title", title.setText)
        root.addWidget(title)

        # --- linha 1: "Seleção" (metade esquerda) | "Opções do gráfico" (metade direita, itens empilhados) ---
        top = QHBoxLayout()
        top.setSpacing(14)
        grp = CollapsibleGroupBox()
        self.tr_.tr("res_grp_select", grp.setTitle)
        form = QFormLayout(grp)
        form.setContentsMargins(14, 18, 14, 10)
        form.setVerticalSpacing(8)
        self.combo_run = QComboBox()
        self.btn_refresh = QPushButton("⟳"); self.btn_refresh.setFixedWidth(36); set_role(self.btn_refresh, "secondary")
        self.btn_open = QPushButton(); set_role(self.btn_open, "secondary")
        self.tr_.tr("btn_open_folder", self.btn_open.setText)
        row = QHBoxLayout(); row.addWidget(self.combo_run, 1); row.addWidget(self.btn_refresh); row.addWidget(self.btn_open)
        self.combo_step = QComboBox()
        self.combo_chart = QComboBox()
        self.combo_g1 = QComboBox(); self.combo_g2 = QComboBox()
        self.lbl_run, self.lbl_step, self.lbl_chart = QLabel(), QLabel(), QLabel()
        self.lbl_g1, self.lbl_g2 = QLabel(), QLabel()
        for lbl, key in ((self.lbl_run, "res_run"), (self.lbl_step, "res_step"), (self.lbl_chart, "res_chart"),
                         (self.lbl_g1, "res_group1"), (self.lbl_g2, "res_group2")):
            self.tr_.tr(key, lbl.setText)
        form.addRow(self.lbl_run, row)
        form.addRow(self.lbl_step, self.combo_step)
        form.addRow(self.lbl_chart, self.combo_chart)
        form.addRow(self.lbl_g1, self.combo_g1)
        form.addRow(self.lbl_g2, self.combo_g2)
        self._fill_steps()
        self.tr_.on_change(lambda _l: self._fill_steps())

        opt = CollapsibleGroupBox()
        self.tr_.tr("res_grp_options", opt.setTitle)
        ol = QVBoxLayout(opt)
        ol.setContentsMargins(14, 18, 14, 10)
        ol.setSpacing(8)
        self.chk_legend = QCheckBox(); self.tr_.tr("res_legend", self.chk_legend.setText)
        self.chk_ma = QCheckBox(); self.tr_.tr("res_moving_avg", self.chk_ma.setText)
        self.ma_value = QLineEdit("20"); self.ma_value.setFixedWidth(70); self.ma_value.setEnabled(False)
        self.chk_ma.toggled.connect(self.ma_value.setEnabled)
        ma_row = QHBoxLayout(); ma_row.addWidget(self.chk_ma); ma_row.addWidget(self.ma_value); ma_row.addStretch()
        self.chk_merge = QCheckBox(); self.tr_.tr("res_merge", self.chk_merge.setText)
        self.btn_add_chart = QPushButton(); set_role(self.btn_add_chart, "secondary")
        self.tr_.tr("res_add_chart", self.btn_add_chart.setText)
        self.ed_list = QPlainTextEdit(); self.ed_list.setReadOnly(True); self.ed_list.setMinimumHeight(70)
        self.btn_add_chart.setEnabled(False); self.ed_list.setEnabled(False)
        self.chk_merge.toggled.connect(self._toggle_merge)
        self.btn_add_chart.clicked.connect(self.add_chart_to_list)
        merge_row = QHBoxLayout(); merge_row.addWidget(self.chk_merge); merge_row.addSpacing(8); merge_row.addWidget(self.btn_add_chart)
        self.btn_clear = QPushButton(); set_role(self.btn_clear, "danger"); self.btn_clear.setFixedWidth(150)
        self.btn_view = QPushButton(); set_role(self.btn_view, "primary"); self.btn_view.setFixedWidth(150)
        self.tr_.tr("btn_clear", self.btn_clear.setText)
        self.tr_.tr("res_btn_view", self.btn_view.setText)
        btn_row = QHBoxLayout(); btn_row.addWidget(self.btn_clear); btn_row.addStretch(); btn_row.addWidget(self.btn_view)
        # coluna 0: os 3 checkboxes (e o botão Add .xvg); coluna 1: a lista dos .xvg do merge, mesclando as 3 linhas
        opt_grid = QGridLayout()
        opt_grid.setHorizontalSpacing(14); opt_grid.setVerticalSpacing(8)
        opt_grid.addWidget(self.chk_legend, 0, 0)
        opt_grid.addLayout(ma_row, 1, 0)
        opt_grid.addLayout(merge_row, 2, 0)
        opt_grid.addWidget(self.ed_list, 0, 1, 3, 1)
        opt_grid.setColumnStretch(0, 0); opt_grid.setColumnStretch(1, 1)
        ol.addLayout(opt_grid)
        ol.addSpacing(4)
        ol.addLayout(btn_row)
        for g in (grp, opt):   # cada grupo ocupa metade da largura, sem impor a do conteúdo à janela
            g.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        top.addWidget(grp, 1, Qt.AlignTop)
        top.addWidget(opt, 1, Qt.AlignTop)
        root.addLayout(top)

        self.status = LogConsole()
        root.addWidget(self.status, 1)

        # --- última linha: relatório final, centralizado ---
        last = QHBoxLayout()
        self.btn_report = QPushButton(); set_role(self.btn_report, "select"); self.btn_report.setFixedSize(260, 40)
        self.tr_.tr("res_btn_report", self.btn_report.setText)
        last.addStretch(); last.addWidget(self.btn_report); last.addStretch()
        root.addLayout(last)
        self._report_worker = None
        self._report_token = None
        self.btn_report.clicked.connect(self.on_report)

        self.combo_step.currentIndexChanged.connect(self._on_step)
        self.combo_chart.currentIndexChanged.connect(self._on_chart)
        self.combo_run.currentIndexChanged.connect(self._update_groups)
        self.btn_refresh.clicked.connect(self.refresh_runs)
        self.btn_open.clicked.connect(self.open_run_folder)
        self.btn_clear.clicked.connect(self.status.clear)
        self.btn_view.clicked.connect(self.on_view)
        self.project.changed.connect(lambda _p: self.refresh_runs())
        self.refresh_runs()
        self._on_step()

    # ---------------------------------------------------------------- estado ----------------------------------------------------------------
    def _fill_steps(self):
        idx = self.combo_step.currentIndex()
        self.combo_step.blockSignals(True)
        self.combo_step.clear()
        self.combo_step.addItem(self.tr_.t("res_pre"), "Pre-production")
        self.combo_step.addItem(self.tr_.t("res_post"), "Post-production")
        self.combo_step.setCurrentIndex(max(idx, 0))
        self.combo_step.blockSignals(False)

    @property
    def runs_dir(self) -> str:
        return self.project.runs_dir

    def refresh_runs(self, select: str = ""):
        cur = select or self.combo_run.currentText()
        self.combo_run.blockSignals(True)
        self.combo_run.clear()
        self.combo_run.addItems(list_run_folders(self.runs_dir))
        if cur:
            i = self.combo_run.findText(cur)
            if i >= 0:
                self.combo_run.setCurrentIndex(i)
        self.combo_run.blockSignals(False)
        self._update_groups()

    def _on_step(self):
        post = self.combo_step.currentData() == "Post-production"
        self.combo_chart.blockSignals(True)
        self.combo_chart.clear()
        self.combo_chart.addItems(POST_CHARTS if post else PRE_CHARTS)
        self.combo_chart.blockSignals(False)
        self._on_chart()
        if post:
            self._update_groups()

    def _on_chart(self):
        post = self.combo_step.currentData() == "Post-production"
        chart = self.combo_chart.currentText()
        g1 = post
        g2 = post and chart not in ONE_GROUP
        for w in (self.lbl_g1, self.combo_g1):
            w.setEnabled(g1)
        for w in (self.lbl_g2, self.combo_g2):
            w.setEnabled(g2)

    def _update_groups(self):
        self.combo_g1.clear(); self.combo_g2.clear()
        run = self.combo_run.currentText()
        if not run:
            return
        groups = read_ndx_groups(os.path.join(self.runs_dir, run, "index.ndx"))
        if not groups:
            for c in (self.combo_g1, self.combo_g2):
                c.addItem(self.tr_.t("res_no_index"))
            return
        for i, name in enumerate(groups):
            for c in (self.combo_g1, self.combo_g2):
                c.addItem(f"{i} - {name}", i)

    def open_run_folder(self):
        run = self.combo_run.currentText()
        if run:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.join(self.runs_dir, run)))

    def log(self, msg: str):
        self.status.log(msg, stamp=True)

    # ---------------------------------------------------------------- visualização ----------------------------------------------------------------
    def _ma_value(self) -> int:
        try:
            return max(1, int(self.ma_value.text()))
        except ValueError:
            return 20

    def on_view(self):
        if self.chk_merge.isChecked():
            try:
                self.plot_merged()
            except Exception as e:
                QMessageBox.warning(self, self.tr_.t("msg_attention"), f"{type(e).__name__}: {e}")
            return
        run = self.combo_run.currentText()
        if not run:
            QMessageBox.information(self, self.tr_.t("msg_attention"), self.tr_.t("res_no_run"))
            return
        post = self.combo_step.currentData() == "Post-production"
        g1 = self.combo_g1.currentData() if post and self.combo_g1.isEnabled() else None
        g2 = self.combo_g2.currentData() if post and self.combo_g2.isEnabled() else None
        if post and g1 is None:
            self.log(self.tr_.t("res_no_index"))
            return
        from BIN.module_view import ViewWorker
        self._view = ViewWorker(self.runs_dir, run, self.combo_step.currentData(), self.combo_chart.currentText(),
                                g1, g2, self.chk_ma.isChecked(), self._ma_value(), self.chk_legend.isChecked())
        self._view.log_view_signal.connect(self.status.log)
        self._view.run()

    # ---------------------------------------------------------------- relatório final ----------------------------------------------------------------
    def on_report(self):
        if self._report_worker is not None and self._report_worker.isRunning():   # o botão vira "cancelar" durante a geração
            self._report_token.cancel()
            self.btn_report.setEnabled(False)
            return
        from BIN import module_report
        if not self.project.is_open:
            QMessageBox.information(self, self.tr_.t("msg_attention"), self.tr_.t("res_report_no_project"))
            return
        if not module_report.list_report_runs(self.project.path):
            QMessageBox.information(self, self.tr_.t("msg_attention"), self.tr_.t("res_report_no_runs"))
            return
        if not module_report.DOCX_AVAILABLE:
            box = QMessageBox(QMessageBox.Warning, self.tr_.t("msg_attention"), self.tr_.t("res_report_need_docx"),
                              QMessageBox.NoButton, self)
            b_inst = box.addButton(self.tr_.t("btn_open_installer"), QMessageBox.AcceptRole)
            box.addButton(self.tr_.t("btn_close"), QMessageBox.RejectRole)
            box.exec_()
            if box.clickedButton() is b_inst:
                self.install_requested.emit()
            return
        self._report_token = CancelToken()
        self._report_worker = ReportWorker(self.project.path, self.tr_.lang, self._report_token, self)
        self._report_worker.progress.connect(lambda m: self.status.log(m, stamp=True))
        self._report_worker.finished_ok.connect(self._report_done)
        self._report_worker.failed.connect(self._report_failed)
        self._report_worker.cancelled.connect(self._report_cancelled)
        self._report_worker.finished.connect(self._report_finished)
        self.tr_.tr("res_btn_report_cancel", self.btn_report.setText)
        set_role(self.btn_report, "danger")
        self.status.log(self.tr_.t("res_report_started"), stamp=True)
        self._report_worker.start()

    def _report_finished(self):
        self.tr_.tr("res_btn_report", self.btn_report.setText)
        set_role(self.btn_report, "select")
        self.btn_report.setEnabled(True)

    def _report_done(self, path: str):
        self.status.log(self.tr_.t("res_report_saved", path=path), stamp=True)
        ans = QMessageBox.question(self, self.tr_.t("res_btn_report"), self.tr_.t("res_report_done", path=path),
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if ans == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _report_failed(self, msg: str):
        self.status.log(self.tr_.t("res_report_failed", msg=msg), stamp=True)
        QMessageBox.warning(self, self.tr_.t("msg_attention"), self.tr_.t("res_report_failed", msg=msg))

    def _report_cancelled(self):
        self.status.log(self.tr_.t("res_report_cancelled"), stamp=True)

    # ---------------------------------------------------------------- mesclagem ----------------------------------------------------------------
    def _toggle_merge(self, on: bool):
        self.btn_add_chart.setEnabled(on)
        self.ed_list.setEnabled(on)
        if not on:
            self.merge_state = {"base_file": None, "base_x": None, "base_label": None, "y_series": []}
            self.ed_list.clear()

    def add_chart_to_list(self):
        start = os.path.join(self.runs_dir, self.combo_run.currentText()) if self.combo_run.currentText() else self.runs_dir
        path, _ = QFileDialog.getOpenFileName(self, self.tr_.t("res_select_xvg"), start, "XVG (*.xvg);;All files (*)")
        if not path:
            return
        xs, ys = parse_xvg_columns(path)
        if not xs:
            QMessageBox.warning(self, self.tr_.t("msg_attention"), self.tr_.t("res_xvg_empty"))
            return
        label = os.path.basename(path)
        st = self.merge_state
        if st["base_file"] is None:
            n = min(len(xs), len(ys))
            st.update(base_file=path, base_x=xs[:n], base_label=label)
            st["y_series"].append({"file": path, "label": label, "y": ys[:n]})
            self.ed_list.appendPlainText(f"[X+Y] {label}")
        else:
            n = len(st["base_x"])
            st["y_series"].append({"file": path, "label": label, "y": ys[:n]})
            self.ed_list.appendPlainText(f"[Y] {label}")

    def plot_merged(self):
        st = self.merge_state
        if st["base_file"] is None or not st["y_series"]:
            QMessageBox.information(self, self.tr_.t("msg_attention"), self.tr_.t("res_merge_need"))
            return
        out = os.path.join(self.runs_dir, f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_merge.xvg")
        x = st["base_x"]
        labels = [s["label"] for s in st["y_series"]]
        ys = [s["y"] for s in st["y_series"]]
        n = min([len(x)] + [len(y) for y in ys])
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"@ title \"Merged: X from {st['base_label']} with multiple Y series\"\n@ legend on\n")
            for i, lab in enumerate(labels, start=1):
                f.write(f"# COL{i} = Y from {lab}\n")
            for i in range(n):
                f.write(" ".join([f"{x[i]:.6f}"] + [f"{y[i]:.6f}" for y in ys[:len(ys)]]) + "\n")
        self.log(f"Merged file saved: {out}")
        from BIN.module_view import ViewWorker
        vw = ViewWorker(self.runs_dir, run_folder="", step="", chart="", use_moving_avg=self.chk_ma.isChecked(),
                        moving_avg_value=self._ma_value(), use_legend=self.chk_legend.isChecked())
        vw.log_view_signal.connect(self.status.log)
        vw.plot_multi_y_vs_x_from_file(out, labels, title="Merged chart (multiple Y vs X)")
