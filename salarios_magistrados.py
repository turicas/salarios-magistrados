#!/usr/bin/env python3
import csv
import datetime
import io
import pathlib
from collections import OrderedDict
from decimal import Decimal
from urllib.parse import urljoin, urlparse, unquote

import openpyxl
import requests
import rows
import xlrd


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
        field_type = rows.fields.DecimalField
    FIELDS[field_name] = field_type


def get_links(date):

    # Download HTML and get all the links (text + url)
    url = 'http://www.cnj.jus.br/transparencia/remuneracao-dos-magistrados'
    response = requests.get(url)
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
            'name': row.name.replace('\xa0', ' '),
            'url': unquote(urljoin(url, row.url)).strip(),
            'date_scraped': date,
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
            if value == 'Nome':
                found_header = True
            elif found_header and value is not None:
                meta['start_row'] = row + 1
                break

    elif filename.name.endswith('.xlsx'):
        book = openpyxl.load_workbook(filename, data_only=True)
        sheet = book.get_sheet_by_name('Contracheque')
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
            if value in ('Nome', 'CPF'):
                found_header = True
            elif found_header and value is not None:
                meta['start_row'] = row + 1
                break

    return meta


def convert_row(row_data, metadata):
    data = metadata.copy()
    data.update(row_data)
    for key, value in data.items():
        if isinstance(value, Decimal):
            data[key] = round(value, 2)

    if len(data['mesano_de_referencia']) == 7:  # as in `01/2018`
        parts = data['mesano_de_referencia'].split('/')
        data['mesano_de_referencia'] = f'{parts[1]}-{parts[0]}-01'

    return data


def extract(filename, link):
    if filename.name.endswith('.xls'):
        import_function = rows.import_from_xls
    elif filename.name.endswith('.xlsx'):
        import_function = rows.import_from_xlsx
    else:
        raise ValueError('Cannot parse this spreadsheet')

    metadata = extract_metadata(filename)
    metadata['url'] = link.url
    metadata['tribunal'] = link.name
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
    result.sort(key=lambda row: (row['orgao'],
                                 - (row['rendimento_liquido'] or 0)))
    return result


def export_csv(data, filename, encoding='utf8'):
    with open(filename, mode='w', encoding=encoding) as fobj:
        writer = csv.DictWriter(fobj, fieldnames=sorted(data[0].keys()))
        writer.writeheader()
        for row in data:
            writer.writerow(row)

def is_filled(data):
    null_set = {'', Decimal('0'), None, '0', '***.***.***-**'}
    values = set(data.values())
    values_are_filled = not values.issubset(null_set)
    has_name = (data['nome'] or '').strip() != ''

    return values_are_filled and has_name


def main():
    now = datetime.datetime.now()
    today = datetime.date(now.year, now.month, now.day)
    download_path = pathlib.Path('download')
    output_path = pathlib.Path('output')
    if not download_path.exists():
        download_path.mkdir()
    if not output_path.exists():
        output_path.mkdir()

    # Get spreadsheet links
    links = get_links(date=today)
    rows.export_to_csv(links, output_path / f'links-{today}.csv')

    # Download all the links
    result = []
    for link in links:
        print(link.name)

        filename = download_path / urlparse(link.url).path.split('/')[-1]

        # Download file
        print(f'  Downloading ({link.url})...', end='', flush=True)
        if filename.exists():
            print(f' already downloaded.')
        else:
            try:
                download(link.url, filename)
            except RuntimeError as exception:
                print(f' {exception.args[0]}')
                continue
            else:
                print(' done.')

        # Extract data
        print(f'  Extracting ({filename})...', end='', flush=True)
        try:
            data = extract(filename, link)
        except Exception as exp:
            import traceback
            print(f' ERROR! {traceback.format_exc().splitlines()[-1]}')
        else:
            print(f' done (rows extracted: {len(data)}).')
            result.extend(data)

    # Extract everything to a new CSV
    output = output_path / f'salarios-magistrados-{today}.csv'
    print(f'Extracting result to {output}...')
    export_csv(result, output)


if __name__ == '__main__':
    main()
