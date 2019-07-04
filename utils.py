import re

import Levenshtein
from rows.fields import slug


MONTHS = "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split()
regexp_tribunal_fim = re.compile(" *\([^)]*\)*$")
regexp_tribunal_ordinal = re.compile("([0-9])a ")
regexp_ordinal = re.compile("([0-9]+)A.")


def fix_tribunal(tribunal):
    """
    >>> fix_tribunal('Tribunal Regional Federal da 4ª Região (')
    'Tribunal Regional Federal da 4ª Região'
    >>> fix_tribunal('Tribunal Regional Federal da 4a Região (XX)')
    'Tribunal Regional Federal da 4ª Região'
    >>> fix_tribunal('Tribunal a /Conselho B')
    'Tribunal A/Conselho B'
    >>> fix_tribunal('Tribunal a/ Conselho B')
    'Tribunal A/Conselho B'
    >>> fix_tribunal('Tribunal de Justiça do Distrito Federal E Dos Territórios')
    'Tribunal de Justiça do Distrito Federal e Territórios'
    >>> fix_tribunal('TRT 1a Região')
    'Tribunal Regional do Trabalho da 1ª Região'
    >>> fix_tribunal('TRF 1a Região')
    'Tribunal Regional Federal da 1ª Região'
    >>> fix_tribunal('TRIBUNAL DE JUSTIÇA DO ESTADO DE MATO GROSSO')
    'Tribunal de Justiça do Mato Grosso'
    >>> fix_tribunal('JUSTIÇA FEDERAL DA 3ª REGIÃO')
    'Tribunal Regional Federal da 3ª Região'
    >>> fix_tribunal('TRE-AM')
    'Tribunal Regional Eleitoral do Amazonas'
    >>> fix_tribunal('TRF 5ª REGIÃO')
    'Tribunal Regional Federal da 5ª Região'
    >>> fix_tribunal('TRF DA 5ª REGIÃO')
    'Tribunal Regional Federal da 5ª Região'
    >>> fix_tribunal('Tribunal de Justica de Santa Catarina')
    'Tribunal de Justiça de Santa Catarina'
    >>> fix_tribunal('Tribunal de Justiça do Estado de Goiás')
    'Tribunal de Justiça do Goiás'
    >>> fix_tribunal('Tribunal de Justiça do Estado do Mato Grosso do Sul')
    'Tribunal de Justiça do Mato Grosso do Sul'
    >>> fix_tribunal('TRIBUNAL DE JUSTIÇA DO ESTADO DE MATO GROSSO')
    'Tribunal de Justiça do Mato Grosso'
    >>> fix_tribunal('Tribunal de Justiça do  Estado de Rondônia')
    'Tribunal de Justiça de Rondônia'
    >>> fix_tribunal('Tribunal de Justiça do Estado de Rondônia')
    'Tribunal de Justiça de Rondônia'
    >>> fix_tribunal('Tribunal de Justiça do Estado de São Paulo')
    'Tribunal de Justiça de São Paulo'
    >>> fix_tribunal('Tribunal de Justiça do Estado de Sergipe')
    'Tribunal de Justiça do Sergipe'
    >>> fix_tribunal('Tribunal de Justiça do Estado do Acre')
    'Tribunal de Justiça do Acre'
    >>> fix_tribunal('Tribunal de Justiça do Estado do Amapá')
    'Tribunal de Justiça do Amapá'
    >>> fix_tribunal('Tribunal de Justiça do Estado do Rio de Janeiro')
    'Tribunal de Justiça do Rio de Janeiro'
    >>> fix_tribunal('Tribunal de Justiça do Estado do Tocantins')
    'Tribunal de Justiça do Tocantins'
    >>> fix_tribunal('Tribunal de Justiça do Pará - TJPA')
    'Tribunal de Justiça do Pará'
    >>> fix_tribunal('Tribunal de Justiça do RN')
    'Tribunal de Justiça do Rio Grande do Norte'
    >>> fix_tribunal('Tribunal de Justiça Estado do Espírito Santo')
    'Tribunal de Justiça do Espírito Santo'
    >>> fix_tribunal('Tribunal de Justiça Militar do Rio Grande do Sul')
    'Tribunal de Justiça Militar do Rio Grande do Sul'
    >>> fix_tribunal('Tribunal de Justiça TJPA')
    'Tribunal de Justiça do Pará'
    >>> fix_tribunal('Tribunal Justiça de Sergipe')
    'Tribunal de Justiça do Sergipe'
    >>> fix_tribunal('Tribunal Regional do Trabalho 12ª Região')
    'Tribunal Regional do Trabalho da 12ª Região'
    >>> fix_tribunal('Tribunal Regional do Trabalho 21a. Região')
    'Tribunal Regional do Trabalho da 21ª Região'
    >>> fix_tribunal('Tribunal Regional do Trabalho 24ª Região')
    'Tribunal Regional do Trabalho da 24ª Região'
    >>> fix_tribunal('Tribunal Regional do Trabalho da 17a Região')
    'Tribunal Regional do Trabalho da 17ª Região'
    >>> fix_tribunal('Tribunal Regional do Trabalho da 6A. Região')
    'Tribunal Regional do Trabalho da 6ª Região'
    >>> fix_tribunal('Tribunal Regional do Trabalho da Terceira Região')
    'Tribunal Regional do Trabalho da 3ª Região'
    >>> fix_tribunal('Tribunal Regional Eleitoral de Bahia')
    'Tribunal Regional Eleitoral da Bahia'
    >>> fix_tribunal('TRIBUNAL REGIONAL ELEITORAL DE GOIÁS - GO')
    'Tribunal Regional Eleitoral do Goiás'
    >>> fix_tribunal('Tribunal Regional Eleitoral de MS')
    'Tribunal Regional Eleitoral do Mato Grosso do Sul'
    >>> fix_tribunal('Tribunal Regional Eleitoral do DF')
    'Tribunal Regional Eleitoral do Distrito Federal e Territórios'
    >>> fix_tribunal('Tribunal Regional Federal 1º ')
    'Tribunal Regional Federal da 1ª Região'
    >>> fix_tribunal('TRIBUNAL REGIONAL FEDERAL - 2ª REGIÃO E SECCIONAIS')
    'Tribunal Regional Federal da 2ª Região'
    >>> fix_tribunal('TRIBUNAL REGIONAL FEDERAL - 2ª REGIÃO')
    'Tribunal Regional Federal da 2ª Região'
    >>> fix_tribunal('TRT 18ª REGIAO')
    'Tribunal Regional do Trabalho da 18ª Região'
    >>> fix_tribunal('Tribunal de Justiça Militar do Estado de Minas Gerais')
    'Tribunal de Justiça Militar de Minas Gerais'
    >>> fix_tribunal('Conselho da Justiça Federal')
    'Conselho da Justiça Federal'
    """

    if tribunal is None:
        return None

    tribunal = regexp_tribunal_ordinal.sub(
        "\\1ª ",
        regexp_tribunal_fim.sub("", tribunal).replace("/ ", "/").replace(" /", "/"),
    )
    result = []
    for word in tribunal.title().split():
        if word in ("Da", "Das", "De", "Do", "Dos", "E"):
            word = word.lower()
        elif word == "Trf":
            word = "Tribunal Regional Federal da"
        elif word == "Trt":
            word = "Tribunal Regional do Trabalho da"
        elif word == "Tre":
            word = "Tribunal Regional Eleitoral do"
        elif word == "Tre-Am":
            word = "Tribunal Regional Eleitoral do Amazonas"
        elif word == "Regiao":
            word = "Região"
        elif word == "Justica":
            word = "Justiça"
        elif word == "-":
            word = "da"
        elif word == "Df":
            word = "Distrito Federal e Territórios"
        elif word == "Terceira":
            word = "3ª"
        elif word.endswith("A."):
            word = regexp_ordinal.sub(r"da \1ª", word)
        elif word.endswith("ª"):
            word = "da " + word
        elif word == "Tjpa":
            word = "do Pará"
        elif word == "Ms":
            word = "Mato Grosso do Sul"
        elif word == "Rn":
            word = "Rio Grande do Norte"
        if "º" in word:
            word = word.replace("º", "ª")
        result.append(word)
    result = (
        " ".join(result)
        .replace("Mili Tar", "Militar")
        .replace("Regional Federal", "Regional Federal da")
        .replace(" e dos Territórios", " e Territórios")
        .replace(" e Seccionais", "")
        .replace(" da da ", " da ")
        .replace(" da da ", " da ")
        .replace(" da da ", " da ")
        .replace(" da do ", " do ")
        .replace(" do Estado de ", " do ")
        .replace(" do Estado do ", " do ")
        .replace(" Estado do ", " do ")
        .replace("Tribunal Justiça ", "Tribunal de Justiça ")
        .replace("do Pará do Pará", "do Pará")
        .replace("do Rondônia", "de Rondônia")
        .replace("do São Paulo", "de São Paulo")
        .replace("de Bahia", "da Bahia")
        .replace("de Goiás da Go", "do Goiás")
        .replace("de Mato Grosso", "do Mato Grosso")
        .replace("do Minas Gerais", "de Minas Gerais")
        .replace("de Sergipe", "do Sergipe")
    )
    if "Justiça Federal" in result and result != "Conselho da Justiça Federal":
        result = result.replace("Justiça Federal", "Tribunal Regional Federal")
    if result.endswith("ª"):
        result += " Região"
    return result


def is_court_name_equivalent(a, b):
    """
    >>> is_court_name_equivalent('Tribunal Regional do Trabalho da 7 Região', 'Tribunal Regional do Trabalho da 7ª Região')
    True
    >>> is_court_name_equivalent('Tribunal Regional do Trabalho da 7 Região', 'Tribunal Regional do Trabalho 7 Região')
    True
    >>> is_court_name_equivalent('Vantagens Eventuais', 'Direitos Eventuais')
    True
    >>> is_court_name_equivalent('TRT 1a Região', 'Tribunal Regional do Trabalho 1a Região')
    True
    """

    def replace_names(a):
        return (
            slug(fix_tribunal(a))
            .replace("vantagens_", "direitos_")
            .replace("trt_", "tribunal_regional_do_trabalho_")
            .replace("trf_", "tribunal_regional_federal_")
            .replace("justica_federal_", "tribunal_regional_federal_")
        )

    return Levenshtein.distance(replace_names(a), replace_names(b)) <= 3
