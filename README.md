
#                                            CODYN VERSION 2025.1.1:                                       #

This tool is designed to automate the molecular dynamics method for protein-ligand complexes, allowing sequential simulation of multiple ligands on the same protein/site. It integrates and controls other software and scripts for exclusive use by terminal commands such as GROMACS and gmx_mmpbsa. Its interface allows the adjustment of simulation parameters such as the choice of force field (CHARMM, AMBER, GROMOS, or OPLS), temperature, salinity, ions, solvent model, box type, equilibration time, production time, and integration time. It prepares topologies and generates performance logs and result graphs. CODYN also includes mechanisms for monitoring the production stage and provides time estimates for completion through progress bars. It was developed in the integrated development environment (IDE) Visual Studio Code (1.105.0), in Python language (3.10.12) and using PyQt5 (5.15.11) as a framework to generate the graphical user interface (GUI) elements.


#                                      1. **INSTALLATION INSTRUCTIONS:**                                  #

# **CODYN:**
**1**
Download the zipped file from:
https://github.com/moimaian/CODYN/archive/refs/heads/main.zip

**2**
Extract the file to a working folder, for example, "$HOME/CODYN":
This is possible graphically in a file manager like Nemo
- Create the folder $HOME/CODYN
- Extract the contents of the CODYN-main.zip file to the $HOME/CODYN folder
Or, on Downloads directory, use the command in the terminal:
>$ sudo apt-get install
>$ unzip CODYN-main.zip && mv $HOME/Downloads/CODYN-main $HOME/CODYN

**3**
Still in the terminal, run the CODYN.py file using the command:
>$ chmod +x $HOME/CODYN/CODYN.sh

**4**
In a file manager double-click on the CODYN.sh icon and click on run in the terminal.
Or run in the terminal:
>$ cd $HOME/CODYN && python3 ./CODYN.py

**Notes:**
Use the following command if you do not have python3 on your system:
>$ sudo apt update && sudo apt install python3 -y

A window will then appear describing the requirements that are not installed in the environment so that the user knows what needs to be installed beforehand. This installation can be done through the interface itself, which will open automatically with the install_requirements.py module window.
In this first execution, the virtual Python environment will be created where the program packages that are prerequisites for running CODYN will be installed (see PREREQUISITES).
For installations via the terminal, this environment can be activated with the command:
>$ source $HOME/.venv/CODYN/bin/activate

# **PREREQUISITES:**
On the first startup, either automatically or through the HOME tab in the interface, you can open the prerequisite installation window. In the case of the HOME tab, there is an Install requirements option at the bottom that, when clicked, takes you to this installation window, where the prerequisites for running CODYN and their versions will be listed. This is a list with checkboxes that allow the user to choose which programs they want to install. If this is your first time running the program, check all options. The proposed versions have been tested and are compatible with each other. However, if the user wishes, they can change to more recent versions, but they must ensure that the new version is compatible with the others.


THIS APPLICATION WAS DEVELOPED AND TESTED ON LINUX MINT 21.3 WITH KERNEL 5.15.0 (6.8 too) AND CUDA-TOOLKIT 12.4. 
IT WILL PROBABLY WORK WELL ON UBUNTU LINUX AND ITS FLAVORS!

IF YOUR MACHINE HAS A WINDOWS DUAL BOOT SYSTEM, WITH TPM 2.0, YOU MUST ENTER THE BIOS AND DISABLE THIS
SECURITY BOOT SYSTEM! OTHERWISE THE GROMACS COMAND WILL NOT BE AUTHORIZED TO ACCESS GPU ON CUDA-TOOLKIT/LINUX PLATFORM!


#                                      2. **INSTRUCTIONS FOR USE:**                                  #

During the CODYN startup process, the necessary directories (LIGANDS, TARGET, RUNS, BIN, BASE, ICONS, TEST) are checked. If LIGANDS, TARGET or RUNS directories are missing, they will be created in the folder where the CODYN.py executable is located. If BIN, BASE, ICONS or TEST directories are missing, the user is redirected to this GitHub page to download it again.

After the home tab, the user's first action will be to define the molecular dynamics parameters in the configuration tab. There, the force field (Charmm36_2021, Charmm27, Amber99SB, Gromos96-54a7, OPLS_AA/L), production time (in nanoseconds), equilibration time (in nanoseconds), integration time (in femtoseconds), temperature (in Kelvin), box type (cubic, triclinic, octahedron, and dodecahedron), Positive ion (SOD, POT, CAL, MG...), Negative ion (CLA, CO3, OH...), salinity (in Molar), solvent model (TIP3P, TIP4P, TIP5P, SPC, and SPC/E), number of threads, address of the ligand folder and target folder.
The .pdbqt files of the ligands, coming from molecular docking, should be placed in the ligand folder, and the .pdb or .pdbqt file of the target protein from the same docking process should be placed in the target folder. It is important to note that in this version, the program does not allow the addition of molecules in specific positions, so you must ensure that the coordinates of the files correspond to the desired positions. In principle, as this version is only intended for the molecular dynamics of protein-ligand complexes, it is highly recommended to use files from the molecular docking results. The names of the ligands should consist of 3-letter lowercase acronyms, as these will be incorporated as residues in the simulation, and therefore acronyms representing the amino acids themselves should be avoided.
Clicking the RUN button will generate a hidden .form_data.json file containing the defined parameter information. Workbooks will also be created within the RUNS folder, named with the date and the names of the ligands and protein. Using the test ligands, asc.pdbqt and ast.pdbqt, and the test protein, akt.pdb, we would have, for example, the folders 2025-11-04_16-06_akt_ast and 2025-11-04_16-06_akt_asc. The base .mdp files, the Charmm36 force field folder (if selected), and the scripts cgenff_charmm2gmx_py3_nx2.py and sort_mol2_bonds.pl will be copied into these folders.
An automated sequence of steps is then initiated, which can be monitored through the status windows in each subsequent tab:

Step 1 - Preparation of ligands: In this step, the ligands are converted to .pdb and .mol2 format, and hydrogen atoms and Gasteiger charges are added. The sort_mol2_bonds.pl script is used to correct bonds, thus generating the asc_fix.mol2 file. This file should be used as input in the portal that will automatically open, CGenFF.com, and after conversion, the input file for parameterization to the Charmm36 force field will be obtained, a file named “<bond_name>_fix.str”. Check the parameterization penalties before using it; if they are much above 50, other means of parameterizing the ligand should be considered. The .str files must be kept in the RUN folder, in the example, asc_fix.str and ast_fix.str. For other force fields, such as Amber, Python packages such as ACPYPE can be used. In later versions, these parameterizations will be implemented in other force fields. The cgenff_charmm2gmx_py3_nx2.py script will be run to generate the parameterization (.prm), topology (.itp), and structure (.gro) files from the ligand structure files _fix.mol2 and _fix.str.

Step 2 - Preparation of targets: In this step, the force field and water model are selected, and the protein is converted to .gro format using the gmx pdb2gmx command. This file is merged with the ligand .gro file to form the complex.gro file, and the topol.top file is adjusted.

Step 3 - Preparation of the solvation unit cell: In this step, a box is generated where the protein-ligand complex and water molecules will be added, obtaining the solv.gro file. Next, positive and negative ions will be added to achieve salinity and charge balance. Finally, energy minimization is applied, generating the potential.xvg file, which can be viewed in the RESULTS tab, and the topol.top file is updated.

Step 4 - System equilibration: In this step, short molecular dynamics simulations are applied under variable pressure (NVT) and variable volume (NPT) conditions until the physical equilibrium condition is reached according to the defined temperature, pressure, and molar compressibility. Next, the temperature.xvg, pressure.xvg, and density.xvg files will be generated, which can be viewed in the RESULTS tab.

Step 5 - Molecular Dynamics Production: In this step, at each integration time, all elements of the system will have their coordinates updated with the application of bound and unbound interaction calculations and updating of the system's potential energy. The files md_0_100.xtc (trajectories), .gro (initial coordinates), md_0_100.tpr (topology), among others, are obtained. Finally, the command to compensate for periodic boundary conditions (PBC) is applied so that the complex is centered in the box (file md_0_100_noPBC.xtc).

Step 6 - MMPBSA and MMGBSA calculations: In this step, the trajectories resulting from the dynamics can be used to obtain binding energy values for the receptor, ligand, and complex using the Generalized Born Surface Area (GBSA) and Poisson-Boltzmann Surface Area (PBSA) techniques. There is a form for choosing parameters and a status window. At the end, the gmx_mmpbsa_ana program opens, allowing the visualization of results, including the decomposition of the contributions of each protein residue to the binding energy of the ligand throughout the production.

Results: In this final tab, you can choose from several previous runs to display the results. The user must choose between pre-production graphs (Potential Energy, Temperature, Pressure, and Density) and post-production graphs (RMSD, RMSD dist, RMSF, SASA, HBonds, and Center of Mass). The pre-production graphs will show whether the system has reached the desired equilibrium state around the predefined conditions. The post-production graphs will provide information about the protein-ligand complex throughout production. The main parameters generated are: RMSD, RMSD Dist, RMSF, SAS, HBonds and Center Of Mass.


ATTENTION! For further information on use, please consult the user_manual.pdf provided.

####################################################################################
Ready! Enjoy! I hope it is useful in your work!

