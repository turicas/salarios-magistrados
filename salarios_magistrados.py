import calendar
import csv
import datetime
import io
import lzma
import pathlib
import re
from collections import OrderedDict
from decimal import Decimal
from multiprocessing import Pool
from urllib.parse import urljoin, urlparse, unquote

import openpyxl
import requests
import rows
import xlrd


class MyDecimalField(rows.fields.DecimalField):

    @classmethod
    def deserialize(cls, value):
        if value is None:
            return None
        return super().deserialize(str(value).replace('???', '').strip())


FIELDS = OrderedDict()
field_names = ('cpf, nome, cargo, lotacao, subsidio, direitos_pessoais, '
                'indenizacoes, direitos_eventuais, total_de_rendimentos, '
                'previdencia_publica, imposto_de_renda, '
                'descontos_diversos, retencao_por_teto_constitucional, '
                'total_de_descontos, rendimento_liquido, '
                'remuneracao_do_orgao_de_origem, diarias').split(', ')
for field_name in field_names:
    if field_name in ('cpf', 'nome', 'cargo', 'lotacao'):
        field_type = rows.fields.TextField
    else:
        field_type = MyDecimalField
    FIELDS[field_name] = field_type
regexp_date = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
regexp_numbers = re.compile(r'[0-9]')

MONTHS = {
     1: 'janeiro',
     2: 'fevereiro',
     3: 'marco',
     4: 'abril',
     5: 'maio',
     6: 'junho',
     7: 'julho',
     8: 'agosto',
     9: 'setembro',
    10: 'outubro',
    11: 'novembro',
    12: 'dezembro',
}
MONTHS2 = {value: key for key, value in MONTHS.items()}


def month_range(start_year, start_month, end_year, end_month):
    current = datetime.date(start_year, start_month, 1)
    end = datetime.date(end_year, end_month, 1)

    if current <= end:
        while current <= end:
            yield current
            current += datetime.timedelta(
                days=calendar.monthrange(current.year, current.month)[1]
            )
    else:
        one_day = datetime.timedelta(days=1)
        while current >= end:
            yield current
            yesterday = current - one_day
            current = datetime.date(yesterday.year, yesterday.month, 1)


def get_links(year, month, date_scraped):

    # Download HTML and get all the links (text + url)
    month = MONTHS[month]
    url = f'http://www.cnj.jus.br/transparencia/remuneracao-dos-magistrados/remuneracao-{month}-{year}'
    response = requests.get(url)
    if not response.ok:
        raise RuntimeError('Data not found')

    rows_xpath = '//a'
    fields_xpath = OrderedDict([
        ('name', './/text()'),
        ('url', './@href')
    ])
    table = rows.import_from_xpath(
        io.BytesIO(response.content),
        encoding=response.encoding,
        rows_xpath=rows_xpath,
        fields_xpath=fields_xpath
    )

    # Filter out links which don't point to spreadsheets
    result = []
    for row in table:
        if not (row.name or '').strip() or row.name == 'documento padrão' or \
                '.xls' not in row.url:
            continue

        data = {
            'date_scraped': date_scraped,
            'month': MONTHS2[month],
            'name': row.name.replace('\xa0', ' '),
            'url': unquote(urljoin(url, row.url)).strip(),
            'year': year,
        }
        result.append(data)
    return rows.import_from_dicts(result)


def download(url, save_path):
    response = requests.get(url)
    if response.status_code >= 400:
        raise RuntimeError(f'ERROR downloading {url}')

    with open(save_path, mode='wb') as fobj:
        fobj.write(response.content)


def extract_metadata(filename):
    meta = {}
    slug = rows.plugins.utils.slug

    if filename.name.endswith('.xls'):
        cell_value = rows.plugins.xls.cell_value
        book = xlrd.open_workbook(filename)
        sheet = book.sheet_by_name('Contracheque')
        for row in (15, 16, 17):
            key = slug(cell_value(sheet, row, 0))
            value = cell_value(sheet, row, 3)
            if value is None:
                value = cell_value(sheet, row, 1)
            meta[key] = value

        # Detect first line of data
        found_header = False
        for row in range(18, 25):
            value = cell_value(sheet, row, 1)
            if found_header and value is not None:
                meta['start_row'] = row
                break
            if value and value.upper() == 'NOME':
                found_header = True

    elif filename.name.endswith('.xlsx'):
        book = openpyxl.load_workbook(filename, data_only=True)
        sheet = book['Contracheque']
        cell_value = rows.plugins.xlsx._cell_to_python
        data = [('A16', 'D16'), ('A17', 'D17'), ('A18', 'D18')]
        for key, value in data:
            key = slug(cell_value(sheet[key]))
            value = cell_value(sheet[value])
            if isinstance(value, datetime.datetime):
                value = str(datetime.date(value.year, value.month, value.day))
            meta[key] = value

        # Detect first line of data
        found_header = False
        for row in range(19, 25):
            value = cell_value(sheet[f'A{row}'])
            if found_header and value is not None:
                meta['start_row'] = row + 1
                break
            if value in ('Nome', 'CPF'):
                found_header = True

    publicacao = meta['data_de_publicacao']
    if isinstance(publicacao, str):
        if not regexp_date.match(publicacao):
            if publicacao.count('/') == 2:
                dia, mes, ano = publicacao.split('/')
                if len(ano) == 2:
                    ano = f'20{ano}'
                meta['data_de_publicacao'] = \
                    f'{ano}-{int(mes):02d}-{int(dia):02d}'
            else:
                assert False, \
                    f'data_de_publicacao ({repr(meta["data_de_publicacao"])})'
    else:
        meta['data_de_publicacao'] = None

    #mes_ano = meta['mesano_de_referencia']
    #if isinstance(mes_ano, str):
    #    if not regexp_date.match(mes_ano):
    #        if ' de ' in mes_ano.lower():
    #            mes, ano = mes_ano.lower().split(' de ')
    #            if len(ano) == 2:
    #                ano = f'20{ano}'
    #            mes = MONTHS2[mes]
    #            meta['mesano_de_referencia'] = f'{ano}-{int(mes):02d}-01'
    #        elif '/' in mes_ano:
    #            mes, ano = mes_ano.split('/')
    #            if len(ano) == 2:
    #                ano = f'20{ano}'
    #            meta['mesano_de_referencia'] = f'{ano}-{int(mes):02d}-01'
    #        else:
    #            assert False, f'mesano_de_referencia ({repr(mes_ano)})'
    #else:
    #    meta['mesano_de_referencia'] = None

    return meta


def convert_row(row_data, metadata):
    data = metadata.copy()
    data.update(row_data)
    for key, value in data.items():
        if isinstance(value, Decimal):
            data[key] = round(value, 2)
        elif isinstance(value, str):
            data[key] = value.strip()

    #if data['mesano_de_referencia'] is not None:
    #    if len(data['mesano_de_referencia']) == 7:  # as in '01/2018'
    #        parts = data['mesano_de_referencia'].split('/')
    #        data['mesano_de_referencia'] = f'{parts[1]}-{parts[0]}-01'
    #    else:
    #        parts = data['mesano_de_referencia'].split('-')
    #        data['mesano_de_referencia'] = f'{parts[0]}-{parts[1]}-01'

    cpf = ''.join(regexp_numbers.findall(data['cpf']))
    if set(cpf) in ({'0'}, {'9'}):
        cpf = ''
    data['cpf'] = cpf

    return data


def extract(year, month, name, url, filename):
    if filename.name.endswith('.xls'):
        import_function = rows.import_from_xls
    elif filename.name.endswith('.xlsx'):
        import_function = rows.import_from_xlsx
    else:
        raise ValueError('Cannot parse this spreadsheet')

    metadata = extract_metadata(filename)
    metadata['url'] = url
    metadata['tribunal'] = name
    metadata['mesano_de_referencia'] = f'{year}-{month}-01'
    start_row = metadata.pop('start_row')

    result = []
    table = import_function(
        str(filename),
        start_row=start_row,
        fields=FIELDS,
        skip_header=False,
    )
    for row in table:
        row_data = row._asdict()
        if is_filled(row_data):
            result.append(convert_row(row_data, metadata))

    # TODO: check rows with rendimento_liquido = 0
    return result


def is_filled(data):
    null_set = {'', Decimal('0'), None, '0', '***.***.***-**'}
    values = set([str(value or '').strip() for value in data.values()])
    values_are_filled = not values.issubset(null_set)
    has_name = (data['nome'] or '').strip() not in ('', '0')

    return values_are_filled and has_name


def download_and_extract(year, month, name, url, download_path):
    # Download file
    filename = download_path / urlparse(url).path.split('/')[-1]
    if not filename.exists():
        try:
            download(url, filename)
        except RuntimeError as exception:
            print(f' ERROR downloading {url} - {exception.args[0]}')
            return []

    # Extract data
    try:
        data = extract(year, month, name, url, filename)
    except Exception as exp:
        import traceback
        print(f' ERROR extracting {filename} - {traceback.format_exc().splitlines()[-1]}')
        return []
    else:
        return data


def main():
    now = datetime.datetime.now()
    today = datetime.date(now.year, now.month, now.day)
    data_path = pathlib.Path('data')
    download_path = data_path / 'download'
    output_path = data_path / 'output'
    for path in [data_path, download_path, output_path]:
        if not path.exists():
            path.mkdir()

    output_links = output_path / f'links.csv.xz'
    output_contracheque = output_path / f'contracheque.csv.xz'
    fobj_links = io.TextIOWrapper(lzma.open(output_links, mode='w'), encoding='utf-8')
    fobj_contracheque = io.TextIOWrapper(lzma.open(output_contracheque, mode='w'), encoding='utf-8')
    header_links = 'name url date_scraped year month'.split()
    header = field_names + \
            'url tribunal orgao data_de_publicacao mesano_de_referencia'.split()
    writer_links = csv.DictWriter(fobj_links, fieldnames=header_links)
    writer_links.writeheader()
    writer_contracheque = csv.DictWriter(fobj_contracheque, fieldnames=header)
    writer_contracheque.writeheader()
    start_month, start_year = 11, 2017
    end_month, end_year = today.month, today.year
    for date in month_range(end_year, end_month, start_year, start_month):
        year, month = date.year, date.month
        print(f'[{year}-{month:02d}] ', end='', flush=True)
        try:
            links = get_links(year, month, date_scraped=today)
        except RuntimeError:  # Month not found
            print('not found')
            continue

        for link in links:
            writer_links.writerow(link._asdict())
        print('working...', end='', flush=True)
        with Pool() as pool:
            results = pool.starmap(
                download_and_extract,
                [(year, month, link.name, link.url, download_path) for link in links]
            )
            for table in results:
                for row in table:
                    writer_contracheque.writerow(row)
        print(' done!')


if __name__ == '__main__':
    main()
