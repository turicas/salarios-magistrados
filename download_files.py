import datetime
import io
from collections import OrderedDict
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import rows
import scrapy
from rows.utils import slug

import settings
import utils


class SalariosMagistradosSpider(scrapy.Spider):

    month_url = "http://www.cnj.jus.br/transparencia/remuneracao-dos-magistrados/remuneracao-{month_slug}-{year}"
    name = "salarios-magistrados"
    start_urls = ["http://www.cnj.jus.br/transparencia/remuneracao-dos-magistrados"]

    def make_month_request(self, year, month, force_url=None):
        if force_url is None:
            url = self.month_url.format(month_slug=slug(utils.MONTHS[month - 1]), year=year)
        else:
            url = force_url

        return scrapy.Request(
            url=url, meta={"year": year, "month": month}, callback=self.parse_month
        )

    def parse(self, response):
        # Get the last updated month
        now = datetime.datetime.now()
        update_message = " ".join(
            response.xpath(
                "//*[contains(text(), 'tribunais e conselhos de')]//text()"
            ).extract()
        )
        last_month = (
            update_message.split("enviaram os dados de")[1]
            .split(",")[0]
            .strip()
            .lower()
        )
        last_year, last_month = now.year, utils.MONTHS.index(last_month) + 1

        # Starting making requests from 2017-11 to last month found (except the
        # last one)
        for year in range(2017, now.year + 1):
            for month in range(1, 12 + 1):
                if year == 2017 and month < 11:
                    continue
                elif year == last_year and month >= last_month:
                    break
                yield self.make_month_request(year, month)

        # Make another request for the last month found (the URL in this case
        # is not in the pattern `self.month_url`)
        yield self.make_month_request(
            last_year, last_month, force_url=self.start_urls[0]
        )

    def parse_month(self, response):
        meta = response.request.meta
        month_meta = {"year": meta["year"], "month": meta["month"]}

        rows_xpath = (
            "//a[contains(@href, 'xls') and not(contains(text(), 'documento'))]"
        )
        fields_xpath = OrderedDict(
            [("name", ".//text()"), ("download_url", ".//@href")]
        )
        table = rows.import_from_xpath(
            io.BytesIO(response.body),
            rows_xpath=rows_xpath,
            encoding=response.encoding,
            fields_xpath=fields_xpath,
        )
        for row in table:
            url = urljoin(self.start_urls[0], unquote(row.download_url)).strip()

            # Fix URLs
            url = url.replace("http:/w", "http://w")
            if " " in url:
                # Case: "http://www.cnj.jus.br/TREMS%20http:/www.cnj.jus.br/files/conteudo/arquivo/2019/04/b91f9672dfe8abfb9cd3fbc6e8a5510e.xls"
                for part in url.split():
                    if ".xls" in part:
                        url = part
                        break

            # Some links have errors (more than one URL inside), so a list of
            # URLs for the same court is generated so we can check later the
            # correct one.
            if url.count("http://") > 1:
                urls = []
                for part in url.split("http:"):
                    if not part:
                        continue
                    urls.append("http:" + part)
            else:
                urls = [url]

            for url in urls:
                filename = settings.DOWNLOAD_PATH / Path(urlparse(url).path).name
                court_meta = month_meta.copy()
                court_meta.update(
                    {
                        "downloaded_at": datetime.datetime.now(),
                        "filename": filename.relative_to(settings.BASE_PATH),
                        "name": row.name.replace("\xa0", " "),
                        "url": url,
                    }
                )
                yield scrapy.Request(
                    url=court_meta["url"],
                    meta={"row": court_meta},
                    callback=self.save_file,
                )
                # Yield the row so we can check later when links are incorrect
                # (repeated, 404 etc.)
                yield court_meta

    def save_file(self, response):
        filename = Path(response.request.meta["row"]["filename"])
        if not filename.parent.exists():
            filename.parent.mkdir(parents=True)
        with open(filename, mode="wb") as fobj:
            fobj.write(response.body)
