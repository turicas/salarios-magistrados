[![Build Status](https://travis-ci.org/thenets/salarios-magistrados.svg?branch=develop)](https://travis-ci.org/thenets/salarios-magistrados)

[![Docker Pulls](https://img.shields.io/docker/pulls/thenets/opendata-salarios-magistrados.svg?style=flat-square)](https://hub.docker.com/r/thenets/opendata-salarios-magistrados/)

# Salários Magistrados - CNJ

Script que baixa todas as [planilhas de salários de magistrados do site do
CNJ](http://www.cnj.jus.br/transparencia/remuneracao-dos-magistrados), extrai a
aba "Contracheque", faz algumas limpezas e exporta tudo para CSV.


## Dados

Caso você não queira rodar o script em sua máquina, [acesse diretamente a
planilha
convertida](https://drive.google.com/open?id=1R59t64Ml5v94YtGu76w5p17PEPb3V2dm).

### Erros nos Dados

Nem todas as planilhas puderam ser convertidas. Verifique o arquivo
[erros.csv](erros.csv) para entender quais erros existem nos dados originais e
como isso se propaga para os dados gerados pelo script.

Encontrou algum erro na conversão que o script faz? [Crie uma issue nesse
repositório](https://github.com/turicas/salarios-magistrados/issues/new).

## Como executar

### Docker / container

Ao utilizar o Docker não é necessário se preocupar com o sistema operacional, bibliotecas ou qualquer outra coisa relativa ao ambiente.

O único requisito é ter o Docker instalado. O guia de instalação pode ser encontrado em [Docker Community Edition](https://www.docker.com/community-edition).

Para gerar os novos dados, basta executar a linha abaixo:

```bash
docker run --rm -it -v $(pwd)/output:/app/output thenets/opendata-salarios-magistrados
```


### Python

Esse script depende de Python 3.6 e de algumas bibliotecas. Instale-as
executando:

```bash
pip install -r requirements.txt
```

Para rodar:

```bash
python salarios_magistrados.py
```

Um diretório `download` será criado com as planilhas baixadas e `output` com os
resultados.
