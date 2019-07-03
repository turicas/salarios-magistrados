import re

import Levenshtein
from rows.fields import slug


MONTHS = "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split()
regexp_tribunal_fim = re.compile(" *\([^)]*\)*$")
regexp_tribunal_ordinal = re.compile("([0-9])a ")


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
        result.append(word)
    result = (
        " ".join(result)
        .replace("Mili Tar", "Militar")
        .replace(" e dos Territórios", " e Territórios")
        .replace(" da da ", " da ")
        .replace(" da do ", " do ")
        .replace(" do Estado de ", " do ")
        .replace(" do Estado do ", " do ")
    )
    return result


def is_sheet_name_equivalent(a, b):
    """
    >>> is_sheet_name_equivalent('Tribunal Regional do Trabalho da 7 Região', 'Tribunal Regional do Trabalho da 7ª Região')
    True
    >>> is_sheet_name_equivalent('Tribunal Regional do Trabalho da 7 Região', 'Tribunal Regional do Trabalho 7 Região')
    True
    >>> is_sheet_name_equivalent('Vantagens Eventuais', 'Direitos Eventuais')
    True
    >>> is_sheet_name_equivalent('TRT 1a Região', 'Tribunal Regional do Trabalho 1a Região')
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
