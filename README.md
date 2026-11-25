# CODYN — Computational Platform for Molecular Dynamics

CODYN is a PyQt5 graphical tool that automates **protein–multiligand molecular dynamics with GROMACS**:
ligand parametrization (CHARMM36 + CGenFF, or AMBER + GAFF/GAFF2), complex assembly, solvation and
ionization, energy minimization, NVT/NPT equilibration, production, MM/GBSA with `gmx_MMPBSA` and
trajectory analysis (RMSD, RMSF, SASA, H-bonds, radius of gyration, center of mass).
The interface is available in **English and Portuguese** (flags in the top-right corner; the first
launch follows the system language).

## Installation

**Debian/Ubuntu/Mint package** (`packaging/dist/codyn_<version>_all.deb`):

```bash
sudo apt install ./packaging/dist/codyn_2.2.0-1_all.deb
```

**From source:**

```bash
git clone https://github.com/moimaian/CODYN ~/CODYN
python3 ~/CODYN/CODYN.py
```

On the first run CODYN creates its own Python environment (`~/.venv/CODYN`), installs PyQt5 and opens.
Everything else is installed from **Help > Install requirements** (or the HOME button): Python packages,
Open Babel, acpype, AmberTools (conda), CUDA toolkit, GROMACS (built from source, with CUDA when `nvcc`
exists) and gmx_MMPBSA. The window shows what is installed and pre-selects what is missing.

### Windows 10/11

Download the repository as a zip, extract it to any folder (e.g. `C:\Users\<you>\CODYN`) and **double-click
`CODYN_Windows.bat`** - there is no need to open PowerShell or type commands. (If Windows shows "Windows
protected your PC", click "More info" > "Run anyway".)

The script, on the first run only:

* looks for Python 3.10 or newer; if none is found, it downloads the official **Python 3.10.11** installer from
  python.org, checks its digital signature and installs it for the current user (no administrator rights);
* runs `python CODYN.py` already answering "yes" to the setup questions (`CODYN_ASSUME_YES=1`);
* the bootstrap then creates the virtual environment in `%USERPROFILE%\.venv\CODYN` with Python **3.10.11** (the
  last 3.10 release with an official Windows installer; on Linux any 3.10+ is accepted) and uses
  `%USERPROFILE%\.venv\CODYN\Scripts\python.exe` for every installation command (`python -m pip install ...`);
* installs the Visual C++ runtime required by the Qt5 DLLs (`winget install --id Microsoft.VCRedist.2015+.x64 -e`;
  Windows asks for confirmation) and PyQt5, opens CODYN and creates the `CODYN.lnk` shortcut on the Desktop and in
  the Start Menu (it starts CODYN with `Scripts\pythonw.exe`, without a console window; the program output is
  shown in **Help > Terminal**).

From then on, open CODYN with the shortcut and use **Help > Install requirements** for the rest. What is
different on Windows:

* **Open Babel** comes from the `openbabel-wheel` pip package and **Perl** (CGenFF preparation) from Strawberry
  Perl, installed with `winget`.
* **GROMACS** has no official Windows binary: the installer compiles it from source into `%USERPROFILE%\GROMACS`
  with CMake and the Visual Studio Build Tools (both installed with `winget` when missing; CUDA is used when the
  CUDA Toolkit is present). It takes a long time. If you already have a `gmx.exe`, set the `CODYN_GMX` environment
  variable to its path (or put it in `C:\Program Files\GROMACS*\bin`).
* **CHARMM36 + CGenFF** is the supported route. The **AMBER/GAFF** method needs AmberTools (antechamber, acpype),
  and **STEP 6 (MM/GBSA)** needs `gmx_MMPBSA` (which also needs AmberTools); AmberTools has no Windows build, so
  these two are Linux-only. All the other steps and the RESULTS tab (plots and final report) work on Windows.
* Keep project and ligand names short: Windows limits a full path to 260 characters.

## User manual

Step-by-step manuals (Portuguese and English) are in [`TUTORIALS/`](TUTORIALS/): `manual_do_usuario_CODYN_pt_BR`
and `User_manual_CODYN_en-US` (`.docx` and `.pdf`). They are regenerated, with fresh screenshots, by
`TUTORIALS/source/build_manual.py` (needs `python-docx` and LibreOffice).

## Workflow

1. **HOME** — hardware (CPU/GPU), software versions and the pipeline overview.
2. **CONFIG** — first create or load a **project** (group *Projects*): it makes
   `PROJECTS/<date>_<name>/` with `LIGANDS/`, `TARGET/` and `RUNS/`, so each work keeps its files apart from
   other projects. Then set force field, water model, ligand method, box, ions, times and hardware.
   Put ligands (`.pdbqt`, `.pdb`, `.mol2`, `.sdf`) in the project's `LIGANDS/` and the protein (`.pdb`) in its
   `TARGET/` (the *Open* button next to each folder opens it). The table lets you pick which ligands to run and
   override their net charge. The project also remembers the parameters of its last run.
3. **STEP 1–5** run automatically, one `PROJECTS/<project>/RUNS/<date>_<protein>_<ligand>/` folder per ligand
   (`run_config.json` records exactly what was simulated). A failed ligand does not stop the others.
4. **STEP 6** — MM/GBSA with `gmx_MMPBSA` (single run or all pending runs).
5. **RESULTS** — plots from the `.xvg` files (selection and chart options side by side); extra analyses are
   computed on demand. **Generate Final Report** writes `PROJECTS/<project>/RESULTS/<project>_REPORT_<date>.docx`
   (needs `python-docx`, offered by the requirements installer): introduction (drug discovery, CADD, molecular
   dynamics, CODYN), the settings used, the method of each STEP, and the results with plots (equilibration, RMSD,
   RMSF, Rg, SASA, H-bonds, protein–ligand distance, MM/GBSA and per-residue decomposition) plus an automatic
   discussion. Language follows the interface (EN/PT). Missing production analyses are computed with `gmx` and
   cached as `rep_*.xvg` in each run folder.

### Ligand parametrization (inside the interface)

* **CHARMM36 → CGenFF.** CODYN prepares the MOL2 and opens a dialog that guides you through the CGenFF
  server, detects the new `.str` in `~/Downloads` (or lets you import it), checks the penalties and
  converts it. A `.str` placed next to the ligand (`<name>_fix.str` / `<name>.str`) is used without asking.
* **AMBER → GAFF/GAFF2** with AM1-BCC or Gasteiger charges, fully automatic (AmberTools + acpype);
  the net charge comes from the converted ligand and can be overridden in the table.

## Versioning and packaging

`BIN/versao.py` is the single source of the version (`MAJOR.MINOR.PATCH-N`); rules in
[`packaging/VERSIONING.md`](packaging/VERSIONING.md). Build the package with `packaging/deb/build.sh`.

## Corrections made in 2.0.0 (relative to 1.x)

* Force field and water are passed to `pdb2gmx` **by name**; before, the menu index was used and the water
  list was misaligned (e.g. "TIP4P" selected the original TIP3P in CHARMM36).
* `.mdp` files are edited **by key**, not by line number; `dt` follows the integration step (it was fixed at
  2 fs while `nsteps` used the chosen step) and `gen_temp` follows the temperature (was fixed at 300 K).
* AMBER-specific non-bonded settings (`potential-shift`, 1.0 nm, `DispCorr = EnerPres`) are applied; the
  AMBER pipeline never worked before (the ligand files it looked for were never produced).
* Ligand residue name is always `LIG`: long ligand names (e.g. `Gefitinib`) corrupted the fixed-width `.gro`
  columns, the CGenFF converter lower-cases its output names, and `sed 's/LIG1/…/'` missed `UNL1` residues.
* Solvation uses the right box file for TIP4P/TIP5P (`spc216.gro` was always used).
* Runs now live inside projects. On first start, an old `RUNS/` folder is moved to
  `PROJECTS/<date>_RUNS_ANTERIORES/RUNS/` (old `LIGANDS/` and `TARGET/` are copied there, originals kept).
* The original `.pdbqt` protein was **deleted** from `TARGET/` after conversion; now it is left untouched.
* Every command's exit code is checked (the pipeline used to continue after failures); GROMACS' normal
  stderr output is no longer shown as "Erro:".
* Cancel really stops GROMACS (`pkill '^gmx'` never matched the full path `/usr/local/gromacs/bin/gmx`).
* `mdrun` retries with a lighter GPU setup (or CPU) instead of failing; CPU-only machines work.
* Production times such as `0.5 ns` no longer crash (`int()` on a decimal); MMPBSA reads the protein and
  ligand index groups from `index.ndx` instead of assuming group `13`.
* Thermostat groups no longer depend on ion names (`Protein_LIG` / `Water_and_ions`).
* A worker thread no longer creates QWidgets or changes the process working directory.

## License

GPL-3.0-or-later (see `LICENSE.txt`).
