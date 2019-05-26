#!/bin/bash

set -e

rm -rf data/output
mkdir -p data/output data/download

time scrapy runspider --loglevel=INFO -o data/output/planilha.csv download_files.py
gzip data/output/planilha.csv
time python parse_files.py
