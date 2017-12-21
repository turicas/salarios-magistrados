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


## Rodando

Esse script depende de Python 3.6 e de algumas bibliotecas. Instale-as
executando:

```bash
pip install -r requirements.txt
```

Para rodar:

```bash
python salarios_magistrados.py
```

## Possíveis problemas

```locale.Error: unsupported locale setting```

Você não tem a localização pt_BR, que é necessária para que o script funcione corretamente.

No Ubuntu, é possivel resolver com:

```bash
sudo locale-gen pt_BR
sudo locale-gen pt_BR.UTF-8
sudo update-locale
```

No Windows, talvez seja necessário instalar os dicionários em Português-Brasil para que funcione corretamente.

Um diretório `download` será criado com as planilhas baixadas e `output` com os
resultados.
