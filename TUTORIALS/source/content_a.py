# -*- coding: utf-8 -*-
"""Manual do CODYN — seções 1 a 7 (descrição, instalação, organização, uso geral, HOME, CONFIG)."""


def build_a(m, V):
    # ============================================================== 1. Descrição
    m.h1(("Descrição", "Description"))
    m.p(("O CODYN é uma ferramenta gráfica de código aberto que automatiza simulações de **dinâmica molecular (DM) de sistemas proteína–ligante** "
         "com o GROMACS. A partir de uma proteína (arquivo PDB) e de um ou vários ligantes (PDBQT, PDB, MOL2 ou SDF), o programa executa todo o fluxo: "
         "conversão e parametrização dos ligantes (CGenFF/CHARMM36 ou GAFF/GAFF2/AMBER), montagem do complexo, definição da caixa, solvatação e "
         "adição de íons, minimização de energia, equilibração NVT e NPT, dinâmica de produção, cálculo da energia livre de ligação por MM/GBSA "
         "(gmx_MMPBSA), análise da trajetória e geração de um relatório final em Word.",
         "CODYN is an open-source graphical tool that automates **molecular dynamics (MD) simulations of protein–ligand systems** with GROMACS. "
         "Starting from a protein (PDB file) and one or several ligands (PDBQT, PDB, MOL2 or SDF), the program runs the whole workflow: "
         "ligand conversion and parametrization (CGenFF/CHARMM36 or GAFF/GAFF2/AMBER), complex assembly, box definition, solvation and ion "
         "addition, energy minimization, NVT and NPT equilibration, production dynamics, binding free-energy calculation by MM/GBSA "
         "(gmx_MMPBSA), trajectory analysis and generation of a final Word report."))
    m.p(("A interface conduz o usuário por um processo longo e propenso a erros — dezenas de comandos do GROMACS, arquivos de topologia, parâmetros "
         "`.mdp` e conversões entre formatos — reduzindo a necessidade de conhecimento em linha de comando. Cada ligante gera uma **execução independente**: "
         "se uma falhar, as demais continuam. Tudo o que foi simulado fica registrado em `run_config.json`, de modo que os resultados são reprodutíveis.",
         "The interface guides the user through a long and error-prone process — dozens of GROMACS commands, topology files, `.mdp` parameters and "
         "format conversions — reducing the need for command-line knowledge. Each ligand produces an **independent run**: if one fails, the others "
         "continue. Everything that was simulated is recorded in `run_config.json`, so the results are reproducible."))
    m.fig("workflow.png", ("Visão geral do fluxo do CODYN, da configuração ao relatório final.", "Overview of the CODYN workflow, from configuration to the final report."), 15.0)
    m.p(("O programa é escrito em Python 3 com PyQt5 e usa, entre outras ferramentas, GROMACS 2024.5, Open Babel, AmberTools (antechamber, sqm, tleap), "
         "acpype, gmx_MMPBSA, NumPy, pandas, Matplotlib, SciPy, psutil, NetworkX e python-docx. A interface está disponível em **português e inglês**. "
         f"Este manual descreve a versão {V}. O programa é distribuído sob a licença GPL-3.0-or-later.",
         "The program is written in Python 3 with PyQt5 and uses, among other tools, GROMACS 2024.5, Open Babel, AmberTools (antechamber, sqm, tleap), "
         "acpype, gmx_MMPBSA, NumPy, pandas, Matplotlib, SciPy, psutil, NetworkX and python-docx. The interface is available in **English and Portuguese**. "
         f"This manual describes version {V}. The program is distributed under the GPL-3.0-or-later license."))

    # ============================================================== 2. Instalação
    m.h1(("Instalação", "Installation"))
    m.h2(("Instalação pelo pacote .deb (recomendada)", "Installation from the .deb package (recommended)"))
    m.p(("Em distribuições baseadas em Debian/Ubuntu/Mint, instale o pacote com:",
         "On Debian/Ubuntu/Mint based distributions, install the package with:"), keep_next=True)
    m.code(f"sudo apt install ./codyn_{V}_all.deb")
    m.p(("A instalação cria:", "The installation creates:"), keep_next=True)
    m.bullets([("`/opt/codyn` — código da aplicação, gerenciado pelo dpkg;", "`/opt/codyn` — application code, managed by dpkg;"),
               ("`/usr/bin/codyn` — lançador em linha de comando;", "`/usr/bin/codyn` — command-line launcher;"),
               ("`/usr/share/applications/codyn.desktop` — entrada no menu de aplicativos.", "`/usr/share/applications/codyn.desktop` — entry in the applications menu.")])
    m.p(("No primeiro acionamento pelo menu, o lançador sincroniza `/opt/codyn` com `$HOME/CODYN` — sem tocar nas pastas `PROJECTS`, `LIGANDS`, `TARGET` e `DADOS` "
         "— e executa o programa a partir dessa cópia. Assim, atualizações do pacote nunca apagam os projetos do usuário. "
         "O pacote não instala o GROMACS, o CUDA nem o gmx_MMPBSA: eles são instalados sob demanda pela janela de requisitos (seção 3).",
         "The first time it is started from the menu, the launcher synchronizes `/opt/codyn` with `$HOME/CODYN` — without touching the `PROJECTS`, `LIGANDS`, "
         "`TARGET` and `DADOS` folders — and runs the program from that copy. Package updates therefore never delete the user's projects. "
         "The package does not install GROMACS, CUDA or gmx_MMPBSA: they are installed on demand from the requirements window (section 3)."))
    m.h2(("Instalação a partir do código-fonte", "Installation from source code"))
    m.p(("Clone o repositório na pasta pessoal e execute o programa:", "Clone the repository into your home folder and run the program:"), keep_next=True)
    m.code("git clone https://github.com/moimaian/CODYN ~/CODYN\npython3 ~/CODYN/CODYN.py")
    m.p(("Se o Python 3 (versão 3.10 ou superior), o módulo `venv` ou o `pip` não estiverem presentes:",
         "If Python 3 (version 3.10 or later), the `venv` module or `pip` are missing:"), keep_next=True)
    m.code("sudo apt update\nsudo apt install python3 python3-venv python3-pip -y")
    m.h2(("Primeira execução e ambiente virtual", "First run and virtual environment"))
    m.p(("Na primeira execução o CODYN cria automaticamente um ambiente virtual Python em `$HOME/.venv/CODYN`, instala o PyQt5 (o suficiente para a "
         "interface abrir) e reinicia a si mesmo dentro desse ambiente. Esse passo precisa de um terminal — o lançador do menu abre um automaticamente (no Windows, use o `CODYN_Windows.bat`, descrito abaixo). "
         "Todo o restante é instalado pela janela **Instalar requisitos**. Para instalar pacotes manualmente, ative o ambiente com:",
         "On the first run CODYN automatically creates a Python virtual environment at `$HOME/.venv/CODYN`, installs PyQt5 (just enough for the interface to open) "
         "and restarts itself inside that environment. This step needs a terminal — the menu launcher opens one automatically (on Windows, use `CODYN_Windows.bat`, described below). "
         "Everything else is installed from the **Install requirements** window. To install packages manually, activate the environment with:"), keep_next=True)
    m.code("source $HOME/.venv/CODYN/bin/activate")

    m.h2(("Instalação no Windows 10/11", "Installation on Windows 10/11"))
    m.p(("No Windows o CODYN roda a partir do código-fonte, em um ambiente Python **3.10.11**. Baixe o repositório como arquivo zip, extraia-o em qualquer pasta "
         "(por exemplo, `C:\\Users\\<usuário>\\CODYN`) e dê um **duplo clique em CODYN_Windows.bat** — não é preciso abrir o PowerShell nem digitar comandos. "
         "Se o Windows exibir \"O Windows protegeu o computador\", clique em *Mais informações* > *Executar assim mesmo*.",
         "On Windows CODYN runs from the source code, in a Python **3.10.11** environment. Download the repository as a zip file, extract it to any folder "
         "(for example `C:\\Users\\<user>\\CODYN`) and **double-click CODYN_Windows.bat** — there is no need to open PowerShell or type commands. "
         "If Windows shows \"Windows protected your PC\", click *More info* > *Run anyway*."), keep_next=True)
    m.p(("O script, **somente na primeira execução**:", "The script, **on the first run only**:"), keep_next=True)
    m.numbered([
        ("procura o Python 3.10 ou superior; se não encontrar, baixa o instalador oficial do **Python 3.10.11** em python.org, confere a assinatura digital e o instala apenas para o usuário atual (sem privilégios de administrador);",
         "looks for Python 3.10 or later; if none is found, it downloads the official **Python 3.10.11** installer from python.org, checks its digital signature and installs it for the current user only (no administrator rights);"),
        ("executa `CODYN.py` já respondendo \"sim\" às perguntas de preparação (variável `CODYN_ASSUME_YES=1`);",
         "runs `CODYN.py` already answering \"yes\" to the setup questions (`CODYN_ASSUME_YES=1` variable);"),
        ("cria o ambiente virtual em `%USERPROFILE%\\.venv\\CODYN` com exatamente o Python 3.10.11 (no Linux qualquer 3.10 ou superior é aceito) e usa `%USERPROFILE%\\.venv\\CODYN\\Scripts\\python.exe` em todos os comandos de instalação;",
         "creates the virtual environment at `%USERPROFILE%\\.venv\\CODYN` with exactly Python 3.10.11 (on Linux any 3.10 or later is accepted) and uses `%USERPROFILE%\\.venv\\CODYN\\Scripts\\python.exe` in every installation command;"),
        ("instala o runtime do Visual C++ exigido pelas DLLs do Qt5 (`winget`; o Windows pede confirmação) e o PyQt5, abre o CODYN e cria os atalhos **CODYN** na Área de Trabalho e no Menu Iniciar.",
         "installs the Visual C++ runtime required by the Qt5 DLLs (`winget`; Windows asks for confirmation) and PyQt5, opens CODYN and creates the **CODYN** shortcuts on the Desktop and in the Start Menu."),
    ])
    m.p(("Depois disso, abra o CODYN pelo atalho: ele inicia com o `pythonw.exe`, **sem janela de console**, e a saída do programa e dos subprocessos aparece em **Ajuda > Terminal** "
         "(uma janela do PowerShell que acompanha o log da sessão, gravado em `%LOCALAPPDATA%\\CODYN`). O restante é instalado pela janela **Instalar requisitos** (seção 3).",
         "From then on, open CODYN from the shortcut: it starts with `pythonw.exe`, **without a console window**, and the output of the program and of its subprocesses appears in "
         "**Help > Terminal** (a PowerShell window that follows the session log, stored in `%LOCALAPPDATA%\\CODYN`). Everything else is installed from the "
         "**Install requirements** window (section 3)."))
    m.p(("**Diferenças no Windows:**", "**Differences on Windows:**"), keep_next=True)
    m.bullets([
        ("O **GROMACS não tem binário oficial para Windows**: a janela de requisitos o compila a partir do código-fonte em `%USERPROFILE%\\GROMACS`, com o CMake e o Visual Studio Build Tools "
         "(ambos instalados com `winget`, se ausentes; o CUDA é usado se o CUDA Toolkit existir). A compilação demora muito. Se você já tem um `gmx.exe`, defina a variável de ambiente `CODYN_GMX` com o caminho dele.",
         "**GROMACS has no official Windows binary**: the requirements window compiles it from source into `%USERPROFILE%\\GROMACS`, using CMake and the Visual Studio Build Tools "
         "(both installed with `winget` if missing; CUDA is used when the CUDA Toolkit is present). The build takes a long time. If you already have a `gmx.exe`, set the `CODYN_GMX` environment variable to its path."),
        ("O **Open Babel** vem do pacote pip `openbabel-wheel` e o **Perl** (preparo do CGenFF) do Strawberry Perl, instalado com `winget`.",
         "**Open Babel** comes from the `openbabel-wheel` pip package and **Perl** (CGenFF preparation) from Strawberry Perl, installed with `winget`."),
        ("O AmberTools não existe para Windows; por isso o método de ligantes **AMBER/GAFF** (antechamber, acpype) e a **ETAPA 6 (MM/GBSA, gmx_MMPBSA)** estão disponíveis **somente no Linux**. "
         "No Windows use o campo de força **CHARMM36 com ligantes CGenFF**; as ETAPAS 1 a 5, a aba RESULTADOS (gráficos) e o relatório final funcionam normalmente.",
         "AmberTools has no Windows build, so the **AMBER/GAFF** ligand method (antechamber, acpype) and **STEP 6 (MM/GBSA, gmx_MMPBSA)** are available on **Linux only**. "
         "On Windows use the **CHARMM36 force field with CGenFF ligands**; STEPS 1 to 5, the RESULTS tab (plots) and the final report work normally."),
        ("Use nomes curtos para projetos e ligantes: o Windows limita o caminho completo de um arquivo a 260 caracteres.",
         "Keep project and ligand names short: Windows limits the full path of a file to 260 characters."),
    ])

    # ============================================================== 3. Requisitos
    m.h1(("Pré-requisitos e instalação de dependências", "Prerequisites and installation of dependencies"))
    m.p(("A janela de instalação de requisitos é oferecida na inicialização quando algo essencial falta e pode ser reaberta a qualquer momento pelo botão "
         "**Instalar Requisitos** da aba INÍCIO ou pelo menu **Ajuda > Instalar requisitos**. Ela mostra, para cada item, se já está instalado (e em qual versão) "
         "e **pré-seleciona o que está ausente**.",
         "The requirements window is offered at startup when something essential is missing and can be reopened at any time from the **Install Requirements** button "
         "on the HOME tab or from the **Help > Install requirements** menu. For each item it shows whether it is already installed (and which version) and "
         "**pre-selects what is missing**."))
    m.fig("req.png", ("Janela de instalação de requisitos, com os itens agrupados por tipo.", "Requirements installer window, with items grouped by type."), 13.5)
    m.table([("Grupo", "Group"), ("Itens", "Items"), ("Observações", "Notes")], [
        [("**Ambiente Python**", "**Python environment**"), ("ambiente virtual, PyQt5, NumPy, pandas, Matplotlib, SciPy, psutil, NetworkX, MDAnalysis, RDKit, python-docx",
                                                              "virtual environment, PyQt5, NumPy, pandas, Matplotlib, SciPy, psutil, NetworkX, MDAnalysis, RDKit, python-docx"),
         ("Instalados com `pip` no ambiente do CODYN, com versões testadas. MDAnalysis e RDKit são opcionais; o python-docx é necessário para o relatório final.",
          "Installed with `pip` in the CODYN environment, with tested versions. MDAnalysis and RDKit are optional; python-docx is required for the final report.")],
        [("**Parametrização de ligantes**", "**Ligand parametrization**"), ("Open Babel, Perl, acpype, AmberTools",
                                                                            "Open Babel, Perl, acpype, AmberTools"),
         ("Open Babel converte os ligantes para MOL2; o Perl é usado pelo `sort_mol2_bonds.pl` (CGenFF); acpype e AmberTools (criado com conda, ambiente `AmberTools`) são exigidos para ligantes AMBER e pelo gmx_MMPBSA.",
          "Open Babel converts ligands to MOL2; Perl is used by `sort_mol2_bonds.pl` (CGenFF); acpype and AmberTools (created with conda, environment `AmberTools`) are required for AMBER ligands and by gmx_MMPBSA.")],
        [("**Ferramentas de simulação**", "**Simulation tools**"), ("CUDA Toolkit, GROMACS, OpenMPI, gmx_MMPBSA",
                                                                    "CUDA Toolkit, GROMACS, OpenMPI, gmx_MMPBSA"),
         ("O GROMACS 2024.5 é baixado e compilado em `~/gromacs_build` (com CUDA, se o `nvcc` existir) — demora bastante. O OpenMPI fornece o `mpirun` usado pelo gmx_MMPBSA.",
          "GROMACS 2024.5 is downloaded and compiled in `~/gromacs_build` (with CUDA if `nvcc` exists) — this takes a long time. OpenMPI provides the `mpirun` used by gmx_MMPBSA.")],
        [("**Atalho do menu**", "**Menu shortcut**"), ("criar/atualizar o atalho do CODYN", "create/update the CODYN shortcut"),
         ("Cria a entrada do CODYN no menu de aplicativos do usuário (no Windows, os atalhos `CODYN.lnk` na Área de Trabalho e no Menu Iniciar).", "Creates the CODYN entry in the user's applications menu (on Windows, the `CODYN.lnk` shortcuts on the Desktop and in the Start Menu).")],
    ], widths=[2.6, 4.4, 8.0], caption=("Grupos da janela de requisitos.", "Groups of the requirements window."))
    m.p(("Use **Selecionar ausentes** para marcar apenas o que falta, **Marcar/Desmarcar tudo**, **Atualizar situação** para reler o sistema e **Instalar selecionados** para iniciar. "
         "O andamento e os erros aparecem no log da própria janela; pacotes do sistema pedem a senha de administrador por uma janela do sistema (no Windows, o `winget` pede a confirmação do Windows). "
         "Se uma instalação falhar, o log indica o item; corrija o problema e execute novamente — itens já instalados são ignorados.",
         "Use **Select missing** to tick only what is missing, **Select/Unselect all**, **Refresh status** to re-read the system and **Install selected** to start. "
         "Progress and errors appear in the window's own log; system packages ask for the administrator password through a system dialog (on Windows, `winget` asks for Windows confirmation). "
         "If an installation fails, the log shows which item; fix the problem and run again — items already installed are skipped."))
    m.note(("A parametrização de ligantes pelo **CGenFF** (campo CHARMM36) usa o servidor web do CGenFF, que exige uma conta acadêmica gratuita (https://cgenff.silcsbio.com). "
            "O CODYN guia esse passo dentro da própria interface (seção 8). Para ligantes **AMBER** (GAFF/GAFF2) nenhuma conta é necessária.",
            "Ligand parametrization with **CGenFF** (CHARMM36 force field) uses the CGenFF web server, which requires a free academic account (https://cgenff.silcsbio.com). "
            "CODYN guides this step inside the interface (section 8). For **AMBER** ligands (GAFF/GAFF2) no account is needed."))

    # ============================================================== 4. Diretórios
    m.h1(("Organização dos diretórios", "Directory organization"))
    m.p(("Na inicialização, o CODYN verifica as pastas necessárias e cria as ausentes. A pasta raiz do programa (`$HOME/CODYN`, ou onde o código foi extraído) contém:",
         "At startup, CODYN checks the required folders and creates the missing ones. The program's root folder (`$HOME/CODYN`, or wherever the code was extracted) contains:"), keep_next=True)
    m.code(("""CODYN/
├── CODYN.py                                  arquivo principal
├── BIN/                                      módulos do programa
├── BASE/                                     modelos .mdp, CHARMM36 e conversor CGenFF
├── ICONS/                                    logotipo e bandeiras
├── TUTORIALS/                                este manual
└── PROJECTS/                                 um subdiretório por projeto
    └── 2026-11-16_16-56_AKT_TUTORIAL/
        ├── LIGANDS/                          ligantes do projeto
        ├── TARGET/                           proteína (.pdb)
        ├── RUNS/                             uma pasta por execução
        │   └── 2026-11-16_16-56_akt_asc/
        ├── RESULTS/                          relatórios e figuras (criada ao gerar)
        └── .form_data.json                   parâmetros da última execução""", """CODYN/
├── CODYN.py                                  main file
├── BIN/                                      program modules
├── BASE/                                     .mdp templates, CHARMM36 and CGenFF converter
├── ICONS/                                    logo and flags
├── TUTORIALS/                                this manual
└── PROJECTS/                                 one subfolder per project
    └── 2026-11-16_16-56_AKT_TUTORIAL/
        ├── LIGANDS/                          project ligands
        ├── TARGET/                           protein (.pdb)
        ├── RUNS/                             one folder per run
        │   └── 2026-11-16_16-56_akt_asc/
        ├── RESULTS/                          reports and figures (created on generation)
        └── .form_data.json                   parameters of the last run"""))
    m.p(("Cada **projeto** é uma pasta `PROJECTS/<AAAA-MM-DD_HH-MM>_<nome>` criada na aba CONFIG, o que mantém os arquivos de um trabalho separados dos de outros projetos e de outros usuários. "
         "Dentro de `RUNS`, cada execução recebe o nome `<data>_<proteína>_<ligante>` e contém todos os arquivos gerados nas etapas 1 a 6:",
         "Each **project** is a `PROJECTS/<YYYY-MM-DD_HH-MM>_<name>` folder created in the CONFIG tab, which keeps the files of one study apart from those of other projects and other users. "
         "Inside `RUNS`, each run is named `<date>_<protein>_<ligand>` and contains all the files generated in steps 1 to 6:"), keep_next=True)
    m.table([("Arquivo(s)", "File(s)"), ("Gerado em", "Generated in"), ("Conteúdo", "Content")], [
        ["`run_config.json`", ("CONFIG", "CONFIG"), ("Registro de tudo o que foi simulado (campo de força, tempos, caixa, íons, versão do CODYN).", "Record of everything that was simulated (force field, times, box, ions, CODYN version).")],
        ["`LIG.mol2`, `LIG.itp`, `LIG.prm`, `LIG.gro`, `posre_lig.itp`", (("Etapa 1", "Step 1")), ("Ligante convertido, topologia, parâmetros e restrições de posição dos átomos pesados.", "Converted ligand, topology, parameters and heavy-atom position restraints.")],
        ["`protein.gro`, `topol.top`, `complex.gro`, `*.mdp`", ("Etapa 2", "Step 2"), ("Proteína e ligante topologizados, complexo montado e arquivos de parâmetros do GROMACS.", "Topologized protein and ligand, assembled complex and GROMACS parameter files.")],
        ["`newbox.gro`, `solv.gro`, `solv_ions.gro`, `em.*`, `potential.xvg`", ("Etapa 3", "Step 3"), ("Caixa, solvente, íons e minimização de energia.", "Box, solvent, ions and energy minimization.")],
        ["`index.ndx`, `nvt.*`, `npt.*`, `temperature.xvg`, `pressure.xvg`, `density.xvg`", ("Etapa 4", "Step 4"), ("Grupos de acoplamento e equilibração NVT/NPT com suas propriedades.", "Coupling groups and NVT/NPT equilibration with their properties.")],
        ["`md_0_<t>.tpr/.xtc/.edr/.log`, `md_0_<t>_noPBC.xtc`", ("Etapa 5", "Step 5"), ("Produção; `<t>` é o tempo em ns (ex.: `md_0_100.xtc`). A versão `_noPBC` tem as condições periódicas removidas.", "Production; `<t>` is the time in ns (e.g. `md_0_100.xtc`). The `_noPBC` version has periodic boundaries removed.")],
        ["`mmpbsa.in`, `FINAL_RESULTS_MMPBSA.dat/.csv`, `FINAL_DECOMP_MMPBSA.dat`", ("Etapa 6", "Step 6"), ("Entrada e resultados do gmx_MMPBSA (energia livre e decomposição por resíduo).", "gmx_MMPBSA input and results (free energy and per-residue decomposition).")],
        ["`*.xvg` (`rmsd_*`, `rmsf_*`, `sasa_*`...)", ("RESULTADOS", "RESULTS"), ("Análises da trajetória, calculadas sob demanda e guardadas para reutilização; as do relatório recebem o prefixo `rep_`.", "Trajectory analyses, computed on demand and cached for reuse; those of the report use the `rep_` prefix.")],
    ], widths=[5.6, 2.0, 7.4], caption=("Principais arquivos de uma pasta de execução.", "Main files of a run folder."), font=8.5)
    m.note(("Os parâmetros de cada projeto (o formulário da aba CONFIG) são guardados no arquivo `.form_data.json` do próprio projeto e restaurados ao carregá-lo. "
            "O CODYN reabre automaticamente o último projeto usado.",
            "The parameters of each project (the CONFIG form) are stored in the project's own `.form_data.json` file and restored when it is loaded. "
            "CODYN automatically reopens the last project used."))
    m.note(("Versões anteriores à 2.1.0 guardavam as execuções em uma pasta `RUNS/` na raiz. Na primeira inicialização, o conteúdo dessa pasta é movido para "
            "`PROJECTS/<data>_RUNS_ANTERIORES/RUNS/` (as pastas `LIGANDS/` e `TARGET/` antigas são copiadas e as originais mantidas) e o projeto migrado é aberto.",
            "Versions before 2.1.0 kept the runs in a `RUNS/` folder in the root. On the first start, the contents of that folder are moved to "
            "`PROJECTS/<date>_RUNS_ANTERIORES/RUNS/` (the old `LIGANDS/` and `TARGET/` folders are copied and the originals kept) and the migrated project is opened."))

    # ============================================================== 5. Uso geral
    m.h1(("Orientações gerais de uso", "General usage guidelines"))
    m.p(("A janela principal é organizada em abas na ordem natural do fluxo de trabalho: **INÍCIO**, **CONFIG**, **ETAPA 1** a **ETAPA 6** e **RESULTADOS**. "
         "As etapas 1 a 5 são executadas automaticamente a partir do botão EXECUTAR da aba CONFIG — o programa troca de aba sozinho conforme o andamento. "
         "As etapas 6 (MM/PBSA) e RESULTADOS são acionadas pelo usuário.",
         "The main window is organized in tabs following the natural order of the workflow: **HOME**, **CONFIG**, **STEP 1** to **STEP 6** and **RESULTS**. "
         "Steps 1 to 5 run automatically from the RUN button of the CONFIG tab — the program switches tabs by itself as the run progresses. "
         "Step 6 (MM/PBSA) and RESULTS are triggered by the user."))
    m.table([("Elemento", "Element"), ("Função", "Function")], [
        [("**Menu**", "**Menu**"), ("Atalhos para cada aba (Configurar Nova Execução, Etapas 1–6, Visualização dos Resultados) e **Sair**.", "Shortcuts to each tab (Configure New Run, Steps 1–6, Results Visualization) and **Exit**.")],
        [("**Ajuda**", "**Help**"), ("**Instalar requisitos** (seção 3); **Terminal**, que abre o log da sessão (saída do programa e dos subprocessos) em tempo real; **Código e documentação (GitHub)**.",
                                      "**Install requirements** (section 3); **Terminal**, which opens the session log (program and subprocess output) in real time; **Code and documentation (GitHub)**.")],
        [("**Sobre**", "**About**"), ("Autores, contato e versão. Fica diretamente na barra de menu.", "Authors, contact and version. Located directly on the menu bar.")],
        [("**Bandeiras**", "**Flags**"), ("Alternam a interface entre português e inglês. A escolha é memorizada; no primeiro uso o idioma do sistema é seguido. O idioma também define o idioma do relatório final.",
                                          "Switch the interface between Portuguese and English. The choice is remembered; on first use the system language is followed. The language also sets the language of the final report.")],
        [("**Monitor CPU/GPU**", "**CPU/GPU Monitor**"), ("Abre uma janela independente com o uso de CPU e GPU em tempo real — útil para acompanhar a simulação.", "Opens a standalone window with real-time CPU and GPU usage — useful for following the simulation.")],
        [("**Título da janela**", "**Window title**"), ("Mostra o nome do projeto aberto.", "Shows the name of the open project.")],
    ], widths=[3.2, 11.8], caption=("Elementos comuns da janela principal.", "Common elements of the main window."))
    m.fig("monitor.png", ("Janela do Monitor CPU/GPU.", "CPU/GPU Monitor window."), 6.5)
    m.p(("Em praticamente todos os campos há **dicas** exibidas ao posicionar o cursor sobre o elemento, explicando seu efeito. "
         "O botão **CANCELAR** das abas de etapa interrompe de verdade os processos do GROMACS (e do acpype/mpirun) e volta à aba INÍCIO, após uma confirmação. "
         "Se a janela for fechada durante uma execução, o programa pergunta se deve cancelá-la. "
         "O CODYN permite apenas uma execução do pipeline por vez; o MM/PBSA, porém, pode ser usado em outro momento sobre execuções já concluídas.",
         "Almost every field has a **tooltip**, shown when the cursor is placed over the element, explaining its effect. "
         "The **CANCEL** button of the step tabs really stops the GROMACS (and acpype/mpirun) processes and returns to the HOME tab, after a confirmation. "
         "If the window is closed during a run, the program asks whether to cancel it. "
         "CODYN allows only one pipeline run at a time; MM/PBSA, however, can be used later on runs that have already finished."))

    # ============================================================== 6. HOME
    m.h1(("Aba INÍCIO — especificações e visão geral", "HOME tab — specifications and overview"))
    m.p(("A aba INÍCIO resume o ambiente em que o CODYN está rodando e o fluxo de trabalho. Na primeira exibição a janela se ajusta ao conteúdo, de modo que não há barra de rolagem.",
         "The HOME tab summarizes the environment CODYN is running on and the workflow. On first display the window fits its content, so there is no scroll bar."))
    m.fig("home.png", ("Aba INÍCIO: especificações de hardware e software detectadas e resumo das etapas do pipeline.", "HOME tab: detected hardware and software specifications and summary of the pipeline steps."), 15.5)
    m.bullets([
        ("**Especificações de Hardware — CPU/GPU**: arquitetura, modelo, clock máximo, núcleos físicos e threads lógicas, caches L2/L3 e RAM; para a GPU NVIDIA, modelo, VRAM, clock máximo, limite de potência, driver e versão do CUDA.",
         "**Hardware Specs — CPU/GPU**: architecture, model, maximum clock, physical cores and logical threads, L2/L3 caches and RAM; for the NVIDIA GPU, model, VRAM, maximum clock, power limit, driver and CUDA version."),
        ("**Software**: versão de cada componente detectado (PyQt5, NumPy, pandas, Matplotlib, SciPy, psutil, NetworkX, MDAnalysis, RDKit, python-docx, GROMACS — com a indicação [CUDA] quando compilado com GPU —, Open Babel, Perl, AmberTools, acpype, gmx_MMPBSA, MPI e CUDA Toolkit). "
         "Componentes ausentes aparecem em vermelho como *não instalado*.",
         "**Software**: version of each detected component (PyQt5, NumPy, pandas, Matplotlib, SciPy, psutil, NetworkX, MDAnalysis, RDKit, python-docx, GROMACS — flagged [CUDA] when built with GPU —, Open Babel, Perl, AmberTools, acpype, gmx_MMPBSA, MPI and CUDA Toolkit). "
         "Missing components appear in red as *not installed*."),
        ("**Pipeline**: resumo da função de cada aba, da configuração aos resultados.", "**Pipeline**: summary of the role of each tab, from configuration to results."),
        ("Botões: **INICIAR** (vai para a aba CONFIG), **Instalar Requisitos** (abre a janela da seção 3) e **Atualizar** (relê o hardware e as versões instaladas).",
         "Buttons: **START** (goes to the CONFIG tab), **Install Requirements** (opens the window from section 3) and **Refresh** (re-reads the hardware and installed versions)."),
    ])
    m.note(("Os grupos da interface podem ser recolhidos clicando no título (▾). Se o GROMACS aparecer sem a marca [CUDA], as simulações rodarão apenas na CPU.",
            "The interface groups can be collapsed by clicking on the title (▾). If GROMACS appears without the [CUDA] mark, simulations will run on the CPU only."))

    # ============================================================== 7. CONFIG
    m.h1(("Aba CONFIG — configuração do projeto e da simulação", "CONFIG tab — project and simulation setup"))
    m.p(("A aba CONFIG reúne todos os parâmetros de uma execução, organizados em seis grupos, em duas colunas. É o primeiro passo obrigatório: "
         "**sem um projeto aberto, o botão EXECUTAR permanece desabilitado**.",
         "The CONFIG tab gathers all parameters of a run, organized in six groups in two columns. It is the mandatory first step: "
         "**without an open project, the RUN button stays disabled**."))
    m.fig("config.png", ("Aba CONFIG com um projeto aberto, dois ligantes e a proteína encontrados.", "CONFIG tab with an open project, two ligands and the protein found."), 15.5)

    m.h2(("Projetos", "Projects"))
    m.p(("O grupo **Projetos** cria ou carrega um projeto de dinâmica molecular. O procedimento é o seguinte:",
         "The **Projects** group creates or loads a molecular dynamics project. The procedure is as follows:"), keep_next=True)
    m.numbered([
        ("Para um projeto novo, marque **Novo Projeto** e digite o **Nome do projeto**. A data e a hora atuais são acrescentadas automaticamente, formando o **ID do projeto** (por exemplo `2026-11-16_16-56_AKT_TUTORIAL`); espaços e caracteres especiais do nome são removidos.",
         "For a new project, tick **New Project** and type the **Project name**. The current date and time are added automatically, forming the **Project ID** (for example `2026-11-16_16-56_AKT_TUTORIAL`); spaces and special characters in the name are removed."),
        ("Para retomar um trabalho, marque **Carregar Projeto Anterior** e escolha o projeto na lista **Projeto anterior** (os mais recentes primeiro).",
         "To resume work, tick **Load Previous Project** and choose the project from the **Previous project** list (most recent first)."),
        ("Clique em **Criar / Carregar Projeto**. Um projeto novo recebe as subpastas `LIGANDS`, `TARGET` e `RUNS`; ao carregar, os parâmetros da última execução do projeto são restaurados.",
         "Click **Create / Load Project**. A new project receives the `LIGANDS`, `TARGET` and `RUNS` subfolders; when loading, the parameters of the project's last run are restored."),
    ])
    m.fig("config_empty.png", ("Aba CONFIG sem projeto aberto: crie ou carregue um projeto para habilitar a execução.", "CONFIG tab with no open project: create or load a project to enable the run."), 15.0)
    m.p(("Uma mensagem verde (*Projeto aberto*) confirma o caminho do projeto; a vermelha avisa que nenhum projeto está aberto. Se já existir um projeto com o mesmo ID (mesmo nome no mesmo minuto), o CODYN avisa e não o sobrescreve.",
         "A green message (*Open project*) confirms the project path; the red one warns that no project is open. If a project with the same ID already exists (same name in the same minute), CODYN warns and does not overwrite it."))

    m.h2(("Pastas do projeto e ligantes", "Project folders and ligands"))
    m.p(("Os campos **Pasta LIGANDS** e **Pasta TARGET** apontam sempre para as subpastas do projeto aberto (somente leitura). Copie para elas os arquivos de entrada: "
         "ligantes em `.pdbqt`, `.pdb`, `.mol2`, `.sdf` ou `.mol` e a proteína em `.pdb` (um `.pdbqt` também é aceito e convertido pelo Open Babel, sem apagar o original). "
         "O botão **Abrir** abre a pasta no gerenciador de arquivos e **⟳** relê o conteúdo.",
         "The **LIGANDS folder** and **TARGET folder** fields always point to the subfolders of the open project (read-only). Copy the input files into them: "
         "ligands as `.pdbqt`, `.pdb`, `.mol2`, `.sdf` or `.mol` and the protein as `.pdb` (a `.pdbqt` is also accepted and converted by Open Babel, without deleting the original). "
         "The **Open** button opens the folder in the file manager and **⟳** re-reads its contents."))
    m.bullets([
        ("**Proteína**: escolhe qual proteína da pasta TARGET será usada. A proteína deve estar preparada (sem moléculas de água indesejadas, com as cadeias e resíduos que serão simulados).",
         "**Protein**: chooses which protein of the TARGET folder will be used. The protein should be prepared (without unwanted water molecules, with the chains and residues to be simulated)."),
        ("**Tabela de ligantes**: lista cada ligante com as colunas **Rodar** (marque os que participarão), **Ligante**, **Formato** e **Carga líquida**. "
         "A carga líquida **auto** é obtida do ligante convertido; para forçar outro valor inteiro, edite a célula. Será criada **uma execução por ligante marcado**.",
         "**Ligand table**: lists each ligand with the columns **Run** (tick those that will take part), **Ligand**, **Format** and **Net charge**. "
         "The **auto** net charge is derived from the converted ligand; to force another integer value, edit the cell. **One run is created per ticked ligand**."),
    ])

    m.h2(("Campo de força e parametrização do ligante", "Force field and ligand parametrization"))
    m.table([("Campo", "Field"), ("Opções e efeito", "Options and effect")], [
        [("**Campo de força**", "**Force field**"), ("CHARMM36 (Jul 2021), AMBER99SB-ILDN ou AMBER99SB. O CHARMM36 usa o CGenFF para o ligante; os campos AMBER usam GAFF/GAFF2.",
                                                      "CHARMM36 (Jul 2021), AMBER99SB-ILDN or AMBER99SB. CHARMM36 uses CGenFF for the ligand; the AMBER fields use GAFF/GAFF2.")],
        [("**Modelo de água**", "**Water model**"), ("TIP3P, TIP4P, TIP5P, SPC ou SPC/E. É passado ao `pdb2gmx` e define o arquivo de caixa usado na solvatação.",
                                                      "TIP3P, TIP4P, TIP5P, SPC or SPC/E. It is passed to `pdb2gmx` and defines the box file used in solvation.")],
        [("**Parâmetros do ligante**", "**Ligand parameters**"), ("CGenFF (CHARMM), GAFF2 (AMBER) ou GAFF (AMBER), conforme o campo de força.", "CGenFF (CHARMM), GAFF2 (AMBER) or GAFF (AMBER), according to the force field.")],
        [("**Cargas parciais**", "**Partial charges**"), ("Apenas para ligantes AMBER: AM1-BCC (mais lento e mais preciso) ou Gasteiger.", "Only for AMBER ligands: AM1-BCC (slower and more accurate) or Gasteiger.")],
        [("**Ignorar H do PDB**", "**Ignore PDB hydrogens**"), ("Equivale a `pdb2gmx -ignh`: reconstrói os hidrogênios com a nomenclatura do campo de força. Use quando o `pdb2gmx` reclamar dos nomes de átomos; descarta estados de protonação definidos no PDB.",
                                                                  "Equivalent to `pdb2gmx -ignh`: rebuilds the hydrogens with the force-field naming. Use it when `pdb2gmx` complains about atom names; it discards protonation states set in the PDB.")],
    ], widths=[3.4, 11.6], caption=("Parâmetros de campo de força e ligante.", "Force-field and ligand parameters."))

    m.h2(("Sistema (caixa e íons)", "System (box and ions)"))
    m.table([("Campo", "Field"), ("Descrição", "Description"), ("Padrão", "Default")], [
        [("**Tipo de caixa**", "**Box type**"), ("cubic, triclinic, dodecahedron ou octahedron. Caixas dodecaédricas/octaédricas usam menos solvente para o mesmo afastamento.", "cubic, triclinic, dodecahedron or octahedron. Dodecahedral/octahedral boxes use less solvent for the same clearance."), "cubic"],
        [("**Distância soluto-caixa**", "**Solute-box distance**"), ("Distância mínima entre o complexo e a borda da caixa (0,5–5 nm).", "Minimum distance between the complex and the box edge (0.5–5 nm)."), ("1,0 nm", "1.0 nm")],
        [("**Íon positivo / negativo**", "**Positive / negative ion**"), ("Escolhidos entre os íons do campo de força (CHARMM36: SOD, POT, CAL, MG, ZN2... / CLA, CO3, OH; AMBER: NA, K, CA, MG, ZN... / CL, BR, IOD); a caixa é editável.",
                                                                          "Chosen among the force field ions (CHARMM36: SOD, POT, CAL, MG, ZN2... / CLA, CO3, OH; AMBER: NA, K, CA, MG, ZN... / CL, BR, IOD); the box is editable."), "SOD / CLA (NA / CL)"],
        [("**Concentração de íons**", "**Ion concentration**"), ("Concentração salina (0–2 M). O sistema é sempre neutralizado antes.", "Salt concentration (0–2 M). The system is always neutralized first."), ("0,150 M", "0.150 M")],
    ], widths=[3.6, 9.4, 2.0], caption=("Parâmetros da caixa e dos íons.", "Box and ion parameters."))

    m.h2(("Simulação e hardware", "Simulation and hardware"))
    m.table([("Campo", "Field"), ("Descrição", "Description"), ("Padrão", "Default")], [
        [("**Tempo de produção**", "**Production time**"), ("Duração da dinâmica de produção, em ns.", "Duration of the production dynamics, in ns."), "100 ns"],
        [("**Tempo de equilibração**", "**Equilibration time**"), ("Usado em cada uma das etapas NVT e NPT.", "Used for each of the NVT and NPT steps."), ("0,5 ns", "0.5 ns")],
        [("**Passo de integração**", "**Integration step**"), ("0,5–4 fs. Com 2 fs as ligações com hidrogênio são restringidas; passos maiores exigem reparticionamento de massa do hidrogênio (o CODYN avisa).",
                                                                "0.5–4 fs. With 2 fs the bonds to hydrogen are constrained; larger steps need hydrogen mass repartitioning (CODYN warns)."), "2 fs"],
        [("**Temperatura**", "**Temperature**"), ("Temperatura de referência dos termostatos e da geração de velocidades.", "Reference temperature of the thermostats and velocity generation."), "310 K"],
        [("**Threads de CPU**", "**CPU threads**"), ("Número de threads OpenMP do `mdrun`.", "Number of OpenMP threads of `mdrun`."), ("todas as lógicas", "all logical")],
        [("**Usar a GPU**", "**Use the GPU**"), ("Envia ao GPU o cálculo não ligado, PME, ligado e atualização. Desabilitada se o GROMACS não tiver suporte a GPU. Se uma configuração de GPU falhar, o CODYN tenta automaticamente uma mais leve e, por fim, a CPU.",
                                                    "Offloads non-bonded, PME, bonded and update to the GPU. Disabled if GROMACS has no GPU support. If a GPU setup fails, CODYN automatically tries a lighter one and finally the CPU."), ("ligado se houver", "on if available")],
    ], widths=[3.6, 9.4, 2.0], caption=("Parâmetros de simulação e hardware.", "Simulation and hardware parameters."))

    m.h2(("Executar", "Running"))
    m.p(("Ao clicar em **EXECUTAR**, o CODYN valida o formulário (campos inválidos, nenhum ligante marcado, nenhuma proteína, ferramentas ausentes), grava os parâmetros no projeto e cria, para cada ligante marcado, "
         "a pasta `PROJECTS/<projeto>/RUNS/<data>_<proteína>_<ligante>` com seu `run_config.json`. Em seguida o pipeline começa na ETAPA 1. **CANCELAR** volta à aba INÍCIO.",
         "When **RUN** is clicked, CODYN validates the form (invalid fields, no ligand ticked, no protein, missing tools), saves the parameters in the project and creates, for each ticked ligand, "
         "the `PROJECTS/<project>/RUNS/<date>_<protein>_<ligand>` folder with its `run_config.json`. The pipeline then starts at STEP 1. **CANCEL** returns to the HOME tab."))
    m.note(("As etapas são executadas **por etapa, para todos os ligantes**: primeiro a ETAPA 1 de todas as execuções, depois a ETAPA 2 de todas, e assim por diante. "
            "Se um ligante falhar em alguma etapa, ele é marcado como *Falhou* na tabela da ETAPA 1 e as demais execuções seguem normalmente.",
            "The steps run **step by step, for all ligands**: first STEP 1 of all runs, then STEP 2 of all, and so on. "
            "If a ligand fails at some step, it is marked as *Failed* in the STEP 1 table and the remaining runs continue normally."))
