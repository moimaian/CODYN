# Versionamento do CODYN

A versão segue **MAJOR.MINOR.PATCH** (SemVer) para o número que importa (o
que aparece antes do traço); o `-N` depois do traço é a *revisão de
empacotamento*, no sentido estrito do Debian — só sobe quando `packaging/`
muda (control.in, postinst, postrm, codyn-launcher, .desktop...) sem nenhuma
mudança de código do programa. Toda mudança de código reseta o `-N` para
`-1`.

**Fonte única do número: [`BIN/versao.py`](../BIN/versao.py)** (`VERSAO =
"..."`). É o mesmo valor que:
- aparece no rodapé da HOME e de cada etapa;
- aparece em Help > About;
- `packaging/deb/build.sh` usa como padrão ao gerar o `.deb`.

`packaging/deb/build.sh` recusa rodar se `BIN/versao.py` e a primeira linha
de `packaging/deb/changelog` não tiverem o mesmo número — os dois precisam
ser atualizados juntos.

```
2.0.0    -1
└─┬─┘    └┬┘
  │       └─ revisão de empacotamento (só packaging/ mudou)
  └─ versão do programa (MAJOR.MINOR.PATCH)
```

## Como decidir qual número sobe

A pergunta é **"alguém que já usa o CODYN hoje vai precisar fazer algo
diferente, ou vai ter algo que parou de funcionar, por causa desta
mudança?"**

- **PATCH** (`2.0.0` → `2.0.1`): corrige um bug sem mudar nenhum
  comportamento esperado.
- **MINOR** (`2.0.0` → `2.1.0`, zera o patch): funcionalidade nova, sem
  quebrar nada do que já existia (ex.: um novo gráfico de análise, uma nova
  opção de parametrização de ligante).
- **MAJOR** (`2.0.0` → `3.0.0`, zera minor e patch): muda ou remove algo de
  um jeito que exige adaptação. Ex.:
  - renumerar/remover uma STEP do fluxo;
  - mudar o formato de `run_config.json`/`.form_data.json` ou o layout de
    `RUNS/<execução>/` sem migração automática;
  - renomear as pastas `RUNS`, `LIGANDS`, `TARGET`, `BASE`, `BIN`;
  - mudar a versão mínima de Python exigida;
  - mudar `/opt/codyn` para outro caminho no `.deb`.

## Ao gerar um novo `.deb`

1. Decida o próximo `MAJOR.MINOR.PATCH` pelas regras acima.
2. Atualize `VERSAO` em `BIN/versao.py`.
3. Adicione uma entrada no topo de `packaging/deb/changelog` (formato Debian:
   `codyn (X.Y.Z-1) unstable; urgency=low`, lista do que mudou, linha
   `-- Nome <email>  data`) com o **mesmo** número do passo 2.
4. Rode `packaging/deb/build.sh`. O pacote sai como
   `packaging/dist/codyn_X.Y.Z-1_all.deb`.

Se a mudança for só de empacotamento, mantenha o `X.Y.Z` e suba só o `-N`
(`2.0.0-1` → `2.0.0-2`) — também em `BIN/versao.py`.
