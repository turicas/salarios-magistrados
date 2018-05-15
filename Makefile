NAME = thenets/opendata-salarios-magistrados
TAG = latest
SHELL = /bin/bash

build: pre-build docker-build post-build

pre-build:

post-build:

docker-build:
	docker build -t $(NAME):$(TAG) --rm .

shell:
	docker run -it --rm --entrypoint=$(SHELL) $(NAME):$(TAG)

build-shell: build shell

build-test: build test

test:
	docker run -it --rm $(NAME):$(TAG)

build-run: build run

run:
	mkdir -p $(PWD)/output
	docker run -it -v $(PWD)/output:/app/output --rm $(NAME):$(TAG)