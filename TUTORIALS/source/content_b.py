# -*- coding: utf-8 -*-
"""Manual do CODYN — seções 8 a 18 (etapas, resultados, relatório, interpretação, fluxo, problemas, licença)."""


def build_b(m, V):
    # ============================================================== 8. ETAPA 1
    m.h1(("ETAPA 1 — Preparo e parametrização dos ligantes", "STEP 1 — Ligand preparation and parametrization"), new_page=True)
    m.p(("Esta etapa é executada automaticamente após **EXECUTAR**. No topo da aba há a **tabela de execuções** (pasta da execução, ligante e situação: *Aguardando*, *Etapa 1: ligante*, ..., *Concluída*, *Falhou* ou *Cancelada*); "
         "um duplo clique em uma linha abre a pasta da execução. Abaixo fica o console com o registro detalhado, e o botão **CANCELAR** interrompe todos os processos.",
         "This step runs automatically after **RUN**. At the top of the tab is the **runs table** (run folder, ligand and status: *Waiting*, *Step 1: ligand*, ..., *Done*, *Failed* or *Cancelled*); "
         "double-clicking a row opens the run folder. Below it is the console with the detailed log, and the **CANCEL** button stops all processes."))
    m.fig("step1.png", ("ETAPA 1: tabela de execuções e registro da preparação e parametrização dos ligantes.", "STEP 1: runs table and log of the ligand preparation and parametrization."), 15.5)
    m.h2(("Conversão e carga líquida", "Conversion and net charge"))
    m.p(("Cada ligante é convertido pelo Open Babel para PDB, recebe hidrogênios e é gravado como `LIG.mol2` (cargas de Gasteiger), com o resíduo sempre chamado **LIG** — nome curto que cabe nas colunas do formato `.gro` e é o mesmo em todos os arquivos. "
         "A **carga líquida** é determinada pela soma das cargas do MOL2 (valor *auto*) ou pelo valor informado na tabela da aba CONFIG, e o registro mostra qual foi usada. "
         "Ao final, a carga total da topologia gerada é comparada com a esperada e qualquer diferença é sinalizada.",
         "Each ligand is converted by Open Babel to PDB, receives hydrogens and is written as `LIG.mol2` (Gasteiger charges), with the residue always named **LIG** — a short name that fits the `.gro` format columns and is the same in all files. "
         "The **net charge** is determined from the sum of the MOL2 charges (*auto* value) or from the value entered in the CONFIG table, and the log shows which was used. "
         "At the end, the total charge of the generated topology is compared with the expected one and any difference is flagged."))
    m.h2(("CHARMM36 e o servidor CGenFF", "CHARMM36 and the CGenFF server"))
    m.p(("Com o campo CHARMM36, os parâmetros do ligante vêm do **CGenFF**. O CODYN corrige as ligações do MOL2 (`sort_mol2_bonds.pl`) e procura um arquivo de parâmetros `.str` já existente "
         "(`<ligante>_fix.str` ou `<ligante>.str`, na pasta LIGANDS, na pasta `RUNS` do projeto ou na própria execução). Se existir, é usado sem perguntar — útil para repetir uma simulação ou compartilhar parâmetros. "
         "Se não existir, o pipeline pausa e abre a janela **Parâmetros CGenFF**:",
         "With the CHARMM36 field, the ligand parameters come from **CGenFF**. CODYN fixes the MOL2 bonds (`sort_mol2_bonds.pl`) and looks for an existing `.str` parameter file "
         "(`<ligand>_fix.str` or `<ligand>.str`, in the LIGANDS folder, in the project's `RUNS` folder or in the run itself). If one exists, it is used without asking — useful to repeat a simulation or share parameters. "
         "If none exists, the pipeline pauses and opens the **CGenFF parameters** window:"), keep_next=True)
    m.fig("cgenff.png", ("Janela de importação do arquivo .str do CGenFF.", "CGenFF .str import window."), 11.0)
    m.numbered([
        ("Clique em **Abrir servidor CGenFF** e envie o MOL2 indicado na janela (**Abrir pasta do MOL2** e **Copiar caminho do MOL2** ajudam a localizá-lo). **Não** marque a opção *Include parameters that are already in CGenFF*.",
         "Click **Open CGenFF server** and upload the MOL2 shown in the window (**Open MOL2 folder** and **Copy MOL2 path** help locate it). Do **not** tick the *Include parameters that are already in CGenFF* option."),
        ("Baixe o arquivo `.str` gerado. A janela monitora a pasta *Downloads* e oferece **Usar arquivo detectado**; alternativamente, use **Importar .str...** para escolhê-lo manualmente.",
         "Download the generated `.str` file. The window watches the *Downloads* folder and offers **Use detected file**; alternatively, use **Import .str...** to choose it manually."),
        ("O arquivo é validado. Se as **penalidades** forem altas, o CODYN pede confirmação antes de usá-lo; **Pular este ligante** descarta a execução desse ligante e segue com as demais.",
         "The file is validated. If the **penalties** are high, CODYN asks for confirmation before using it; **Skip this ligand** discards that ligand's run and continues with the others."),
    ])
    m.note(("As **penalidades do CGenFF** medem a confiança nos parâmetros e nas cargas atribuídos por analogia: abaixo de 10 são, em geral, aceitáveis; entre 10 e 50 recomenda-se verificar os parâmetros destacados; "
            "acima de 50 os parâmetros precisam de validação ou refinamento antes de uma conclusão confiável. O CODYN registra as penalidades no console e as usa no relatório final.",
            "The **CGenFF penalties** measure the confidence in the parameters and charges assigned by analogy: below 10 they are generally acceptable; between 10 and 50 checking the highlighted parameters is recommended; "
            "above 50 the parameters need validation or refinement before a reliable conclusion. CODYN logs the penalties in the console and uses them in the final report."))
    m.p(("O `.str` é convertido para o GROMACS pelo script `cgenff_charmm2gmx` (incluído em `BASE/`, que depende do NetworkX 2.x), gerando `LIG.itp` e `LIG.prm`.",
         "The `.str` is converted to GROMACS by the `cgenff_charmm2gmx` script (included in `BASE/`, which depends on NetworkX 2.x), producing `LIG.itp` and `LIG.prm`."))
    m.h2(("AMBER, GAFF e GAFF2", "AMBER, GAFF and GAFF2"))
    m.p(("Com os campos AMBER, a parametrização é **totalmente automática**: o `acpype` (com antechamber/sqm do AmberTools) atribui tipos atômicos GAFF ou GAFF2 e cargas AM1-BCC ou Gasteiger, respeitando a carga líquida definida. "
         "O cálculo AM1-BCC pode demorar alguns minutos por ligante.",
         "With the AMBER fields, the parametrization is **fully automatic**: `acpype` (with antechamber/sqm from AmberTools) assigns GAFF or GAFF2 atom types and AM1-BCC or Gasteiger charges, respecting the defined net charge. "
         "The AM1-BCC calculation may take a few minutes per ligand."))
    m.h2(("Restrições de posição do ligante", "Ligand position restraints"))
    m.p(("Em ambos os casos o CODYN cria `posre_lig.itp` com restrições harmônicas (1000 kJ·mol⁻¹·nm⁻²) nos **átomos pesados** do ligante e as inclui em `LIG.itp` dentro de um bloco `#ifdef POSRES`, "
         "de modo que elas só valem durante a equilibração (ETAPA 4) e não na produção.",
         "In both cases CODYN creates `posre_lig.itp` with harmonic restraints (1000 kJ·mol⁻¹·nm⁻²) on the ligand **heavy atoms** and includes them in `LIG.itp` inside a `#ifdef POSRES` block, "
         "so that they apply only during equilibration (STEP 4) and not in production."))

    # ============================================================== 9. ETAPA 2
    m.h1(("ETAPA 2 — Preparo do complexo", "STEP 2 — Complex preparation"))
    m.p(("Prepara a proteína, une o ligante e gera a topologia e os arquivos de parâmetros da execução.",
         "Prepares the protein, merges the ligand and generates the run's topology and parameter files."))
    m.fig("step2.png", ("ETAPA 2: preparo do complexo proteína–ligante.", "STEP 2: preparation of the protein–ligand complex."), 15.0)
    m.numbered([
        ("**Proteína**: o PDB da pasta TARGET é copiado para a execução (um `.pdbqt` é convertido com o Open Babel, preservando o original).",
         "**Protein**: the PDB from the TARGET folder is copied into the run (a `.pdbqt` is converted with Open Babel, preserving the original)."),
        ("**pdb2gmx**: gera `protein.gro`, `topol.top` e `posre.itp` com o campo de força e o modelo de água escolhidos (passados **pelo nome**), com `-ignh` se a opção estiver marcada.",
         "**pdb2gmx**: generates `protein.gro`, `topol.top` and `posre.itp` with the chosen force field and water model (passed **by name**), with `-ignh` if the option is ticked."),
        ("**Complexo**: as coordenadas do ligante (`LIG.gro`) são acrescentadas às da proteína em `complex.gro`, e o ligante é incluído em `topol.top` (parâmetros `LIG.prm`, no caso do CHARMM, e `LIG.itp`, com a linha `LIG 1` em `[ molecules ]`).",
         "**Complex**: the ligand coordinates (`LIG.gro`) are appended to those of the protein in `complex.gro`, and the ligand is included in `topol.top` (`LIG.prm` parameters, in the CHARMM case, and `LIG.itp`, with the `LIG 1` line in `[ molecules ]`)."),
        ("**Arquivos .mdp**: os modelos de `BASE/` (`em`, `ions`, `nvt`, `npt` e `md`) são copiados e ajustados **por chave** (passo `dt`, número de passos, temperatura, grupos de acoplamento). "
         "Nos campos AMBER também são aplicados os parâmetros não ligados apropriados (corte de 1,0 nm, `potential-shift`, `DispCorr = EnerPres`).",
         "**.mdp files**: the templates in `BASE/` (`em`, `ions`, `nvt`, `npt` and `md`) are copied and adjusted **by key** (`dt` step, number of steps, temperature, coupling groups). "
         "For AMBER fields the appropriate non-bonded settings are also applied (1.0 nm cut-off, `potential-shift`, `DispCorr = EnerPres`)."),
    ])
    m.note(("O ligante deve já estar **posicionado no sítio de ligação**, em um referencial compatível com o da proteína (por exemplo, a pose obtida por *docking*). O CODYN não faz docking nem reposiciona o ligante.",
            "The ligand must already be **positioned in the binding site**, in a frame compatible with that of the protein (for example, the pose obtained by *docking*). CODYN does not perform docking or reposition the ligand."))

    # ============================================================== 10. ETAPA 3
    m.h1(("ETAPA 3 — Célula unitária e minimização de energia", "STEP 3 — Unit cell and energy minimization"))
    m.p(("Define a caixa de simulação, preenche-a com solvente, neutraliza o sistema com íons e relaxa a estrutura. A aba mostra uma barra de progresso e o tempo restante estimado.",
         "Defines the simulation box, fills it with solvent, neutralizes the system with ions and relaxes the structure. The tab shows a progress bar and the estimated remaining time."))
    m.fig("step3.png", ("ETAPA 3: caixa, solvatação, íons e minimização de energia.", "STEP 3: box, solvation, ions and energy minimization."), 15.0)
    m.bullets([
        ("`editconf` — cria a caixa do tipo escolhido, centrando o complexo e respeitando a distância soluto-caixa;", "`editconf` — creates the box of the chosen type, centering the complex and respecting the solute-box distance;"),
        ("`solvate` — preenche a caixa com o modelo de água selecionado (usando o arquivo de caixa correto para TIP4P/TIP5P) e atualiza a topologia;", "`solvate` — fills the box with the selected water model (using the correct box file for TIP4P/TIP5P) and updates the topology;"),
        ("`grompp` + `genion` — substitui moléculas de água pelos íons escolhidos, **neutralizando** o sistema e atingindo a concentração salina definida (o registro mostra quantos íons de cada tipo foram adicionados);",
         "`grompp` + `genion` — replaces water molecules with the chosen ions, **neutralizing** the system and reaching the defined salt concentration (the log shows how many ions of each type were added);"),
        ("**Minimização de energia** — método da máxima descida (*steepest descent*), até a força máxima ficar abaixo de 1000 kJ·mol⁻¹·nm⁻¹ ou 100 000 passos, sempre na CPU. "
         "O registro mostra a energia potencial final e a força máxima, e avisa se a minimização não convergiu; a energia é gravada em `potential.xvg`.",
         "**Energy minimization** — steepest descent, until the maximum force falls below 1000 kJ·mol⁻¹·nm⁻¹ or 100,000 steps, always on the CPU. "
         "The log shows the final potential energy and maximum force, and warns if the minimization did not converge; the energy is written to `potential.xvg`."),
    ])

    # ============================================================== 11. ETAPA 4
    m.h1(("ETAPA 4 — Equilibração do sistema", "STEP 4 — System equilibration"))
    m.p(("A equilibração leva o sistema, ainda restringido, à temperatura e à densidade de trabalho, em duas fases de duração igual ao **tempo de equilibração** definido na CONFIG.",
         "Equilibration brings the system, still restrained, to the working temperature and density, in two phases each lasting the **equilibration time** defined in CONFIG."))
    m.fig("step4.png", ("ETAPA 4: equilibração NVT e NPT, com a média das propriedades ao final de cada fase.", "STEP 4: NVT and NPT equilibration, with the average of the properties at the end of each phase."), 15.0)
    m.bullets([
        ("**Grupos de acoplamento** — o `make_ndx` cria os grupos `Protein_LIG` e `Water_and_ions` em `index.ndx`, usados no acoplamento de temperatura (assim o procedimento não depende dos nomes dos íons).",
         "**Coupling groups** — `make_ndx` creates the `Protein_LIG` and `Water_and_ions` groups in `index.ndx`, used in temperature coupling (so the procedure does not depend on the ion names)."),
        ("**NVT** (volume constante) — termostato *V-rescale* (τ = 0,1 ps) na temperatura escolhida, com velocidades iniciais geradas pela distribuição de Maxwell e **restrições de posição** nos átomos pesados da proteína e do ligante. A temperatura é gravada em `temperature.xvg`.",
         "**NVT** (constant volume) — *V-rescale* thermostat (τ = 0.1 ps) at the chosen temperature, with initial velocities generated from the Maxwell distribution and **position restraints** on the heavy atoms of the protein and the ligand. The temperature is written to `temperature.xvg`."),
        ("**NPT** (pressão constante) — continua do NVT, com o barostato *C-rescale* isotrópico (τp = 2 ps, 1 bar, compressibilidade 4,5×10⁻⁵ bar⁻¹), ainda com restrições. Pressão e densidade são gravadas em `pressure.xvg` e `density.xvg`.",
         "**NPT** (constant pressure) — continues from NVT, with the isotropic *C-rescale* barostat (τp = 2 ps, 1 bar, compressibility 4.5×10⁻⁵ bar⁻¹), still restrained. Pressure and density are written to `pressure.xvg` and `density.xvg`."),
    ])
    m.p(("O `mdrun` usa a GPU quando disponível, tentando, em ordem, **GPU completa** (não ligado, ligado, PME e atualização), **GPU só para não ligado e PME** e, por fim, **somente CPU** — um `mdrun` interrompido retoma do ponto de controle. "
         "Confira nos gráficos da aba RESULTADOS se a temperatura estabilizou em torno do valor desejado e se a densidade ficou próxima de 1000 kg/m³ antes de confiar na produção.",
         "`mdrun` uses the GPU when available, trying, in order, **full GPU** (non-bonded, bonded, PME and update), **GPU for non-bonded and PME only** and, finally, **CPU only** — an interrupted `mdrun` resumes from the checkpoint. "
         "Check in the RESULTS tab plots that the temperature settled around the desired value and that the density is close to 1000 kg/m³ before trusting the production."))

    # ============================================================== 12. ETAPA 5
    m.h1(("ETAPA 5 — Produção da dinâmica molecular", "STEP 5 — Molecular dynamics production"))
    m.p(("É a simulação propriamente dita, sem restrições de posição, pelo **tempo de produção** definido. Os tempos de execução crescem rapidamente com o tamanho do sistema e o tempo simulado: "
         "a barra de progresso e o tempo restante, lido do próprio `mdrun`, permitem acompanhar.",
         "This is the simulation proper, without position restraints, for the defined **production time**. Run times grow quickly with system size and simulated time: "
         "the progress bar and the remaining time, read from `mdrun` itself, let you follow it."))
    m.fig("step5.png", ("ETAPA 5: dinâmica de produção e remoção das condições periódicas da trajetória.", "STEP 5: production dynamics and removal of periodic boundaries from the trajectory."), 15.0)
    m.bullets([
        ("O `grompp` continua do estado da NPT (`npt.gro` e `npt.cpt`); o integrador é o *leap-frog* com restrições LINCS nas ligações com hidrogênio, esquema de vizinhos Verlet e PME para as interações eletrostáticas de longo alcance, com termostato *V-rescale* e barostato *C-rescale* (τp = 3,2 ps).",
         "`grompp` continues from the NPT state (`npt.gro` and `npt.cpt`); the integrator is leap-frog with LINCS constraints on bonds to hydrogen, the Verlet neighbor scheme and PME for long-range electrostatics, with a *V-rescale* thermostat and *C-rescale* barostat (τp = 3.2 ps)."),
        ("Coordenadas e energias são gravadas a cada 5000 passos (**10 ps** com passo de 2 fs, isto é, 100 quadros por ns), nos arquivos `md_0_<t>.xtc` e `md_0_<t>.edr`, em que `<t>` é o tempo de produção em ns.",
         "Coordinates and energies are written every 5000 steps (**10 ps** with a 2 fs step, i.e. 100 frames per ns), in the `md_0_<t>.xtc` and `md_0_<t>.edr` files, where `<t>` is the production time in ns."),
        ("Ao final, o `trjconv` remove os artefatos de condição periódica (`-pbc mol -center`, centrando na proteína), gerando `md_0_<t>_noPBC.xtc`, a trajetória usada nas análises e no MM/GBSA.",
         "At the end, `trjconv` removes the periodic-boundary artifacts (`-pbc mol -center`, centering on the protein), producing `md_0_<t>_noPBC.xtc`, the trajectory used in the analyses and in MM/GBSA."),
    ])
    m.note(("Ao terminar a ETAPA 5 o programa exibe *Dinâmica finalizada!* (ou informa quantas execuções falharam). A partir daí as execuções já podem ser analisadas na aba RESULTADOS e submetidas ao MM/PBSA na ETAPA 6.",
            "When STEP 5 ends the program shows *Dynamics finished!* (or reports how many runs failed). From then on the runs can be analyzed in the RESULTS tab and submitted to MM/PBSA in STEP 6."))

    # ============================================================== 13. ETAPA 6
    m.h1(("ETAPA 6 — Energia livre de ligação (MM/PBSA e MM/GBSA)", "STEP 6 — Binding free energy (MM/PBSA and MM/GBSA)"))
    m.p(("A ETAPA 6 usa o **gmx_MMPBSA** para estimar a energia livre de ligação ΔG a partir de quadros da trajetória de produção e decompô-la por resíduo. "
         "Nesta versão o CODYN executa o **MM/GBSA** (solvatação por Born generalizado). Diferentemente das etapas anteriores, ela é acionada pelo usuário e só lista execuções que já possuem trajetória de produção.",
         "STEP 6 uses **gmx_MMPBSA** to estimate the binding free energy ΔG from frames of the production trajectory and to decompose it by residue. "
         "In this version CODYN runs **MM/GBSA** (generalized Born solvation). Unlike the previous steps, it is triggered by the user and lists only runs that already have a production trajectory."))
    m.fig("step6.png", ("ETAPA 6: parâmetros do MM/PBSA em três colunas e console do gmx_MMPBSA.", "STEP 6: MM/PBSA parameters in three columns and gmx_MMPBSA console."), 15.5)
    m.table([("Parâmetro", "Parameter"), ("Descrição", "Description"), ("Padrão", "Default")], [
        [("**Pasta da execução**", "**Run folder**"), ("Execução usada pelo botão EXECUÇÃO ÚNICA (⟳ relê a lista).", "Run used by the SINGLE RUN button (⟳ re-reads the list)."), "—"],
        [("**Processos MPI**", "**MPI processes**"), ("Processos paralelos do `mpirun`. Nunca excedem o número de quadros analisados.", "Parallel `mpirun` processes. They never exceed the number of analyzed frames."), ("metade dos núcleos", "half the cores")],
        [("**Quadro inicial / final**", "**Start / End frame**"), ("Faixa de quadros da trajetória `_noPBC` a analisar. **O quadro final não pode ultrapassar o número de quadros da trajetória** (tempo em ps ÷ 10).",
                                                                  "Range of frames of the `_noPBC` trajectory to analyze. **The end frame cannot exceed the number of frames in the trajectory** (time in ps ÷ 10)."), "1 / 2000"],
        [("**Intervalo**", "**Interval**"), ("Passo entre quadros: 1 usa todos; valores maiores reduzem o custo.", "Step between frames: 1 uses all; larger values reduce the cost."), "1"],
        [("**Verbose**", "**Verbose**"), ("Quantidade de termos de energia impressos na saída final (0–3).", "Number of energy terms printed in the final output (0–3)."), "2"],
        [("**Modelo GB (igb)**", "**GB model (igb)**"), ("Modelo de Born generalizado do Amber (1–8); 5 corresponde ao OBC.", "Amber generalized Born model (1–8); 5 is OBC."), "5"],
        [("**Concentração de sal**", "**Salt concentration**"), ("Força iônica do solvente implícito, em mol/L.", "Ionic strength of the implicit solvent, in mol/L."), ("0,15", "0.15")],
        [("**Decomposição (idecomp)**", "**Decomposition (idecomp)**"), ("Esquema de decomposição por resíduo (0 desliga; 1–4 escolhem como os termos 1-4 são atribuídos).", "Per-residue decomposition scheme (0 turns it off; 1–4 choose how 1-4 terms are assigned)."), "2"],
        [("**Verbose da decomp.**", "**Decomposition verbose**"), ("Nível de detalhe da saída da decomposição (0–3).", "Detail level of the decomposition output (0–3)."), "3"],
    ], widths=[3.6, 9.2, 2.2], caption=("Parâmetros da ETAPA 6.", "STEP 6 parameters."), font=8.5)
    m.p(("O botão **EXECUÇÃO ÚNICA** processa a pasta selecionada; **EXECUTAR TODAS PENDENTES** processa em sequência todas as execuções com trajetória que ainda não têm `FINAL_RESULTS_MMPBSA.dat`; **CANCELAR** interrompe o cálculo. "
         "Para cada execução o CODYN grava `mmpbsa.in`, identifica no `index.ndx` os grupos *Protein* e *LIG* e roda o gmx_MMPBSA, que gera `FINAL_RESULTS_MMPBSA.dat/.csv` e `FINAL_DECOMP_MMPBSA.dat`. "
         "Ao terminar sem erros o programa abre a aba RESULTADOS.",
         "The **SINGLE RUN** button processes the selected folder; **RUN ALL PENDING** processes in sequence all runs with a trajectory that do not yet have `FINAL_RESULTS_MMPBSA.dat`; **CANCEL** stops the calculation. "
         "For each run CODYN writes `mmpbsa.in`, identifies the *Protein* and *LIG* groups in `index.ndx` and runs gmx_MMPBSA, which produces `FINAL_RESULTS_MMPBSA.dat/.csv` and `FINAL_DECOMP_MMPBSA.dat`. "
         "When it finishes without errors the program opens the RESULTS tab."))
    m.note(("O MM/GBSA fornece uma estimativa **relativa** e de **ponto final**: a energia livre é calculada como ΔG = ΔG(gás) + ΔG(solv) (ΔVDWAALS + ΔEEL + ΔEGB + ΔESURF), **sem o termo entrópico**, e tende a superestimar valores absolutos. "
            "Ela é mais indicada para **comparar ligantes** do mesmo alvo do que para prever afinidades absolutas. Use trechos estáveis e longos da trajetória e, se possível, réplicas.",
            "MM/GBSA provides a **relative**, **end-point** estimate: the free energy is computed as ΔG = ΔG(gas) + ΔG(solv) (ΔVDWAALS + ΔEEL + ΔEGB + ΔESURF), **without the entropic term**, and tends to overestimate absolute values. "
            "It is better suited to **comparing ligands** of the same target than to predicting absolute affinities. Use long, stable portions of the trajectory and, if possible, replicas."))

    # ============================================================== 14. RESULTADOS
    m.h1(("Aba RESULTADOS — gráficos e relatório final", "RESULTS tab — plots and final report"))
    m.p(("A aba RESULTADOS reúne a visualização dos gráficos das simulações do projeto aberto e a geração do relatório final. O grupo **Seleção** ocupa a metade esquerda e o grupo **Opções do gráfico** a metade direita; "
         "na última linha fica o botão **Gerar Relatório Final**.",
         "The RESULTS tab brings together the visualization of the plots from the open project's simulations and the generation of the final report. The **Selection** group occupies the left half and the **Chart options** group the right half; "
         "the **Generate Final Report** button is on the last row."))
    m.fig("results.png", ("Aba RESULTADOS: seleção da execução e do gráfico, opções do gráfico e botão do relatório final.", "RESULTS tab: run and plot selection, chart options and final report button."), 15.5)
    m.h2(("Seleção e gráficos disponíveis", "Selection and available plots"))
    m.p(("Escolha a **Pasta da execução** (⟳ atualiza a lista; **Abrir** abre a pasta), a **Fase** e o **Resultado**. Os gráficos são lidos dos arquivos `.xvg` da execução; os de pós-produção são **calculados sob demanda** com o GROMACS e guardados na pasta para reutilização.",
         "Choose the **Run folder** (⟳ refreshes the list; **Open** opens the folder), the **Stage** and the **Result**. The plots are read from the run's `.xvg` files; post-production ones are **computed on demand** with GROMACS and stored in the folder for reuse."), keep_next=True)
    m.table([("Fase", "Stage"), ("Resultado", "Result"), ("O que mostra", "What it shows")], [
        [("Pré-produção", "Pre-production"), "Potential Energy-Minimization", ("Energia potencial durante a minimização.", "Potential energy during minimization.")],
        [("Pré-produção", "Pre-production"), "Temperature-NVT", ("Temperatura ao longo da fase NVT.", "Temperature along the NVT phase.")],
        [("Pré-produção", "Pre-production"), "Pressure-NPT / Density-NPT", ("Pressão e densidade ao longo da fase NPT.", "Pressure and density along the NPT phase.")],
        [("Pós-produção", "Post-production"), "RMSD", ("Desvio quadrático médio de um grupo após ajuste a outro (ex.: esqueleto da proteína, ligante). Usa dois grupos de índice.", "Root-mean-square deviation of a group after fitting to another (e.g. protein backbone, ligand). Uses two index groups.")],
        [("Pós-produção", "Post-production"), "RMSD Dist", ("RMSD baseado em matriz de distâncias, independente de ajuste.", "Distance-matrix-based RMSD, independent of fitting.")],
        [("Pós-produção", "Post-production"), "RMSF", ("Flutuação por resíduo (flexibilidade local).", "Per-residue fluctuation (local flexibility).")],
        [("Pós-produção", "Post-production"), "SASA", ("Área acessível ao solvente, total e por resíduo.", "Solvent-accessible surface area, total and per residue.")],
        [("Pós-produção", "Post-production"), "HBONDs", ("Número de ligações de hidrogênio entre dois grupos (ex.: proteína–ligante). Usa dois grupos.", "Number of hydrogen bonds between two groups (e.g. protein–ligand). Uses two groups.")],
        [("Pós-produção", "Post-production"), "Center Of Mass", ("Distância entre os centros de massa (proteína–ligante) ao longo do tempo.", "Distance between centers of mass (protein–ligand) over time.")],
        [("Pós-produção", "Post-production"), "Rgyration", ("Raio de giro: compactação do grupo ao longo do tempo.", "Radius of gyration: compactness of the group over time.")],
    ], widths=[2.8, 4.6, 7.6], caption=("Gráficos disponíveis na aba RESULTADOS.", "Plots available in the RESULTS tab."), font=8.5)
    m.p(("Os campos **Grupo de índice 1** e **Grupo de índice 2** listam os grupos do `index.ndx` da execução (0 – System, Protein, LIG, Backbone, ...). Resultados que usam um único grupo ignoram o segundo.",
         "The **Index group 1** and **Index group 2** fields list the groups from the run's `index.ndx` (0 – System, Protein, LIG, Backbone, ...). Results that use a single group ignore the second."))
    m.h2(("Opções do gráfico", "Chart options"))
    m.bullets([
        ("**Mostrar legenda** — exibe ou oculta a legenda.", "**Show legend** — shows or hides the legend."),
        ("**Média móvel** — sobrepõe uma curva tracejada vermelha suavizada pela janela indicada (em número de pontos; padrão 20).", "**Moving average** — overlays a dashed red curve smoothed by the indicated window (in number of points; default 20)."),
        ("**Mesclar gráficos** — permite sobrepor vários `.xvg` (de execuções diferentes, por exemplo): marque a opção, use **Adicionar .xvg** para escolher os arquivos (o primeiro define o eixo X) e a lista abaixo mostra o que foi adicionado.",
         "**Merge charts** — lets you overlay several `.xvg` files (from different runs, for example): tick the option, use **Add .xvg** to choose the files (the first defines the X axis) and the list below shows what was added."),
        ("**LIMPAR** esvazia a lista de mesclagem; **VISUALIZAR** abre o gráfico em uma janela do Matplotlib, com ferramentas de zoom, deslocamento e salvamento da imagem.",
         "**CLEAR** empties the merge list; **VIEW** opens the plot in a Matplotlib window, with zoom, pan and image-saving tools."),
    ])
    m.fig("view_rmsd.png", ("Exemplo de gráfico de RMSD aberto por VISUALIZAR, com média móvel.", "Example of an RMSD plot opened by VIEW, with moving average."), 12.5, per_lang=False)
    m.h2(("Relatório final", "Final report"))
    m.p(("O botão **Gerar Relatório Final**, centralizado na última linha, produz um documento Word (`.docx`) do **projeto aberto**, inspirado no relatório do CODRUG. "
         "Ele exige o pacote **python-docx** — se estiver ausente, o CODYN oferece abrir a janela de requisitos. A geração roda em segundo plano (o botão vira **Cancelar relatório**) "
         "e o andamento aparece no console da aba. Ao terminar, o programa pergunta se deseja abrir o arquivo.",
         "The **Generate Final Report** button, centered on the last row, produces a Word document (`.docx`) for the **open project**, inspired by the CODRUG report. "
         "It requires the **python-docx** package — if missing, CODYN offers to open the requirements window. Generation runs in the background (the button turns into **Cancel report**) "
         "and progress appears in the tab's console. When it finishes, the program asks whether to open the file."))
    m.fig("results_report.png", ("Geração do relatório final: etapas de coleta e análise registradas no console.", "Final report generation: collection and analysis steps logged in the console."), 15.0)
    m.p(("O arquivo é salvo em `PROJECTS/<projeto>/RESULTS/<projeto>_REPORT_<data>.docx`, e as figuras em `RESULTS/figures_<data>/<execução>/`. O **idioma do relatório segue o da interface** (português ou inglês). "
         "Análises de produção que ainda não existem (RMSD do esqueleto e do ligante, RMSF, raio de giro, SASA, ligações de hidrogênio e distância proteína–ligante) são calculadas com o `gmx` e guardadas como `rep_*.xvg` em cada execução. O relatório contém:",
         "The file is saved at `PROJECTS/<project>/RESULTS/<project>_REPORT_<date>.docx`, and the figures at `RESULTS/figures_<date>/<run>/`. The **report language follows the interface** (Portuguese or English). "
         "Production analyses that do not yet exist (backbone and ligand RMSD, RMSF, radius of gyration, SASA, hydrogen bonds and protein–ligand distance) are computed with `gmx` and stored as `rep_*.xvg` in each run. The report contains:"), keep_next=True)
    m.bullets([
        ("**Introdução** — descoberta de fármacos, CADD (desenho de fármacos assistido por computador, baseado em estrutura e em ligantes), fundamentos da dinâmica molecular, do MM/PBSA e do próprio CODYN, com um fluxograma do pipeline;",
         "**Introduction** — drug discovery, CADD (computer-aided drug design, structure- and ligand-based), fundamentals of molecular dynamics, MM/PBSA and CODYN itself, with a pipeline flowchart;"),
        ("**Cabeçalho e configurações** — projeto, data, versão do CODYN, e tabela dos parâmetros empregados (campo de força, água, caixa, íons, tempos, temperatura, hardware, parametrização do ligante);",
         "**Header and settings** — project, date, CODYN version, and a table of the parameters used (force field, water, box, ions, times, temperature, hardware, ligand parametrization);"),
        ("**Detalhe de cada etapa (1 a 6)** — o método aplicado e os números reais de cada execução: carga e penalidades do ligante, composição do sistema (átomos, água, íons), minimização, equilibração, desempenho da produção (ns/dia) e MM/GBSA;",
         "**Details of each step (1 to 6)** — the method applied and the actual numbers of each run: ligand charge and penalties, system composition (atoms, water, ions), minimization, equilibration, production performance (ns/day) and MM/GBSA;"),
        ("**Resultados** — para cada ligante, gráficos de equilibração, RMSD, RMSF, raio de giro, SASA, ligações de hidrogênio, distância proteína–ligante, componentes de energia do MM/GBSA e decomposição por resíduo, cada um com **discussão automática** baseada em limiares;",
         "**Results** — for each ligand, plots of equilibration, RMSD, RMSF, radius of gyration, SASA, hydrogen bonds, protein–ligand distance, MM/GBSA energy components and per-residue decomposition, each with an **automatic discussion** based on thresholds;"),
        ("**Comparação entre ligantes** (quando há mais de uma execução com MM/GBSA) — tabela de classificação por ΔG e gráfico comparativo;", "**Comparison among ligands** (when more than one run has MM/GBSA) — ranking table by ΔG and a comparison chart;"),
        ("**Conclusões e limitações** e **Referências**.", "**Conclusions and limitations** and **References**."),
    ])
    m.fig("report_page_a.png", ("Páginas do relatório final: introdução e fluxograma do pipeline.", "Pages of the final report: introduction and pipeline flowchart."), 15.0)
    m.fig("report_page_b.png", ("Páginas do relatório final: resultados de uma execução, com gráficos e discussão.", "Pages of the final report: results of one run, with plots and discussion."), 15.0)
    m.note(("A discussão automática aponta tendências (estabilidade do RMSD, flexibilidade dos resíduos, persistência de ligações de hidrogênio, favorabilidade do ΔG) com base em critérios numéricos simples. "
            "Ela é um ponto de partida: **revise o texto e os gráficos** e considere o tempo simulado — trajetórias curtas não permitem conclusões sobre convergência.",
            "The automatic discussion points out trends (RMSD stability, residue flexibility, persistence of hydrogen bonds, favorability of ΔG) based on simple numerical criteria. "
            "It is a starting point: **review the text and the plots** and consider the simulated time — short trajectories do not allow conclusions about convergence."))

    # ============================================================== 15. Interpretação
    m.h1(("Interpretação dos resultados", "Interpreting the results"))
    m.p(("A tabela resume o que cada gráfico informa e como lê-lo. Os valores indicados são **referências gerais** — dependem da proteína, do ligante e do tempo simulado — e não substituem a análise crítica do pesquisador.",
         "The table summarizes what each plot tells and how to read it. The values given are **general references** — they depend on the protein, the ligand and the simulated time — and do not replace the researcher's critical analysis."), keep_next=True)
    m.table([("Gráfico", "Plot"), ("O que verificar", "What to check")], [
        [("Energia potencial (minimização)", "Potential energy (minimization)"), ("Deve diminuir e estabilizar em valor negativo e alto em módulo; força máxima abaixo de 1000 kJ·mol⁻¹·nm⁻¹. Falta de convergência sugere choques estéricos ou topologia incorreta.",
                                                                                 "It should decrease and settle at a large negative value; maximum force below 1000 kJ·mol⁻¹·nm⁻¹. Lack of convergence suggests steric clashes or an incorrect topology.")],
        [("Temperatura (NVT)", "Temperature (NVT)"), ("Oscila poucos kelvin em torno do valor de referência (por exemplo, 310 K).", "Oscillates a few kelvin around the reference value (e.g. 310 K).")],
        [("Pressão e densidade (NPT)", "Pressure and density (NPT)"), ("A pressão flutua muito (centenas de bar); importa a média próxima de 1 bar. A densidade deve estabilizar perto de 1000 kg/m³ (sistemas solvatados costumam ficar em torno de 1000–1030).",
                                                                       "Pressure fluctuates strongly (hundreds of bar); what matters is the average close to 1 bar. Density should settle near 1000 kg/m³ (solvated systems are around 1000–1030).")],
        [("RMSD da proteína", "Protein RMSD"), ("Uma curva que atinge um **platô** indica equilíbrio estrutural. Aumentos contínuos sugerem desdobramento ou simulação ainda não equilibrada; platôs de poucos décimos de nm são comuns para proteínas globulares.",
                                                  "A curve that reaches a **plateau** indicates structural equilibrium. Continuous increases suggest unfolding or a still-unequilibrated simulation; plateaus of a few tenths of a nm are common for globular proteins.")],
        [("RMSD do ligante", "Ligand RMSD"), ("Valores baixos e estáveis indicam que o ligante mantém a pose; saltos indicam troca de pose ou saída do sítio. Verifique junto com a distância entre centros de massa.",
                                                "Low, stable values indicate that the ligand keeps its pose; jumps indicate a pose change or exit from the site. Check together with the center-of-mass distance.")],
        [("RMSF", "RMSF"), ("Picos em alças e extremidades são esperados; resíduos do sítio de ligação com baixa flutuação sugerem interação estável com o ligante.", "Peaks in loops and termini are expected; binding-site residues with low fluctuation suggest a stable interaction with the ligand.")],
        [("Raio de giro e SASA", "Radius of gyration and SASA"), ("Valores estáveis indicam que a proteína não se expandiu nem colapsou; variações do SASA do ligante informam seu grau de exposição ao solvente.", "Stable values indicate that the protein neither expanded nor collapsed; variations in the ligand SASA tell its degree of solvent exposure.")],
        [("Ligações de hidrogênio", "Hydrogen bonds"), ("Número médio e persistência ao longo do tempo: ligações presentes na maior parte dos quadros indicam contatos importantes.", "Average number and persistence over time: bonds present in most frames indicate important contacts.")],
        [("Distância proteína–ligante", "Protein–ligand distance"), ("Deve permanecer aproximadamente constante; aumento contínuo indica dissociação.", "Should remain roughly constant; a continuous increase indicates dissociation.")],
        [("MM/GBSA (ΔG)", "MM/GBSA (ΔG)"), ("Quanto **mais negativo**, mais favorável. Compare ligantes pelo valor e pelo desvio-padrão/erro-padrão; diferenças menores que a incerteza não são conclusivas. Os componentes (ΔVDWAALS, ΔEEL, ΔEGB, ΔESURF) mostram a origem da afinidade.",
                                              "The **more negative**, the more favorable. Compare ligands by value and by standard deviation/error; differences smaller than the uncertainty are not conclusive. The components (ΔVDWAALS, ΔEEL, ΔEGB, ΔESURF) show the origin of the affinity.")],
        [("Decomposição por resíduo", "Per-residue decomposition"), ("Resíduos com contribuições mais negativas são os principais contatos do ligante — candidatos a mutagênese ou a otimização química.", "Residues with the most negative contributions are the ligand's main contacts — candidates for mutagenesis or chemical optimization.")],
    ], widths=[3.6, 11.4], caption=("Guia de leitura dos gráficos.", "Guide to reading the plots."), font=8.5)

    # ============================================================== 16. Fluxo recomendado
    m.h1(("Fluxo recomendado e boas práticas", "Recommended workflow and best practices"))
    m.numbered([
        ("**Instale os requisitos** (seção 3) e confira na aba INÍCIO que GROMACS, AmberTools (se usar AMBER ou MM/GBSA), gmx_MMPBSA e python-docx aparecem instalados.",
         "**Install the requirements** (section 3) and check in the HOME tab that GROMACS, AmberTools (if using AMBER or MM/GBSA), gmx_MMPBSA and python-docx appear as installed."),
        ("**Crie um projeto** na aba CONFIG e copie a proteína e os ligantes para as pastas TARGET e LIGANDS do projeto.", "**Create a project** in the CONFIG tab and copy the protein and the ligands into the project's TARGET and LIGANDS folders."),
        ("**Faça um teste curto** (por exemplo, 0,1 a 1 ns de produção e 0,01 a 0,1 ns de equilibração) para validar os arquivos e a parametrização antes do cálculo longo; a pasta de execução do teste pode ser apagada depois.",
         "**Run a short test** (e.g. 0.1 to 1 ns of production and 0.01 to 0.1 ns of equilibration) to validate the files and the parametrization before the long calculation; the test run folder can be deleted afterwards."),
        ("**Ajuste o tempo e rode** a simulação definitiva. Acompanhe o log de cada etapa e o Monitor CPU/GPU.", "**Set the time and run** the final simulation. Follow each step's log and the CPU/GPU Monitor."),
        ("**Verifique a equilibração** nos gráficos pré-produção e o RMSD/distância na pós-produção antes de calcular energias.", "**Check the equilibration** in the pre-production plots and the RMSD/distance in post-production before computing energies."),
        ("**Calcule o MM/GBSA** (ETAPA 6) em um trecho estável da trajetória, com o quadro final dentro do número de quadros disponível.", "**Compute MM/GBSA** (STEP 6) on a stable portion of the trajectory, with the end frame within the number of available frames."),
        ("**Gere o relatório final** e revise-o. Faça cópia de segurança da pasta do projeto, que contém tudo o que é necessário para reproduzir e auditar o estudo.", "**Generate the final report** and review it. Back up the project folder, which contains everything needed to reproduce and audit the study."),
    ])
    m.bullets([
        ("**Preparo da proteína**: remova moléculas indesejadas, trate resíduos ausentes e defina estados de protonação adequados antes de usar o PDB. A opção *Ignorar H do PDB* reconstrói os hidrogênios, mas descarta protonações definidas.",
         "**Protein preparation**: remove unwanted molecules, handle missing residues and set appropriate protonation states before using the PDB. The *Ignore PDB hydrogens* option rebuilds the hydrogens but discards defined protonations."),
        ("**Ligantes**: use poses de docking de boa qualidade e confirme a carga líquida (estado de ionização no pH de interesse). Verifique as penalidades do CGenFF.",
         "**Ligands**: use good-quality docking poses and confirm the net charge (ionization state at the pH of interest). Check the CGenFF penalties."),
        ("**Amostragem**: para conclusões sobre estabilidade e afinidade, use tempos de produção de dezenas a centenas de ns e, se possível, réplicas independentes. Trajetórias de 1 ns servem apenas para testar o fluxo.",
         "**Sampling**: for conclusions about stability and affinity, use production times of tens to hundreds of ns and, if possible, independent replicas. 1 ns trajectories only serve to test the workflow."),
        ("**Hardware**: com GPU NVIDIA e GROMACS compilado com CUDA, a produção é muito mais rápida; mantenha a opção *Usar a GPU* marcada e o número de threads de CPU compatível com a máquina.",
         "**Hardware**: with an NVIDIA GPU and GROMACS built with CUDA, production is much faster; keep the *Use the GPU* option ticked and the CPU thread count compatible with the machine."),
    ])

    # ============================================================== 17. Problemas
    m.h1(("Solução de problemas", "Troubleshooting"))
    m.p(("Em caso de erro, comece pelo console da etapa e pelo log da sessão (**Ajuda > Terminal**); os arquivos `*.log` da própria pasta da execução (`em.log`, `nvt.log`, `md_0_<t>.log`, `gmx_MMPBSA.log`) trazem detalhes do GROMACS e do gmx_MMPBSA.",
         "In case of error, start with the step's console and the session log (**Help > Terminal**); the `*.log` files in the run folder itself (`em.log`, `nvt.log`, `md_0_<t>.log`, `gmx_MMPBSA.log`) give details from GROMACS and gmx_MMPBSA."), keep_next=True)
    m.table([("Sintoma", "Symptom"), ("Causa provável e ação", "Probable cause and action")], [
        [("O botão EXECUTAR está desabilitado", "The RUN button is disabled"), ("Nenhum projeto aberto. Crie ou carregue um projeto no grupo *Projetos* da aba CONFIG.", "No project open. Create or load a project in the *Projects* group of the CONFIG tab.")],
        [("*GROMACS ('gmx') not found*", "*GROMACS ('gmx') not found*"), ("O GROMACS não está instalado ou não está no caminho. Instale-o pela janela de requisitos (compilação) ou instale um pacote do sistema.", "GROMACS is not installed or not in the path. Install it from the requirements window (build) or install a system package.")],
        [("*CGenFF .str was not provided; ligand skipped*", "*CGenFF .str was not provided; ligand skipped*"), ("A janela do CGenFF foi fechada ou o ligante foi pulado. Execute novamente e importe o `.str`, ou coloque `<ligante>_fix.str` na pasta LIGANDS.", "The CGenFF window was closed or the ligand skipped. Run again and import the `.str`, or place `<ligand>_fix.str` in the LIGANDS folder.")],
        [("*cgenff_charmm2gmx failed* / *No module named networkx*", "*cgenff_charmm2gmx failed* / *No module named networkx*"), ("O conversor usa a API do NetworkX 2.x. Instale o NetworkX recomendado pela janela de requisitos, no ambiente `~/.venv/CODYN`.", "The converter uses the NetworkX 2.x API. Install the recommended NetworkX from the requirements window, in the `~/.venv/CODYN` environment.")],
        [("Penalidades CGenFF altas", "High CGenFF penalties"), ("Os parâmetros do ligante têm baixa confiança. Refine-os (por exemplo, com ferramentas de otimização de parâmetros) ou interprete os resultados com cautela.", "The ligand parameters have low confidence. Refine them (e.g. with parameter-optimization tools) or interpret the results with caution.")],
        [("`pdb2gmx` falha por nomes de átomos ou resíduos", "`pdb2gmx` fails because of atom or residue names"), ("Marque *Ignorar H do PDB* e verifique átomos ausentes e resíduos não padrão no PDB.", "Tick *Ignore PDB hydrogens* and check for missing atoms and non-standard residues in the PDB.")],
        [("Minimização não convergiu", "Minimization did not converge"), ("Há choques estéricos ou erro de topologia. Revise a pose do ligante, a proteína e a carga líquida.", "There are steric clashes or a topology error. Review the ligand pose, the protein and the net charge.")],
        [("Erro de GPU no `mdrun`", "GPU error in `mdrun`"), ("O CODYN tenta automaticamente uma configuração mais leve e, por fim, a CPU. Se persistir, desmarque *Usar a GPU* e verifique o driver/CUDA.", "CODYN automatically tries a lighter setup and finally the CPU. If it persists, untick *Use the GPU* and check the driver/CUDA.")],
        [("O gmx_MMPBSA falha logo no início", "gmx_MMPBSA fails right at the start"), ("Verifique se o **quadro final** não excede os quadros da trajetória (tempo em ps ÷ 10), se `md_0_<t>_noPBC.xtc` e `index.ndx` existem e se o AmberTools está instalado.", "Check that the **end frame** does not exceed the trajectory frames (time in ps ÷ 10), that `md_0_<t>_noPBC.xtc` and `index.ndx` exist and that AmberTools is installed.")],
        [("Windows: *AMBER/GAFF* ou ETAPA 6 indisponível", "Windows: *AMBER/GAFF* or STEP 6 unavailable"), ("O AmberTools não existe para Windows. Use CHARMM36 com ligantes CGenFF; o MM/GBSA (gmx_MMPBSA) só roda no Linux.", "AmberTools has no Windows build. Use CHARMM36 with CGenFF ligands; MM/GBSA (gmx_MMPBSA) runs on Linux only.")],
        [("Windows: o GROMACS não aparece como instalado", "Windows: GROMACS does not appear as installed"), ("Não há binário oficial: instale-o pela janela de requisitos (compilação, demorada) ou aponte a variável de ambiente `CODYN_GMX` para um `gmx.exe` existente. Confira o log em **Ajuda > Terminal**.", "There is no official binary: install it from the requirements window (build, slow) or point the `CODYN_GMX` environment variable to an existing `gmx.exe`. Check the log in **Help > Terminal**.")],
        [("Windows: erro de DLL ao abrir o Qt/PyQt5", "Windows: DLL error when opening Qt/PyQt5"), ("Falta o runtime do Visual C++. Instale-o (`winget install --id Microsoft.VCRedist.2015+.x64 -e`) e abra o CODYN de novo pelo `CODYN_Windows.bat`.", "The Visual C++ runtime is missing. Install it (`winget install --id Microsoft.VCRedist.2015+.x64 -e`) and open CODYN again with `CODYN_Windows.bat`.")],
        [("Windows: caminho ou nome de arquivo longo demais", "Windows: path or file name too long"), ("O Windows limita o caminho completo a 260 caracteres. Use nomes curtos de projeto e de ligante e uma pasta de instalação próxima da raiz (por exemplo, `C:\\CODYN`).", "Windows limits the full path to 260 characters. Use short project and ligand names and an installation folder close to the root (for example `C:\\CODYN`).")],
        [("O relatório pede o python-docx", "The report asks for python-docx"), ("Instale o *python-docx* pela janela de requisitos (**Ajuda > Instalar requisitos**).", "Install *python-docx* from the requirements window (**Help > Install requirements**).")],
        [("*A run is already in progress*", "*A run is already in progress*"), ("Só uma execução do pipeline roda por vez. Aguarde o término ou cancele.", "Only one pipeline run goes at a time. Wait for it to finish or cancel.")],
    ], widths=[5.0, 10.0], caption=("Problemas comuns e soluções.", "Common problems and solutions."), font=8.5)

    # ============================================================== 18. Licença
    m.h1(("Licença, repositório e citação", "License, repository and citation"))
    m.p(("O CODYN é software livre, distribuído sob a **GNU General Public License, versão 3 ou posterior** (GPL-3.0-or-later); o texto completo está em `LICENSE.txt`. "
         "O código-fonte, a documentação e o acompanhamento de problemas estão em https://github.com/moimaian/CODYN. "
         "Contato: moimaian@gmail.com.",
         "CODYN is free software, distributed under the **GNU General Public License, version 3 or later** (GPL-3.0-or-later); the full text is in `LICENSE.txt`. "
         "The source code, documentation and issue tracking are at https://github.com/moimaian/CODYN. "
         "Contact: moimaian@gmail.com."))
    m.p(("Desenvolvido por Ahmad Kassein El Zein, Bernardo Mussa, Gustavo Henrique Scheiffer, Moisés Maia Neto, Roberto Pontarolo e Raul Edison Luna Lazo — Universidade Federal do Paraná (UFPR), Brasil — © 2025–2026 CEB/UFPR.",
         "Developed by Ahmad Kassein El Zein, Bernardo Mussa, Gustavo Henrique Scheiffer, Moisés Maia Neto, Roberto Pontarolo and Raul Edison Luna Lazo — Federal University of Paraná (UFPR), Brazil — © 2025–2026 CEB/UFPR."))
    m.h2(("Como citar", "How to cite"))
    m.p(("Ao publicar resultados obtidos com o CODYN, cite o programa e as ferramentas em que ele se apoia:",
         "When publishing results obtained with CODYN, cite the program and the tools it relies on:"), keep_next=True)
    m.bullets([
        (f"CEB/UFPR. **CODYN — Computational Platform for Molecular Dynamics**, versão {V}. Universidade Federal do Paraná, 2026. https://github.com/moimaian/CODYN",
         f"CEB/UFPR. **CODYN — Computational Platform for Molecular Dynamics**, version {V}. Federal University of Paraná, 2026. https://github.com/moimaian/CODYN"),
        ("Abraham, M. J. et al. GROMACS: High performance molecular simulations through multi-level parallelism from laptops to supercomputers. SoftwareX 1–2, 19–25 (2015).", "Abraham, M. J. et al. GROMACS: High performance molecular simulations through multi-level parallelism from laptops to supercomputers. SoftwareX 1–2, 19–25 (2015)."),
        ("Huang, J. et al. CHARMM36m: an improved force field for folded and intrinsically disordered proteins. Nat. Methods 14, 71–73 (2017).", "Huang, J. et al. CHARMM36m: an improved force field for folded and intrinsically disordered proteins. Nat. Methods 14, 71–73 (2017)."),
        ("Vanommeslaeghe, K. et al. CHARMM general force field: a force field for drug-like molecules compatible with the CHARMM all-atom additive biological force fields. J. Comput. Chem. 31, 671–690 (2010).", "Vanommeslaeghe, K. et al. CHARMM general force field: a force field for drug-like molecules compatible with the CHARMM all-atom additive biological force fields. J. Comput. Chem. 31, 671–690 (2010)."),
        ("Wang, J. et al. Development and testing of a general amber force field. J. Comput. Chem. 25, 1157–1174 (2004).", "Wang, J. et al. Development and testing of a general amber force field. J. Comput. Chem. 25, 1157–1174 (2004)."),
        ("Sousa da Silva, A. W. & Vranken, W. F. ACPYPE — AnteChamber PYthon Parser interfacE. BMC Res. Notes 5, 367 (2012).", "Sousa da Silva, A. W. & Vranken, W. F. ACPYPE — AnteChamber PYthon Parser interfacE. BMC Res. Notes 5, 367 (2012)."),
        ("Valdés-Tresanco, M. S. et al. gmx_MMPBSA: a new tool to perform end-state free energy calculations with GROMACS. J. Chem. Theory Comput. 17, 6281–6291 (2021).", "Valdés-Tresanco, M. S. et al. gmx_MMPBSA: a new tool to perform end-state free energy calculations with GROMACS. J. Chem. Theory Comput. 17, 6281–6291 (2021)."),
        ("O'Boyle, N. M. et al. Open Babel: an open chemical toolbox. J. Cheminform. 3, 33 (2011).", "O'Boyle, N. M. et al. Open Babel: an open chemical toolbox. J. Cheminform. 3, 33 (2011)."),
    ])
