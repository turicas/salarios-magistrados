import re

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
        result.append(word)
    result = (
        " ".join(result)
        .replace("Mili Tar", "Militar")
        .replace(" e dos Territórios", " e Territórios")
    )
    return result
