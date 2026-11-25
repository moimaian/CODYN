# -*- coding: utf-8 -*-
"""Modelo de configuração de uma execução: campos de força, modelos de água e RunConfig.

Sem Qt. O RunConfig é gravado em `.form_data.json` (últimos valores usados, para preencher o
formulário na próxima abertura) e em `run_config.json` dentro de cada pasta RUNS/<execução>/
(registro reprodutível do que foi simulado).
"""

import json
import os
from dataclasses import asdict, dataclass, field, fields
from typing import Dict, List, Optional

# Nome residual interno do ligante: curto (cabe nas colunas do .gro) e igual em todos os arquivos.
LIG_RESNAME = "LIG"

# ----------------------------- campos de força -----------------------------

FORCE_FIELDS: Dict[str, dict] = {
    "charmm36": {
        "label": "CHARMM36 (Jul 2021)",
        "family": "charmm",
        "gmx_ff": "charmm36-jul2021",      # pasta BASE/charmm36-jul2021.ff, copiada para a execução
        "local_dir": "charmm36-jul2021.ff",
        "ions_pos": ["SOD", "POT", "CAL", "MG", "ZN2", "LIT", "CU1P", "NI2P", "FE2P", "FE3P"],
        "ions_neg": ["CLA", "CO3", "OH"],
        "default_pos": "SOD",
        "default_neg": "CLA",
        "ligand_methods": ["cgenff"],
    },
    "amber99sb-ildn": {
        "label": "AMBER99SB-ILDN",
        "family": "amber",
        "gmx_ff": "amber99sb-ildn",
        "local_dir": None,
        "ions_pos": ["NA", "K", "CA", "MG", "ZN", "LI", "CU", "NI", "FE"],
        "ions_neg": ["CL", "BR", "IOD"],
        "default_pos": "NA",
        "default_neg": "CL",
        "ligand_methods": ["gaff2", "gaff"],
    },
    "amber99sb": {
        "label": "AMBER99SB",
        "family": "amber",
        "gmx_ff": "amber99sb",
        "local_dir": None,
        "ions_pos": ["NA", "K", "CA", "MG", "ZN", "LI", "CU", "NI", "FE"],
        "ions_neg": ["CL", "BR", "IOD"],
        "default_pos": "NA",
        "default_neg": "CL",
        "ligand_methods": ["gaff2", "gaff"],
    },
}

# índice numérico usado pelas versões <= 1.x do CODYN (pdb2gmx lia o número do menu)
LEGACY_FF_INDEX = {"1": "charmm36", "6": "amber99sb", "9": "charmm36", "15": "charmm36", "16": "charmm36"}
LEGACY_WATER_INDEX = {"1": "tip3p", "2": "tip4p", "3": "tip5p", "4": "spc", "5": "spce"}

# modelo de água -> (rótulo, arquivo de caixa para `gmx solvate -cs`)
WATER_MODELS: Dict[str, tuple] = {
    "tip3p": ("TIP3P", "spc216.gro"),
    "tip4p": ("TIP4P", "tip4p.gro"),
    "tip5p": ("TIP5P", "tip5p.gro"),
    "spc": ("SPC", "spc216.gro"),
    "spce": ("SPC/E", "spc216.gro"),
}

BOX_TYPES = ["cubic", "triclinic", "dodecahedron", "octahedron"]
LIGAND_METHOD_LABELS = {"cgenff": "CGenFF (CHARMM)", "gaff2": "GAFF2 (AMBER)", "gaff": "GAFF (AMBER)"}
CHARGE_MODELS = {"bcc": "AM1-BCC", "gas": "Gasteiger"}


def ff_family(ff_key: str) -> str:
    return FORCE_FIELDS.get(ff_key, FORCE_FIELDS["charmm36"])["family"]


@dataclass
class RunConfig:
    force_field: str = "charmm36"
    solvent_model: str = "tip3p"
    production_time_ns: float = 100.0
    equilibration_time_ns: float = 0.5
    integration_time_fs: float = 2.0
    temperature_K: float = 310.0
    box_type: str = "cubic"
    box_distance_nm: float = 1.0
    positive_ion: str = "SOD"
    negative_ion: str = "CLA"
    ion_concentration_M: float = 0.15
    n_threads: int = field(default_factory=lambda: os.cpu_count() or 4)
    use_gpu: bool = True
    ligand_method: str = "cgenff"       # cgenff | gaff2 | gaff
    ligand_charge_model: str = "bcc"    # bcc | gas   (só AMBER)
    ligand_charges: Dict[str, int] = field(default_factory=dict)  # carga líquida manual por ligante (vazio = automática)
    ignore_hydrogens: bool = False      # pdb2gmx -ignh
    selected_ligands: List[str] = field(default_factory=list)  # vazio = todos os ligantes da pasta
    ligands_dir: str = ""
    protein_dir: str = ""

    # ---- derivados ----
    @property
    def family(self) -> str:
        return ff_family(self.force_field)

    @property
    def gmx_ff(self) -> str:
        return FORCE_FIELDS[self.force_field]["gmx_ff"]

    @property
    def dt_ps(self) -> float:
        return self.integration_time_fs / 1000.0

    @property
    def steps_md(self) -> int:
        return int(round(self.production_time_ns * 1_000_000 / self.integration_time_fs))

    @property
    def steps_eq(self) -> int:
        return int(round(self.equilibration_time_ns * 1_000_000 / self.integration_time_fs))

    @property
    def md_tag(self) -> str:
        """Sufixo dos arquivos de produção (md_0_<tag>.*): 100 -> '100', 0.5 -> '0.5'."""
        v = self.production_time_ns
        return str(int(v)) if float(v).is_integer() else (f"{v:g}")

    def validate(self) -> List[str]:
        """Lista de mensagens de erro (vazia se tudo OK)."""
        errs = []
        if self.force_field not in FORCE_FIELDS:
            errs.append("force_field")
        if self.solvent_model not in WATER_MODELS:
            errs.append("solvent_model")
        if self.box_type not in BOX_TYPES:
            errs.append("box_type")
        for name in ("production_time_ns", "equilibration_time_ns", "integration_time_fs",
                     "temperature_K", "box_distance_nm", "ion_concentration_M"):
            if not (getattr(self, name) > 0):
                errs.append(name)
        if self.n_threads < 1:
            errs.append("n_threads")
        if self.ligand_method not in FORCE_FIELDS.get(self.force_field, {}).get("ligand_methods", []):
            errs.append("ligand_method")
        if not self.ligands_dir:
            errs.append("ligands_dir")
        if not self.protein_dir:
            errs.append("protein_dir")
        return errs

    # ---- persistência ----
    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(self.to_dict(), f, indent=4, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "RunConfig":
        """Aceita tanto o formato novo quanto o antigo (índices numéricos, valores em texto)."""
        d = dict(data or {})
        ff = str(d.get("force_field", "charmm36"))
        d["force_field"] = LEGACY_FF_INDEX.get(ff, ff) if ff in LEGACY_FF_INDEX else ff
        sm = str(d.get("solvent_model", "tip3p"))
        d["solvent_model"] = LEGACY_WATER_INDEX.get(sm, sm) if sm in LEGACY_WATER_INDEX else sm
        known = {f.name: f for f in fields(cls)}
        kwargs = {}
        for k, v in d.items():
            if k not in known:
                continue
            t = known[k].type
            try:
                if t in (float, "float"):
                    v = float(v)
                elif t in (int, "int"):
                    v = int(float(v))
                elif t in (bool, "bool"):
                    v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "sim")
            except (TypeError, ValueError):
                continue
            kwargs[k] = v
        if isinstance(d.get("ligand_charges"), dict):
            kwargs["ligand_charges"] = {str(a): int(b) for a, b in d["ligand_charges"].items()}
        if isinstance(d.get("selected_ligands"), list):
            kwargs["selected_ligands"] = [str(x) for x in d["selected_ligands"]]
        cfg = cls(**kwargs)
        spec = FORCE_FIELDS.get(cfg.force_field, FORCE_FIELDS["charmm36"])
        if cfg.ligand_method not in spec["ligand_methods"]:
            cfg.ligand_method = spec["ligand_methods"][0]
        return cfg

    @classmethod
    def load(cls, path: str) -> Optional["RunConfig"]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        except Exception:
            return None
