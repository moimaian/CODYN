# -*- coding: utf-8 -*-
"""Relatório final do CODYN (.docx) — inspirado no relatório do CODRUG.

Gera  <projeto>/RESULTS/<projeto>_REPORT_<data-hora>.docx  com:
  * Introdução (descoberta de fármacos, CADD, dinâmica molecular e o CODYN) + fluxograma;
  * Cabeçalho do projeto e a configuração empregada;
  * Método de cada etapa (STEP 1–6) montado a partir do que cada execução realmente registrou
    (run_config.json, .mdp, logs, topologia, saídas do gmx_MMPBSA);
  * Resultados: gráficos de equilibração e de produção (RMSD, RMSF, Rg, SASA, ligações de hidrogênio,
    distância proteína–ligante), MM/GBSA e decomposição por resíduo, com discussão automática.

Os gráficos de produção são calculados aqui (gmx rms/rmsf/gyrate/sasa/hbond/distance) quando ainda não
existem, em arquivos rep_*.xvg dentro de cada pasta de execução. Sem PyQt: pode ser usado/testado sem GUI.
Idioma: "pt" ou "en" (o da interface no momento da geração)."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch

try:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt
    DOCX_AVAILABLE = True
except Exception:  # python-docx não instalado
    DOCX_AVAILABLE = False

from BIN import tools
from BIN.mdp_tools import mdp_get, ndx_group_index
from BIN.module_ligands import itp_total_charge, parse_cgenff_str
from BIN.runconfig import FORCE_FIELDS, LIG_RESNAME, WATER_MODELS
from BIN.tools import CancelToken, PipelineCancelled
from BIN.versao import VERSAO

COLOR_TITLE_BAR = "BDD6EE"
COLOR_SECTION_BAR = "DAE3F3"
COLOR_ACCENT_BAR = "E2EFDA"
C_BLUE, C_ORANGE, C_GREEN, C_GREY, C_RED = "#1F5FA8", "#D2691E", "#2E8B57", "#6B7785", "#C0392B"
PROD_RE = re.compile(r"md_0_([0-9]+(?:\.[0-9]+)?)\.xtc")
INDENT = Cm(1.25) if DOCX_AVAILABLE else None


def require_docx() -> None:
    if not DOCX_AVAILABLE:
        raise RuntimeError("python-docx is not installed. Install it from Help > Install requirements.")


# =====================================================================================================
#  Leitura de arquivos
# =====================================================================================================
def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def read_xvg(path: str) -> Optional[Dict[str, Any]]:
    """Lê um .xvg: {'x', 'cols' (lista de arrays de y), 'legends', 'xlabel', 'ylabel', 'title'}. O eixo X
    de tempo é convertido para ns quando o rótulo indica ps."""
    if not os.path.isfile(path):
        return None
    xs: List[float] = []
    cols: List[List[float]] = []
    meta = {"xlabel": "", "ylabel": "", "title": ""}
    legends: Dict[int, str] = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("#"):
                continue
            if line.startswith("@"):
                m = re.match(r'@\s+(title|xaxis\s+label|yaxis\s+label)\s+"(.*)"', line)
                if m:
                    key = {"title": "title", "xaxis": "xlabel", "yaxis": "ylabel"}[m.group(1).split()[0]]
                    meta[key] = m.group(2)
                m = re.match(r'@\s+s(\d+)\s+legend\s+"(.*)"', line)
                if m:
                    legends[int(m.group(1))] = m.group(2)
                continue
            parts = line.split()
            try:
                vals = [float(p) for p in parts]
            except ValueError:
                continue
            if len(vals) < 2:
                continue
            xs.append(vals[0])
            while len(cols) < len(vals) - 1:
                cols.append([])
            for i, v in enumerate(vals[1:]):
                cols[i].append(v)
    if not xs:
        return None
    x = np.array(xs, dtype=float)
    if re.search(r"\(ps\)", meta["xlabel"], re.I):
        x = x / 1000.0
        meta["xlabel"] = "Time (ns)"
    return {"x": x, "cols": [np.array(c, dtype=float) for c in cols],
            "legends": [legends.get(i, "") for i in range(len(cols))], **meta}


def _y(xvg: Optional[Dict[str, Any]], col: int = 0) -> Optional[np.ndarray]:
    return xvg["cols"][col] if xvg and len(xvg["cols"]) > col else None


def desc(y: Optional[np.ndarray]) -> Optional[Dict[str, float]]:
    if y is None or len(y) == 0:
        return None
    return {"n": int(len(y)), "mean": float(np.mean(y)), "sd": float(np.std(y, ddof=1)) if len(y) > 1 else 0.0,
            "min": float(np.min(y)), "max": float(np.max(y)), "first": float(y[0]), "last": float(y[-1])}


def thirds(y: np.ndarray) -> Tuple[float, float, float]:
    k = max(1, len(y) // 3)
    return float(np.mean(y[:k])), float(np.mean(y[k:2 * k])), float(np.mean(y[-k:]))


def parse_mdp_value(path: str, key: str, default: str = "") -> str:
    try:
        v = mdp_get(path, key)
    except OSError:
        v = None
    return v if v is not None else default


def parse_gro_info(path: str) -> Tuple[Optional[int], Optional[Tuple[float, float, float]]]:
    """(nº de átomos, caixa) de um .gro."""
    lines = _read_text(path).splitlines()
    if len(lines) < 3:
        return None, None
    try:
        n = int(lines[1].strip())
        box = tuple(float(v) for v in lines[-1].split()[:3])
        return n, box  # type: ignore[return-value]
    except ValueError:
        return None, None


def parse_top_molecules(path: str) -> List[Tuple[str, int]]:
    mols, on = [], False
    for raw in _read_text(path).splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            on = re.match(r"\[\s*molecules\s*\]", line, re.I) is not None
            continue
        if on:
            p = line.split()
            if len(p) >= 2 and p[1].isdigit():
                mols.append((p[0], int(p[1])))
    return mols


def parse_em_log(path: str) -> Dict[str, Any]:
    text = _read_text(path)
    out: Dict[str, Any] = {}
    m = re.search(r"Steepest Descents converged to Fmax < ([\d.e+]+) in (\d+) steps", text)
    if m:
        out.update(converged=True, fmax_tol=float(m.group(1)), steps=int(m.group(2)))
    elif re.search(r"did not converge|not converge", text):
        out["converged"] = False
    for key, rx in (("epot", r"Potential Energy\s*=\s*([-\d.e+]+)"), ("fmax", r"Maximum force\s*=\s*([-\d.e+]+)")):
        mm = re.search(rx, text)
        if mm:
            out[key] = float(mm.group(1))
    return out


def parse_md_perf(path: str) -> Dict[str, float]:
    text = _read_text(path)
    out: Dict[str, float] = {}
    m = re.search(r"Performance:\s+([\d.]+)\s+([\d.]+)", text)
    if m:
        out["ns_day"] = float(m.group(1))
    m = re.search(r"Time:\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", text)
    if m:
        out["wall_s"] = float(m.group(2))
    return out


def parse_mmgbsa(dat_path: str) -> Optional[Dict[str, Any]]:
    """Bloco 'Delta (Complex - Receptor - Ligand)' do FINAL_RESULTS_MMPBSA.dat por modelo (GB/PB)."""
    text = _read_text(dat_path)
    if not text:
        return None
    res: Dict[str, Any] = {"frames": None, "models": {}}
    m = re.search(r"performed using (\d+) complex frames", text)
    if m:
        res["frames"] = int(m.group(1))
    m = re.search(r"Using temperature = ([\d.]+) K", text)
    if m:
        res["temperature"] = float(m.group(1))
    model, in_delta = None, False
    for line in text.splitlines():
        s = line.strip()
        if s in ("GENERALIZED BORN:", "POISSON BOLTZMANN:"):
            model = "GB" if s.startswith("GENERALIZED") else "PB"
            res["models"].setdefault(model, {})
            in_delta = False
            continue
        if s.startswith("Delta ("):
            in_delta = True
            continue
        if in_delta and model and s.startswith("Δ"):
            m = re.match(r"Δ(.+?)\s+(-?\d[\d.]*)\s+(-?\d[\d.]*)\s+(-?\d[\d.]*)\s+(-?\d[\d.]*)\s+(-?\d[\d.]*)$", s)
            if m:  # colunas: média, SD(Prop.), SD, SEM(Prop.), SEM
                res["models"][model][m.group(1)] = (float(m.group(2)), float(m.group(4)), float(m.group(6)))
    res["models"] = {k: v for k, v in res["models"].items() if v}
    return res if res["models"] else None


def parse_decomp_deltas(path: str, top: int = 10) -> List[Tuple[str, float, float]]:
    """Residuos que mais contribuem (mais negativos) na seção DELTAS da decomposição: [(resíduo, média, SD)]."""
    lines = _read_text(path).splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == "DELTAS:")
    except StopIteration:
        return []
    rows: List[Tuple[str, float, float]] = []
    for line in lines[start + 1:]:
        if not re.match(r"^[RL]:[A-Za-z0-9]*:[A-Za-z0-9]+:\d+,", line):
            continue
        parts = next(csv.reader(io.StringIO(line)))
        try:
            avg, sd = float(parts[-3]), float(parts[-2])
        except (ValueError, IndexError):
            continue
        _, _chain, resn, num = parts[0].split(":")[:4]
        rows.append((f"{resn if resn.upper() == LIG_RESNAME else resn.title()}{num}", avg, sd))
    rows.sort(key=lambda r: r[1])
    return rows[:top]


# =====================================================================================================
#  Coleta + análises gmx de cada execução
# =====================================================================================================
def production_tag(run_path: str) -> Optional[str]:
    for fname in sorted(os.listdir(run_path)):
        m = PROD_RE.fullmatch(fname)
        if m:
            return m.group(1)
    return None


def _fresh(out: str, ref: str) -> bool:
    return os.path.isfile(out) and os.path.getmtime(out) >= os.path.getmtime(ref)


def run_analyses(run_path: str, gmx: Optional[str], log: Callable[[str], None], token: Optional[CancelToken] = None
                 ) -> Dict[str, str]:
    """Calcula (se ainda não existirem) os .xvg de produção. Devolve {nome: caminho} dos disponíveis."""
    tag = production_tag(run_path)
    avail: Dict[str, str] = {}
    if not tag or not gmx:
        return avail
    tpr, xtc, ndx = f"md_0_{tag}.tpr", f"md_0_{tag}_noPBC.xtc", "index.ndx"
    if not (os.path.isfile(os.path.join(run_path, tpr)) and os.path.isfile(os.path.join(run_path, xtc))):
        return avail
    ndx_path = os.path.join(run_path, ndx)
    has_ndx = os.path.isfile(ndx_path)
    ref = os.path.join(run_path, xtc)
    traj = ["-s", tpr, "-f", xtc] + (["-n", ndx] if has_ndx else [])
    prot = "Protein"
    bb = "Backbone" if has_ndx and ndx_group_index(ndx_path, "Backbone") is not None else prot
    ca = "C-alpha" if has_ndx and ndx_group_index(ndx_path, "C-alpha") is not None else prot
    lig = LIG_RESNAME if has_ndx and ndx_group_index(ndx_path, LIG_RESNAME) is not None else None
    jobs: List[Tuple[str, str, List[str], str]] = [
        ("rmsd_bb", "rep_rmsd_backbone.xvg", ["rms"] + traj + ["-o", "rep_rmsd_backbone.xvg", "-tu", "ns"], f"{bb}\n{bb}\n"),
        ("rmsf", "rep_rmsf.xvg", ["rmsf"] + traj + ["-o", "rep_rmsf.xvg", "-res"], f"{ca}\n"),
        ("rg", "rep_rg.xvg", ["gyrate"] + traj + ["-o", "rep_rg.xvg"], f"{prot}\n"),
        ("sasa", "rep_sasa.xvg", ["sasa"] + traj + ["-o", "rep_sasa.xvg", "-tu", "ns"], f"{prot}\n"),
    ]
    if lig:
        jobs += [
            ("rmsd_lig", "rep_rmsd_ligand.xvg", ["rms"] + traj + ["-o", "rep_rmsd_ligand.xvg", "-tu", "ns"], f"{bb}\n{lig}\n"),
            ("hbonds", "rep_hbonds.xvg", ["hbond"] + traj + ["-num", "rep_hbonds.xvg", "-tu", "ns"], f"{prot}\n{lig}\n"),
            ("dist", "rep_dist.xvg", ["distance", "-s", tpr, "-f", xtc, "-n", ndx, "-select",
                                      f'com of group "{prot}" plus com of group "{lig}"', "-oall", "rep_dist.xvg", "-tu", "ns"], ""),
        ]
    for key, fname, args, stdin in jobs:
        if token is not None and token.is_set():
            raise PipelineCancelled()
        out = os.path.join(run_path, fname)
        if not _fresh(out, ref):
            log(f"  gmx {args[0]} ({key})...")
            rc, txt = tools.run_cmd([gmx] + args, cwd=run_path, input_text=stdin or None, token=token)
            if rc != 0 or not os.path.isfile(out):
                log(f"  ! gmx {args[0]} failed: {tools.tail(txt, 3)}")
                continue
        avail[key] = out
    return avail


def collect_run(run_path: str, gmx: Optional[str], log: Callable[[str], None],
                token: Optional[CancelToken] = None) -> Dict[str, Any]:
    """Reúne tudo o que se sabe de uma execução (configuração, sistema, etapas, séries e MM/GBSA)."""
    d: Dict[str, Any] = {"path": run_path, "name": os.path.basename(run_path)}
    try:
        with open(os.path.join(run_path, "run_config.json"), "r", encoding="utf-8") as f:
            d["cfg"] = json.load(f)
    except (OSError, ValueError):
        d["cfg"] = {}
    cfg = d["cfg"]
    parts = d["name"].split("_")
    d["protein"] = cfg.get("protein") or (parts[-2] if len(parts) >= 4 else "protein")
    d["ligand"] = cfg.get("ligand") or (parts[-1] if len(parts) >= 4 else "ligand")
    p = lambda n: os.path.join(run_path, n)  # noqa: E731

    # ligante
    lig: Dict[str, Any] = {}
    itp = p(f"{LIG_RESNAME}.itp")
    if os.path.isfile(itp):
        lig["net_charge"] = itp_total_charge(itp)
        txt = _read_text(itp)
        m = re.search(r"\[\s*atoms\s*\]([\s\S]*?)(?:\n\s*\[|\Z)", txt)
        if m:
            lig["n_atoms"] = sum(1 for l in m.group(1).splitlines() if l.split(";", 1)[0].strip())
    strp = p(f"{LIG_RESNAME}.str")
    if os.path.isfile(strp):
        try:
            lig["cgenff"] = parse_cgenff_str(strp)
        except OSError:
            pass
    d["lig"] = lig

    # sistema
    n_atoms, box = parse_gro_info(p("solv_ions.gro"))
    cplx_atoms, _ = parse_gro_info(p("complex.gro"))
    d["system"] = {"n_atoms": n_atoms, "complex_atoms": cplx_atoms, "box": box,
                   "molecules": parse_top_molecules(p("topol.top"))}
    # etapas
    d["em"] = parse_em_log(p("em.log"))
    d["em"]["mdp"] = {k: parse_mdp_value(p("em.mdp"), k) for k in ("integrator", "emtool", "emstep", "nsteps")}
    keys = ("integrator", "dt", "nsteps", "tcoupl", "tc-grps", "tau_t", "ref_t", "pcoupl", "pcoupltype", "tau_p", "ref_p",
            "constraints", "constraint_algorithm", "coulombtype", "rcoulomb", "rvdw", "vdw-modifier", "DispCorr", "define",
            "nstxout-compressed", "gen_vel", "pme_order", "fourierspacing")
    for step in ("nvt", "npt", "md"):
        d[step] = {k: parse_mdp_value(p(f"{step}.mdp"), k) for k in keys}
    tag = production_tag(run_path)
    d["tag"] = tag
    d["perf"] = parse_md_perf(p(f"md_0_{tag}.log")) if tag else {}
    d["pre"] = {k: read_xvg(p(f)) for k, f in (("potential", "potential.xvg"), ("temperature", "temperature.xvg"),
                                                ("pressure", "pressure.xvg"), ("density", "density.xvg"))}
    # produção
    avail = run_analyses(run_path, gmx, log, token)
    d["series"] = {k: read_xvg(v) for k, v in avail.items()}
    # MM/GBSA
    d["mm"] = parse_mmgbsa(p("FINAL_RESULTS_MMPBSA.dat"))
    d["decomp"] = parse_decomp_deltas(p("FINAL_DECOMP_MMPBSA.dat")) if d["mm"] else []
    mmin = p("mmpbsa.in")
    d["mm_in"] = _read_text(mmin)
    return d


# =====================================================================================================
#  Gráficos (matplotlib sem pyplot: thread-safe)
# =====================================================================================================
def _save(fig: Figure, path: str) -> str:
    FigureCanvasAgg(fig)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    return path


def _style(ax, xlabel: str, ylabel: str, title: str = ""):
    ax.set_xlabel(xlabel, fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)
    if title:
        ax.set_title(title, fontsize=9, fontweight="bold")
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.25, linewidth=0.5)


def _mean_line(ax, y, color):
    if y is not None and len(y):
        ax.axhline(float(np.mean(y)), color=color, linestyle="--", linewidth=0.8, alpha=0.7)


def plot_equilibration(run: Dict[str, Any], out: str, lang: str) -> Optional[str]:
    pre = run["pre"]
    panels = [("potential", "Potential energy (EM)" if lang == "en" else "Energia potencial (EM)", "kJ/mol", C_BLUE),
              ("temperature", "Temperature (NVT)" if lang == "en" else "Temperatura (NVT)", "K", C_ORANGE),
              ("pressure", "Pressure (NPT)" if lang == "en" else "Pressão (NPT)", "bar", C_GREEN),
              ("density", "Density (NPT)" if lang == "en" else "Densidade (NPT)", "kg/m³", C_GREY)]
    if not any(pre.get(k) for k, *_ in panels):
        return None
    fig = Figure(figsize=(7.2, 5.0))
    for i, (key, title, unit, color) in enumerate(panels):
        ax = fig.add_subplot(2, 2, i + 1)
        x = pre.get(key)
        if x is None:
            ax.axis("off")
            continue
        xv = x["x"] * (1000.0 if x["xlabel"].startswith("Time (ns)") else 1.0)
        xlabel = "Step" if key == "potential" else "Time (ps)"
        ax.plot(xv, x["cols"][0], color=color, linewidth=0.9)
        if key != "potential":
            _mean_line(ax, x["cols"][0], color)
        _style(ax, xlabel, unit, title)
    fig.tight_layout()
    return _save(fig, out)


def plot_two_series(run: Dict[str, Any], keys: List[Tuple[str, str, str, str]], out: str, ncols: int = 1,
                    figsize=(7.0, 3.2)) -> Optional[str]:
    """keys: [(serie, rótulo, cor, ylabel)] → painéis lado a lado (ou um só com várias curvas se ncols=1)."""
    avail = [(k, lab, col, yl) for k, lab, col, yl in keys if run["series"].get(k)]
    if not avail:
        return None
    fig = Figure(figsize=figsize)
    ax = fig.add_subplot(1, 1, 1)
    for k, lab, col, yl in avail:
        xv = run["series"][k]
        ax.plot(xv["x"], xv["cols"][0], color=col, linewidth=0.9, label=lab)
    ax.legend(fontsize=7, frameon=False)
    _style(ax, "Time (ns)", avail[0][3])
    fig.tight_layout()
    return _save(fig, out)


def plot_series_grid(run: Dict[str, Any], panels: List[Tuple[str, str, str, str]], out: str) -> Optional[str]:
    avail = [p for p in panels if run["series"].get(p[0])]
    if not avail:
        return None
    n = len(avail)
    fig = Figure(figsize=(7.2, 2.6 * math.ceil(n / 2)))
    for i, (k, title, ylabel, color) in enumerate(avail):
        ax = fig.add_subplot(math.ceil(n / 2), 2 if n > 1 else 1, i + 1)
        xv = run["series"][k]
        ax.plot(xv["x"], xv["cols"][0], color=color, linewidth=0.9)
        _mean_line(ax, xv["cols"][0], color)
        _style(ax, "Time (ns)", ylabel, title)
    fig.tight_layout()
    return _save(fig, out)


def plot_rmsf(run: Dict[str, Any], out: str) -> Optional[str]:
    xv = run["series"].get("rmsf")
    if not xv:
        return None
    fig = Figure(figsize=(7.0, 3.0))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(xv["x"], xv["cols"][0], color=C_BLUE, linewidth=0.9)
    _style(ax, "Residue", "RMSF (nm)")
    fig.tight_layout()
    return _save(fig, out)


def plot_mmgbsa_bars(runs: List[Dict[str, Any]], out: str, lang: str) -> Optional[str]:
    rows = [(r["ligand"], r["mm"]["models"].get("GB", {}).get("TOTAL")) for r in runs if r.get("mm")]
    rows = [(n, v) for n, v in rows if v]
    if not rows:
        return None
    rows.sort(key=lambda t: t[1][0])
    fig = Figure(figsize=(7.0, 0.5 * len(rows) + 1.8))
    ax = fig.add_subplot(1, 1, 1)
    ax.barh([n for n, _ in rows], [v[0] for _, v in rows], xerr=[v[1] for _, v in rows], color=C_BLUE,
            ecolor=C_GREY, capsize=3)
    ax.invert_yaxis()
    _style(ax, "ΔG (kcal/mol)" if lang == "en" else "ΔG (kcal/mol)", "")
    fig.tight_layout()
    return _save(fig, out)


def plot_components(run: Dict[str, Any], out: str, lang: str) -> Optional[str]:
    mm = run.get("mm")
    if not mm:
        return None
    comp = mm["models"].get("GB") or next(iter(mm["models"].values()))
    names = [n for n in ("VDWAALS", "EEL", "EGB", "ESURF", "GGAS", "GSOLV", "TOTAL") if n in comp]
    fig = Figure(figsize=(7.0, 2.8))
    ax = fig.add_subplot(1, 1, 1)
    vals = [comp[n][0] for n in names]
    ax.bar(["Δ" + n for n in names], vals, yerr=[comp[n][1] for n in names],
           color=[C_GREEN if v < 0 else C_ORANGE for v in vals], ecolor=C_GREY, capsize=3)
    ax.axhline(0, color="black", linewidth=0.6)
    _style(ax, "", "kcal/mol")
    fig.tight_layout()
    return _save(fig, out)


def plot_decomp(run: Dict[str, Any], out: str) -> Optional[str]:
    rows = run.get("decomp") or []
    if not rows:
        return None
    fig = Figure(figsize=(7.0, 0.32 * len(rows) + 1.2))
    ax = fig.add_subplot(1, 1, 1)
    ax.barh([r[0] for r in rows], [r[1] for r in rows], xerr=[r[2] for r in rows], color=C_ORANGE, ecolor=C_GREY, capsize=2)
    ax.invert_yaxis()
    _style(ax, "ΔG (kcal/mol)", "")
    fig.tight_layout()
    return _save(fig, out)


def plot_workflow(out: str, lang: str) -> str:
    steps = [("STEP 1", "Ligand\npreparation" if lang == "en" else "Preparo do\nligante"),
             ("STEP 2", "Complex\ntopology" if lang == "en" else "Topologia do\ncomplexo"),
             ("STEP 3", "Box, solvent,\nions, EM" if lang == "en" else "Caixa, solvente,\níons, EM"),
             ("STEP 4", "NVT / NPT\nequilibration" if lang == "en" else "Equilibração\nNVT / NPT"),
             ("STEP 5", "Production\nMD" if lang == "en" else "Dinâmica de\nprodução"),
             ("STEP 6", "MM/PBSA\n(gmx_MMPBSA)"),
             ("RESULTS", "Analysis and\nreport" if lang == "en" else "Análises e\nrelatório")]
    fig = Figure(figsize=(7.4, 1.8))
    ax = fig.add_subplot(1, 1, 1)
    ax.set_xlim(0, len(steps) * 1.25)
    ax.set_ylim(0, 1.6)
    ax.axis("off")
    for i, (tag, label) in enumerate(steps):
        x = i * 1.25 + 0.05
        face = C_ORANGE if i in (0, 5) else C_BLUE
        ax.add_patch(FancyBboxPatch((x, 0.3), 1.0, 0.95, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc=face, ec="none", alpha=0.92))
        ax.text(x + 0.5, 1.05, tag, ha="center", va="center", color="white", fontsize=7, fontweight="bold")
        ax.text(x + 0.5, 0.66, label, ha="center", va="center", color="white", fontsize=6.5)
        if i < len(steps) - 1:
            ax.annotate("", xy=(x + 1.2, 0.78), xytext=(x + 1.03, 0.78),
                        arrowprops=dict(arrowstyle="->", color=C_GREY, lw=1.2))
    return _save(fig, out)


# =====================================================================================================
#  Texto fixo (introdução, referências) — pt/en
# =====================================================================================================
INTRO: Dict[str, Dict[str, List[str]]] = {
    "pt": {
        "title": ["RELATÓRIO FINAL CODYN: Introdução"],
        "p": [
            "A descoberta e o desenvolvimento de fármacos é um processo longo, caro e de alto risco, que parte da "
            "identificação e validação de um alvo molecular, passa pela busca de compostos ativos (hits), pela otimização "
            "de leads e pela avaliação de propriedades farmacocinéticas e toxicológicas (ADMET), e segue para ensaios "
            "pré-clínicos e clínicos. O Design de Fármacos Assistido por Computador (CADD) reduz o custo e o tempo desse "
            "caminho ao priorizar in silico os compostos mais promissores antes dos ensaios experimentais.",
            "O CADD reúne duas grandes abordagens: o Design Baseado no Ligante (LBDD), que usa a estrutura e a "
            "bioatividade de moléculas conhecidas (QSAR, farmacóforos, similaridade), e o Design Baseado na Estrutura "
            "(SBDD), que usa a estrutura tridimensional do alvo biológico. No SBDD, o docking molecular propõe a pose e "
            "uma pontuação de afinidade para cada composto, mas trata o alvo de forma essencialmente rígida e em fase "
            "isolada. Por isso, as poses mais promissoras costumam ser refinadas por simulações de dinâmica molecular.",
            "A Dinâmica Molecular (MD) resolve numericamente as equações de movimento de Newton para todos os átomos do "
            "sistema (proteína, ligante, água e íons), com as forças derivadas de um campo de força — como o CHARMM36 "
            "(ligantes parametrizados pelo CGenFF) ou o AMBER (ligantes pelo GAFF/GAFF2). A simulação ocorre em uma caixa "
            "com condições periódicas de contorno, interações eletrostáticas de longo alcance tratadas por Particle Mesh "
            "Ewald (PME), ligações com hidrogênio restritas por LINCS e integração com passo de 2 fs. Antes da produção, "
            "o sistema é relaxado por minimização de energia e equilibrado em dois estágios: NVT (temperatura constante, "
            "com termostato) e NPT (temperatura e pressão constantes, com barostato), mantendo restrições de posição na "
            "proteína e no ligante. A trajetória de produção permite avaliar a estabilidade do complexo por meio do "
            "desvio quadrático médio (RMSD), da flutuação por resíduo (RMSF), do raio de giração (Rg), da área acessível "
            "ao solvente (SASA), das ligações de hidrogênio e da distância entre proteína e ligante.",
            "A energia livre de ligação pode ser estimada a partir da trajetória pelos métodos de ponto final MM/PBSA e "
            "MM/GBSA, que combinam a energia de mecânica molecular em fase gasosa com a energia de solvatação "
            "(Poisson–Boltzmann ou Generalized Born) e permitem decompor a contribuição de cada resíduo. Esses métodos "
            "não incluem o termo entrópico e superestimam valores absolutos, de modo que são mais adequados para "
            "comparar e ordenar ligantes de uma mesma série do que para prever afinidades absolutas.",
            "O CODYN é um software de código aberto que automatiza esse fluxo para sistemas proteína–múltiplos ligantes "
            "com o GROMACS: preparo e parametrização do ligante (CGenFF ou GAFF/GAFF2), construção do complexo, caixa, "
            "solvatação e íons, minimização, equilibração NVT/NPT, dinâmica de produção, MM/PBSA e análises dos "
            "resultados, organizados em projetos. Este relatório descreve a configuração empregada e os resultados "
            "obtidos no projeto, com os gráficos e a discussão correspondentes.",
        ],
        "fig1": "Figura 1. Fluxo de trabalho do CODYN: da preparação do ligante até as análises e o relatório final.",
    },
    "en": {
        "title": ["CODYN FINAL REPORT: Introduction"],
        "p": [
            "Drug discovery and development is a long, expensive and high-risk process that starts with the "
            "identification and validation of a molecular target, goes through the search for active compounds (hits), "
            "lead optimization and the evaluation of pharmacokinetic and toxicological properties (ADMET), and proceeds "
            "to preclinical and clinical trials. Computer-Aided Drug Design (CADD) reduces the cost and time of this "
            "path by prioritizing, in silico, the most promising compounds before the experimental assays.",
            "CADD comprises two major approaches: Ligand-Based Drug Design (LBDD), which uses the structure and "
            "bioactivity of known molecules (QSAR, pharmacophores, similarity), and Structure-Based Drug Design (SBDD), "
            "which uses the three-dimensional structure of the biological target. In SBDD, molecular docking proposes a "
            "pose and an affinity score for each compound, but treats the target as an essentially rigid, isolated "
            "system. For this reason, the most promising poses are usually refined with molecular dynamics simulations.",
            "Molecular Dynamics (MD) numerically solves Newton's equations of motion for every atom of the system "
            "(protein, ligand, water and ions), with forces derived from a force field — such as CHARMM36 (ligands "
            "parametrized by CGenFF) or AMBER (ligands by GAFF/GAFF2). The simulation takes place in a box with periodic "
            "boundary conditions, long-range electrostatics handled by Particle Mesh Ewald (PME), bonds to hydrogen "
            "constrained by LINCS and a 2 fs integration time step. Before production, the system is relaxed by energy "
            "minimization and equilibrated in two stages: NVT (constant temperature, thermostat) and NPT (constant "
            "temperature and pressure, barostat), keeping position restraints on the protein and the ligand. The "
            "production trajectory allows the stability of the complex to be assessed through the root-mean-square "
            "deviation (RMSD), per-residue fluctuation (RMSF), radius of gyration (Rg), solvent-accessible surface area "
            "(SASA), hydrogen bonds and the protein–ligand distance.",
            "The binding free energy can be estimated from the trajectory by the end-point methods MM/PBSA and MM/GBSA, "
            "which combine the gas-phase molecular-mechanics energy with the solvation energy (Poisson–Boltzmann or "
            "Generalized Born) and allow the contribution of each residue to be decomposed. These methods do not include "
            "the entropic term and overestimate absolute values, so they are better suited to comparing and ranking "
            "ligands of the same series than to predicting absolute affinities.",
            "CODYN is an open-source program that automates this workflow for protein–multiple-ligand systems with "
            "GROMACS: ligand preparation and parametrization (CGenFF or GAFF/GAFF2), complex building, box, solvation "
            "and ions, minimization, NVT/NPT equilibration, production dynamics, MM/PBSA and result analyses, organized "
            "in projects. This report describes the configuration used and the results obtained in the project, with "
            "the corresponding plots and discussion.",
        ],
        "fig1": "Figure 1. CODYN workflow: from ligand preparation to the analyses and the final report.",
    },
}

REFERENCES = [
    "Abraham, M. J. et al. GROMACS: high performance molecular simulations through multi-level parallelism from "
    "laptops to supercomputers. SoftwareX 1–2, 19–25 (2015).",
    "Huang, J. et al. CHARMM36m: an improved force field for folded and intrinsically disordered proteins. "
    "Nat. Methods 14, 71–73 (2017).",
    "Vanommeslaeghe, K. et al. CHARMM general force field: a force field for drug-like molecules compatible with "
    "the CHARMM all-atom additive biological force fields. J. Comput. Chem. 31, 671–690 (2010).",
    "Lindorff-Larsen, K. et al. Improved side-chain torsion potentials for the Amber ff99SB protein force field. "
    "Proteins 78, 1950–1958 (2010).",
    "Wang, J. et al. Development and testing of a general amber force field. J. Comput. Chem. 25, 1157–1174 (2004).",
    "Sousa da Silva, A. W. & Vranken, W. F. ACPYPE – AnteChamber PYthon Parser interfacE. BMC Res. Notes 5, 367 (2012).",
    "Jorgensen, W. L. et al. Comparison of simple potential functions for simulating liquid water. "
    "J. Chem. Phys. 79, 926–935 (1983).",
    "Essmann, U. et al. A smooth particle mesh Ewald method. J. Chem. Phys. 103, 8577–8593 (1995).",
    "Hess, B. et al. LINCS: a linear constraint solver for molecular simulations. J. Comput. Chem. 18, 1463–1472 (1997).",
    "Bussi, G., Donadio, D. & Parrinello, M. Canonical sampling through velocity rescaling. "
    "J. Chem. Phys. 126, 014101 (2007).",
    "Parrinello, M. & Rahman, A. Polymorphic transitions in single crystals: a new molecular dynamics method. "
    "J. Appl. Phys. 52, 7182–7190 (1981).",
    "Valdés-Tresanco, M. S. et al. gmx_MMPBSA: a new tool to perform end-state free energy calculations with "
    "GROMACS. J. Chem. Theory Comput. 17, 6281–6291 (2021).",
]


# =====================================================================================================
#  Utilitários de documento
# =====================================================================================================
def _shade(cell: Any, color_hex: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color_hex)
    tc_pr.append(shd)


def _width_cm(doc: Any) -> float:
    s = doc.sections[0]
    return (s.page_width - s.left_margin - s.right_margin) / 360000


def bar(doc: Any, text: str, color: str = COLOR_SECTION_BAR) -> None:
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    cell.width = Cm(_width_cm(doc))
    _shade(cell, color)
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.add_run(text).bold = True
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def field_line(doc: Any, label: str, value: Any) -> None:
    if value in (None, "", "None"):
        return
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    p.add_run(f"{label}: ").bold = True
    p.add_run(str(value))


def para(doc: Any, text: str = "") -> Any:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.first_line_indent = INDENT
    if text:
        p.add_run(text)
    return p


def subheading(doc: Any, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(11)


class Numbering:
    """Numeração de figuras e tabelas (rótulo em negrito antes do texto, como no relatório do CODRUG)."""

    def __init__(self, lang: str, start_fig: int = 1):
        self.lang = lang
        self.fig = start_fig - 1
        self.tab = 0

    def caption(self, doc: Any, kind: str, text: str) -> None:
        if kind == "fig":
            self.fig += 1
            label = f"{'Figura' if self.lang == 'pt' else 'Figure'} {self.fig}."
        else:
            self.tab += 1
            label = f"{'Tabela' if self.lang == 'pt' else 'Table'} {self.tab}."
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.keep_with_next = True      # a legenda nunca fica sozinha no fim da página
        r = p.add_run(label)
        r.bold = True
        r.font.size = Pt(9)
        r2 = p.add_run(" " + text)
        r2.font.size = Pt(9)


def add_image(doc: Any, path: Optional[str], width_cm: float = 15.0) -> bool:
    if not path or not os.path.isfile(path):
        return False
    try:
        doc.add_picture(path, width=Cm(width_cm))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        return True
    except Exception:
        return False


def add_table(doc: Any, header: List[str], rows: List[List[Any]], font: int = 8) -> None:
    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        cell = table.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(str(h))
        run.bold = True
        run.font.size = Pt(font)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        _shade(cell, COLOR_SECTION_BAR)
    for row in rows:
        cells = table.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run("" if v is None else str(v))
            run.font.size = Pt(font)
            cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT if i == 0 else WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def f(v: Any, nd: int = 2, unit: str = "") -> str:
    try:
        return f"{float(v):.{nd}f}{unit}"
    except (TypeError, ValueError):
        return "—"


def pm(stats: Optional[Dict[str, float]], nd: int = 2) -> str:
    return f"{stats['mean']:.{nd}f} ± {stats['sd']:.{nd}f}" if stats else "—"


def _join(items: List[str], lang: str) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + (" e " if lang == "pt" else " and ") + items[-1]


def T(lang: str, pt: str, en: str) -> str:
    return pt if lang == "pt" else en


# =====================================================================================================
#  Discussão automática (a partir dos números de cada execução)
# =====================================================================================================
def _traj_ns(run: Dict[str, Any]) -> Optional[float]:
    for k in ("rmsd_bb", "rg", "sasa"):
        x = run["series"].get(k)
        if x is not None:
            return float(x["x"][-1])
    return None


def disc_equilibration(run: Dict[str, Any], lang: str) -> List[str]:
    out: List[str] = []
    em, pre, cfg = run["em"], run["pre"], run["cfg"]
    if em.get("epot") is not None:
        conv = em.get("converged")
        out.append(T(lang,
                     f"A minimização de energia (máxima descida) "
                     f"{'convergiu em ' + str(em.get('steps')) + ' passos' if conv else 'terminou'} com energia potencial de "
                     f"{em['epot']:.3e} kJ/mol e força máxima de {em.get('fmax', float('nan')):.0f} kJ/mol/nm, "
                     f"{'abaixo da tolerância de ' + format(em.get('fmax_tol', 0), 'g') + ' kJ/mol/nm, ' if conv else ''}"
                     f"o que indica a remoção de choques estéricos antes da dinâmica.",
                     f"Energy minimization (steepest descent) "
                     f"{'converged in ' + str(em.get('steps')) + ' steps' if conv else 'finished'} with a potential energy of "
                     f"{em['epot']:.3e} kJ/mol and a maximum force of {em.get('fmax', float('nan')):.0f} kJ/mol/nm, "
                     f"{'below the ' + format(em.get('fmax_tol', 0), 'g') + ' kJ/mol/nm tolerance, ' if conv else ''}"
                     f"indicating that steric clashes were removed before the dynamics."))
    ref_t = float(cfg.get("temperature_K") or 0) or None
    t = desc(_y(pre.get("temperature")))
    if t and ref_t:
        dev = t["mean"] - ref_t
        out.append(T(lang,
                     f"Na equilibração NVT a temperatura média foi de {t['mean']:.1f} ± {t['sd']:.1f} K para o valor-alvo de "
                     f"{ref_t:g} K (desvio de {dev:+.1f} K), {'confirmando que o termostato manteve o sistema na temperatura desejada' if abs(dev) < 3 else 'com desvio relevante, que pode indicar equilibração insuficiente'}.",
                     f"During NVT equilibration the mean temperature was {t['mean']:.1f} ± {t['sd']:.1f} K for a target of "
                     f"{ref_t:g} K (deviation of {dev:+.1f} K), {'confirming that the thermostat kept the system at the desired temperature' if abs(dev) < 3 else 'a relevant deviation that may indicate insufficient equilibration'}."))
    pr, de = desc(_y(pre.get("pressure"))), desc(_y(pre.get("density")))
    if pr or de:
        a = T(lang, "Na etapa NPT ", "In the NPT stage ")
        if pr:
            a += T(lang, f"a pressão média foi de {pr['mean']:.1f} ± {pr['sd']:.0f} bar (alvo de 1 bar); flutuações de centenas de bar são "
                         f"esperadas em sistemas desse tamanho e a média é o que deve ser comparada ao alvo",
                   f"the mean pressure was {pr['mean']:.1f} ± {pr['sd']:.0f} bar (target 1 bar); fluctuations of hundreds of bar "
                   f"are expected for systems of this size and it is the mean that should be compared to the target")
        if pr and de:
            a += T(lang, ", e ", ", and ")
        if de:
            ok = 980 <= de["mean"] <= 1060
            a += T(lang, f"a densidade média foi de {de['mean']:.0f} ± {de['sd']:.0f} kg/m³, "
                         f"{'compatível com a de um sistema aquoso solvatado (~1000–1030 kg/m³)' if ok else 'fora da faixa típica de sistemas aquosos solvatados (~1000–1030 kg/m³)'}",
                   f"the mean density was {de['mean']:.0f} ± {de['sd']:.0f} kg/m³, "
                   f"{'consistent with a solvated aqueous system (~1000–1030 kg/m³)' if ok else 'outside the typical range of solvated aqueous systems (~1000–1030 kg/m³)'}")
        out.append(a + ".")
    return out


def disc_production(run: Dict[str, Any], lang: str) -> List[str]:
    out: List[str] = []
    S = run["series"]
    ns = _traj_ns(run)
    bb, lg = S.get("rmsd_bb"), S.get("rmsd_lig")
    if bb is not None:
        y = _y(bb)
        d = desc(y)
        a, b, c = thirds(y)
        drift = c - b
        stable = abs(drift) < 0.05 and d["sd"] < 0.1
        s = T(lang,
              f"O RMSD do esqueleto da proteína (ajustado a ele mesmo) teve média de {d['mean']:.3f} ± {d['sd']:.3f} nm "
              f"(máximo de {d['max']:.3f} nm). A média no terço final ({c:.3f} nm) difere {abs(drift):.3f} nm da do terço central ({b:.3f} nm), "
              f"{'sugerindo que a estrutura atingiu um platô' if stable else 'sem platô claro, o que sugere que a proteína ainda se reorganizava'}.",
              f"The protein backbone RMSD (self-fitted) averaged {d['mean']:.3f} ± {d['sd']:.3f} nm (maximum {d['max']:.3f} nm). "
              f"The mean over the final third ({c:.3f} nm) differs by {abs(drift):.3f} nm from the middle third ({b:.3f} nm), "
              f"{'suggesting the structure reached a plateau' if stable else 'with no clear plateau, suggesting the protein was still rearranging'}.")
        out.append(s)
    if lg is not None:
        y = _y(lg)
        d = desc(y)
        verdict = T(lang, "pose estável no sítio", "stable pose in the site") if d["mean"] <= 0.2 else (
            T(lang, "mobilidade moderada do ligante", "moderate ligand mobility") if d["mean"] <= 0.4 else
            T(lang, "grande deslocamento/reorientação do ligante", "large ligand displacement/reorientation"))
        out.append(T(lang,
                     f"O RMSD do ligante (após ajuste ao esqueleto da proteína) foi de {d['mean']:.3f} ± {d['sd']:.3f} nm "
                     f"(máximo de {d['max']:.3f} nm), valor compatível com {verdict}.",
                     f"The ligand RMSD (after fitting to the protein backbone) was {d['mean']:.3f} ± {d['sd']:.3f} nm "
                     f"(maximum {d['max']:.3f} nm), a value consistent with {verdict}."))
    dist = S.get("dist")
    if dist is not None:
        y = _y(dist)
        d = desc(y)
        moved = d["max"] - d["first"]
        out.append(T(lang,
                     f"A distância entre os centros de massa da proteína e do ligante foi de {d['mean']:.2f} ± {d['sd']:.2f} nm "
                     f"(inicial {d['first']:.2f} nm; final {d['last']:.2f} nm). "
                     f"{'O ligante permaneceu associado à proteína durante a simulação.' if moved < 0.5 else 'O aumento de ' + format(moved, '.2f') + ' nm indica afastamento do ligante em relação à posição inicial, devendo ser verificado visualmente.'}",
                     f"The distance between the centers of mass of the protein and the ligand was {d['mean']:.2f} ± {d['sd']:.2f} nm "
                     f"(initial {d['first']:.2f} nm; final {d['last']:.2f} nm). "
                     f"{'The ligand remained associated with the protein throughout the simulation.' if moved < 0.5 else 'The increase of ' + format(moved, '.2f') + ' nm indicates the ligand moved away from its initial position and should be inspected visually.'}"))
    rmsf = S.get("rmsf")
    if rmsf is not None:
        y = _y(rmsf)
        order = np.argsort(y)[::-1][:5]
        res = [str(int(rmsf["x"][i])) for i in order]
        out.append(T(lang,
                     f"A flutuação por resíduo (RMSF dos C-alfa) teve média de {np.mean(y):.3f} nm; as regiões mais móveis estão "
                     f"nos resíduos {_join(res, lang)} (RMSF entre {np.max(y):.3f} e {y[order[-1]]:.3f} nm), em geral alças e extremidades, "
                     f"enquanto os elementos de estrutura secundária e o sítio de ligação tendem a flutuar menos.",
                     f"The per-residue fluctuation (C-alpha RMSF) averaged {np.mean(y):.3f} nm; the most mobile regions are "
                     f"residues {_join(res, lang)} (RMSF between {np.max(y):.3f} and {y[order[-1]]:.3f} nm), usually loops and termini, "
                     f"whereas secondary-structure elements and the binding site tend to fluctuate less."))
    rg, sa = S.get("rg"), S.get("sasa")
    if rg is not None or sa is not None:
        a = ""
        if rg is not None:
            y = _y(rg)
            d = desc(y)
            first, _, last = thirds(y)
            ch = (last - first) / first * 100 if first else 0
            a += T(lang, f"O raio de giração da proteína foi de {d['mean']:.3f} ± {d['sd']:.3f} nm, com variação de {ch:+.1f}% entre o início e o fim, "
                         f"{'indicando compactação estável' if abs(ch) < 2 else 'indicando mudança de compactação a ser examinada'}",
                   f"The protein radius of gyration was {d['mean']:.3f} ± {d['sd']:.3f} nm, a change of {ch:+.1f}% from start to end, "
                   f"{'indicating a stable compactness' if abs(ch) < 2 else 'indicating a change in compactness that deserves examination'}")
        if sa is not None:
            d = desc(_y(sa))
            a += (T(lang, "; ", "; ") if a else "") + T(lang, f"a SASA média foi de {d['mean']:.1f} ± {d['sd']:.1f} nm²",
                                                         f"the mean SASA was {d['mean']:.1f} ± {d['sd']:.1f} nm²")
        out.append(a + ".")
    hb = S.get("hbonds")
    if hb is not None:
        y = _y(hb)
        d = desc(y)
        frac = float(np.mean(y >= 1)) * 100
        out.append(T(lang,
                     f"Foram observadas em média {d['mean']:.2f} ± {d['sd']:.2f} ligações de hidrogênio entre proteína e ligante "
                     f"(máximo de {d['max']:.0f}); ao menos uma ligação esteve presente em {frac:.0f}% dos quadros.",
                     f"On average {d['mean']:.2f} ± {d['sd']:.2f} protein–ligand hydrogen bonds were observed "
                     f"(maximum {d['max']:.0f}); at least one bond was present in {frac:.0f}% of the frames."))
    if ns is not None and ns < 10:
        out.append(T(lang,
                     f"Ressalva: a trajetória analisada tem {ns:.2f} ns, curta para concluir sobre convergência e estabilidade de longo "
                     f"prazo; recomenda-se estender a simulação (idealmente ≥ 50–100 ns, com réplicas) antes de generalizar as observações.",
                     f"Caveat: the analyzed trajectory is {ns:.2f} ns long, which is short for conclusions about convergence and "
                     f"long-term stability; the simulation should be extended (ideally ≥ 50–100 ns, with replicas) before generalizing."))
    return out


def disc_mm(run: Dict[str, Any], lang: str) -> List[str]:
    mm = run.get("mm")
    if not mm:
        return []
    out: List[str] = []
    model = "GB" if "GB" in mm["models"] else next(iter(mm["models"]))
    c = mm["models"][model]
    tot = c.get("TOTAL")
    if not tot:
        return []
    name = T(lang, "MM/GBSA" if model == "GB" else "MM/PBSA", "MM/GBSA" if model == "GB" else "MM/PBSA")
    parts = {k: c[k][0] for k in ("VDWAALS", "EEL", "EGB", "EPB", "ESURF", "ENPOLAR") if k in c}
    gas_vdw, gas_eel = parts.get("VDWAALS"), parts.get("EEL")
    dom = ""
    if gas_vdw is not None and gas_eel is not None:
        if abs(gas_vdw) > abs(gas_eel):
            dom = T(lang, "a contribuição dispersiva/hidrofóbica (van der Waals) supera a eletrostática em fase gasosa, típico de ligantes apolares ou com o sítio predominantemente hidrofóbico",
                    "the dispersive/hydrophobic (van der Waals) contribution exceeds the gas-phase electrostatics, typical of apolar ligands or predominantly hydrophobic sites")
        else:
            dom = T(lang, "a contribuição eletrostática em fase gasosa supera a de van der Waals, mas é em grande parte compensada pela penalidade de dessolvatação polar",
                    "the gas-phase electrostatic contribution exceeds van der Waals, but is largely offset by the polar desolvation penalty")
    out.append(T(lang,
                 f"A energia livre de ligação estimada por {name} foi ΔG = {tot[0]:.2f} ± {tot[1]:.2f} kcal/mol (SEM {tot[2]:.2f}) "
                 f"em {mm.get('frames') or '?'} quadros. {'O valor negativo indica ligação termodinamicamente favorável' if tot[0] < 0 else 'O valor positivo indica ligação desfavorável nesta estimativa'}"
                 f"{'; ' + dom if dom else ''}.",
                 f"The binding free energy estimated by {name} was ΔG = {tot[0]:.2f} ± {tot[1]:.2f} kcal/mol (SEM {tot[2]:.2f}) "
                 f"over {mm.get('frames') or '?'} frames. {'The negative value indicates thermodynamically favorable binding' if tot[0] < 0 else 'The positive value indicates unfavorable binding in this estimate'}"
                 f"{'; ' + dom if dom else ''}."))
    if mm.get("frames") and mm["frames"] < 50:
        out.append(T(lang,
                     f"Atenção: apenas {mm['frames']} quadros foram usados; para estimativas robustas recomenda-se pelo menos 100 quadros "
                     f"de uma trajetória já equilibrada, e os valores devem ser tratados como indicativos.",
                     f"Warning: only {mm['frames']} frames were used; for robust estimates at least 100 frames from an equilibrated "
                     f"trajectory are recommended, and the values should be treated as indicative."))
    if run.get("decomp"):
        top = run["decomp"][:5]
        out.append(T(lang,
                     f"Na decomposição por resíduo, os que mais contribuem para a ligação são {_join([f'{r} ({v:.1f} kcal/mol)' for r, v, _ in top], lang)}; "
                     f"estes resíduos definem os principais contatos do ligante e são candidatos a mutagênese ou a otimização química.",
                     f"In the per-residue decomposition, the residues contributing most to binding are {_join([f'{r} ({v:.1f} kcal/mol)' for r, v, _ in top], lang)}; "
                     f"these residues define the main contacts of the ligand and are candidates for mutagenesis or chemical optimization."))
    out.append(T(lang,
                 "Como os métodos de ponto final desprezam a entropia conformacional e usam solvente implícito, os valores absolutos "
                 "superestimam a afinidade experimental; a interpretação mais segura é comparativa entre ligantes do mesmo alvo.",
                 "Because end-point methods neglect conformational entropy and use implicit solvent, absolute values overestimate "
                 "the experimental affinity; the safest interpretation is comparative among ligands of the same target."))
    return out


# =====================================================================================================
#  Seções do documento
# =====================================================================================================
METHOD_LABELS = {"cgenff": "CGenFF", "gaff2": "GAFF2", "gaff": "GAFF"}


def _cfg_signature(cfg: Dict[str, Any]) -> str:
    keys = ("force_field", "solvent_model", "ligand_method", "ligand_charge_model", "box_type", "box_distance_nm",
            "positive_ion", "negative_ion", "ion_concentration_M", "production_time_ns", "equilibration_time_ns",
            "integration_time_fs", "temperature_K", "n_threads", "use_gpu", "ignore_hydrogens")
    return json.dumps({k: cfg.get(k) for k in keys}, sort_keys=True)


def _cfg_rows(cfg: Dict[str, Any], run: Dict[str, Any], lang: str) -> List[Tuple[str, str]]:
    ff = FORCE_FIELDS.get(cfg.get("force_field", ""), {})
    water = WATER_MODELS.get(cfg.get("solvent_model", ""), (cfg.get("solvent_model", "—"),))[0]
    method = METHOD_LABELS.get(cfg.get("ligand_method", ""), cfg.get("ligand_method", "—"))
    if cfg.get("ligand_method") in ("gaff", "gaff2"):
        method += " + " + {"bcc": "AM1-BCC", "gas": "Gasteiger"}.get(cfg.get("ligand_charge_model", "bcc"), "AM1-BCC")
    md = run.get("md", {})
    return [
        (T(lang, "Campo de força", "Force field"), ff.get("label", cfg.get("force_field", "—"))),
        (T(lang, "Modelo de água", "Water model"), water),
        (T(lang, "Parametrização do ligante", "Ligand parametrization"), method),
        (T(lang, "Caixa", "Box"), f"{cfg.get('box_type', '—')}, {cfg.get('box_distance_nm', '—')} nm"),
        (T(lang, "Íons", "Ions"), f"{cfg.get('positive_ion', '—')}/{cfg.get('negative_ion', '—')}, {cfg.get('ion_concentration_M', '—')} M"),
        (T(lang, "Temperatura", "Temperature"), f"{cfg.get('temperature_K', '—')} K"),
        (T(lang, "Passo de integração", "Integration time step"), f"{cfg.get('integration_time_fs', '—')} fs"),
        (T(lang, "Equilibração (NVT e NPT, cada)", "Equilibration (NVT and NPT, each)"), f"{cfg.get('equilibration_time_ns', '—')} ns"),
        (T(lang, "Produção", "Production"), f"{cfg.get('production_time_ns', '—')} ns"),
        (T(lang, "Termostato / barostato", "Thermostat / barostat"), f"{md.get('tcoupl', '—')} / {md.get('pcoupl', '—') or '—'}"),
        (T(lang, "Hardware (GROMACS)", "Hardware (GROMACS)"),
         f"{cfg.get('n_threads', '—')} threads, " + (T(lang, "GPU", "GPU") if cfg.get("use_gpu") else "CPU")),
    ]


def _hardware_text() -> str:
    try:
        from BIN import hw_info
        cpu = dict(hw_info.cpu_info())
        gpu = dict(hw_info.gpu_info())
        s = f"{cpu.get('hw_model', '?')} ({cpu.get('hw_threads', '?')} threads, {cpu.get('hw_ram', '?')})"
        if gpu.get("hw_gpu") and "not" not in gpu["hw_gpu"].lower():
            s += f"; {gpu['hw_gpu']} ({gpu.get('hw_vram', '?')})"
        return s
    except Exception:
        return ""


def _parse_project_started(name: str) -> Optional[datetime]:
    try:
        return datetime.strptime(name[:16], "%Y-%m-%d_%H-%M")
    except ValueError:
        return None


def add_intro(doc: Any, fig_path: Optional[str], num: Numbering, lang: str) -> None:
    t = INTRO[lang]
    bar(doc, t["title"][0], COLOR_TITLE_BAR)
    for p in t["p"]:
        para(doc, p)
    doc.add_paragraph()
    if fig_path:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.keep_with_next = True
        num.fig += 1
        r = p.add_run(t["fig1"].split(". ", 1)[0] + ".")
        r.bold = True
        r.font.size = Pt(9)
        r2 = p.add_run(" " + t["fig1"].split(". ", 1)[1])
        r2.font.size = Pt(9)
        add_image(doc, fig_path, 16.0)
    doc.add_page_break()


def add_header(doc: Any, project: str, runs: List[Dict[str, Any]], gmxi: Dict[str, str], lang: str, now: datetime) -> None:
    bar(doc, T(lang, "RELATÓRIO FINAL CODYN: Método e Resultados", "CODYN FINAL REPORT: Method and Results"), COLOR_TITLE_BAR)
    field_line(doc, T(lang, "Projeto", "Project"), project)
    field_line(doc, T(lang, "Versão do CODYN", "CODYN Version"), VERSAO)
    field_line(doc, T(lang, "Versão do GROMACS", "GROMACS Version"), gmxi.get("version", ""))
    field_line(doc, T(lang, "Execuções (proteína–ligante)", "Runs (protein–ligand)"),
               f"{len(runs)}: " + ", ".join(f"{r['protein']}–{r['ligand']}" for r in runs))
    field_line(doc, "Hardware", _hardware_text())
    started = _parse_project_started(project)
    if started:
        field_line(doc, T(lang, "Projeto criado em", "Project created"), started.strftime("%Y-%m-%d %H:%M"))
    field_line(doc, T(lang, "Relatório gerado em", "Report generated"), now.strftime("%Y-%m-%d %H:%M"))
    doc.add_paragraph()


def add_config(doc: Any, runs: List[Dict[str, Any]], num: Numbering, lang: str) -> None:
    bar(doc, T(lang, "CONFIGURAÇÕES EMPREGADAS", "SETTINGS USED"))
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in runs:
        groups.setdefault(_cfg_signature(r["cfg"]), []).append(r)
    para(doc, T(lang,
                "A Tabela abaixo resume os parâmetros da simulação registrados em run_config.json de cada execução. "
                + ("Todas as execuções usaram a mesma configuração." if len(groups) == 1 else
                   f"As execuções se dividem em {len(groups)} configurações distintas, uma por coluna."),
                "The Table below summarizes the simulation parameters recorded in each run's run_config.json. "
                + ("All runs used the same configuration." if len(groups) == 1 else
                   f"The runs split into {len(groups)} distinct configurations, one per column.")))
    cols = list(groups.values())
    header = [T(lang, "Parâmetro", "Parameter")] + [", ".join(x["ligand"] for x in g)[:40] if len(cols) > 1 else T(lang, "Valor", "Value") for g in cols]
    base_rows = [_cfg_rows(g[0]["cfg"], g[0], lang) for g in cols]
    rows = [[base_rows[0][i][0]] + [br[i][1] for br in base_rows] for i in range(len(base_rows[0]))]
    num.caption(doc, "tab", T(lang, "Parâmetros da simulação.", "Simulation parameters."))
    add_table(doc, header, rows)


def add_step1(doc: Any, runs: List[Dict[str, Any]], num: Numbering, lang: str) -> None:
    bar(doc, T(lang, "STEP 1 - PREPARO DOS LIGANTES", "STEP 1 - LIGAND PREPARATION"))
    cfg = runs[0]["cfg"]
    method = cfg.get("ligand_method", "cgenff")
    names = _join([r["ligand"] for r in runs], lang)
    para(doc, T(lang,
                f"Cada ligante ({names}) foi convertido do formato de entrada para PDB e MOL2 com o Open Babel, com adição de "
                f"hidrogênios e cargas parciais de Gasteiger usadas apenas como estimativa inicial. O resíduo do ligante foi "
                f"renomeado para {LIG_RESNAME} em todas as execuções, o que evita conflitos de nomes na topologia.",
                f"Each ligand ({names}) was converted from its input format to PDB and MOL2 with Open Babel, adding hydrogens and "
                f"Gasteiger partial charges used only as an initial estimate. The ligand residue was renamed to {LIG_RESNAME} in all "
                f"runs, which avoids naming conflicts in the topology."))
    if method == "cgenff":
        para(doc, T(lang,
                    "A topologia foi gerada com o CGenFF (CHARMM General Force Field): o arquivo MOL2 foi enviado ao servidor CGenFF e o "
                    "arquivo de parâmetros (.str) retornado foi importado, validado (inclusive as penalidades de parâmetros e de cargas) "
                    "e convertido para o formato do GROMACS (cgenff_charmm2gmx). Penalidades abaixo de 10 indicam boa analogia com "
                    "parâmetros já otimizados; entre 10 e 50 recomenda-se validação; acima de 50 a parametrização é pouco confiável.",
                    "The topology was generated with CGenFF (CHARMM General Force Field): the MOL2 file was submitted to the CGenFF server "
                    "and the returned parameter file (.str) was imported, validated (including parameter and charge penalties) and "
                    "converted to GROMACS format (cgenff_charmm2gmx). Penalties below 10 indicate good analogy with already "
                    "optimized parameters; between 10 and 50 validation is recommended; above 50 the parametrization is unreliable."))
    else:
        cm = {"bcc": "AM1-BCC", "gas": "Gasteiger"}.get(cfg.get("ligand_charge_model", "bcc"), "AM1-BCC")
        para(doc, T(lang,
                    f"A topologia foi gerada automaticamente com o acpype/AmberTools (antechamber, parmchk2 e tleap), com tipos atômicos "
                    f"{method.upper()} e cargas {cm}. A carga líquida de cada ligante foi detectada a partir da estrutura (ou fornecida "
                    f"manualmente) e conferida contra a soma das cargas do arquivo .itp.",
                    f"The topology was generated automatically with acpype/AmberTools (antechamber, parmchk2 and tleap), with "
                    f"{method.upper()} atom types and {cm} charges. The net charge of each ligand was detected from the structure (or "
                    f"given manually) and checked against the sum of the charges in the .itp file."))
    rows = []
    for r in runs:
        lg, cg = r["lig"], r["lig"].get("cgenff") or {}
        rows.append([r["ligand"], METHOD_LABELS.get(method, method), lg.get("n_atoms", "—"), f(lg.get("net_charge"), 3),
                     f"{f(cg.get('param_penalty'), 1)} / {f(cg.get('charge_penalty'), 1)}" if cg else "—"])
    num.caption(doc, "tab", T(lang, "Ligantes parametrizados: número de átomos, carga líquida da topologia e penalidades CGenFF (parâmetros / cargas).",
                              "Parametrized ligands: number of atoms, net charge of the topology and CGenFF penalties (parameters / charges)."))
    add_table(doc, [T(lang, "Ligante", "Ligand"), T(lang, "Método", "Method"), T(lang, "Átomos", "Atoms"),
                    T(lang, "Carga líquida", "Net charge"), T(lang, "Penalidades", "Penalties")], rows)


def add_step2(doc: Any, runs: List[Dict[str, Any]], lang: str) -> None:
    bar(doc, T(lang, "STEP 2 - PREPARO DO COMPLEXO", "STEP 2 - COMPLEX PREPARATION"))
    cfg = runs[0]["cfg"]
    ff = FORCE_FIELDS.get(cfg.get("force_field", ""), {})
    water = WATER_MODELS.get(cfg.get("solvent_model", ""), (cfg.get("solvent_model", ""),))[0]
    para(doc, T(lang,
                f"A topologia da proteína ({runs[0]['protein']}) foi construída com o pdb2gmx, usando o campo de força "
                f"{ff.get('label', cfg.get('force_field', ''))} e o modelo de água {water}"
                f"{', com remoção e reconstrução dos hidrogênios do PDB (-ignh)' if cfg.get('ignore_hydrogens') else ''}. As coordenadas do ligante "
                f"foram incorporadas às da proteína e a topologia do ligante ({LIG_RESNAME}.itp) foi incluída na topologia do sistema, "
                f"junto com restrições de posição para a etapa de equilibração.",
                f"The protein topology ({runs[0]['protein']}) was built with pdb2gmx using the {ff.get('label', cfg.get('force_field', ''))} "
                f"force field and the {water} water model"
                f"{', removing and rebuilding the PDB hydrogens (-ignh)' if cfg.get('ignore_hydrogens') else ''}. The ligand coordinates were "
                f"merged with those of the protein and the ligand topology ({LIG_RESNAME}.itp) was included in the system topology, "
                f"together with position restraints for the equilibration stage."))


def add_step3(doc: Any, runs: List[Dict[str, Any]], num: Numbering, lang: str) -> None:
    bar(doc, T(lang, "STEP 3 - CÉLULA UNITÁRIA E MINIMIZAÇÃO", "STEP 3 - UNIT CELL AND MINIMIZATION"))
    cfg, em = runs[0]["cfg"], runs[0]["em"].get("mdp", {})
    para(doc, T(lang,
                f"O complexo foi centralizado em uma caixa {cfg.get('box_type', '')} com distância mínima de "
                f"{cfg.get('box_distance_nm', '')} nm entre o soluto e as bordas (editconf), solvatado com o modelo de água "
                f"{WATER_MODELS.get(cfg.get('solvent_model', ''), ('',))[0]} (solvate) e neutralizado com íons "
                f"{cfg.get('positive_ion', '')}/{cfg.get('negative_ion', '')} até a concentração de {cfg.get('ion_concentration_M', '')} M (genion). "
                f"Em seguida o sistema foi minimizado por {em.get('integrator') or 'steep'} (até {em.get('nsteps') or '—'} passos) para remover "
                f"contatos desfavoráveis.",
                f"The complex was centered in a {cfg.get('box_type', '')} box with a minimum distance of {cfg.get('box_distance_nm', '')} nm "
                f"between the solute and the box edges (editconf), solvated with the "
                f"{WATER_MODELS.get(cfg.get('solvent_model', ''), ('',))[0]} water model (solvate) and neutralized with "
                f"{cfg.get('positive_ion', '')}/{cfg.get('negative_ion', '')} ions up to a concentration of {cfg.get('ion_concentration_M', '')} M "
                f"(genion). The system was then minimized with {em.get('integrator') or 'steep'} (up to {em.get('nsteps') or '—'} steps) to remove "
                f"unfavorable contacts."))
    rows = []
    for r in runs:
        mols = dict(r["system"]["molecules"])
        pos, neg = cfg.get("positive_ion"), cfg.get("negative_ion")
        sol = mols.get("SOL", mols.get("WAT"))
        box = r["system"]["box"]
        rows.append([r["ligand"], r["system"]["n_atoms"] or "—", sol or "—", mols.get(pos, "—"), mols.get(neg, "—"),
                     f"{box[0]:.2f}" if box else "—", f(r["em"].get("epot"), 0)])
    num.caption(doc, "tab", T(lang, "Composição do sistema solvatado, aresta da caixa e energia potencial após a minimização.",
                              "Composition of the solvated system, box edge and potential energy after minimization."))
    add_table(doc, [T(lang, "Ligante", "Ligand"), T(lang, "Átomos", "Atoms"), T(lang, "Águas", "Waters"),
                    f"{cfg.get('positive_ion', '+')}", f"{cfg.get('negative_ion', '-')}",
                    T(lang, "Caixa (nm)", "Box (nm)"), "Epot EM (kJ/mol)"], rows)


def add_step4(doc: Any, runs: List[Dict[str, Any]], num: Numbering, lang: str) -> None:
    bar(doc, T(lang, "STEP 4 - EQUILIBRAÇÃO DO SISTEMA", "STEP 4 - SYSTEM EQUILIBRATION"))
    r0 = runs[0]
    nvt, npt = r0["nvt"], r0["npt"]

    def ps(d):
        try:
            return float(d["dt"]) * int(float(d["nsteps"]))
        except (ValueError, KeyError, TypeError):
            return None

    para(doc, T(lang,
                f"A equilibração ocorreu em dois estágios com restrições de posição ({nvt.get('define') or '—'}) sobre a proteína e o ligante. "
                f"No estágio NVT ({f(ps(nvt), 0)} ps) o termostato {nvt.get('tcoupl') or '—'} acoplou os grupos {nvt.get('tc-grps') or '—'} "
                f"(τ = {nvt.get('tau_t') or '—'} ps) a {nvt.get('ref_t') or '—'} K. No estágio NPT ({f(ps(npt), 0)} ps) foi adicionado o barostato "
                f"{npt.get('pcoupl') or '—'} ({npt.get('pcoupltype') or '—'}, τp = {npt.get('tau_p') or '—'} ps, {npt.get('ref_p') or '—'} bar). "
                f"Em ambos, as interações eletrostáticas de longo alcance foram tratadas por {npt.get('coulombtype') or '—'} "
                f"(corte de {npt.get('rcoulomb') or '—'} nm), as de van der Waals com corte de {npt.get('rvdw') or '—'} nm "
                f"({npt.get('vdw-modifier') or '—'}) e as ligações com hidrogênio foram restritas por {npt.get('constraint_algorithm') or 'LINCS'} "
                f"({npt.get('constraints') or '—'}).",
                f"Equilibration took place in two stages with position restraints ({nvt.get('define') or '—'}) on the protein and the ligand. "
                f"In the NVT stage ({f(ps(nvt), 0)} ps) the {nvt.get('tcoupl') or '—'} thermostat coupled the groups {nvt.get('tc-grps') or '—'} "
                f"(τ = {nvt.get('tau_t') or '—'} ps) at {nvt.get('ref_t') or '—'} K. In the NPT stage ({f(ps(npt), 0)} ps) the "
                f"{npt.get('pcoupl') or '—'} barostat was added ({npt.get('pcoupltype') or '—'}, τp = {npt.get('tau_p') or '—'} ps, "
                f"{npt.get('ref_p') or '—'} bar). In both, long-range electrostatics were handled by {npt.get('coulombtype') or '—'} "
                f"({npt.get('rcoulomb') or '—'} nm cutoff), van der Waals with a {npt.get('rvdw') or '—'} nm cutoff "
                f"({npt.get('vdw-modifier') or '—'}) and bonds to hydrogen were constrained by {npt.get('constraint_algorithm') or 'LINCS'} "
                f"({npt.get('constraints') or '—'})."))


def add_step5(doc: Any, runs: List[Dict[str, Any]], num: Numbering, lang: str) -> None:
    bar(doc, T(lang, "STEP 5 - DINÂMICA MOLECULAR DE PRODUÇÃO", "STEP 5 - PRODUCTION MOLECULAR DYNAMICS"))
    r0 = runs[0]
    md = r0["md"]
    try:
        total_ns = float(md["dt"]) * int(float(md["nsteps"])) / 1000.0
    except (ValueError, KeyError, TypeError):
        total_ns = None
    para(doc, T(lang,
                f"A produção foi realizada sem restrições de posição por {f(total_ns, 3)} ns (passo de {md.get('dt') or '—'} ps; "
                f"{md.get('nsteps') or '—'} passos), mantendo o termostato {md.get('tcoupl') or '—'} e o barostato {md.get('pcoupl') or '—'}, "
                f"com coordenadas gravadas a cada {md.get('nstxout-compressed') or '—'} passos. A execução usou o mdrun do GROMACS "
                f"{'com aceleração por GPU (não-ligado, PME, ligado e atualização, com recuo automático para configurações mais leves se necessário)' if r0['cfg'].get('use_gpu') else 'somente em CPU'}. "
                f"Ao final, os artefatos de condição periódica foram removidos da trajetória (trjconv -pbc mol -center), centralizando a proteína.",
                f"Production was run without position restraints for {f(total_ns, 3)} ns ({md.get('dt') or '—'} ps time step; "
                f"{md.get('nsteps') or '—'} steps), keeping the {md.get('tcoupl') or '—'} thermostat and the {md.get('pcoupl') or '—'} barostat, "
                f"with coordinates saved every {md.get('nstxout-compressed') or '—'} steps. The run used GROMACS mdrun "
                f"{'with GPU acceleration (nonbonded, PME, bonded and update, with automatic fallback to lighter setups if needed)' if r0['cfg'].get('use_gpu') else 'on CPU only'}. "
                f"Afterwards, periodic-boundary artifacts were removed from the trajectory (trjconv -pbc mol -center), centering the protein."))
    rows = [[r["ligand"], f(_traj_ns(r), 3), f(r["perf"].get("ns_day"), 1), f(r["perf"].get("wall_s"), 0)] for r in runs]
    num.caption(doc, "tab", T(lang, "Tempo simulado analisado e desempenho do mdrun por execução.", "Analyzed simulated time and mdrun performance per run."))
    add_table(doc, [T(lang, "Ligante", "Ligand"), T(lang, "Trajetória (ns)", "Trajectory (ns)"), "ns/day", T(lang, "Tempo de parede (s)", "Wall time (s)")], rows)


def add_step6(doc: Any, runs: List[Dict[str, Any]], lang: str) -> None:
    done = [r for r in runs if r.get("mm")]
    bar(doc, T(lang, "STEP 6 - ENERGIA LIVRE DE LIGAÇÃO (MM/PBSA)", "STEP 6 - BINDING FREE ENERGY (MM/PBSA)"))
    if not done:
        para(doc, T(lang, "O MM/PBSA ainda não foi executado para as execuções deste projeto (STEP 6); esta seção e a discussão energética "
                          "foram omitidas.", "MM/PBSA has not been run for the runs of this project yet (STEP 6); this section and the energetic "
                          "discussion were omitted."))
        return
    m = done[0]["mm_in"]
    g = lambda k, d="—": (re.search(rf"{k}\s*=\s*([^\s,]+)", m) or [None, d])[1]  # noqa: E731
    para(doc, T(lang,
                f"A energia livre de ligação foi estimada com o gmx_MMPBSA (modelo Generalized Born, igb = {g('igb')}, sal = {g('saltcon')} M, "
                f"{done[0]['mm'].get('frames') or '—'} quadros, intervalo {g('interval')}), a partir da trajetória de produção sem artefatos "
                f"periódicos, tratando a proteína como receptor e o ligante {LIG_RESNAME} como ligante. Também foi feita a decomposição por "
                f"resíduo (idecomp = {g('idecomp')}). ΔG = G(complexo) − G(receptor) − G(ligante); valores negativos indicam ligação favorável.",
                f"The binding free energy was estimated with gmx_MMPBSA (Generalized Born model, igb = {g('igb')}, salt = {g('saltcon')} M, "
                f"{done[0]['mm'].get('frames') or '—'} frames, interval {g('interval')}) from the production trajectory with periodic artifacts "
                f"removed, treating the protein as receptor and the {LIG_RESNAME} ligand as ligand. Per-residue decomposition was also "
                f"performed (idecomp = {g('idecomp')}). ΔG = G(complex) − G(receptor) − G(ligand); negative values indicate favorable binding."))


def add_results(doc: Any, runs: List[Dict[str, Any]], fig_dir: str, num: Numbering, lang: str,
                progress: Callable[[str], None]) -> None:
    bar(doc, T(lang, "RESULTADOS E DISCUSSÃO", "RESULTS AND DISCUSSION"), COLOR_ACCENT_BAR)
    for r in runs:
        progress(f"Results: {r['protein']}-{r['ligand']}...")
        safe = re.sub(r"[^\w.-]", "_", r["name"])
        sub = os.path.join(fig_dir, safe)
        os.makedirs(sub, exist_ok=True)
        subheading(doc, f"{r['protein']} – {r['ligand']}")

        # equilibração
        para_list = disc_equilibration(r, lang)
        img = plot_equilibration(r, os.path.join(sub, "equilibration.png"), lang)
        if img:
            num.caption(doc, "fig", T(lang, f"Minimização e equilibração do sistema {r['protein']}–{r['ligand']}: energia potencial, temperatura (NVT), pressão e densidade (NPT); linhas tracejadas indicam a média.",
                                      f"Minimization and equilibration of the {r['protein']}–{r['ligand']} system: potential energy, temperature (NVT), pressure and density (NPT); dashed lines show the mean."))
            add_image(doc, img, 15.0)
        for t in para_list:
            para(doc, t)

        # produção
        img = plot_two_series(r, [("rmsd_bb", T(lang, "Esqueleto da proteína", "Protein backbone"), C_BLUE, "RMSD (nm)"),
                                  ("rmsd_lig", T(lang, "Ligante", "Ligand"), C_ORANGE, "RMSD (nm)")],
                              os.path.join(sub, "rmsd.png"))
        if img:
            num.caption(doc, "fig", T(lang, f"RMSD do esqueleto da proteína e do ligante ({r['ligand']}) ao longo da produção.",
                                      f"RMSD of the protein backbone and the ligand ({r['ligand']}) during production."))
            add_image(doc, img, 14.0)
        img = plot_rmsf(r, os.path.join(sub, "rmsf.png"))
        if img:
            num.caption(doc, "fig", T(lang, "RMSF por resíduo (C-alfa).", "Per-residue RMSF (C-alpha)."))
            add_image(doc, img, 14.0)
        img = plot_series_grid(r, [("rg", T(lang, "Raio de giração da proteína", "Protein radius of gyration"), "Rg (nm)", C_BLUE),
                                   ("sasa", T(lang, "Área acessível ao solvente", "Solvent-accessible surface area"), "SASA (nm²)", C_GREEN),
                                   ("hbonds", T(lang, "Ligações de hidrogênio proteína–ligante", "Protein–ligand hydrogen bonds"), T(lang, "Nº de ligações", "No. of bonds"), C_ORANGE),
                                   ("dist", T(lang, "Distância entre centros de massa", "Center-of-mass distance"), "d (nm)", C_GREY)],
                               os.path.join(sub, "properties.png"))
        if img:
            num.caption(doc, "fig", T(lang, "Raio de giração, SASA, ligações de hidrogênio e distância proteína–ligante durante a produção.",
                                      "Radius of gyration, SASA, hydrogen bonds and protein–ligand distance during production."))
            add_image(doc, img, 15.0)
        prod = disc_production(r, lang)
        rows = []
        for key, label, nd in (("rmsd_bb", T(lang, "RMSD esqueleto (nm)", "Backbone RMSD (nm)"), 3), ("rmsd_lig", T(lang, "RMSD ligante (nm)", "Ligand RMSD (nm)"), 3),
                               ("rg", "Rg (nm)", 3), ("sasa", "SASA (nm²)", 1), ("hbonds", T(lang, "Ligações H", "H-bonds"), 2),
                               ("dist", T(lang, "Distância P–L (nm)", "P–L distance (nm)"), 2)):
            s = desc(_y(r["series"].get(key)))
            if s:
                rows.append([label, pm(s, nd), f(s["min"], nd), f(s["max"], nd)])
        if rows:
            num.caption(doc, "tab", T(lang, f"Estatísticas da trajetória de produção de {r['protein']}–{r['ligand']}.",
                                      f"Production trajectory statistics for {r['protein']}–{r['ligand']}."))
            add_table(doc, [T(lang, "Propriedade", "Property"), T(lang, "Média ± DP", "Mean ± SD"), T(lang, "Mínimo", "Minimum"), T(lang, "Máximo", "Maximum")], rows)
        for t in prod:
            para(doc, t)
        if not rows and not prod:
            para(doc, T(lang, "Não há trajetória de produção analisável nesta execução (a dinâmica de produção não foi concluída).",
                        "There is no analyzable production trajectory for this run (production dynamics did not finish)."))

        # MM/GBSA
        if r.get("mm"):
            comp = r["mm"]["models"].get("GB") or next(iter(r["mm"]["models"].values()))
            crow = [[("Δ" + k)] + [f"{round(x, 2) + 0.0:.2f}" for x in v[:3]] for k, v in comp.items()]  # sem "-0.00"
            num.caption(doc, "tab", T(lang, f"Componentes da energia livre de ligação (kcal/mol) de {r['ligand']}: média, desvio padrão e erro padrão.",
                                      f"Binding free energy components (kcal/mol) for {r['ligand']}: mean, standard deviation and standard error."))
            add_table(doc, [T(lang, "Componente", "Component"), T(lang, "Média", "Mean"), "SD", "SEM"], crow)
            img = plot_components(r, os.path.join(sub, "mm_components.png"), lang)
            if img:
                num.caption(doc, "fig", T(lang, "Componentes da energia livre de ligação (média ± DP).", "Binding free energy components (mean ± SD)."))
                add_image(doc, img, 14.0)
            img = plot_decomp(r, os.path.join(sub, "mm_decomp.png"))
            if img:
                num.caption(doc, "fig", T(lang, "Resíduos que mais contribuem para a energia livre de ligação (decomposição, ΔG por resíduo).",
                                          "Residues contributing most to the binding free energy (per-residue decomposition, ΔG)."))
                add_image(doc, img, 14.0)
            for t in disc_mm(r, lang):
                para(doc, t)


def add_comparison(doc: Any, runs: List[Dict[str, Any]], fig_dir: str, num: Numbering, lang: str) -> None:
    ranked = [r for r in runs if r.get("mm") and r["mm"]["models"].get("GB", {}).get("TOTAL")]
    if len(ranked) < 2:
        return
    subheading(doc, T(lang, "Comparação entre os ligantes", "Comparison among ligands"))
    ranked.sort(key=lambda r: r["mm"]["models"]["GB"]["TOTAL"][0])
    rows = []
    for i, r in enumerate(ranked, 1):
        t = r["mm"]["models"]["GB"]["TOTAL"]
        lg = desc(_y(r["series"].get("rmsd_lig")))
        hb = desc(_y(r["series"].get("hbonds")))
        rows.append([i, r["ligand"], f"{t[0]:.2f} ± {t[1]:.2f}", pm(lg, 3) if lg else "—", f"{hb['mean']:.2f}" if hb else "—"])
    num.caption(doc, "tab", T(lang, "Ranqueamento dos ligantes pela energia livre de ligação estimada (mais negativa primeiro).",
                              "Ranking of the ligands by estimated binding free energy (most negative first)."))
    add_table(doc, ["#", T(lang, "Ligante", "Ligand"), "ΔG (kcal/mol)", T(lang, "RMSD ligante (nm)", "Ligand RMSD (nm)"),
                    T(lang, "Ligações H (média)", "H-bonds (mean)")], rows)
    img = plot_mmgbsa_bars(ranked, os.path.join(fig_dir, "ranking.png"), lang)
    if img:
        num.caption(doc, "fig", T(lang, "ΔG de ligação (MM/GBSA) por ligante, com o desvio padrão.", "Binding ΔG (MM/GBSA) per ligand, with standard deviation."))
        add_image(doc, img, 14.0)
    best, worst = ranked[0], ranked[-1]
    gb, gw = best["mm"]["models"]["GB"]["TOTAL"], worst["mm"]["models"]["GB"]["TOTAL"]
    diff = gw[0] - gb[0]
    overlap = diff < (gb[1] + gw[1])
    para(doc, T(lang,
                f"Entre os {len(ranked)} ligantes, {best['ligand']} apresentou a energia livre de ligação mais favorável "
                f"({gb[0]:.2f} kcal/mol), e {worst['ligand']} a menos favorável ({gw[0]:.2f} kcal/mol), uma diferença de {diff:.2f} kcal/mol. "
                f"{'Como a diferença é comparável aos desvios padrão, o ranqueamento não é estatisticamente conclusivo e requer mais amostragem (trajetórias mais longas ou réplicas).' if overlap else 'A diferença supera os desvios padrão, o que reforça o ranqueamento obtido, embora ele deva ser confirmado com mais amostragem e, se possível, com dados experimentais.'}",
                f"Among the {len(ranked)} ligands, {best['ligand']} showed the most favorable binding free energy "
                f"({gb[0]:.2f} kcal/mol) and {worst['ligand']} the least favorable ({gw[0]:.2f} kcal/mol), a difference of {diff:.2f} kcal/mol. "
                f"{'Since the difference is comparable to the standard deviations, the ranking is not statistically conclusive and needs more sampling (longer trajectories or replicas).' if overlap else 'The difference exceeds the standard deviations, which supports the ranking obtained, although it should be confirmed with more sampling and, if possible, experimental data.'}"))


def add_conclusions(doc: Any, runs: List[Dict[str, Any]], lang: str) -> None:
    bar(doc, T(lang, "CONCLUSÕES E LIMITAÇÕES", "CONCLUSIONS AND LIMITATIONS"), COLOR_ACCENT_BAR)
    stable = []
    for r in runs:
        lg = desc(_y(r["series"].get("rmsd_lig")))
        if lg and lg["mean"] <= 0.3:
            stable.append(r["ligand"])
    s = T(lang, f"Foram simuladas {len(runs)} execução(ões) proteína–ligante com o protocolo descrito. ",
          f"{len(runs)} protein–ligand run(s) were simulated with the protocol described. ")
    if stable:
        s += T(lang, f"Os ligantes {_join(stable, lang)} permaneceram com RMSD médio ≤ 0,3 nm, compatível com ligação estável no sítio durante o tempo simulado. ",
               f"Ligands {_join(stable, lang)} kept a mean RMSD ≤ 0.3 nm, consistent with stable binding in the site during the simulated time. ")
    para(doc, s)
    para(doc, T(lang,
                "Limitações: o tempo de simulação, a ausência de réplicas independentes e o uso de uma única pose inicial limitam a "
                "amostragem conformacional; as energias MM/PBSA e MM/GBSA desprezam a entropia e dependem do solvente implícito; e a "
                "qualidade da parametrização do ligante (por exemplo, as penalidades do CGenFF) afeta diretamente os resultados. "
                "Recomenda-se estender as trajetórias, executar réplicas e validar os melhores candidatos experimentalmente.",
                "Limitations: simulation time, the absence of independent replicas and the use of a single starting pose limit conformational "
                "sampling; MM/PBSA and MM/GBSA energies neglect entropy and depend on the implicit solvent; and the quality of the ligand "
                "parametrization (e.g., CGenFF penalties) directly affects the results. Extending the trajectories, running replicas and "
                "validating the best candidates experimentally is recommended."))


def add_references(doc: Any, lang: str) -> None:
    bar(doc, T(lang, "REFERÊNCIAS", "REFERENCES"), COLOR_ACCENT_BAR)
    for i, ref in enumerate(REFERENCES, 1):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(f"[{i}] {ref}")
        r.font.size = Pt(9)


# =====================================================================================================
#  Ponto de entrada
# =====================================================================================================
def list_report_runs(project_dir: str) -> List[str]:
    runs_dir = os.path.join(project_dir, "RUNS")
    if not os.path.isdir(runs_dir):
        return []
    ok = []
    for d in sorted(os.listdir(runs_dir)):
        try:
            with open(os.path.join(runs_dir, d, "run_config.json"), "r", encoding="utf-8") as fh:
                if isinstance(json.load(fh), dict):
                    ok.append(d)
        except (OSError, ValueError):
            continue
    return ok


def generate_final_report(project_dir: str, lang: str = "pt", progress: Optional[Callable[[str], None]] = None,
                          token: Optional[CancelToken] = None, gmx: Optional[str] = None) -> str:
    """Gera o relatório do projeto e devolve o caminho do .docx. Levanta RuntimeError se não houver execuções."""
    require_docx()
    lang = "en" if lang == "en" else "pt"
    log = progress or (lambda msg: None)
    gmx = gmx or tools.find_gmx()
    project = os.path.basename(os.path.normpath(project_dir))
    names = list_report_runs(project_dir)
    if not names:
        raise RuntimeError(T(lang, "Este projeto não tem execuções (RUNS/<execução>/run_config.json).",
                             "This project has no runs (RUNS/<run>/run_config.json)."))
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d_%H-%M")
    results_dir = os.path.join(project_dir, "RESULTS")
    fig_dir = os.path.join(results_dir, f"figures_{stamp}")
    os.makedirs(fig_dir, exist_ok=True)

    runs: List[Dict[str, Any]] = []
    for n in names:
        if token is not None and token.is_set():
            raise PipelineCancelled()
        log(f"Collecting {n}...")
        runs.append(collect_run(os.path.join(project_dir, "RUNS", n), gmx, log, token))

    log("Building document...")
    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Cm(2)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)
    num = Numbering(lang)
    add_intro(doc, plot_workflow(os.path.join(fig_dir, "workflow.png"), lang), num, lang)
    add_header(doc, project, runs, tools.gmx_info(gmx) if gmx else {}, lang, now)
    add_config(doc, runs, num, lang)
    add_step1(doc, runs, num, lang)
    add_step2(doc, runs, lang)
    add_step3(doc, runs, num, lang)
    add_step4(doc, runs, num, lang)
    add_step5(doc, runs, num, lang)
    add_step6(doc, runs, lang)
    add_results(doc, runs, fig_dir, num, lang, log)
    add_comparison(doc, runs, fig_dir, num, lang)
    add_conclusions(doc, runs, lang)
    add_references(doc, lang)

    os.makedirs(results_dir, exist_ok=True)
    out = os.path.join(results_dir, f"{project}_REPORT_{stamp}.docx")
    doc.save(out)
    log(f"Saved {out}")
    return out
