# -*- coding: utf-8 -*-
"""CONFIG — formulário de configuração da dinâmica (grupos recolhíveis, tradução em tempo real)."""

import os
from datetime import datetime
from typing import List, Optional

from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox, QTableWidget,
    QSizePolicy, QTableWidgetItem, QVBoxLayout, QWidget,
)

from BIN import tools
from BIN.i18n import Translator
from BIN.module_ligands import find_ligand_file, list_ligands
from BIN.module_protein import list_proteins
from BIN.pipeline import create_run_folders
from BIN.platform_utils import IS_WINDOWS
from BIN.projects import (
    ProjectManager, clean_project_name, create_project, list_projects, project_id,
)
from BIN.runconfig import (
    BOX_TYPES, CHARGE_MODELS, FORCE_FIELDS, LIGAND_METHOD_LABELS, WATER_MODELS, RunConfig,
)
from BIN.theme import PALETTE, set_role
from BIN.widgets import CollapsibleGroupBox, make_title

AUTO_CHARGE = -11  # valor "especial" do spin = detecção automática


class ConfigForm(QWidget):
    run_requested = pyqtSignal(object, list)   # (RunConfig, run_infos)
    cancel_requested = pyqtSignal()
    install_requested = pyqtSignal()

    def __init__(self, codyn_dir: str, tr_: Translator, project: ProjectManager, parent=None):
        super().__init__(parent)
        self.codyn_dir = codyn_dir
        self.project = project
        self.tr_ = tr_
        self.cfg_path = os.path.join(codyn_dir, ".form_data.json")
        self._loading = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        self.root = QVBoxLayout(body)
        self.root.setContentsMargins(24, 16, 24, 16)
        self.root.setSpacing(12)

        self.title = make_title()
        self.tr_.tr("cfg_title", self.title.setText)
        self.root.addWidget(self.title)

        # grupos em duas colunas independentes (cada uma empilha seus grupos sem folgas entre eles):
        # esquerda = projetos, campo de força, simulação; direita = pastas/ligantes, sistema, hardware
        cols = QHBoxLayout()
        cols.setSpacing(14)
        self.col_layouts = []
        for _ in range(2):
            c = QVBoxLayout()
            c.setSpacing(12)
            cols.addLayout(c, 1)
            self.col_layouts.append(c)
        self.root.addLayout(cols)
        self._build_projects_group()
        self._build_ff_group()
        self._build_sim_group()
        self._build_folders_group()
        self._build_system_group()
        self._build_hw_group()
        for c in self.col_layouts:
            c.addStretch()
        self.root.addStretch()

        btns = QHBoxLayout()
        self.btn_cancel = QPushButton(); set_role(self.btn_cancel, "danger"); self.btn_cancel.setFixedWidth(160)
        self.btn_run = QPushButton(); set_role(self.btn_run, "primary"); self.btn_run.setFixedWidth(160)
        self.tr_.tr("btn_cancel", self.btn_cancel.setText)
        self.tr_.tr("cfg_btn_run", self.btn_run.setText)
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)
        self.btn_run.clicked.connect(self.on_run)
        btns.addWidget(self.btn_cancel)
        btns.addStretch()
        btns.addWidget(self.btn_run)
        self.root.addLayout(btns)

        self._on_ff_changed()
        self.load_last()
        self._loading = False
        self.tr_.on_change(lambda _l: self._update_counts())
        self.project.changed.connect(self._on_project_changed)
        self._on_project_changed(self.project.path)

    # ------------------------------------------------------------------ construção ------------------------------------------------------------------
    def _group(self, title_key: str, row: int = 0, col: int = 0, colspan: int = 1):
        grp = CollapsibleGroupBox()
        self.tr_.tr(title_key, grp.setTitle)
        form = QFormLayout(grp)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        form.setContentsMargins(14, 18, 14, 12)
        # largura "Ignored": o grupo se ajusta à coluna em vez de impor a largura do conteúdo à janela
        grp.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.col_layouts[col].addWidget(grp, 0, Qt.AlignTop)
        return grp, form

    def _row(self, form: QFormLayout, key: str, widget, tip_key: Optional[str] = None) -> QLabel:
        lbl = QLabel()
        self.tr_.tr(key, lbl.setText)
        if tip_key:
            self.tr_.tr(tip_key, lambda txt, w=widget, l=lbl: (w.setToolTip(txt), l.setToolTip(txt)))
        form.addRow(lbl, widget)
        return lbl

    def _build_projects_group(self):
        """Criar ou carregar um projeto (PROJECTS/<data>_<nome>/ com LIGANDS, TARGET e RUNS) — formato do CODEEP."""
        self.grp_proj, form = self._group("cfg_grp_projects", 0, 0)
        self.rb_new, self.rb_load = QCheckBox(), QCheckBox()
        self.tr_.tr("cfg_proj_new", self.rb_new.setText)
        self.tr_.tr("cfg_proj_load", self.rb_load.setText)
        self._proj_modes = QButtonGroup(self)          # os dois checkboxes são mutuamente exclusivos
        self._proj_modes.setExclusive(True)
        self._proj_modes.addButton(self.rb_new)
        self._proj_modes.addButton(self.rb_load)
        self.rb_new.setChecked(True)
        self.lbl_proj_date = QLabel()
        self.ed_proj_name = QLineEdit()
        self.ed_proj_name.setMaximumWidth(340)
        self.tr_.tr("cfg_proj_ph_name", self.ed_proj_name.setPlaceholderText)
        self.cb_prev = QComboBox()
        self.cb_prev.setMaximumWidth(340)
        self.cb_prev.setEnabled(False)
        self.tr_.tr("cfg_proj_prev_tip", self.cb_prev.setToolTip)
        self.lbl_proj_id = QLabel("—")
        self.lbl_proj_id.setStyleSheet(f"font-weight:bold;color:{PALETTE['accent']};")
        self.lbl_proj_status = QLabel()
        self.lbl_proj_status.setWordWrap(True)
        self.lbl_proj_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.btn_proj = QPushButton(); set_role(self.btn_proj, "primary")
        self.btn_proj.setFixedSize(230, 38)
        self.tr_.tr("cfg_proj_btn", self.btn_proj.setText)
        self._row(form, "cfg_proj_date", self.lbl_proj_date)
        form.addRow(self.rb_new)
        self._row(form, "cfg_proj_name", self.ed_proj_name)
        form.addRow(self.rb_load)
        self._row(form, "cfg_proj_prev", self.cb_prev)
        self._row(form, "cfg_proj_id", self.lbl_proj_id)
        wrap = QWidget()
        bl = QHBoxLayout(wrap)
        bl.setContentsMargins(0, 6, 0, 0)
        bl.addStretch(1); bl.addWidget(self.btn_proj); bl.addStretch(1)
        form.addRow(wrap)
        form.addRow(self.lbl_proj_status)
        self.rb_new.toggled.connect(self._sync_proj_mode)
        self.ed_proj_name.textChanged.connect(self._update_proj_id)
        self.cb_prev.currentIndexChanged.connect(self._update_proj_id)
        self.btn_proj.clicked.connect(self._proj_run)
        self.tr_.on_change(lambda _l: self._update_proj_status())
        self._refresh_prev_projects()
        self._sync_proj_mode()

    def _refresh_prev_projects(self, select: str = ""):
        cur = select or self.cb_prev.currentText() or self.project.name
        self.cb_prev.blockSignals(True)
        self.cb_prev.clear()
        self.cb_prev.addItems(list_projects(self.codyn_dir))
        i = self.cb_prev.findText(cur)
        if i >= 0:
            self.cb_prev.setCurrentIndex(i)
        self.cb_prev.blockSignals(False)

    def _sync_proj_mode(self):
        load = self.rb_load.isChecked()
        self.ed_proj_name.setEnabled(not load)
        self.cb_prev.setEnabled(load)
        if load:
            self._refresh_prev_projects()
        self._update_proj_id()

    def _update_proj_id(self):
        if self.rb_load.isChecked():
            self.lbl_proj_id.setText(self.cb_prev.currentText() or "—")
            return
        now = datetime.now()
        self.lbl_proj_date.setText(now.strftime("%Y-%m-%d_%H-%M"))
        self.lbl_proj_id.setText(project_id(self.ed_proj_name.text(), now) or "—")

    def _proj_run(self):
        if self.rb_load.isChecked():
            name = self.cb_prev.currentText().strip()
            if not name:
                QMessageBox.warning(self, self.tr_.t("msg_attention"), self.tr_.t("cfg_proj_select_prev"))
                return
            path = os.path.join(self.codyn_dir, "PROJECTS", name)
            if not self.project.open(path):
                QMessageBox.warning(self, self.tr_.t("msg_attention"), self.tr_.t("cfg_proj_not_found", path=path))
                self._refresh_prev_projects()
            return
        name = clean_project_name(self.ed_proj_name.text())
        if not name:
            QMessageBox.warning(self, self.tr_.t("msg_attention"), self.tr_.t("cfg_proj_name_required"))
            return
        try:
            path = create_project(self.codyn_dir, name)
        except FileExistsError:
            QMessageBox.warning(self, self.tr_.t("msg_attention"), self.tr_.t("cfg_proj_exists"))
            return
        except OSError as e:
            QMessageBox.warning(self, self.tr_.t("msg_attention"), str(e))
            return
        self.ed_proj_name.clear()
        self._refresh_prev_projects(select=os.path.basename(path))
        self.rb_load.setChecked(True)                  # passa a mostrar o projeto recém-criado como o aberto
        self.cb_prev.setCurrentText(os.path.basename(path))
        self.project.open(path)

    def _update_proj_status(self):
        if self.project.is_open:
            self.lbl_proj_status.setText(self.tr_.t("cfg_proj_open", path=self.project.path))
            self.lbl_proj_status.setStyleSheet(f"font-size:9pt;color:{PALETTE['accent']};")
        else:
            self.lbl_proj_status.setText(self.tr_.t("cfg_proj_none"))
            self.lbl_proj_status.setStyleSheet(f"font-size:9pt;color:{PALETTE['danger']};")

    def _on_project_changed(self, _path: str = ""):
        """Projeto aberto/fechado: aponta as pastas de ligantes e proteínas para ele, recarrega os
        parâmetros que ele guardou e relê as pastas."""
        self.lig_dir.setText(self.project.ligands_dir)
        self.prot_dir.setText(self.project.target_dir)
        self.lig_dir.setToolTip(self.project.ligands_dir)
        self.prot_dir.setToolTip(self.project.target_dir)
        self._update_proj_status()
        self._refresh_prev_projects(select=self.project.name)
        if self.project.is_open:
            cfg = RunConfig.load(self.project.config_path) if os.path.isfile(self.project.config_path) else None
            if cfg:
                self._loading = True
                try:
                    self._apply_config(cfg)
                finally:
                    self._loading = False
            self.rb_load.setChecked(True)              # mostra o projeto aberto no modo "carregar"
            self.cb_prev.setCurrentText(self.project.name)
            self._update_proj_id()
        self.btn_run.setEnabled(self.project.is_open)
        self.refresh_folders()
        self.apply_saved_selection()

    def _build_ff_group(self):
        self.grp_ff, form = self._group("cfg_grp_ff", 1, 0)
        self.ff = QComboBox()
        for key, spec in FORCE_FIELDS.items():
            if IS_WINDOWS and spec["family"] == "amber":
                continue   # AMBER/GAFF depende do AmberTools (antechamber/acpype), que não existe para Windows
            self.ff.addItem(spec["label"], key)
        self.water = QComboBox()
        for key, (label, _) in WATER_MODELS.items():
            self.water.addItem(label, key)
        self.lig_method = QComboBox()
        self.charge_model = QComboBox()
        for key, label in CHARGE_MODELS.items():
            self.charge_model.addItem(label, key)
        self.chk_ignh = QCheckBox()
        self.tr_.tr("cfg_ignh", self.chk_ignh.setText)
        self.tr_.tr("cfg_ignh_tip", self.chk_ignh.setToolTip)
        self._row(form, "cfg_ff", self.ff, "cfg_ff_tip")
        self._row(form, "cfg_water", self.water)
        self._row(form, "cfg_lig_method", self.lig_method, "cfg_lig_method_tip")
        self.lbl_charge_model = self._row(form, "cfg_charge_model", self.charge_model, "cfg_charge_model_tip")
        form.addRow("", self.chk_ignh)
        self.ff.currentIndexChanged.connect(self._on_ff_changed)
        self.lig_method.currentIndexChanged.connect(self._on_method_changed)

    def _build_system_group(self):
        self.grp_sys, form = self._group("cfg_grp_system", 1, 1)
        self.box_type = QComboBox()
        self.box_type.addItems(BOX_TYPES)
        self.box_dist = QDoubleSpinBox()
        self.box_dist.setRange(0.5, 5.0); self.box_dist.setSingleStep(0.1); self.box_dist.setDecimals(2); self.box_dist.setSuffix(" nm")
        self.p_ion = QComboBox(); self.p_ion.setEditable(True)
        self.n_ion = QComboBox(); self.n_ion.setEditable(True)
        self.conc = QDoubleSpinBox()
        self.conc.setRange(0.0, 2.0); self.conc.setSingleStep(0.05); self.conc.setDecimals(3); self.conc.setSuffix(" M")
        self._row(form, "cfg_box_type", self.box_type)
        self._row(form, "cfg_box_dist", self.box_dist, "cfg_box_dist_tip")
        self._row(form, "cfg_pos_ion", self.p_ion)
        self._row(form, "cfg_neg_ion", self.n_ion)
        self._row(form, "cfg_conc", self.conc)

    def _build_sim_group(self):
        self.grp_sim, form = self._group("cfg_grp_sim", 2, 0)
        self.t_md = QDoubleSpinBox(); self.t_md.setRange(0.001, 100000); self.t_md.setDecimals(3); self.t_md.setSuffix(" ns")
        self.t_eq = QDoubleSpinBox(); self.t_eq.setRange(0.001, 1000); self.t_eq.setDecimals(3); self.t_eq.setSuffix(" ns")
        self.t_int = QDoubleSpinBox(); self.t_int.setRange(0.5, 4.0); self.t_int.setSingleStep(0.5); self.t_int.setDecimals(1); self.t_int.setSuffix(" fs")
        self.temp = QDoubleSpinBox(); self.temp.setRange(1, 1000); self.temp.setDecimals(1); self.temp.setSuffix(" K")
        self._row(form, "cfg_t_md", self.t_md)
        self._row(form, "cfg_t_eq", self.t_eq, "cfg_t_eq_tip")
        self._row(form, "cfg_t_int", self.t_int, "cfg_t_int_tip")
        self._row(form, "cfg_temp", self.temp)

    def _build_hw_group(self):
        self.grp_hw, form = self._group("cfg_grp_hw", 2, 1)
        self.threads = QSpinBox(); self.threads.setRange(1, max(256, os.cpu_count() or 1))
        self.chk_gpu = QCheckBox()
        self.tr_.tr("cfg_use_gpu", self.chk_gpu.setText)
        self.lbl_gpu_state = QLabel()
        self.lbl_gpu_state.setWordWrap(True)
        self.lbl_gpu_state.setStyleSheet(f"color:{PALETTE['muted']};font-size:9pt;")
        self._row(form, "cfg_threads", self.threads)
        form.addRow("", self.chk_gpu)
        form.addRow("", self.lbl_gpu_state)
        gmx = tools.find_gmx()
        self._gpu_ok = bool(gmx) and tools.gmx_has_gpu(gmx)
        self.chk_gpu.setEnabled(self._gpu_ok)
        if not self._gpu_ok:
            self.chk_gpu.setChecked(False)
            self.tr_.tr("cfg_gpu_unavailable", self.lbl_gpu_state.setText)
        else:
            self.tr_.tr("cfg_gpu_available", self.lbl_gpu_state.setText)

    def _build_folders_group(self):
        self.grp_dirs, form = self._group("cfg_grp_folders", 0, 1)
        self.lig_dir = QLineEdit(); self.lig_dir.setReadOnly(True)
        self.prot_dir = QLineEdit(); self.prot_dir.setReadOnly(True)
        row1, row2 = QHBoxLayout(), QHBoxLayout()
        for ed, row in ((self.lig_dir, row1), (self.prot_dir, row2)):
            b_open, b_scan = QPushButton(), QPushButton("⟳")
            set_role(b_open, "secondary"); set_role(b_scan, "secondary")
            b_scan.setFixedWidth(36)
            self.tr_.tr("btn_open_folder", b_open.setText)
            self.tr_.tr("cfg_rescan_tip", b_scan.setToolTip)
            row.addWidget(ed, 1); row.addWidget(b_open); row.addWidget(b_scan)
            b_open.clicked.connect(lambda _=False, e=ed: self._open_dir(e))
            b_scan.clicked.connect(self.refresh_folders)
        self._row(form, "cfg_lig_dir", row1)
        self.protein = QComboBox()
        self._row(form, "cfg_prot_dir", row2)
        self._row(form, "cfg_protein", self.protein)

        self.lbl_lig_count = QLabel()
        self.lbl_lig_count.setWordWrap(True)
        self.lbl_lig_count.setStyleSheet(f"color:{PALETTE['muted']};font-size:9pt;")
        form.addRow("", self.lbl_lig_count)
        self.table = QTableWidget(0, 4)
        self.table.setMinimumHeight(150)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Stretch)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tr_.on_change(lambda _l: self._retitle_table())
        self._retitle_table()
        form.addRow(self.table)

    def _retitle_table(self):
        self.table.setHorizontalHeaderLabels([self.tr_.t("cfg_col_use"), self.tr_.t("cfg_col_ligand"),
                                              self.tr_.t("cfg_col_format"), self.tr_.t("cfg_col_charge")])
        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r, 3)
            if isinstance(w, QSpinBox):
                w.setSpecialValueText(self.tr_.t("cfg_charge_auto"))

    # ------------------------------------------------------------------ comportamento ------------------------------------------------------------------
    def _on_ff_changed(self):
        key = self.ff.currentData()
        spec = FORCE_FIELDS[key]
        prev_p, prev_n = self.p_ion.currentText(), self.n_ion.currentText()
        self.p_ion.blockSignals(True); self.n_ion.blockSignals(True)
        self.p_ion.clear(); self.p_ion.addItems(spec["ions_pos"])
        self.n_ion.clear(); self.n_ion.addItems(spec["ions_neg"])
        self.p_ion.setCurrentText(prev_p if prev_p in spec["ions_pos"] else spec["default_pos"])
        self.n_ion.setCurrentText(prev_n if prev_n in spec["ions_neg"] else spec["default_neg"])
        self.p_ion.blockSignals(False); self.n_ion.blockSignals(False)
        self.lig_method.blockSignals(True)
        cur = self.lig_method.currentData()
        self.lig_method.clear()
        for m in spec["ligand_methods"]:
            self.lig_method.addItem(LIGAND_METHOD_LABELS[m], m)
        idx = self.lig_method.findData(cur)
        self.lig_method.setCurrentIndex(max(idx, 0))
        self.lig_method.blockSignals(False)
        self._on_method_changed()

    def _on_method_changed(self):
        amber = self.lig_method.currentData() in ("gaff", "gaff2")
        self.charge_model.setVisible(amber)
        self.lbl_charge_model.setVisible(amber)

    def _open_dir(self, edit: QLineEdit):
        """Abre a pasta do projeto no gerenciador de arquivos (para colocar ligantes/proteínas nela)."""
        path = edit.text().strip()
        if path and os.path.isdir(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.information(self, self.tr_.t("msg_attention"), self.tr_.t("cfg_no_project"))

    def refresh_folders(self):
        """Atualiza a lista de proteínas e a tabela de ligantes a partir das pastas escolhidas."""
        if self._loading:
            return
        prots = [os.path.splitext(f)[0] for f in list_proteins(self.prot_dir.text())]
        cur = self.protein.currentText()
        self.protein.clear()
        self.protein.addItems(prots)
        if cur in prots:
            self.protein.setCurrentText(cur)
        ligs = list_ligands(self.lig_dir.text())
        previous = {}
        for r in range(self.table.rowCount()):
            name = self.table.item(r, 1).text()
            previous[name] = (self.table.item(r, 0).checkState() == Qt.Checked, self.table.cellWidget(r, 3).value())
        self.table.setRowCount(len(ligs))
        for r, name in enumerate(ligs):
            use = QTableWidgetItem()
            use.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            use.setCheckState(Qt.Checked if previous.get(name, (True, 0))[0] else Qt.Unchecked)
            self.table.setItem(r, 0, use)
            self.table.setItem(r, 1, QTableWidgetItem(name))
            f = find_ligand_file(self.lig_dir.text(), name) or ""
            self.table.setItem(r, 2, QTableWidgetItem(os.path.splitext(f)[1].lstrip(".")))
            spin = QSpinBox()
            spin.setRange(AUTO_CHARGE, 10)
            spin.setValue(previous.get(name, (True, AUTO_CHARGE))[1])
            spin.setSpecialValueText(self.tr_.t("cfg_charge_auto"))
            self.table.setCellWidget(r, 3, spin)
        self._update_counts()

    def _update_counts(self):
        self.lbl_lig_count.setText(self.tr_.t("cfg_counts", nl=self.table.rowCount(), np=self.protein.count()))

    # ------------------------------------------------------------------ valores <-> widgets ------------------------------------------------------------------
    def to_config(self) -> RunConfig:
        selected, charges = [], {}
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).checkState() == Qt.Checked:
                name = self.table.item(r, 1).text()
                selected.append(name)
                v = self.table.cellWidget(r, 3).value()
                if v != AUTO_CHARGE:
                    charges[name] = v
        return RunConfig(
            force_field=self.ff.currentData(), solvent_model=self.water.currentData(),
            production_time_ns=self.t_md.value(), equilibration_time_ns=self.t_eq.value(),
            integration_time_fs=self.t_int.value(), temperature_K=self.temp.value(),
            box_type=self.box_type.currentText(), box_distance_nm=self.box_dist.value(),
            positive_ion=self.p_ion.currentText().strip(), negative_ion=self.n_ion.currentText().strip(),
            ion_concentration_M=self.conc.value(), n_threads=self.threads.value(),
            use_gpu=self.chk_gpu.isChecked() and self._gpu_ok,
            ligand_method=self.lig_method.currentData() or "cgenff",
            ligand_charge_model=self.charge_model.currentData(), ligand_charges=charges,
            ignore_hydrogens=self.chk_ignh.isChecked(), selected_ligands=selected,
            ligands_dir=self.project.ligands_dir, protein_dir=self.project.target_dir,
        )

    def load_last(self):
        """Parâmetros da última execução (valores iniciais antes de qualquer projeto ser aberto)."""
        self._apply_config(RunConfig.load(self.cfg_path) or RunConfig(n_threads=os.cpu_count() or 4))

    def _apply_config(self, cfg: RunConfig):
        self.ff.setCurrentIndex(max(self.ff.findData(cfg.force_field), 0))
        self._on_ff_changed()
        self.water.setCurrentIndex(max(self.water.findData(cfg.solvent_model), 0))
        self.lig_method.setCurrentIndex(max(self.lig_method.findData(cfg.ligand_method), 0))
        self.charge_model.setCurrentIndex(max(self.charge_model.findData(cfg.ligand_charge_model), 0))
        self.chk_ignh.setChecked(cfg.ignore_hydrogens)
        self.box_type.setCurrentText(cfg.box_type)
        self.box_dist.setValue(cfg.box_distance_nm)
        self.p_ion.setCurrentText(cfg.positive_ion)
        self.n_ion.setCurrentText(cfg.negative_ion)
        self.conc.setValue(cfg.ion_concentration_M)
        self.t_md.setValue(cfg.production_time_ns)
        self.t_eq.setValue(cfg.equilibration_time_ns)
        self.t_int.setValue(cfg.integration_time_fs)
        self.temp.setValue(cfg.temperature_K)
        self.threads.setValue(cfg.n_threads)
        self.chk_gpu.setChecked(cfg.use_gpu and self._gpu_ok)
        self._last_cfg = cfg

    def apply_saved_selection(self):
        """Reaplica seleção/cargas salvas na tabela (chamado depois do primeiro refresh)."""
        cfg = getattr(self, "_last_cfg", None)
        if not cfg:
            return
        for r in range(self.table.rowCount()):
            name = self.table.item(r, 1).text()
            if cfg.selected_ligands:
                self.table.item(r, 0).setCheckState(Qt.Checked if name in cfg.selected_ligands else Qt.Unchecked)
            self.table.cellWidget(r, 3).setValue(cfg.ligand_charges.get(name, AUTO_CHARGE))

    # ------------------------------------------------------------------ execução ------------------------------------------------------------------
    def _missing_tools(self, cfg: RunConfig) -> List[str]:
        missing = []
        if not tools.find_gmx():
            missing.append("GROMACS (gmx)")
        if not tools.find_obabel():
            missing.append("Open Babel (obabel)")
        if cfg.ligand_method == "cgenff":
            if not tools.find_perl():
                missing.append("Perl")
        else:
            if not tools.find_executable("acpype", search_conda=True):
                missing.append("acpype")
            if not tools.find_executable("antechamber", search_conda=True):
                missing.append("AmberTools (antechamber)")
        return missing

    def on_run(self):
        if not self.project.is_open:
            QMessageBox.warning(self, self.tr_.t("msg_attention"), self.tr_.t("cfg_no_project"))
            return
        cfg = self.to_config()
        errors = cfg.validate()
        if errors:
            QMessageBox.warning(self, self.tr_.t("msg_attention"),
                                self.tr_.t("cfg_invalid_fields", fields=", ".join(errors)))
            return
        if not cfg.selected_ligands:
            QMessageBox.warning(self, self.tr_.t("msg_attention"), self.tr_.t("cfg_no_ligands"))
            return
        prot = self.protein.currentText()
        if not prot:
            QMessageBox.warning(self, self.tr_.t("msg_attention"), self.tr_.t("cfg_no_protein"))
            return
        missing = self._missing_tools(cfg)
        if missing:
            box = QMessageBox(QMessageBox.Warning, self.tr_.t("msg_attention"),
                              self.tr_.t("cfg_missing_tools", tools=", ".join(missing)), QMessageBox.NoButton, self)
            b_inst = box.addButton(self.tr_.t("btn_open_installer"), QMessageBox.AcceptRole)
            box.addButton(self.tr_.t("btn_close"), QMessageBox.RejectRole)
            box.exec_()
            if box.clickedButton() is b_inst:
                self.install_requested.emit()
            return
        try:
            cfg.save(self.cfg_path)
            cfg.save(self.project.config_path)         # o projeto lembra os parâmetros da sua última execução
        except OSError as e:
            QMessageBox.warning(self, self.tr_.t("msg_attention"), str(e))
        infos = create_run_folders(self.project.runs_dir, cfg, [prot], cfg.selected_ligands)
        self.run_requested.emit(cfg, infos)
