import os
import time

from src.sindri.sindri import Sindri


# Load sample data.
# This assumes the sindri-resources repo is cloned in the parent dir of this repo
dir_name = os.path.dirname(os.path.abspath(__file__))
sindri_resources_path = os.path.join(dir_name, "..", "..", "sindri-resources")
assert os.path.exists(sindri_resources_path)

circuit_dir = os.path.join(sindri_resources_path, "circuit_database", "noir", "not_equal")
proof_input_file_path = os.path.join(circuit_dir, "Prover.toml")
assert os.path.exists(circuit_dir)
assert os.path.exists(proof_input_file_path)
proof_input = ""
with open(proof_input_file_path, "r") as f:
    proof_input = f.read()


# Create an instance of the Sindri SDK
api_key = os.environ.get("SINDRI_API_KEY", "unset")
api_url = os.environ.get("SINDRI_API_URL", "https://sindri.app/api")
sindri = Sindri(api_key, api_url=api_url, verbose_level=2)


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

    def test_get_all_proofs(self):
        sindri.get_all_proofs()

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
        circuit_id = sindri.create_circuit(circuit_dir)
        proof_id = sindri.prove_circuit(circuit_id, proof_input)
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

        circuit_id = sindri.create_circuit(circuit_dir, wait=False)

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


        proof_id = sindri.prove_circuit(circuit_id, proof_input)

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