# Medição do acervo de planos do TxDOT

`measure.py` percorre as listagens de pasta de `https://ftp.txdot.gov/plans/` e mede o acervo **sem baixar nenhum arquivo**: só lê o HTML das listagens. Usa apenas a biblioteca padrão do Python 3.

```bash
python3 tools/txdot/measure.py --out txdot-measure          # varredura completa
python3 tools/txdot/measure.py --out txdot-measure --max-dirs 50   # teste rápido
python3 tools/txdot/measure.py --out txdot-measure --report-only   # só refaz o relatório
```

Se for interrompida, a varredura retoma de onde parou: as pastas já lidas ficam em `listing.jsonl`.

Saídas em `--out`:

| Arquivo | Conteúdo |
|---|---|
| `REPORT.md` | Volume total, recorte dos últimos 5 anos, volume por ano, pasta e extensão, maiores arquivos |
| `catalog.csv` | Uma linha por arquivo: caminho, nome, extensão, tamanho, data |
| `summary.json` | Os mesmos números do relatório, em JSON |
| `listing.jsonl` | Listagem bruta por pasta (usada para retomar) |
| `sample_root.html` | HTML da pasta raiz, para conferir o formato |
| `errors.jsonl` | Pastas ou arquivos que falharam |

O recorte "últimos N anos" (`--years`) usa a data de modificação do arquivo. Se as pastas forem organizadas por data de licitação, a tabela "por pasta" dá o recorte mais fiel.

Por padrão o script espera 0,3 s entre requisições (`--delay`) para não sobrecarregar o servidor. As credenciais padrão são as públicas que o próprio TxDOT divulga para o acervo.
