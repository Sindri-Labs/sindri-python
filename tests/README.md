# Tests for Sindri SDK

These tests assume the Sindri API is functioning normally and you have a valid `SINDRI_API_KEY`.

# Setup
1. In the parent directory of this repo, clone the [sindri-resources](https://github.com/Sindri-Labs/sindri-resources) repo: `git clone https://github.com/Sindri-Labs/sindri-resources.git`
1. Obtain a valid Sindri API Key. See [sindri.app/docs](sindri.app/docs) for more information about creating a Sindri account.
1. Configure your python environment (see below)
1. Configure your environment variables (see below)

### Setup Virtual Environment & Install Modules
Ensure you have a python3 environment set up with dependent modules for Sindri SDK and testing:
- `requests`
- `pytest`

```bash
# Create virtual environment called `venv`
python3 -m venv venv
# Activate virtual environment
source venv/bin/activate
# Install necessary modules
pip install poetry
poetry install
# Run `deactivate` to deactivate virtual environment
```

### Environment Variables
When running `pytest`, these environment variables must be set in your environment. You may prefix your command with the environment variables as well. For example: `SINDRI_API_KEY=your_api_key pytest`

- `SINDRI_API_KEY=your_api_key` *Required*
- `SINDRI_API_URL=https://sindri.app/api` *Optional. Default value shown*

### Run Pytest
You must be in the root directory of this repo: `cd ..`

Here are several options for running tests with environment variables:

Exporting ENVs:
```bash
export SINDRI_API_KEY=your_api_key
export SINDRI_API_URL=https://sindri.app/api
pytest
```

Prefixing ENVs:
```bash
SINDRI_API_KEY=your_api_key SINDRI_API_URL=https://sindri.app/api pytest
```
