# -*- coding: utf-8 -*-
"""Projetos do CODYN (mesmo formato do CODEEP).

Cada projeto é uma pasta  PROJECTS/<AAAA-MM-DD_HH-MM>_<nome>/  na raiz do CODYN, com as subpastas
LIGANDS (ligantes), TARGET (proteínas) e RUNS (uma pasta por execução: <data>_<proteína>_<ligante>).
Assim os arquivos de cada trabalho ficam separados dos de outros projetos/usuários.
"""

import os
import re
import shutil
from datetime import datetime
from typing import List, Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal

PROJECTS_DIRNAME = "PROJECTS"
SUBDIRS = ("LIGANDS", "TARGET", "RUNS")
STAMP_FMT = "%Y-%m-%d_%H-%M"
PROJECT_CONFIG = ".form_data.json"        # parâmetros da última execução, guardados dentro do projeto
LEGACY_PROJECT_NAME = "RUNS_ANTERIORES"   # projeto criado ao migrar a antiga pasta RUNS


def projects_root(codyn_dir: str) -> str:
    return os.path.join(codyn_dir, PROJECTS_DIRNAME)


def list_projects(codyn_dir: str) -> List[str]:
    """Nomes das pastas de projeto, as mais recentes primeiro."""
    root = projects_root(codyn_dir)
    if not os.path.isdir(root):
        return []
    return sorted((d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))), reverse=True)


def clean_project_name(name: str) -> str:
    """Nome seguro para pasta: sem espaços nem caracteres que quebrem caminhos/shell."""
    name = re.sub(r"\s+", "_", (name or "").strip())
    name = re.sub(r"[^\w.\-]", "", name, flags=re.UNICODE)
    return name.strip("._-")


def project_id(name: str, when: Optional[datetime] = None) -> str:
    name = clean_project_name(name)
    return f"{(when or datetime.now()).strftime(STAMP_FMT)}_{name}" if name else ""


def ensure_subdirs(path: str) -> None:
    for sub in SUBDIRS:
        os.makedirs(os.path.join(path, sub), exist_ok=True)


def create_project(codyn_dir: str, name: str, when: Optional[datetime] = None) -> str:
    """Cria PROJECTS/<data>_<nome>/ com LIGANDS, TARGET e RUNS. Levanta ValueError (nome vazio) ou
    FileExistsError (projeto já existe)."""
    pid = project_id(name, when)
    if not pid:
        raise ValueError("empty project name")
    path = os.path.join(projects_root(codyn_dir), pid)
    if os.path.exists(path):
        raise FileExistsError(path)
    os.makedirs(path)
    ensure_subdirs(path)
    return path


class ProjectManager(QObject):
    """Projeto aberto no momento. Quem precisa das pastas consulta as propriedades abaixo e
    reage ao sinal `changed` (caminho do projeto ou '' quando nenhum está aberto)."""

    changed = pyqtSignal(str)

    def __init__(self, codyn_dir: str, parent=None):
        super().__init__(parent)
        self.codyn_dir = codyn_dir
        self._path = ""

    @property
    def path(self) -> str:
        return self._path

    @property
    def name(self) -> str:
        return os.path.basename(self._path) if self._path else ""

    @property
    def is_open(self) -> bool:
        return bool(self._path) and os.path.isdir(self._path)

    @property
    def ligands_dir(self) -> str:
        return os.path.join(self._path, "LIGANDS") if self._path else ""

    @property
    def target_dir(self) -> str:
        return os.path.join(self._path, "TARGET") if self._path else ""

    @property
    def runs_dir(self) -> str:
        # sem projeto aberto devolve um caminho inexistente (as listagens ficam vazias)
        return os.path.join(self._path, "RUNS") if self._path else os.path.join(self.codyn_dir, PROJECTS_DIRNAME, ".none", "RUNS")

    @property
    def config_path(self) -> str:
        return os.path.join(self._path, PROJECT_CONFIG) if self._path else ""

    def open(self, path: str) -> bool:
        """Abre um projeto existente (recria subpastas que tenham sido apagadas)."""
        if not path or not os.path.isdir(path):
            return False
        ensure_subdirs(path)
        self._path = os.path.abspath(path)
        self.changed.emit(self._path)
        return True

    def close(self) -> None:
        self._path = ""
        self.changed.emit("")


# --------------------------------------------------------------- migração da estrutura antiga ---------------------------------------------------------------
def _copy_contents(src: str, dst: str) -> int:
    """Copia (sem sobrescrever) o conteúdo de src para dst. Devolve quantos itens copiou."""
    n = 0
    if not os.path.isdir(src):
        return 0
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.exists(d):
            continue
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
        n += 1
    return n


def legacy_runs_pending(codyn_dir: str) -> bool:
    runs = os.path.join(codyn_dir, "RUNS")
    return os.path.isdir(runs) and bool(os.listdir(runs))


def migrate_legacy(codyn_dir: str) -> Optional[Tuple[str, int, int]]:
    """Move o conteúdo da antiga pasta RUNS/ (execuções, merges .xvg, .str) para um projeto
    PROJECTS/<data>_RUNS_ANTERIORES/RUNS/ e COPIA para ele os LIGANDS/ e TARGET/ antigos (os originais
    ficam intactos). Só age se RUNS/ tiver conteúdo; depois remove a RUNS/ vazia.

    Devolve (caminho do projeto, itens movidos, itens copiados) ou None se não havia nada a migrar."""
    if not legacy_runs_pending(codyn_dir):
        return None
    old_runs = os.path.join(codyn_dir, "RUNS")
    # reaproveita o projeto de migração se ele já existir (migração interrompida/repetida)
    existing = [p for p in list_projects(codyn_dir) if p.endswith("_" + LEGACY_PROJECT_NAME)]
    if existing:
        proj = os.path.join(projects_root(codyn_dir), existing[0])
        ensure_subdirs(proj)
    else:
        proj = create_project(codyn_dir, LEGACY_PROJECT_NAME)
    moved = 0
    dst_runs = os.path.join(proj, "RUNS")
    for name in sorted(os.listdir(old_runs)):
        dst = os.path.join(dst_runs, name)
        if os.path.exists(dst):               # nunca sobrescreve
            base, ext = os.path.splitext(name)
            k = 2
            while os.path.exists(dst):
                dst = os.path.join(dst_runs, f"{base}-migrated{k}{ext}")
                k += 1
        shutil.move(os.path.join(old_runs, name), dst)
        moved += 1
    copied = 0
    for sub in ("LIGANDS", "TARGET"):
        copied += _copy_contents(os.path.join(codyn_dir, sub), os.path.join(proj, sub))
    try:
        os.rmdir(old_runs)                    # só remove se ficou vazia
    except OSError:
        pass
    return proj, moved, copied
