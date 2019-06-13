# Salários Magistrados - CNJ

Script que baixa todas as [planilhas de salários de magistrados do site do
CNJ](http://www.cnj.jus.br/transparencia/remuneracao-dos-magistrados), extrai a
aba "Contracheque", faz algumas limpezas e exporta tudo para CSV.


## Licença

A licença do código é [LGPL3](https://www.gnu.org/licenses/lgpl-3.0.en.html) e
dos dados convertidos [Creative Commons Attribution
ShareAlike](https://creativecommons.org/licenses/by-sa/4.0/). Caso utilize os
dados, **cite a fonte original e quem tratou os dados**, como: **Fonte:
Conselho Nacional de Justiça, dados tratados por Álvaro
Justen/[Brasil.IO](https://brasil.io/)**. Caso compartilhe os dados, **utilize
a mesma licença**.


## Dados

Caso você não queira/possa rodar o script, **[acesse diretamente os dados
convertidos no Brasil.IO](https://brasil.io/dataset/salarios-magistrados)**.

Se esse programa e/ou os dados resultantes foram úteis a você ou à sua empresa,
considere [fazer uma doação ao projeto Brasil.IO](https://brasil.io/doe), que é
mantido voluntariamente.


### Erros nos Dados

Nem todas as planilhas puderam ser convertidas. Verifique o arquivo
[erros.csv](erros.csv) para entender quais erros existem nos dados originais e
como isso se propaga para os dados gerados pelo script.

Encontrou algum erro na conversão que o script faz? [Crie uma issue nesse
repositório](https://github.com/turicas/salarios-magistrados/issues/new).


## Rodando

Esse script depende de Python 3.7+ e de algumas bibliotecas. Instale-as
executando:

```bash
pip install -r requirements.txt
```

Para rodar:

```bash
./run.sh
```

Esse script irá rodar dois scripts, um que baixa as planilhas e outro que as
extrai e gera o resultado. Você pode rodá-los independentemente também:

```bash
# Baixa planilhas e gera `data/output/planilha.csv`:
scrapy runspider --loglevel=INFO -o data/output/planilha.csv download_files.py
gzip data/output/planilha.csv

# Lê `data/output/planilha.csv.gz` e gera outros arquivos em `data/output`:
python parse_files.py
```

Um diretório `data` será criado, onde:
- `data/download`: planilhas baixadas;
- `data/output`: arquivos de saída (CSVs compactados).
