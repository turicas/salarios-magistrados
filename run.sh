#!/bin/bash

set -e

rm -rf data/output
python salarios_magistrados.py
rows csv2sqlite data/output/links.csv.xz data/output/contracheque.csv.xz data/output/salarios-magistrados.sqlite
