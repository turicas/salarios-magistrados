#!/bin/bash

set -e
rm -rf data/output

time scrapy runspider --loglevel=INFO -o data/output/planilha.csv download_files.py
gzip data/output/planilha.csv
time python parse_files.py
