# -*- coding: utf-8 -*-
"""Montagem do manual (.docx) a partir de uma lista de blocos bilíngues.

Estilo inspirado no manual do CODRUG: Calibri 11 justificado, títulos verdes, blocos de código
sombreados, legendas itálicas após as figuras e quadros "Observação". O sumário usa campos PAGEREF
(o Word atualiza com F9; o valor em cache vem da paginação do LibreOffice na passada anterior).
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

GREEN = "A05A2C"      # laranja escuro da logo (nome histórico da constante)
DARK = "1A1A1A"
GRAY = "555555"
RED = "C0392B"
HEADER_FILL = "F3E3D6"
CODE_FILL = "F0F0F0"
TEXT_WIDTH_CM = 16.0


# ----------------------------------------------------------------------------------- utilidades de baixo nível
def _shade(el, fill: str):
    pr = el.get_or_add_tcPr() if hasattr(el, "get_or_add_tcPr") else el.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    pr.append(shd)


def _rfonts(run, name: str):
    rpr = run._r.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs"):
        rf.set(qn(a), name)


def _field(par, instr: str, cached: str = "", size_pt: Optional[float] = None, bold=False):
    """Campo complexo (PAGE, PAGEREF...) com valor em cache."""
    def mk(kind=None, text=None, instr_text=None):
        r = par.add_run()
        if size_pt:
            r.font.size = Pt(size_pt)
        r.font.bold = bold
        if kind:
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), kind)
            r._r.append(fc)
        if instr_text is not None:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = instr_text
            r._r.append(it)
        if text is not None:
            r.text = text
        return r
    mk("begin")
    mk(instr_text=f" {instr} ")
    mk("separate")
    mk(text=cached or "1")
    mk("end")


_bm_id = [100]


def _bookmark(par, name: str):
    _bm_id[0] += 1
    s = OxmlElement("w:bookmarkStart")
    s.set(qn("w:id"), str(_bm_id[0]))
    s.set(qn("w:name"), name)
    e = OxmlElement("w:bookmarkEnd")
    e.set(qn("w:id"), str(_bm_id[0]))
    par._p.insert(1 if par._p.pPr is not None else 0, s)
    par._p.append(e)


_TOKEN = re.compile(r"(\*\*.+?\*\*|\*[^*\s][^*]*?\*|`.+?`)")


def add_rich(par, text: str, size: Optional[float] = None, color: Optional[str] = None, italic=False, bold=False):
    """Texto com **negrito** e `código` inline."""
    for tok in _TOKEN.split(text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            r = par.add_run(tok[2:-2]); r.bold = True
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            r = par.add_run(tok[1:-1]); r.italic = True
        elif tok.startswith("`") and tok.endswith("`"):
            r = par.add_run(tok[1:-1]); _rfonts(r, "Consolas"); r.font.size = Pt((size or 11) - 1.5)
            r.font.color.rgb = RGBColor.from_string("2B2B2B")
            if not size:
                r.font.size = Pt(9.5)
            continue
        else:
            r = par.add_run(tok)
            r.bold = bold or None
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = RGBColor.from_string(color)
        if italic:
            r.italic = True


# ----------------------------------------------------------------------------------- documento
class Manual:
    def __init__(self, lang: str, version: str, strings: Dict[str, str], img_root: str, logo: str):
        self.lang = lang
        self.i = 0 if lang == "pt" else 1
        self.s = strings
        self.img_root = img_root
        self.logo = logo
        self.version = version
        self.doc = Document()
        self.fig_n = 0
        self.tab_n = 0
        self.toc: List[Tuple[int, str, str]] = []     # (nível, título, marcador)
        self._h1 = 0
        self._h2 = 0
        self._setup()

    # -- estilos
    def _setup(self):
        d = self.doc
        sec = d.sections[0]
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.left_margin = sec.right_margin = Cm(2.5)
        sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.2)
        st = d.styles["Normal"]
        st.font.name = "Calibri"
        st.font.size = Pt(11)
        st.font.color.rgb = RGBColor.from_string(DARK)
        _rfonts_style(st, "Calibri")
        pf = st.paragraph_format
        pf.space_after = Pt(8)
        pf.line_spacing = 1.15
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        for name, size, before, after in (("Heading 1", 18, 20, 10), ("Heading 2", 14, 14, 6), ("Heading 3", 12, 10, 4)):
            h = d.styles[name]
            h.font.name = "Calibri"
            h.font.size = Pt(size)
            h.font.bold = True
            h.font.color.rgb = RGBColor.from_string(GREEN)
            _rfonts_style(h, "Calibri")
            h.paragraph_format.space_before = Pt(before)
            h.paragraph_format.space_after = Pt(after)
            h.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
            h.paragraph_format.keep_with_next = True
        for name in ("List Bullet", "List Number"):
            d.styles[name].paragraph_format.space_after = Pt(3)

    def t(self, pair) -> str:
        return pair[self.i] if isinstance(pair, (tuple, list)) else pair

    # -- capa e sumário
    def cover(self, title, product, subtitle, tagline, ver_line, org_line, url):
        """Capa. Formatação alinhada à edição manual feita no manual em português: fontes Futura Md BT
        (título e nome) e Futura Lt BT (demais linhas), 30/40/12/10,5/10 pt, sem linha em branco entre
        a logo e o título e com um parágrafo vazio (70 pt) após a frase de apresentação."""
        d = self.doc
        for _ in range(3):
            d.add_paragraph()
        p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(self.logo, width=Cm(6.0))
        MD, LT = "Futura Md BT", "Futura Lt BT"
        # (texto, tamanho, cor, negrito, espaço depois em pt (None = padrão), fonte)
        for text, size, color, bold, after, font in ((title, 30, GREEN, True, 4, MD), (product, 40, DARK, True, None, MD),
                                                       (subtitle, 12, GRAY, False, 2, LT), (tagline, 10.5, GRAY, False, 70, LT)):
            p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if after is not None:
                p.paragraph_format.space_after = Pt(after)
            r = p.add_run(text); r.font.size = Pt(size); r.bold = bold
            r.font.color.rgb = RGBColor.from_string(color)
            _rfonts(r, font)
        spacer = d.add_paragraph(); spacer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        spacer.paragraph_format.space_after = Pt(70)
        for text in (ver_line, org_line, url):
            p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(text); r.font.size = Pt(10); r.font.color.rgb = RGBColor.from_string(GRAY)
            _rfonts(r, LT)
        self.page_break()

    def page_break(self):
        par = self.doc.add_paragraph()
        par.paragraph_format.space_after = Pt(0)
        par.paragraph_format.space_before = Pt(0)
        par.paragraph_format.line_spacing = Pt(1)
        r = par.add_run(); r.font.size = Pt(1)
        r.add_break(WD_BREAK.PAGE)

    def toc_placeholder(self):
        """Posição do sumário: preenchida em `finish_toc` depois que todos os títulos são conhecidos."""
        p = self.doc.add_paragraph()
        self._toc_anchor = p
        return p

    def finish_toc(self, title: str, pages: Dict[str, int]):
        anchor = self._toc_anchor
        body = anchor._p.getparent()
        idx = body.index(anchor._p)
        new_pars = []

        def newp(text=None, size=11, bold=False, color=None, left=0.0, after=2.0, before=0.0):
            p = self.doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.left_indent = Cm(left)
            p.paragraph_format.space_after = Pt(after)
            p.paragraph_format.space_before = Pt(before)
            p.paragraph_format.line_spacing = 1.0
            if text:
                r = p.add_run(text); r.font.size = Pt(size); r.bold = bold
                if color:
                    r.font.color.rgb = RGBColor.from_string(color)
            return p
        t = newp(title, 16, True, GREEN, after=10)
        t.paragraph_format.keep_with_next = True
        new_pars.append(t)
        for level, text, mark in self.toc:
            p = newp(left=0.0 if level == 1 else 0.7, after=1.5 if level == 2 else 2.5, before=3.0 if level == 1 else 0.0)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
            r = p.add_run(text); r.bold = level == 1; r.font.size = Pt(10.5 if level == 1 else 10)
            p.add_run("\t")
            _field(p, f"PAGEREF {mark} \\h", str(pages.get(mark, 1)), size_pt=10.5 if level == 1 else 10, bold=level == 1)
            new_pars.append(p)
        for p in new_pars:
            body.remove(p._p)
        for k, p in enumerate(new_pars):
            body.insert(idx + k, p._p)
        body.remove(anchor._p)

    # -- títulos
    def h1(self, pair, new_page=False):
        text = self.t(pair)
        self._h1 += 1
        self._h2 = 0
        label = f"{self._h1}. {text}"
        mark = f"_Toc{self._h1:03d}00"
        p = self.doc.add_heading(label, level=1)
        if new_page:
            p.paragraph_format.page_break_before = True
        _bookmark(p, mark)
        self.toc.append((1, label, mark))
        return p

    def h2(self, pair):
        text = self.t(pair)
        self._h2 += 1
        label = f"{self._h1}.{self._h2} {text}"
        mark = f"_Toc{self._h1:03d}{self._h2:02d}"
        p = self.doc.add_heading(label, level=2)
        _bookmark(p, mark)
        self.toc.append((2, label, mark))
        return p

    def h3(self, pair):
        return self.doc.add_heading(self.t(pair), level=3)

    # -- texto
    def p(self, pair, keep_next=False):
        par = self.doc.add_paragraph()
        add_rich(par, self.t(pair))
        if keep_next:
            par.paragraph_format.keep_with_next = True
        return par

    def bullets(self, items):
        for it in items:
            par = self.doc.add_paragraph(style="List Bullet")
            add_rich(par, self.t(it))

    def numbered(self, items):
        # numeração reiniciada a cada lista: usa numeração manual (evita continuar a lista anterior)
        for n, it in enumerate(items, 1):
            par = self.doc.add_paragraph()
            par.paragraph_format.left_indent = Cm(1.0)
            par.paragraph_format.first_line_indent = Cm(-0.6)
            par.paragraph_format.space_after = Pt(3)
            r = par.add_run(f"{n}.  "); r.bold = True; r.font.color.rgb = RGBColor.from_string(GREEN)
            add_rich(par, self.t(it))

    def note(self, pair, kind="note"):
        label, color = (self.s["note"], GREEN) if kind == "note" else (self.s["warn"], RED)
        par = self.doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        par.paragraph_format.left_indent = Cm(0.6)
        par.paragraph_format.space_before = Pt(4)
        par.paragraph_format.space_after = Pt(8)
        _left_border(par, color)
        r = par.add_run(label + " "); r.bold = True; r.font.size = Pt(10); r.font.color.rgb = RGBColor.from_string(color)
        add_rich(par, self.t(pair), size=10, italic=True)

    def code(self, text):
        text = self.t(text)
        tbl = self.doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.rows[0].cells[0]
        _shade(cell._tc, CODE_FILL)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
        first = True
        for line in text.strip("\n").split("\n"):
            par = cell.paragraphs[0] if first else cell.add_paragraph()
            first = False
            par.alignment = WD_ALIGN_PARAGRAPH.LEFT
            par.paragraph_format.space_after = Pt(0)
            par.paragraph_format.space_before = Pt(0)
            par.paragraph_format.line_spacing = 1.0
            r = par.add_run(line if line else " ")
            _rfonts(r, "Consolas"); r.font.size = Pt(8.5)
        _fix_width(tbl, [TEXT_WIDTH_CM])
        sp = self.doc.add_paragraph(); sp.paragraph_format.space_after = Pt(4)
        sp.paragraph_format.line_spacing = 0.5

    def fig(self, name: str, caption, width_cm: float = 15.5, per_lang: bool = True):
        path = os.path.join(self.img_root, self.lang if per_lang else "", name)
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        self.fig_n += 1
        par = self.doc.add_paragraph(); par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.paragraph_format.keep_with_next = True
        par.paragraph_format.space_before = Pt(4)
        par.paragraph_format.space_after = Pt(3)
        par.add_run().add_picture(path, width=Cm(width_cm))
        cap = self.doc.add_paragraph(); cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_after = Pt(12)
        r = cap.add_run(f"{self.s['figure']} {self.fig_n} — "); r.italic = True; r.font.size = Pt(9); r.bold = True
        r.font.color.rgb = RGBColor.from_string(GRAY)
        add_rich(cap, self.t(caption), size=9, color=GRAY, italic=True)

    def table(self, header, rows, widths: Optional[List[float]] = None, caption=None, font=9):
        if caption is not None:
            self.tab_n += 1
            cp = self.doc.add_paragraph(); cp.alignment = WD_ALIGN_PARAGRAPH.LEFT
            cp.paragraph_format.keep_with_next = True
            cp.paragraph_format.space_after = Pt(3)
            r = cp.add_run(f"{self.s['table']} {self.tab_n} — "); r.bold = True; r.font.size = Pt(9)
            r.font.color.rgb = RGBColor.from_string(GRAY)
            add_rich(cp, self.t(caption), size=9, color=GRAY, italic=True)
        header = [self.t(h) for h in header]
        tbl = self.doc.add_table(rows=1, cols=len(header))
        tbl.style = "Table Grid"
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.autofit = False
        for j, h in enumerate(header):
            c = tbl.rows[0].cells[j]
            _shade(c._tc, HEADER_FILL)
            par = c.paragraphs[0]; par.alignment = WD_ALIGN_PARAGRAPH.LEFT
            par.paragraph_format.space_after = Pt(2)
            r = par.add_run(h); r.bold = True; r.font.size = Pt(font)
        _repeat_header(tbl.rows[0])
        for row in rows:
            cells = tbl.add_row().cells
            for j, val in enumerate(row):
                par = cells[j].paragraphs[0]; par.alignment = WD_ALIGN_PARAGRAPH.LEFT
                par.paragraph_format.space_after = Pt(2)
                par.paragraph_format.line_spacing = 1.0
                add_rich(par, self.t(val), size=font)
        ws = widths or [1.0] * len(header)
        _fix_width(tbl, [TEXT_WIDTH_CM * w / sum(ws) for w in ws])
        sp = self.doc.add_paragraph(); sp.paragraph_format.space_after = Pt(6)

    # -- rodapé com numeração (sem na capa)
    def footer(self, text: str):
        sec = self.doc.sections[0]
        sec.different_first_page_header_footer = True
        par = sec.footer.paragraphs[0]
        par.alignment = WD_ALIGN_PARAGRAPH.LEFT
        par.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), WD_TAB_ALIGNMENT.RIGHT)
        r = par.add_run(text + "\t"); r.font.size = Pt(8.5); r.font.color.rgb = RGBColor.from_string(GRAY)
        _field(par, "PAGE", "1", size_pt=8.5)

    def save(self, path: str):
        self.doc.save(path)


def _fix_width(tbl, widths_cm):
    """Largura fixa: grade (gridCol), células e tblW, para que Word e LibreOffice respeitem."""
    tbl.autofit = False
    pr = tbl._tbl.tblPr
    for tag in ("w:tblW", "w:tblLayout"):
        el = pr.find(qn(tag))
        if el is not None:
            pr.remove(el)
    w = OxmlElement("w:tblW"); w.set(qn("w:w"), str(int(sum(widths_cm) / 2.54 * 1440))); w.set(qn("w:type"), "dxa"); pr.append(w)
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); pr.append(lay)
    for j, wc in enumerate(widths_cm):
        tbl.columns[j].width = Cm(wc)
        for row in tbl.rows:
            row.cells[j].width = Cm(wc)


def _rfonts_style(style, name):
    rpr = style.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), name)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rf.get(qn(a)) is not None:
            del rf.attrib[qn(a)]


def _left_border(par, color: str):
    ppr = par._p.get_or_add_pPr()
    b = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single"); left.set(qn("w:sz"), "18"); left.set(qn("w:space"), "6"); left.set(qn("w:color"), color)
    b.append(left)
    ppr.append(b)


def _repeat_header(row):
    trpr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trpr.append(el)
