#!/usr/bin/env python3
import csv
import datetime
import io
import pathlib
from collections import OrderedDict
from decimal import Decimal
from urllib.parse import urljoin, urlparse

import openpyxl
import requests
import rows
import xlrd
import concurrent.futures



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
        if row.name is None or row.name == 'documento padrão' or \
                '.xls' not in row.url:
            continue

        data = {
            'name': row.name.replace('\xa0', ' '),
            'url': urljoin(url, row.url),
            'date_scraped': date,
        }
        result.append(data)
    return rows.import_from_dicts(result)


def download(download_info):
    url, save_path = download_info
    print(f'Downloading {url}...', end='', flush=True)
    response = requests.get(url)

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

    elif filename.name.endswith('.xlsx'):
        book = openpyxl.load_workbook(filename)
        sheet = book.get_sheet_by_name('Contracheque')
        cell_value = rows.plugins.xlsx._cell_to_python
        data = [('A16', 'D16'), ('A17', 'D17'), ('A18', 'D18')]
        for key, value in data:
            key = slug(cell_value(sheet[key]))
            value = cell_value(sheet[value])
            if isinstance(value, datetime.datetime):
                value = str(datetime.date(value.year, value.month, value.day))
            meta[key] = value

    return meta


def extract(filename):
    print(f'Extracting {filename.name}...', end='', flush=True)
    try:
        # TODO: check header position
        if filename.name.endswith('.xls'):
            import_function = rows.import_from_xls
        elif filename.name.endswith('.xlsx'):
            import_function = rows.import_from_xlsx
        else:
            raise ValueError('Cannot parse this spreadsheet')

        metadata = extract_metadata(filename)

        result = []
        with rows.locale_context('pt_BR.UTF-8'):
            table = import_function(
                str(filename),
                start_row=21,
                fields=FIELDS,
                skip_header=False,
            )
            for row in table:
                row_data = row._asdict()
                if is_filled(row_data):
                    # Created this way so first columns will be metadata
                    data = metadata.copy()
                    data.update(row_data)
                    for key, value in data.items():
                        if isinstance(value, Decimal):
                            data[key] = round(value, 2)
                    result.append(data)

        # TODO: check rows with rendimento_liquido = 0
        result.sort(key=lambda row: (row['orgao'],
                                     - (row['rendimento_liquido'] or 0)))
    except Exception as exp:
            import traceback
            print(f' ERROR! {traceback.format_exc().splitlines()[-1]}')
    else:
        print(' done.')
        return result


def export_csv(data, filename, encoding='utf8'):
    with open(filename, mode='w', encoding=encoding) as fobj:
        writer = csv.DictWriter(fobj, fieldnames=data[0].keys())
        writer.writeheader()
        for row in data:
            writer.writerow(row)

def is_filled(data):
    null_set = {'', Decimal('0'), None, '0', '***.***.***-**'}
    values = set(data.values())

    return not values.issubset(null_set)


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

    # Download all the links, with multiple connections
    filenames = []
    download_list = []
    for link in links:
        save_path = download_path / urlparse(link.url).path.split('/')[-1]
        filenames.append(save_path)
        if not save_path.exists():
            print(f'Set to download {link.url}...', end='', flush=True)
            download_list.append((link.url, save_path))
        else:
            print(f'Skipping {save_path.name}...')

    with concurrent.futures.ProcessPoolExecutor() as executor:
        for item in zip(download_list, executor.map(download, download_list)):
            print(' done.')

    result = []
    # Extract data from all the spreadsheets, with threads
    with concurrent.futures.ProcessPoolExecutor() as executor:
        for filename, data in zip(filenames, executor.map(extract, filenames)):
            if data:
                result.extend(data)

    # Extract everything to a new CSV
    output = output_path / f'salarios-magistrados-{today}.csv'
    print(f'Extracting result to {output}...')
    export_csv(result, output)


if __name__ == '__main__':
    main()
