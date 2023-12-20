#!/usr/bin/env bash
mkdir -p docs/docstrings

# pip install lazydocs
lazydocs \
    --output-path="./docs/docstrings" \
    --overview-file="README.md" \
    --src-base-url="https://github.com/Sindri-Labs/sindri-python/blob/main/" \
    src/sindri_labs

# Transform markdown to jsx syntax so it can be rendered in Docusaurus
python3 _transform_md_to_jsx.py