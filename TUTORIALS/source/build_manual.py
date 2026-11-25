#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera os manuais do usuário do CODYN (português e inglês) em .docx e .pdf.

Uso (dentro de ~/.venv/CODYN com python-docx instalado):
    python3 TUTORIALS/source/build_manual.py            # os dois idiomas
    python3 TUTORIALS/source/build_manual.py pt         # só português
    python3 TUTORIALS/source/build_manual.py en --no-pdf

As figuras ficam em TUTORIALS/source/img/<idioma>/ (capturas de tela feitas com o próprio programa).
O PDF é gerado com o LibreOffice (soffice); o sumário é paginado em duas passadas.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))            # raiz do CODYN
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from BIN.versao import VERSAO                              # noqa: E402
from content_a import build_a                              # noqa: E402
from content_b import build_b                              # noqa: E402
from docgen import Manual                                  # noqa: E402

OUT_DIR = os.path.dirname(HERE)
IMG = os.path.join(HERE, "img")
LOGO = os.path.join(ROOT, "ICONS", "LOGO_CODYN.png")
NAMES = {"pt": "manual_do_usuario_CODYN_pt_BR", "en": "User_manual_CODYN_en-US"}

STRINGS = {
    "pt": {"note": "Observação:", "warn": "Atenção:", "figure": "Figura", "table": "Tabela"},
    "en": {"note": "Note:", "warn": "Warning:", "figure": "Figure", "table": "Table"},
}
COVER = {
    "pt": ("MANUAL DO USUÁRIO", "CODYN", "Plataforma Computacional de Dinâmica Molecular", "Sistemas proteína–ligante com GROMACS",
           f"Versão {VERSAO}", "CEB/UFPR · Licença GPL-3.0", "https://github.com/moimaian/CODYN", "Sumário"),
    "en": ("USER MANUAL", "CODYN", "Computational Platform for Molecular Dynamics", "Protein–ligand systems with GROMACS",
           f"Version {VERSAO}", "CEB/UFPR · GPL-3.0 License", "https://github.com/moimaian/CODYN", "Contents"),
}
FOOTER = {"pt": f"CODYN — Manual do Usuário · v{VERSAO}", "en": f"CODYN — User Manual · v{VERSAO}"}


def build(lang: str, pages=None) -> Manual:
    m = Manual(lang, VERSAO, STRINGS[lang], IMG, LOGO)
    title, product, sub, tag, ver, org, url, toc_title = COVER[lang]
    m.cover(title, product, sub, tag, ver, org, url)
    m.toc_placeholder()
    m.page_break()
    build_a(m, VERSAO)
    build_b(m, VERSAO)
    m.finish_toc(toc_title, pages or {})
    m.footer(FOOTER[lang])
    return m


def to_pdf(docx_path: str, out_dir: str) -> str:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        raise RuntimeError("LibreOffice (soffice) não encontrado.")
    prof = tempfile.mkdtemp(prefix="lo_prof_")
    subprocess.run([exe, f"-env:UserInstallation=file://{prof}", "--headless", "--convert-to", "pdf", "--outdir", out_dir, docx_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(prof, ignore_errors=True)
    return os.path.join(out_dir, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")


def heading_pages(pdf: str, toc) -> dict:
    """Página (1-based) em que cada título aparece, procurando fora das linhas do sumário (que têm '....')."""
    text = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout
    pages = text.split("\f")
    found = {}
    start = 2
    for level, label, mark in toc:
        key = re.sub(r"\s+", " ", label)[:38]
        for i in range(start, len(pages)):
            hit = False
            for line in pages[i].splitlines():
                s = re.sub(r"\s+", " ", line.strip())
                if s.startswith(key) and "...." not in s:
                    hit = True
                    break
            if hit:
                found[mark] = i + 1
                start = i
                break
    return found


def make(lang: str, pdf: bool = True):
    tmp = tempfile.mkdtemp(prefix="manual_")
    docx_path = os.path.join(OUT_DIR, NAMES[lang] + ".docx")
    m = build(lang)                                  # passada 1: números de página provisórios
    m.save(os.path.join(tmp, NAMES[lang] + ".docx"))
    pages = {}
    if pdf:
        p1 = to_pdf(os.path.join(tmp, NAMES[lang] + ".docx"), tmp)
        pages = heading_pages(p1, m.toc)
        missing = [lab for _, lab, mk in m.toc if mk not in pages]
        if missing:
            print(f"[{lang}] aviso: títulos não localizados no PDF: {missing}")
    m2 = build(lang, pages)                          # passada 2: com os números de página
    m2.save(docx_path)
    out = [docx_path]
    if pdf:
        p2 = to_pdf(docx_path, OUT_DIR)
        pages2 = heading_pages(p2, m2.toc)
        if pages2 != pages:                          # a paginação mudou: refaz uma vez
            m3 = build(lang, pages2)
            m3.save(docx_path)
            p2 = to_pdf(docx_path, OUT_DIR)
        out.append(p2)
    shutil.rmtree(tmp, ignore_errors=True)
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    langs = args or ["pt", "en"]
    for lg in langs:
        for f in make(lg, pdf="--no-pdf" not in sys.argv):
            print("OK", f)
