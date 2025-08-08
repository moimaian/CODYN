import os
import re
import numpy as np
import subprocess
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D 

class ViewWorker(QObject):
    log_view_signal = pyqtSignal(str)

    def __init__(self, codyn_dir, run_folder, step, chart, group_index1=None, group_index2=None, use_moving_avg=False, moving_avg_value=20, use_legend=False):
        super().__init__()
        self.codyn_dir = codyn_dir
        self.run_folder = run_folder
        self.step = step
        self.chart = chart
        self.group_index1 = group_index1
        self.group_index2 = group_index2
        self.use_moving_avg = use_moving_avg
        self.moving_avg_value = moving_avg_value
        self.use_legend = use_legend

    def log(self, message: str):
        """Adiciona mensagem no status_prot com timestamp e faz auto-scroll."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view_signal.emit(f"[{ts}] {message}")

    def plot_2D(self, file_name, x_label, y_label, legend_name, title, prot_name, lig_name):
        xvg_path = os.path.join(self.codyn_dir, "RUNS", self.run_folder, f"{file_name}")
        if not os.path.exists(xvg_path):
            self.log(f"File {file_name} not found.")
            return
        x = []
        y = []
        with open(xvg_path, "r") as f:
            for line in f:
                if line.startswith(("#", "@")):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    x.append(float(parts[0]))
                    y.append(float(parts[1]))
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
        
    def plot_3D(self, file_name, title, prot_name, lig_name):
        xvg_path = os.path.join(self.codyn_dir, "RUNS", self.run_folder, file_name)
        if not os.path.exists(xvg_path):
            self.log(f"File {file_name} not found.")
            return
        x, y, z = [], [], []
        with open(xvg_path, "r") as f:
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
        colors = [
            (1, 1 - 0.6*i/(n_points-1), 0.5 - 0.5*i/(n_points-1))
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
        
    def chart_post_production_rmsd(self, run_path, index1, index2, t_ns_md, prot_name, lig_name):
        rmsd_xvg = f"rmsd_{prot_name}_{lig_name}_{index1}_{index2}.xvg"  
        if not os.path.exists(f"{run_path}/{rmsd_xvg}"):     
            cmd = f"gmx rms -s md_0_{t_ns_md}.tpr -f md_0_{t_ns_md}_noPBC.xtc -n index.ndx -o {rmsd_xvg} -tu ns"
            self.log(f"\nCommand: {cmd}\n")
            result=subprocess.run(cmd, shell=True, cwd=run_path, input=f"{index1}\n{index2}\n", text=True, capture_output=True)
            if result.stdout:
                self.log(result.stdout.strip())
            if result.stderr:
                self.log("Erro: " + result.stderr.strip())
            self.plot_2D(f"{rmsd_xvg}", "Time (ns)", "RMSD (nm)", f"RMSD_{index1}_{index2}", "RMSD Analysis", prot_name, lig_name)
        else:
            self.log(f"File {rmsd_xvg} already exists. Skipping RMSD calculation.")
            self.plot_2D(f"{rmsd_xvg}", "Time (ns)", "RMSD (nm)", f"RMSD_{index1}_{index2}", "RMSD Analysis", prot_name, lig_name)            

    def chart_post_production_distrmsd(self, run_path, index1, t_ns_md, prot_name, lig_name):
        distrmsd_xvg = f"distrmsd_{prot_name}_{lig_name}_{index1}.xvg"  
        if not os.path.exists(f"{run_path}/{distrmsd_xvg}"):     
            cmd = f"gmx rmsdist -s md_0_{t_ns_md}.tpr -f md_0_{t_ns_md}_noPBC.xtc -n index.ndx -o {distrmsd_xvg}"
            self.log(f"\nCommand: {cmd}\n")
            result=subprocess.run(cmd, shell=True, cwd=run_path, input=f"{index1}\n", text=True, capture_output=True)
            if result.stdout:
                self.log(result.stdout.strip())
            if result.stderr:
                self.log("Erro: " + result.stderr.strip())                   
            self.plot_2D(f"{distrmsd_xvg}", "Time (ns)", "RMSD (nm)", f"RMSD_{index1}", "RMSD Analysis", prot_name, lig_name)
        else:
            self.log(f"File {distrmsd_xvg} already exists. Skipping RMSDist calculation.")
            self.plot_2D(f"{distrmsd_xvg}", "Time (ns)", "RMSD (nm)", f"RMSD_{index1}", "RMSD Dist. Analysis", prot_name, lig_name)

    def chart_post_production_rmsf(self, run_path, index1, t_ns_md, prot_name, lig_name):
        rmsf_xvg = f"rmsf_{prot_name}_{lig_name}_{index1}.xvg"  
        if not os.path.exists(f"{run_path}/{rmsf_xvg}"):     
            cmd = f"gmx rmsf -s md_0_{t_ns_md}.tpr -f md_0_{t_ns_md}_noPBC.xtc -n index.ndx -o {rmsf_xvg} -res"
            self.log(f"\nCommand: {cmd}\n")
            result=subprocess.run(cmd, shell=True, cwd=run_path, input=f"{index1}\n", text=True, capture_output=True)
            if result.stdout:
                self.log(result.stdout.strip())
            if result.stderr:
                self.log("Erro: " + result.stderr.strip())
            self.plot_2D(f"{rmsf_xvg}", "Residue", "RMSF (nm)", f"RMSF_{index1}", "RMSF Analysis", prot_name, lig_name)
        else:
            self.log(f"File {rmsf_xvg} already exists. Skipping RMSF calculation.")
            self.plot_2D(f"{rmsf_xvg}", "Residue", "RMSF (nm)", f"RMSF_{index1}", "RMSF Analysis", prot_name, lig_name)
            
    def chart_post_production_sasa(self, run_path, index1, t_ns_md, prot_name, lig_name):
        sasa_xvg = f"sasa_{prot_name}_{lig_name}_{index1}.xvg"
        sasa_atom_xvg = f"sasa_atom_{prot_name}_{lig_name}_{index1}.xvg"
        sasa_res_xvg = f"sasa_res_{prot_name}_{lig_name}_{index1}.xvg"
        if not os.path.exists(f"{run_path}/{sasa_xvg}"):     
            cmd = f"gmx sasa -s md_0_{t_ns_md}.tpr -f md_0_{t_ns_md}_noPBC.xtc -n index.ndx -o {sasa_xvg} -oa {sasa_atom_xvg} -or {sasa_res_xvg} -tu ns"
            self.log(f"\nCommand: {cmd}\n")
            result=subprocess.run(cmd, shell=True, cwd=run_path, input=f"{index1}\n", text=True, capture_output=True)                    
            if result.stdout:
                self.log(result.stdout.strip())
            if result.stderr:
                self.log("Erro: " + result.stderr.strip())
            self.plot_2D(f"{sasa_xvg}", "Time (ns)", "Area (nm²)", f"SASA_{index1}", "SASA Analysis", prot_name, lig_name)
            self.plot_2D(f"{sasa_res_xvg}", "Residue", "Area (nm²)", f"SASA_Res_{index1}", "SASA Residue Analysis", prot_name, lig_name)
        else:
            self.log(f"File {sasa_xvg} already exists. Skipping SASA calculation.")
            self.plot_2D(f"{sasa_xvg}", "Time (ns)", "Area (nm²)", f"SASA_{index1}", "SASA Analysis", prot_name, lig_name)
            self.plot_2D(f"{sasa_res_xvg}", "Residue", "Area (nm²)", f"SASA_Res_{index1}", "SASA Residue Analysis", prot_name, lig_name)
            
    def chart_post_production_hbonds(self, run_path, index1, index2, t_ns_md, prot_name, lig_name):
        hbonds_xvg = f"hbonds_{prot_name}_{lig_name}_{index1}_{index2}.xvg"  
        if not os.path.exists(f"{run_path}/{hbonds_xvg}"):     
            cmd = f"gmx hbond -s md_0_{t_ns_md}.tpr -f md_0_{t_ns_md}_noPBC.xtc -n index.ndx -num {hbonds_xvg} -tu ns"
            self.log(f"\nCommand: {cmd}\n")
            result=subprocess.run(cmd, shell=True, cwd=run_path, input=f"{index1}\n{index2}\n", text=True, capture_output=True)
            if result.stdout:
                self.log(result.stdout.strip())
            if result.stderr:
                self.log("Erro: " + result.stderr.strip())
            self.plot_2D(f"{hbonds_xvg}", "Time (ns)", "Nº Hbonds", f"Hbonds_{index1}_{index2}", "Hbonds Analysis", prot_name, lig_name)
        else:
            self.log(f"File {hbonds_xvg} already exists. Skipping Hbonds calculation.")
            self.plot_2D(f"{hbonds_xvg}", "Time (ns)", "Nº Hbonds", f"Hbonds_{index1}_{index2}", "Hbonds Analysis", prot_name, lig_name)
    
    def chart_post_production_com(self, run_path, index1, t_ns_md, prot_name, lig_name):
        com_xvg = f"com_{prot_name}_{lig_name}_{index1}.xvg"  
        if not os.path.exists(f"{run_path}/{com_xvg}"):     
            cmd = f"gmx traj -s md_0_{t_ns_md}.tpr -f md_0_{t_ns_md}_noPBC.xtc -n index.ndx -com yes -ox {com_xvg} -x yes -y yes -z yes -nojump yes -tu ns"
            self.log(f"\nCommand: {cmd}\n")
            result=subprocess.run(cmd, shell=True, cwd=run_path, input=f"{index1}\n", text=True, capture_output=True)
            if result.stdout:
                self.log(result.stdout.strip())
            if result.stderr:
                self.log("Erro: " + result.stderr.strip())
            self.plot_3D(f"{com_xvg}", "Center Of Mass Analysis", prot_name, lig_name)
        else:
            self.log(f"File {com_xvg} already exists. Skipping Center Of Mass calculation.")
            self.plot_3D(f"{com_xvg}", "Center Of Mass Analysis", prot_name, lig_name)

    def run(self):
        parts = self.run_folder.split('_')
        if len(parts) >= 4:
            prot_name = parts[-2]
            lig_name = parts[-1]
        else:
            prot_name = "Unknown"
            lig_name = "Unknown"
            
        # Caminho da pasta
        run_path = os.path.join(self.codyn_dir, "RUNS", self.run_folder)

        # Procura o arquivo .xtc que começa com md_0_ e termina com .xtc
        xtc_file = None
        for fname in os.listdir(run_path):
            match = re.match(r"md_0_(\d+)\.xtc", fname)
            if match:
                t_ns_md = match.group(1)  # Valor do tempo de produção
                xtc_file = fname
                break
        else:
            t_ns_md = "Unknown"        
       
        try:
            self.log(f"Starting analysis for Run Folder: {self.run_folder}")
            # Exemplo de lógica para diferentes opções
            if self.step == "Pre-production":
                if self.chart == "Potential Energy-Minimization":
                    self.log(f"View potential energy minimization for {prot_name} and {lig_name}...")
                    self.plot_2D("potential.xvg", "Time (ps)", "Energy (kJ/mol)", "Potential Energy",
                                              f"Potential Energy Minimization", prot_name, lig_name)
                elif self.chart == "Temperature-NVT":
                    self.log(f"View temperature for {prot_name} and {lig_name} during NVT equilibration...")
                    self.plot_2D("temperature.xvg", "Time (ps)", "Temperature (K)", "Temperature",
                                              f"Temperature NVT", prot_name, lig_name)
                elif self.chart == "Pressure-NPT":
                    self.log(f"View pressure for {prot_name} and {lig_name} during NPT equilibration...")
                    self.plot_2D("pressure.xvg", "Time (ps)", "Pressure (bar)", "Pressure",
                                              f"Pressure NPT", prot_name, lig_name)
                elif self.chart == "Density-NPT":
                    self.log(f"View density for {prot_name} and {lig_name} during NPT equilibration...")
                    self.plot_2D("density.xvg", "Time (ps)", "Density (g/cm³)", "Density",
                                              f"Density NPT", prot_name, lig_name)
                else:
                    self.log(f"Analysis for {self.chart} not implemented.")
            elif self.step == "Post-production":
                if self.chart == "RMSD":
                    self.log(f"Starting RMSD analysis for {prot_name} and {lig_name} in {t_ns_md} ns...")
                    self.chart_post_production_rmsd(run_path, self.group_index1, self.group_index2, t_ns_md, prot_name, lig_name)
                elif self.chart == "RMSD Dist":
                    self.log(f"Starting RMSD Dist analysis for {prot_name} and {lig_name} in {t_ns_md} ns...")
                    self.chart_post_production_distrmsd(run_path, self.group_index1, t_ns_md, prot_name, lig_name)
                elif self.chart == "RMSF":
                    self.log(f"RMSF analysis for {prot_name} and {lig_name} not implemented yet.")
                    self.chart_post_production_rmsf(run_path, self.group_index1, t_ns_md, prot_name, lig_name)
                elif self.chart == "SASA":
                    self.log(f"SASA analysis for {prot_name} and {lig_name} not implemented yet.")
                    self.chart_post_production_sasa(run_path, self.group_index1, t_ns_md, prot_name, lig_name)
                elif self.chart == "HBONDs":
                    self.log(f"HBONDs analysis for {prot_name} and {lig_name} not implemented yet.")
                    self.chart_post_production_hbonds(run_path, self.group_index1, self.group_index2, t_ns_md, prot_name, lig_name)
                elif self.chart == "Center Of Mass":
                    self.log(f"Center of Mass analysis for {prot_name} and {lig_name} not implemented yet.")
                    self.chart_post_production_com(run_path, self.group_index1, t_ns_md, prot_name, lig_name)
                else:
                    self.log(f"Option {self.chart} not yet implemented!")

        except Exception as e:
            self.log(f"Error: {str(e)}")
