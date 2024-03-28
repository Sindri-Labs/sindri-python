import os
import time

import pytest

from src.sindri.sindri import Sindri

# Load sample data.
# This assumes the sindri-resources repo is cloned in the parent dir of this repo
dir_name = os.path.dirname(os.path.abspath(__file__))
sindri_resources_path = os.path.join(dir_name, "..", "..", "sindri-resources")
assert os.path.exists(sindri_resources_path)

# This Noir circuit sample data is the fastest circuit for general compile+prove testing
noir_circuit_dir = os.path.join(sindri_resources_path, "circuit_database", "noir", "not_equal")
noir_proof_input_file_path = os.path.join(noir_circuit_dir, "Prover.toml")
assert os.path.exists(noir_circuit_dir)
assert os.path.exists(noir_proof_input_file_path)
noir_proof_input = ""
with open(noir_proof_input_file_path, "r") as f:
    noir_proof_input = f.read()

# This Circom circuit is slightly slower to compile+prove, but it supports smart contract verifier
# code generation and returning the proof formatted as calldata for that smart contract
circom_circuit_dir = os.path.join(
    sindri_resources_path, "circuit_database", "circom", "multiplier2"
)
circom_proof_input_file_path = os.path.join(circom_circuit_dir, "input.json")
assert os.path.exists(circom_circuit_dir)
assert os.path.exists(circom_proof_input_file_path)
circom_proof_input = ""
with open(circom_proof_input_file_path, "r") as f:
    circom_proof_input = f.read()


# Create an instance of the Sindri SDK
api_key = os.environ.get("SINDRI_API_KEY", "unset")
base_url = os.environ.get("SINDRI_BASE_URL", "https://sindri.app")
sindri = Sindri(api_key, base_url=base_url, verbose_level=2)


class TestSindriSdk:
    """Test Sindri SDK methods.

    All methods may raise Sindri.APIError.
    - If this error is raised, the pytest will fail as well.
    - Tests that do not assert anything are still successful if they pass because the Sindri SDK
    method did not raise an error.

    NOTE: These current unit test not perfectly designed. Unit tests should mock calls to and
    responses from the API. Until these unit tests are properly written, we use strategies such as
    the one in `test_circuit_create_prove_other()` to test the functionality of the Sindri SDK
    methods.
    """

    def test_user_team_details(self):
        sindri.get_user_team_details()

    def test_get_all_circuits(self):
        sindri.get_all_circuits()

    def test_circuit_create_prove_other(self):
        """
        Most SDK methods require a circuit and a proof to be created.
        This test combines several tests so we only have to create 1 circuit and 1 proof.
        The order of these steps is carefully designed so all data is available in Sindri
        when necessary.
        1. Test create a circuit
        1. Test prove the circuit.
        1. Test list circuit proofs
        1. Test circuit detail
        1. Test proof detail
        1. Test delete proof
        1. Test delete circuit
        """
        circuit_id = sindri.create_circuit(noir_circuit_dir)
        proof_id = sindri.prove_circuit(circuit_id, noir_proof_input)
        sindri.get_all_circuit_proofs(circuit_id)
        sindri.get_circuit(circuit_id)
        sindri.get_proof(proof_id)
        sindri.delete_proof(proof_id)
        sindri.delete_circuit(circuit_id)

    def test_circuit_create_prove_no_wait(self):
        """
        This test is similar to `test_circuit_create_prove_other()`, but it supplies
        `wait=False` to `sindri.create_circuit()` and `sindri.prove_circuit()` to ensure
        that those methods do not poll for the result. Manually poll instead.
        """
        polling_interval_sec = 1.0
        max_polling_intervals = 120

        circuit_id = sindri.create_circuit(noir_circuit_dir, wait=False)

        # manually poll circuit detail until status is ready/failed
        status = ""
        for _ in range(0, max_polling_intervals):
            time.sleep(polling_interval_sec)
            status = sindri.get_circuit(circuit_id).get("status", "")
            if status in ["Ready", "Failed"]:
                break
        else:
            raise RuntimeError("Max polling reached")
        assert status == "Ready"

        proof_id = sindri.prove_circuit(circuit_id, noir_proof_input)

        # manually poll proof detail until status is ready/failed
        status = ""
        for _ in range(0, max_polling_intervals):
            time.sleep(polling_interval_sec)
            status = sindri.get_proof(proof_id).get("status", "")
            if status in ["Ready", "Failed"]:
                break
        else:
            raise RuntimeError("Max polling reached")
        assert status == "Ready"

        sindri.delete_proof(proof_id)
        sindri.delete_circuit(circuit_id)

    def test_circuit_create_prove_smart_contract_calldata(self):
        """
        Most SDK methods require a circuit and a proof to be created.
        This test combines several tests so we only have to create 1 circuit and 1 proof.
        The order of these steps is carefully designed so all data is available in Sindri
        when necessary.
        1. Test create a circuit
        1. Test prove the circuit.
        1. Test fetching the circuit's smart contract verifier code
        1. Test proof detail with including the proof calldata
        1. Test delete proof
        1. Test delete circuit
        """
        circuit_id = sindri.create_circuit(circom_circuit_dir)
        proof_id = sindri.prove_circuit(circuit_id, circom_proof_input)
        sindri.get_smart_contract_verifier(circuit_id)
        sindri.get_proof(proof_id, include_smart_contract_calldata=True)
        sindri.delete_circuit(circuit_id)


class TestInitSindriSdkWithUrl:
    def test_api_url(self):
        """Test valid and invalid api_url."""
        expected_resulting_api_url = "https://sindri.app/api/v1/"

        # No trailing slash
        url = "https://sindri.app/api"
        s = Sindri("a", api_url=url)
        assert s._api_url == expected_resulting_api_url

        # Trailing slash
        url = "https://sindri.app/api/"
        s = Sindri("a", api_url=url)
        assert s._api_url == expected_resulting_api_url

        # Multiple trailing slashes
        url = "https://sindri.app/api//"
        s = Sindri("a", api_url=url)
        assert s._api_url == expected_resulting_api_url

        # Missing trailing /api path
        url = "https://sindri.app"
        with pytest.raises(Sindri.APIError):
            s = Sindri("a", api_url=url)

        # Invalid trailing /api path
        url = "https://sindri.app/api/apiiii"
        with pytest.raises(Sindri.APIError):
            s = Sindri("a", api_url=url)

    def test_base_url(self):
        """Test valid and invalid base_url."""
        expected_resulting_api_url = "https://sindri.app/api/v1/"

        # No trailing slash
        url = "https://sindri.app"
        s = Sindri("a", base_url=url)
        assert s._api_url == expected_resulting_api_url

        # Trailing slash
        url = "https://sindri.app/"
        s = Sindri("a", base_url=url)
        assert s._api_url == expected_resulting_api_url

        # Multiple trailing slashes
        url = "https://sindri.app//"
        s = Sindri("a", base_url=url)
        assert s._api_url == expected_resulting_api_url

        # Includes /api trailing path
        url = "https://sindri.app/api"
        with pytest.raises(Sindri.APIError):
            s = Sindri("a", base_url=url)

        # Invalid any trailing path
        url = "https://sindri.app/apiiii"
        with pytest.raises(Sindri.APIError):
            s = Sindri("a", base_url=url)

    def test_api_url_and_base_url(self):
        """Test valid and invalid api_url + base_url."""

        # Valid api_url and valid base_url should return base_url
        expected_resulting_api_url = "https://base-url.sindri.app/api/v1/"
        api_url = "https://api-url.sindri.app/api"
        base_url = "https://base-url.sindri.app"
        s = Sindri("a", api_url=api_url, base_url=base_url)
        assert s._api_url == expected_resulting_api_url

        # Invalid api_url and valid base_url should return base_url.
        # api_url is ignored because base_url is prioritized
        api_url = "https://api-url.sindri.app/apiiiiii"
        base_url = "https://base-url.sindri.app"
        s = Sindri("a", api_url=api_url, base_url=base_url)
        assert s._api_url == expected_resulting_api_url

        # Valid api_url and invalid base_url should raise exception
        # base_url is prioritized
        api_url = "https://api-url.sindri.app/apiiiiii"
        base_url = "https://base-url.sindri.app/aaaaaaaa"
        with pytest.raises(Sindri.APIError):
            s = Sindri("a", api_url=api_url, base_url=base_url)

        # Invalid api_url and invalid base_url should raise exception
        api_url = "https://api-url.sindri.app/apiiiiii"
        base_url = "https://base-url.sindri.app/aaaaaaaa"
        with pytest.raises(Sindri.APIError):
            s = Sindri("a", api_url=api_url, base_url=base_url)

    def test_default_url(self):
        """Test default url is used when api_url and base_url are not specified."""
        s = Sindri("a")
        assert s.DEFAULT_SINDRI_API_URL == s._api_url

    def test_not_a_url(self):
        """Test api_url base_url are not urls."""
        with pytest.raises(Sindri.APIError):
            _ = Sindri("a", api_url="not_a_url")

        with pytest.raises(Sindri.APIError):
            _ = Sindri("a", base_url="not_a_url")
