#!/usr/bin/env bash
mkdir -p docs/docstrings


lazydocs \
    --output-path="./docs/docstrings" \
    --overview-file="README.md" \
    --src-base-url="https://github.com/Sindri-Labs/sindri-python/blob/main/" \
    src/sindri_labs

mkdocs build
