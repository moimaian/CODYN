import json
import os
import re
import subprocess
from datetime import datetime

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registra a projeção 3d)

from BIN.tools import find_gmx

class ViewWorker(QObject):
    log_view_signal = pyqtSignal(str)

    def __init__(self, runs_dir, run_folder, step, chart, group_index1=None, group_index2=None, use_moving_avg=False, moving_avg_value=20, use_legend=False):
        super().__init__()
        self.runs_dir = runs_dir
        self.run_folder = run_folder
        self.step = step
        self.chart = chart
        self.group_index1 = group_index1
        self.group_index2 = group_index2
        self.use_moving_avg = use_moving_avg
        self.moving_avg_value = moving_avg_value
        self.use_legend = use_legend
        self.gmx = find_gmx() or "gmx"

    def log(self, message: str):
        """Adiciona mensagem no status_prot com timestamp e faz auto-scroll."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view_signal.emit(f"[{ts}] {message}")

    def plot_2D(self, file_name, x_label, y_label, legend_name, title, prot_name, lig_name):
        xvg_path = os.path.join(self.runs_dir, self.run_folder, f"{file_name}")
        if not os.path.exists(xvg_path):
            self.log(f"File {file_name} not found.")
            return
        x = []
        y = []
        with open(xvg_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith(("#", "@")):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        x.append(float(parts[0]))
                        y.append(float(parts[1]))
                    except ValueError:
                        continue
        if not x or not y:
            self.log(f"File {file_name} does not contain valid data.")
            return
        plt.figure(figsize=(8, 4))
        plt.plot(x, y, label=legend_name)
        # Adiciona média móvel
        if self.use_moving_avg == True:
            window = self.moving_avg_value
            if len(y) >= window:
                y_ma = np.convolve(y, np.ones(window)/window, mode='valid')
                x_ma = x[:len(y_ma)]
                plt.plot(x_ma, y_ma, label=f"Moving Avg (value: {self.moving_avg_value})", color="red", linestyle="--")
        plt.xlabel(x_label)
        plt.ylabel(y_label)
        plt.title(f"{title} - Protein: {prot_name} | Ligand: {lig_name}")
        if self.use_legend == True:
            plt.legend()
        plt.tight_layout()
        plt.show()
        self.log("Chart displayed successfully.")

    def plot_multi_y_vs_x_from_file(self, merge_path, y_labels, title="Merged chart"):
        """
        Lê um arquivo com formato:
            COL0 = X (float)
            COL1..k = Y_i (float)
        e plota múltiplas curvas: Y_i vs X, uma cor por série.
        """
        if not os.path.exists(merge_path):
            self.log(f"Merged file not found: {merge_path}")
            return

        rows = []
        with open(merge_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith(("#", "@")):
                    continue
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        vals = [float(p) for p in parts]
                        rows.append(vals)
                    except:
                        pass
        if not rows:
            self.log("Merged file has no numeric data.")
            return

        import numpy as np
        data = np.array(rows, dtype=float)   # shape: (n, m)
        if data.shape[1] < 2:
            self.log("Merged file must have at least 2 columns: X and one Y.")
            return

        x = data[:, 0]
        plt.figure(figsize=(8, 4))
        m = data.shape[1]

        for i in range(1, m):
            y = data[:, i]
            label = y_labels[i-1] if i-1 < len(y_labels) else f"Y_{i}"
            # Y vs X (X no eixo horizontal)
            plt.plot(x, y, label=label)

        plt.xlabel("X (from first file)")
        plt.ylabel("Y (from selected files)")
        plt.title(title)
        if getattr(self, "use_legend", True):
            plt.legend()
        plt.tight_layout()
        plt.show()
        self.log("Merged multiple Y vs X chart displayed successfully.")

    def plot_3D(self, file_name, title, prot_name, lig_name):
        xvg_path = os.path.join(self.runs_dir, self.run_folder, file_name)
        if not os.path.exists(xvg_path):
            self.log(f"File {file_name} not found.")
            return
        x, y, z = [], [], []
        with open(xvg_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith(("#", "@")):
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    x.append(float(parts[1]))
                    y.append(float(parts[2]))
                    z.append(float(parts[3]))
        if not x or not y or not z:
            self.log(f"File {file_name} does not contain valid 3D data.")
            return

        fig = plt.figure(figsize=(8, 6))
        ax = fig.add_subplot(111, projection='3d')
        ax.plot(x, y, z, label="COM Trajectory", color="blue")

        # Gradiente de cor dos marcadores: do amarelo claro ao laranja escuro
        n_points = len(x)
        # Interpolação entre amarelo claro (rgb: 1,1,0.5) e laranja escuro (rgb: 1,0.4,0)
        denom = max(n_points - 1, 1)
        colors = [
            (1, 1 - 0.6 * i / denom, 0.5 - 0.5 * i / denom)
            for i in range(n_points)
        ]
        ax.scatter(x, y, z, s=50, c=colors, marker="o")

        ax.set_xlabel("X (nm)")
        ax.set_ylabel("Y (nm)")
        ax.set_zlabel("Z (nm)")
        ax.set_title(f"{title} - Protein: {prot_name} | Ligand: {lig_name}")
        if self.use_legend == True:
            ax.legend()
        plt.tight_layout()
        plt.show()
        self.log("3D COM chart displayed successfully.")
        
    # ------------------------------------------------------------------ análises (gmx) ------------------------------------------------------------------
    def _analysis(self, run_path, out_files, args, group_inputs, label):
        """Roda `gmx <args>` (se o .xvg principal ainda não existe) e registra a saída.

        Devolve True se os arquivos estão disponíveis para plotar."""
        main_out = os.path.join(run_path, out_files[0])
        if os.path.exists(main_out):
            self.log(f"File {out_files[0]} already exists. Skipping {label} calculation.")
            return True
        cmd = [self.gmx] + args
        self.log("Command: " + " ".join(cmd))
        try:
            # entrada em bytes: em modo texto o Windows converteria "\n" em "\r\n" (o gmx leria "0\r")
            res = subprocess.run(cmd, cwd=run_path, input="".join(f"{g}\n" for g in group_inputs).encode("utf-8"),
                                 capture_output=True)
            res.stdout = res.stdout.decode("utf-8", "replace")
            res.stderr = res.stderr.decode("utf-8", "replace")
        except OSError as e:
            self.log(f"Error: could not run gmx ({e}).")
            return False
        if res.returncode != 0 or not os.path.exists(main_out):
            msg = (res.stderr or res.stdout or "").strip().splitlines()
            self.log(f"Error: gmx {args[0]} failed (exit code {res.returncode}).\n" + "\n".join(msg[-8:]))
            return False
        return True

    def _traj_args(self, t):
        return ["-s", f"md_0_{t}.tpr", "-f", f"md_0_{t}_noPBC.xtc", "-n", "index.ndx"]

    def chart_post_production_rmsd(self, run_path, index1, index2, t, prot_name, lig_name):
        f = f"rmsd_{prot_name}_{lig_name}_{index1}_{index2}.xvg"
        if self._analysis(run_path, [f], ["rms"] + self._traj_args(t) + ["-o", f, "-tu", "ns"], [index1, index2], "RMSD"):
            self.plot_2D(f, "Time (ns)", "RMSD (nm)", f"RMSD_{index1}_{index2}", "RMSD Analysis", prot_name, lig_name)

    def chart_post_production_distrmsd(self, run_path, index1, t, prot_name, lig_name):
        f = f"distrmsd_{prot_name}_{lig_name}_{index1}.xvg"
        if self._analysis(run_path, [f], ["rmsdist"] + self._traj_args(t) + ["-o", f], [index1], "RMSDist"):
            self.plot_2D(f, "Time (ps)", "RMSD (nm)", f"RMSD_{index1}", "RMSD Dist. Analysis", prot_name, lig_name)

    def chart_post_production_rmsf(self, run_path, index1, t, prot_name, lig_name):
        f = f"rmsf_{prot_name}_{lig_name}_{index1}.xvg"
        if self._analysis(run_path, [f], ["rmsf"] + self._traj_args(t) + ["-o", f, "-res"], [index1], "RMSF"):
            self.plot_2D(f, "Residue", "RMSF (nm)", f"RMSF_{index1}", "RMSF Analysis", prot_name, lig_name)

    def chart_post_production_sasa(self, run_path, index1, t, prot_name, lig_name):
        f = f"sasa_{prot_name}_{lig_name}_{index1}.xvg"
        f_atom = f"sasa_atom_{prot_name}_{lig_name}_{index1}.xvg"
        f_res = f"sasa_res_{prot_name}_{lig_name}_{index1}.xvg"
        if self._analysis(run_path, [f, f_atom, f_res],
                          ["sasa"] + self._traj_args(t) + ["-o", f, "-oa", f_atom, "-or", f_res, "-tu", "ns"], [index1], "SASA"):
            self.plot_2D(f, "Time (ns)", "Area (nm²)", f"SASA_{index1}", "SASA Analysis", prot_name, lig_name)
            self.plot_2D(f_res, "Residue", "Area (nm²)", f"SASA_Res_{index1}", "SASA Residue Analysis", prot_name, lig_name)

    def chart_post_production_hbonds(self, run_path, index1, index2, t, prot_name, lig_name):
        f = f"hbonds_{prot_name}_{lig_name}_{index1}_{index2}.xvg"
        if self._analysis(run_path, [f], ["hbond"] + self._traj_args(t) + ["-num", f, "-tu", "ns"], [index1, index2], "Hbonds"):
            self.plot_2D(f, "Time (ns)", "Nº Hbonds", f"Hbonds_{index1}_{index2}", "Hbonds Analysis", prot_name, lig_name)

    def chart_post_production_com(self, run_path, index1, t, prot_name, lig_name):
        f = f"com_{prot_name}_{lig_name}_{index1}.xvg"
        if self._analysis(run_path, [f], ["traj"] + self._traj_args(t) + ["-com", "yes", "-ox", f, "-x", "yes", "-y", "yes",
                                                                           "-z", "yes", "-nojump", "yes", "-tu", "ns"], [index1], "Center of Mass"):
            self.plot_3D(f, "Center Of Mass Analysis", prot_name, lig_name)

    def chart_post_production_rgyration(self, run_path, index1, t, prot_name, lig_name):
        f = f"rgyration_{prot_name}_{lig_name}_{index1}.xvg"
        if self._analysis(run_path, [f], ["gyrate"] + self._traj_args(t) + ["-o", f], [index1], "Rgyration"):
            self.plot_2D(f, "Time (ps)", "Rg (nm)", f"Rgyration_{index1}", "Rgyration Analysis", prot_name, lig_name)

    # ------------------------------------------------------------------ execução ------------------------------------------------------------------
    @staticmethod
    def names_from_run(run_path, run_folder):
        """(proteína, ligante): de run_config.json; para pastas antigas, do nome da pasta."""
        try:
            with open(os.path.join(run_path, "run_config.json"), "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if cfg.get("protein") and cfg.get("ligand"):
                return cfg["protein"], cfg["ligand"]
        except (OSError, ValueError):
            pass
        parts = run_folder.split("_")
        return (parts[-2], parts[-1]) if len(parts) >= 4 else ("Unknown", "Unknown")

    def run(self):
        run_path = os.path.join(self.runs_dir, self.run_folder)
        if not os.path.isdir(run_path):
            self.log(f"Run folder not found: {run_path}")
            return
        prot_name, lig_name = self.names_from_run(run_path, self.run_folder)

        t_ns_md = "Unknown"
        for fname in sorted(os.listdir(run_path)):
            m = re.fullmatch(r"md_0_([0-9]+(?:\.[0-9]+)?)\.xtc", fname)
            if m:
                t_ns_md = m.group(1)
                break

        try:
            self.log(f"Starting analysis for Run Folder: {self.run_folder}")
            if self.step == "Pre-production":
                table = {
                    "Potential Energy-Minimization": ("potential.xvg", "Time (ps)", "Energy (kJ/mol)", "Potential Energy", "Potential Energy Minimization"),
                    "Temperature-NVT": ("temperature.xvg", "Time (ps)", "Temperature (K)", "Temperature", "Temperature NVT"),
                    "Pressure-NPT": ("pressure.xvg", "Time (ps)", "Pressure (bar)", "Pressure", "Pressure NPT"),
                    "Density-NPT": ("density.xvg", "Time (ps)", "Density (kg/m³)", "Density", "Density NPT"),
                }
                if self.chart in table:
                    f, xl, yl, leg, title = table[self.chart]
                    self.log(f"View {leg.lower()} for {prot_name} and {lig_name}...")
                    self.plot_2D(f, xl, yl, leg, title, prot_name, lig_name)
                else:
                    self.log(f"Analysis for {self.chart} not implemented.")
            elif self.step == "Post-production":
                if t_ns_md == "Unknown":
                    self.log("Production trajectory (md_0_*_noPBC.xtc) not found in this run folder.")
                    return
                g1, g2 = self.group_index1, self.group_index2
                self.log(f"Starting {self.chart} analysis for {prot_name} and {lig_name} ({t_ns_md} ns)...")
                if self.chart == "RMSD":
                    self.chart_post_production_rmsd(run_path, g1, g2, t_ns_md, prot_name, lig_name)
                elif self.chart == "RMSD Dist":
                    self.chart_post_production_distrmsd(run_path, g1, t_ns_md, prot_name, lig_name)
                elif self.chart == "RMSF":
                    self.chart_post_production_rmsf(run_path, g1, t_ns_md, prot_name, lig_name)
                elif self.chart == "SASA":
                    self.chart_post_production_sasa(run_path, g1, t_ns_md, prot_name, lig_name)
                elif self.chart == "HBONDs":
                    self.chart_post_production_hbonds(run_path, g1, g2, t_ns_md, prot_name, lig_name)
                elif self.chart == "Center Of Mass":
                    self.chart_post_production_com(run_path, g1, t_ns_md, prot_name, lig_name)
                elif self.chart == "Rgyration":
                    self.chart_post_production_rgyration(run_path, g1, t_ns_md, prot_name, lig_name)
                else:
                    self.log(f"Option {self.chart} not yet implemented!")
        except Exception as e:
            self.log(f"Error: {type(e).__name__}: {e}")
