# Sindri Python SDK

## Build Status

![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/sindri-labs/sindri-python/ci.yml?style=for-the-badge)

## Description
The Sindri Python SDK.
Contains SDK code for Sindri APIs. Please see [Sindri.app](https://sindri.app) for more details.

This SDK is an alpha (testing) release and may change at any time.

## Usage

### Prove An Existing Circuit
```
from sindri_labs.sindri import Sindri
sindri = Sindri('api_key')
with open('./anonklub-circom/input.json', 'r') as file:
    sindri.prove_circuit('7c2c5e9d-235b-40ef-9c6a-694e6a2dc034', file.read())
```

## License
[![](https://img.shields.io/github/license/sindri-labs/sindri-python?style=for-the-badge)](https://img.shields.io/github/license/sindri-labs/sindri-python?style=for-the-badge)

sindri-python is licensed under a [MIT License](LICENSE) and is copyright [Sindri Labs, LLC](https://sindri.app).
