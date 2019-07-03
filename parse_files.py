#!/usr/bin/env python3
import logging
import os
import re
from collections import OrderedDict
from decimal import Decimal, DecimalException
from pathlib import Path

import openpyxl
import rows
import scrapy
import xlrd
from cached_property import cached_property
from rows.utils import load_schema, make_header, open_compressed, slug

import settings
import utils


# TODO: add option to pass custom logger to FileExtractor class
if not settings.LOG_PATH.exists():
    settings.LOG_PATH.mkdir()
logging.basicConfig(
    filename=settings.LOG_PATH / "parser.log", filemode="w", format="%(name)s - %(levelname)s - %(message)s"
)
regexp_date = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
regexp_numbers = re.compile(r"[0-9]")
regexp_parenthesis = re.compile("(\([^)]+\))")


class CustomDecimalField(rows.fields.DecimalField):
    @classmethod
    def deserialize(cls, value):
        if not value:
            return None
        elif isinstance(value, str):  # When string, they use "," as separator
            value = value.replace("???", "").replace(".", "").replace(",", ".")
        else:  # Integer or Float
            value = str(value)
        try:
            value = super().deserialize(value.strip())
        except ValueError:
            logging.warning(f"Error converting {repr(value)} to decimal.")
            return None
        else:
            return value


class CPFField(rows.fields.TextField):
    @classmethod
    def deserialize(cls, value):
        # Usually string, but can be integer too
        cpf = "".join(regexp_numbers.findall(str(value or ""))).strip()
        if set(cpf) in ({"0"}, {"9"}) or len(cpf) < 4:
            cpf = ""
        return cpf


def read_schema(filename):
    """Read schema and with custom fields"""

    fields = load_schema(
        str(filename),
        context={
            "cpf": CPFField,
            "text": rows.fields.TextField,
            "decimal": CustomDecimalField,
            "date": rows.fields.DateField,
            "integer": rows.fields.IntegerField,
        },
    )

    # Add "optional" parameter
    for row in rows.import_from_csv(filename):
        fields[row.field_name] = fields[row.field_name]()
        fields[row.field_name].optional = "optional" in (row.options or "")

    return fields


SHEET_INFO = OrderedDict(
    [
        (
            "Contracheque",
            {
                "schema": read_schema(settings.SCHEMA_PATH / "contracheque.csv"),
                "output_filename": settings.OUTPUT_PATH / "contracheque.csv.gz",
            },
        ),
        (
            "Subsídio - Direitos Pessoais",
            {
                "schema": read_schema(settings.SCHEMA_PATH / "direito-pessoal.csv"),
                "output_filename": settings.OUTPUT_PATH / "direito-pessoal.csv.gz",
            },
        ),
        (
            "Indenizações",
            {
                "schema": read_schema(settings.SCHEMA_PATH / "indenizacao.csv"),
                "output_filename": settings.OUTPUT_PATH / "indenizacao.csv.gz",
            },
        ),
        (
            "Direitos Eventuais",
            {
                "schema": read_schema(settings.SCHEMA_PATH / "direito-eventual.csv"),
                "output_filename": settings.OUTPUT_PATH / "direito-eventual.csv.gz",
            },
        ),
        (
            "Dados Cadastrais",
            {
                "schema": read_schema(settings.SCHEMA_PATH / "cadastro.csv"),
                "output_filename": settings.OUTPUT_PATH / "cadastro.csv.gz",
            },
        ),
    ]
)


def merge_header_lines(first, second):
    result = []
    for value1, value2 in zip(first, second):
        if value1 is None and value2 is None:
            result.append(None)
        elif value1 is None:
            result.append(value2)
        elif value2 is None:
            result.append(value1)
        else:
            result.append(f"{value1} {value2}")
    return result


def fix_header(sheet_name, header):
    name = sheet_name
    if "-" in name:
        name = name.split(" - ")[1]
    sheet_slug = slug(name)
    new_header = []
    for value in header:
        field_name = slug(regexp_parenthesis.sub("", value or "").strip())
        if (
            value is None
            or "deverao_ser_preenchidos" in field_name
            or "observacao" in field_name
            or field_name in ("sjsp", "trf", "sjms")
        ):
            break

        field_name = (
            field_name.replace("vant_art_", "vantagens_artigo_")
            .replace("vantagens_art_", "vantagens_artigo_")
            .replace("outra_1_dirpes", "outra")
            .replace("outra_2_dirpes", "outra_2")
            .replace("outra_1_direvent", "outra")
            .replace("outra_2_direvent", "outra_2")
            .replace("outra_1", "outra")
            .replace("gratificacao_presidencia", "gratificacao_de_presidencia")
            .replace("vantagens_eventuavs_", "vantagens_eventuais_")
            .replace("auxilioalimentacao", "auxilio_alimentacao")
            .replace("auxilio_preescolar", "auxilio_pre_escolar")
            .replace("correcao_monetariajuros", "correcao_monetaria_juros")
            .replace("vantagens_eventuais", "direitos_eventuais")
            .replace("vantagens_pessoais", "direitos_pessoais")
        )
        if field_name.startswith(sheet_slug):
            field_name = field_name[len(sheet_slug) :]
        elif field_name.startswith("vantagens_eventuais_"):
            field_name = field_name[len("vantagens_eventuais_") :]
        elif field_name in (
            "subsidio_total_de",
            "subsidio_outra",
            "subsidio_outra_detalhe",
        ):
            field_name = field_name.replace("subsidio_", "")
        field_name = slug(field_name)

        if field_name.endswith(sheet_slug):
            field_name = field_name[: -(len(sheet_slug))]
        elif field_name.endswith("_vantagens_pessoais"):
            field_name = field_name[: -(len("_vantagens_pessoais"))]
        field_name = slug(field_name)

        if field_name in ("total_de", "total_de_"):
            field_name = "total"
        elif field_name == "cargo_origem":
            field_name = "cargo_de_origem"
        elif field_name == "outra_detalhe":
            field_name = "detalhe"
        elif field_name == "outra_pae":
            field_name = "parcela_autonoma_de_equivalencia"
        elif field_name == "previdencia_publica":
            field_name = "descontos_previdencia_publica"
        elif field_name == "vantagens_artigo_184_e_192_lei_171152":
            field_name = "vantagens_artigo_184_i_e_192_i_lei_171152"
        elif field_name == "abono_constitucional_de_1_3_de_ferias":
            field_name = "abono_constitucional_de_13_de_ferias"
        elif field_name == "gratificacao_por_encargo_cursoconcurso":
            field_name = "gratificacao_por_encargo_curso_concurso"

        new_header.append(field_name)
    header = make_header(new_header)

    schema = SHEET_INFO[sheet_name]["schema"]
    reference_header = list(schema.keys())
    diff1 = set(reference_header) - set(header)
    diff2 = set(header) - set(reference_header)

    for field_name, field_type in schema.items():
        if field_name in diff1 and field_type.optional:
            diff1.remove(field_name)
    if diff1 or diff2:
        if len(diff1) > 1 or len(diff2) > 1 or len(diff1) != len(diff2):
            raise ValueError(
                f"Invalid header: {header} (expected: {reference_header}). A - B: {diff2}, B - A: {diff1}"
            )
        header[header.index(diff2.pop())] = diff1.pop()

    return header


def make_fields(sheet_name, header):
    reference_fields = SHEET_INFO[sheet_name]["schema"]
    fields = OrderedDict()
    for key in header:
        fields[key] = reference_fields[key]
    return fields


def make_row(fields, row_values):
    """Make a dict given a schema and values

    Note: if row_values is bigger than fields, will ignore last values.
    """

    row = {
        field_name: field_type.deserialize(row_values[index])
        for index, (field_name, field_type) in enumerate(fields.items())
    }
    return row


def is_filled(row):
    null_set = {"", Decimal("0"), None, "0", "***.***.***-**"}
    values = set([str(value or "").strip() for value in row.values()])
    values_are_filled = not values.issubset(null_set)
    has_name = (row["nome"] or "").strip() not in ("", "0")

    return values_are_filled and has_name


class FileExtractor:
    def read_data(self, *args, **kwargs):
        raise NotImplementedError()

    def __init__(self, filename, file_metadata=None):
        self.filename = Path(filename)
        self.file_metadata = file_metadata or {}

    @cached_property
    def relative_filename(self):
        return self.filename.relative_to(settings.BASE_PATH)

    @property
    def workbook(self):
        raise NotImplementedError()

    @property
    def sheet_names(self):
        raise NotImplementedError()

    def sheet(self, name):
        raise NotImplementedError()

    def define_sheet_name(self, name):
        """Fix a sheet name"""

        if name not in SHEET_INFO:
            raise ValueError(f"Invalid sheet name {repr(name)}.")

        if name in self.sheet_names:
            return name

        # Try slugging the names, compare and fix (if found)
        name_slug = slug(name)
        for sheet_name in self.sheet_names:
            if slug(sheet_name) == name_slug:
                logging.info(
                    f"Using {repr(sheet_name)} instead of {repr(name)} on {self.relative_filename}"
                )
                return sheet_name

        # First try didn't work
        try:
            new_name = self.sheet_names[list(SHEET_INFO.keys()).index(name)]
        except IndexError:
            logging.error(f"Sheet {repr(name)} not found on {self.relative_filename}")
            return None

        logging.warning(
            f"Using {repr(new_name)} instead of {repr(name)} on {self.relative_filename}"
        )
        return new_name

    def sheet_rows(self, name):
        raise NotImplementedError()

    def metadata(self, sheet_name):
        header, start_row = [], None
        for index, row in enumerate(self.sheet_rows(sheet_name)):
            if "CPF" in row or "Nome" in row:  # First header line
                header.append(row)
            elif len(header) == 1:
                if (
                    row[0] in (None, "")
                    and set(type(value) for value in row).issubset({type(None), str})
                    and any(
                        "total" in (value or "").lower()
                        or "outra" in (value or "").lower()
                        for value in row
                    )
                ):
                    # Second header line
                    header.append(row)
                    start_row = index + 1
                else:
                    # Data starts in this row
                    start_row = index
                break
        if len(header) > 1:
            header = merge_header_lines(*header)
        else:
            header = header[0]

        return {
            "fields": make_fields(sheet_name, fix_header(sheet_name, header)),
            "start_row": start_row,
        }

    @cached_property
    def general_metadata(self):
        """Get court, reference and publication month from Contracheque sheet"""

        # First, build the dict
        meta = {}
        for index, row in enumerate(self.sheet_rows("Contracheque")):
            if "CPF" in row or "Nome" in row:
                end_row = index - 1
                break
        sheet_name = self.define_sheet_name("Contracheque")
        table = self.read_data(sheet_name=sheet_name, end_row=end_row)
        for row in table:
            values = list(row._asdict().values())
            if "-" not in (values[0] or ""):
                non_empty_values = []
                for value in values:
                    if value and value not in non_empty_values:
                        non_empty_values.append(value)
                if non_empty_values and len(non_empty_values) >= 2:
                    meta[slug(non_empty_values[0])] = non_empty_values[1]

        # Check, convert and rename if needed

        # Court name
        court_from_metadata = self.file_metadata["tribunal"]
        court = meta.pop("orgao", "")
        if (
            court.lower() != court_from_metadata.lower()
            and court.lower() not in court_from_metadata.lower()
        ):
            logging.warning(
                f"orgao from metadata ({repr(court or None)}) different from file metadata ({repr(self.file_metadata['tribunal'])}) on {self.relative_filename}"
            )
        # Using same court named from download page to maintain consistency
        # (court names from there are more correct in general and will make
        # joins between tables easily).
        meta["tribunal"] = utils.fix_tribunal(court_from_metadata or court)

        # Reference month
        reference_month = str(meta.pop("mesano_de_referencia", None) or "")
        reference_from_metadata = (
            f"{self.file_metadata['ano']}-{self.file_metadata['mes']:02d}-01"
        )
        if not reference_month:
            meta["mes_ano_de_referencia"] = reference_from_metadata
        elif regexp_date.match(reference_month):
            parts = reference_month.split("-")
            meta["mes_ano_de_referencia"] = f"{parts[0]}-{parts[1]}-01"
        elif " de " in reference_month.lower():
            month, year = reference_month.lower().split(" de ")
            if len(year) == 2:
                year = f"20{year}"
            month = utils.MONTHS.index(slug(month)) + 1
            meta["mes_ano_de_referencia"] = f"{year}-{month:02d}-01"
        elif "/" in reference_month:
            month, year = reference_month.split("/")
            if len(year) == 2:
                year = f"20{year}"
            meta["mes_ano_de_referencia"] = f"{year}-{int(month):02d}-01"
        else:
            logging.error(
                f"Can't parse mes_ano_de_referencia ({repr(reference_month)}) in {self.relative_filename}"
            )
            meta["mes_ano_de_referencia"] = reference_from_metadata
        if meta["mes_ano_de_referencia"] != reference_from_metadata:
            logging.warning(
                "mes_ano_de_referencia ({repr(reference_month)}) different from file metadata ({repr(reference_from_metadata)})"
            )

        # Publication date
        publication_date = meta.get("data_de_publicacao", None)
        if isinstance(publication_date, str):
            if not regexp_date.match(publication_date):
                if publication_date.count("/") == 2:
                    day, month, year = publication_date.split("/")
                    if len(year) == 2:
                        year = f"20{year}"
                    meta[
                        "data_de_publicacao"
                    ] = f"{year}-{int(month):02d}-{int(day):02d}"
                else:
                    logging.error(
                        f"Can't parse data_de_publicacao ({repr(publication_date)}) from {self.relative_filename}"
                    )
            else:
                meta["data_de_publicacao"] = publication_date.split()[0]
        else:
            if publication_date is not None:
                logging.error(
                    f"Can't parse data_de_publicacao ({repr(publication_date)}) and it's not None from {self.relative_filename}"
                )
            meta["data_de_publicacao"] = None
        if "T" in str(meta["data_de_publicacao"] or ""):
            # Got as datetime
            meta["data_de_publicacao"] = meta["data_de_publicacao"].split("T")[0]
        elif str(meta["data_de_publicacao"] or "").isdigit():
            # Filled incorrectly
            meta["data_de_publicacao"] = None

        for key in list(meta.keys()):
            if key not in ("data_de_publicacao", "tribunal", "mes_ano_de_referencia"):
                del meta[key]
                logging.warning(
                    f"Ignoring invalid general_metadata key {repr(key)} from {self.relative_filename}"
                )

        return meta

    def data(self, sheet_name):
        final_sheet_name = self.define_sheet_name(sheet_name)
        if final_sheet_name is None:
            return
        meta = self.metadata(sheet_name)
        start_row = meta.pop("start_row")
        fields = meta.pop("fields")
        table = self.read_data(
            sheet_name=final_sheet_name,
            start_row=start_row,
            end_column=len(fields) - 1,
            fields=fields,
        )
        for row in table:
            row = row._asdict()
            if is_filled(row):
                # TODO: if value is a discount, check if it's < 0 (convert if
                # needed)
                yield row

    def extract(self, sheet_name):
        # Generate base dict with all needed keys
        base_row = {key: None for key in SHEET_INFO[sheet_name]["schema"].keys()}
        metadata = self.general_metadata.copy()
        metadata["ano_de_referencia"] = self.file_metadata["ano"]
        metadata["mes_de_referencia"] = self.file_metadata["mes"]
        base_row.update(metadata)

        for row in self.data(sheet_name):
            new_row = base_row.copy()
            for key, value in row.items():
                new_row[key] = value.strip() if isinstance(value, str) else value
            yield new_row


class XLSFileExtractor(FileExtractor):
    def read_data(self, *args, **kwargs):
        if kwargs["sheet_name"] is None:
            return []
        else:
            kwargs["skip_header"] = False

            if "end_column" not in kwargs:
                # Avoid reading all columns (even if blank)
                kwargs["end_column"] = 50

        return rows.import_from_xls(self.filename, *args, **kwargs)

    @cached_property
    def workbook(self):
        try:
            wb = xlrd.open_workbook(self.filename, logfile=open(os.devnull, mode="w"))
        except xlrd.XLRDError as exp:
            logging.error(
                f"Cannot load workbook ({repr(exp.args[0])}) on {self.relative_filename}"
            )
            return None
        else:
            return wb

    @cached_property
    def sheet_names(self):
        return self.workbook.sheet_names()

    def sheet(self, name):
        """Get the desired sheet, fixing the name if needed"""
        return self.workbook.sheet_by_name(self.define_sheet_name(name))

    def sheet_rows(self, name):
        sheet = self.sheet(name)
        for row_index, row in enumerate(sheet.get_rows()):
            yield [
                rows.plugins.xls.cell_value(sheet, row_index, col_index)
                for col_index, cell in enumerate(row)
            ]


class XLSXFileExtractor(FileExtractor):
    def read_data(self, *args, **kwargs):
        if kwargs["sheet_name"] is None:
            return []
        else:
            kwargs["skip_header"] = False

            if "end_column" not in kwargs:
                # Avoid reading all columns (even if blank)
                kwargs["end_column"] = 50

        return rows.import_from_xlsx(
            self.filename, workbook_kwargs={"data_only": True}, *args, **kwargs
        )

    @cached_property
    def workbook(self):
        return openpyxl.load_workbook(self.filename, data_only=True, read_only=True)

    @cached_property
    def sheet_names(self):
        return self.workbook.sheetnames

    def sheet(self, name):
        """Get the desired sheet, fixing the name if needed"""

        return self.workbook[self.define_sheet_name(name)]

    def sheet_rows(self, name):
        for row in self.sheet(name).rows:
            yield [rows.plugins.xlsx._cell_to_python(cell) for cell in row]


if __name__ == "__main__":
    import argparse
    import csv

    import rows
    from tqdm import tqdm

    import settings

    parser = argparse.ArgumentParser()
    parser.add_argument("--start_at")
    args = parser.parse_args()

    extractors = {"xls": XLSFileExtractor, "xlsx": XLSXFileExtractor}
    file_list = open_compressed(settings.OUTPUT_PATH / "planilha.csv.gz", mode="rb")
    fobjs, writers = [], {}
    for sheet_name, info in SHEET_INFO.items():
        fobj = open_compressed(info["output_filename"], mode="w", encoding="utf-8")
        field_names = list(SHEET_INFO[sheet_name]["schema"].keys()) + [
            "tribunal",
            "mes_de_referencia",
            "mes_ano_de_referencia",
            "ano_de_referencia",
            "data_de_publicacao",
        ]
        writers[sheet_name] = csv.DictWriter(fobj, fieldnames=field_names)
        writers[sheet_name].writeheader()
        fobjs.append(fobj)

    started = False if args.start_at is not None else True
    for row in tqdm(rows.import_from_csv(file_list)):
        filename = settings.BASE_PATH / Path(row.arquivo)
        if args.start_at == str(filename.relative_to(settings.BASE_PATH)):
            started = True
        if not started:
            continue
        if not filename.exists():
            logging.warning(f"File not found: {row.arquivo}")
            continue

        extension = filename.name.split(".")[-1].lower()
        metadata = {"ano": row.ano, "mes": row.mes, "tribunal": row.tribunal}
        extractor = extractors[extension](filename, metadata)
        if extractor.workbook is None:
            continue
        for sheet_name in SHEET_INFO.keys():
            writer = writers[sheet_name]
            try:
                data = list(extractor.extract(sheet_name))
            except ValueError:
                import traceback

                message = traceback.format_exc().strip().splitlines()[-1]
                logging.error(
                    f"Exception when parsing sheet {repr(sheet_name)} from {extractor.relative_filename}: {message}"
                )
            else:
                writer.writerows(data)

    for fobj in fobjs:
        fobj.close()
