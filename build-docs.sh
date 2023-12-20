#!/usr/bin/env bash
mkdir -p docs/docstrings

# pip install requests>=2.13.0 lazydocs
lazydocs \
    --output-path="docs/docstrings" \
    --overview-file="README.md" \
    --src-base-url="https://github.com/Sindri-Labs/sindri-python/blob/main/" \
    --no-watermark \
    src/sindri_labs