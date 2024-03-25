import io
import json
import os
import pathlib
import platform
import tarfile
import time
from pprint import pformat

import requests

from . import __version__


class Sindri:
    """# Sindri API SDK

    A utility class for interacting with the [Sindri API](https://www.sindri.app).

    ### Dependencies

    - `requests`: (`pip install requests`)

    ### Usage Example

    ```python
    circuit_upload_path = "circom/multiplier2"
    proof_input = ""
    proof_input_file_path = "circom/multiplier2/input.json"
    with open(proof_input_file_path, "r") as f:
        proof_input = f.read()

    # Run Sindri API
    API_KEY = <YOUR_API_KEY>
    sindri = Sindri(API_KEY)
    circuit_id = sindri.create_circuit(circuit_upload_path)
    proof_id = sindri.prove_circuit(circuit_id, proof_input)
    ```

    """

    class APIError(Exception):
        """Custom Exception for Sindri API Errors"""

        pass

    DEFAULT_SINDRI_API_URL = "https://sindri.app/api/"
    API_VERSION = "v1"

    def __init__(
        self,
        api_key: str,
        api_url: str = DEFAULT_SINDRI_API_URL,
        verbose_level: int = 0,
    ):
        """
        Parameters

        - `api_key: str`: Sindri API Key
        - `api_url: str`: Sindri API Url
        - `verbose_level: int`: Stdout print level. Options=`[0,1,2]`
        """
        # Obtain version from module
        self.version = __version__

        self.headers_json: dict = {}  # set in set_api_key()

        # Do not print anything during initial setup
        self.set_verbose_level(0)

        self.polling_interval_sec: int = 1  # polling interval for circuit compilation & proving
        self.max_polling_iterations: int = 172800  # 2 days with polling interval 1 second
        self.perform_verify: bool = False
        self.set_api_url(api_url)
        self.set_api_key(api_key)

        # Set desired verbose level
        self.set_verbose_level(verbose_level)
        if self.verbose_level > 0:
            self._print_sindri_logo()
            print(f"Sindri API Url: {self.api_url}")
            print(f"Sindri API Key: {self.api_key}\n")

    def _get_circuit(self, circuit_id: str, include_verification_key: bool = False) -> dict:
        """Hit the circuit_detail API endpoint and validate the response. Do not print anything.
        This may raise `Sindri.APIError` if the response is invalid."""
        response_status_code, response_json = self._hit_api(
            "GET",
            f"circuit/{circuit_id}/detail",
            data={"include_verification_key": include_verification_key},
        )
        if response_status_code != 200:
            raise Sindri.APIError(
                f"Unable to fetch circuit_id={circuit_id}."
                f" status={response_status_code} response={response_json}"
            )
        if not isinstance(response_json, dict):
            raise Sindri.APIError("Received unexpected type for circuit detail response.")
        return response_json

    def _get_proof(
        self,
        proof_id: str,
        include_proof: bool = False,
        include_public: bool = False,
        include_smart_contract_calldata: bool = False,
        include_verification_key: bool = False,
    ) -> dict:
        """Hit the proof_detail API endpoint and validate the response. Do not print anything.
        This may raise `Sindri.APIError` if the response is invalid."""
        response_status_code, response_json = self._hit_api(
            "GET",
            f"proof/{proof_id}/detail",
            data={
                "include_proof": include_proof,
                "include_public": include_public,
                "include_smart_contract_calldata": include_smart_contract_calldata,
                "include_verification_key": include_verification_key,
            },
        )
        if response_status_code != 200:
            raise Sindri.APIError(
                f"Unable to fetch proof_id={proof_id}."
                f" status={response_status_code} response={response_json}"
            )
        if not isinstance(response_json, dict):
            raise Sindri.APIError("Received unexpected type for proof detail response.")
        return response_json

    def _get_verbose_1_circuit_detail(self, circuit_detail: dict) -> dict:
        """Return a slim circuit detail object for printing."""
        return {
            "circuit_id": circuit_detail.get("circuit_id", None),
            "circuit_name": circuit_detail.get("circuit_name", None),
            "circuit_type": circuit_detail.get("circuit_type", None),
            "compute_time": circuit_detail.get("compute_time", None),
            "date_created": circuit_detail.get("date_created", None),
            "status": circuit_detail.get("status", None),
        }

    def _get_verbose_1_proof_detail(self, proof_detail: dict) -> dict:
        """Return a slim proof detail object for printing."""
        return {
            "circuit_id": proof_detail.get("circuit_id", None),
            "circuit_name": proof_detail.get("circuit_name", None),
            "circuit_type": proof_detail.get("circuit_type", None),
            "compute_time": proof_detail.get("compute_time", None),
            "date_created": proof_detail.get("date_created", None),
            "proof_id": proof_detail.get("proof_id", None),
            "status": proof_detail.get("status", None),
        }

    def _hit_api(self, method: str, path: str, data=None, files=None) -> tuple[int, dict | list]:
        """
        Hit the Sindri API.

        Returns
        - int:  response status code
        - dict: response json

        Raises an Exception if

        - response is None
        - cannot connect to the API
        - response cannot be JSON decoded
        - invalid API Key
        """

        # Initialize data if not provided
        if data is None:
            data = {}

        # Construct the full path to the API endpoint.
        full_path = os.path.join(self.api_url, path)
        try:
            if method == "POST":
                response = requests.post(
                    full_path, headers=self.headers_json, data=data, files=files
                )
            elif method == "GET":
                response = requests.get(full_path, headers=self.headers_json, params=data)
            elif method == "DELETE":
                response = requests.delete(full_path, headers=self.headers_json, data=data)
            else:
                raise Sindri.APIError("Invalid request method")
        except requests.exceptions.ConnectionError:
            # Raise a clean exception and suppress the original exception's traceback.
            raise Sindri.APIError(
                f"Unable to connect to the Sindri API. path={full_path}"
            ) from None

        if response is None:
            raise Sindri.APIError(
                f"No response received. method={method}, path={full_path},"
                f" data={data} headers={self.headers_json}, files={files}"
            )
        if response.status_code == 401:
            raise Sindri.APIError(f"401 - Invalid API Key. path={full_path}")
        elif response.status_code == 404:
            raise Sindri.APIError(f"404 - Not found. path={full_path}")
        else:
            # Decode JSON response
            try:
                response_json = response.json()
            except json.decoder.JSONDecodeError:
                raise Sindri.APIError(
                    f"Unexpected Error. Unable to decode response as JSON."
                    f" status={response.status_code} response={response.text}"
                ) from None
        return response.status_code, response_json

    def _print_sindri_logo(self):
        # https://ascii-generator.site/ 32 columns
        print(
            f"""Sindri API Python SDK - {self.version}
     .+******************+.     
     =********************=     
 .:.  -==================-      
=****                           
=****-                          
 .::-*+==================-      
     =********************=     
     .+******************+.     
                           =**+:
                          :*****
    .:::::::::::::::::::::++==- 
  .***********************+     
  .***********************-"""
        )

    def _set_json_request_headers(self) -> None:
        """Set JSON request headers (set `self.headers_json`). Use `self.api_key` for `Bearer`.
        Additionally set the `Sindri-Client` header.
        """
        self.headers_json = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Sindri-Client": f"sindri-py-sdk/{self.version} ({platform.platform()}) python_version:{platform.python_version()}",  # noqa: E501
        }

    def create_circuit(
        self, circuit_upload_path: str, tags: list[str] | None = None, wait: bool = True
    ) -> str:
        """Create a circuit.

        Args:
            `circuit_upload_path`: The path to a directory containing your circuit files or
                the path to a compressed file (`.tar.gz` or `.zip`) of your circuit directory.
                If it is a directory, it will automatically be tarred before sending.
            `tags`: A list of tags to assign the circuit. Defaults to `[]"latest"]` if not
                sepecified.
            `wait`: If `True`, block until the circuit is finished compiling. If `False`, this
                will submit the circuit and return immediately.

        Returns:
            `circuit_id`: The unique idetifier for your circuit. This is generated by Sindri.

        Raises:
            `Sindri.APIError`: If your API Key is invalid, there is an error connecting to the
                Sindri API, there is an error with your circuit upload, or the
                circuit has a compilation error (if `wait=True`).
        """

        # Return value
        circuit_id = ""  # set later

        # 1. Create a circuit, obtain a circuit_id.
        if self.verbose_level > 0:
            print("Circuit: Create")
        if self.verbose_level > 1:
            print(f"    upload_path:   {circuit_upload_path}")

        # Ensure circuit_upload_path exists
        if not os.path.exists(circuit_upload_path):
            raise Sindri.APIError(f"circuit_upload_path does not exist: {circuit_upload_path}")
        # Prepare files for upload
        if os.path.isfile(circuit_upload_path):
            # Assume the path is already a tarfile
            files = {"files": open(circuit_upload_path, "rb")}
        elif os.path.isdir(circuit_upload_path):
            # Create a tar archive and upload via byte stream
            circuit_upload_path = os.path.abspath(circuit_upload_path)
            file_name = f"{pathlib.Path(circuit_upload_path).stem}.tar.gz"
            fh = io.BytesIO()
            with tarfile.open(fileobj=fh, mode="w:gz") as tar:
                tar.add(circuit_upload_path, arcname=file_name)
            files = {"files": fh.getvalue()}  # type: ignore

        # Hit circuit/create API endpoint
        response_status_code, response_json = self._hit_api(
            "POST",
            "circuit/create",
            data={"tags": tags},
            files=files,
        )
        if response_status_code != 201:
            raise Sindri.APIError(
                f"Unable to create a new circuit."
                f" status={response_status_code} response={response_json}"
            )
        if not isinstance(response_json, dict):
            raise Sindri.APIError("Received unexpected type for circuit detail response.")
        # Obtain circuit_id from response
        circuit_id = response_json.get("circuit_id", "")
        if self.verbose_level > 0:
            print(f"    circuit_id:   {circuit_id}")

        if wait:
            # 2. Poll circuit detail until it has a status of Ready/Failed
            if self.verbose_level > 0:
                print("Circuit: Poll until Ready/Failed")
            for _ in range(self.max_polling_iterations):
                circuit = self._get_circuit(circuit_id, include_verification_key=False)
                circuit_status = circuit.get("status", "")
                if circuit_status == "Failed":
                    raise Sindri.APIError(
                        f"Circuit compilation failed." f" error={circuit.get('error', '')}"
                    )
                if circuit_status == "Ready":
                    break
                time.sleep(self.polling_interval_sec)
            else:
                raise Sindri.APIError("Circuit compile polling timed out.")

        if self.verbose_level > 0:
            self.get_circuit(circuit_id, include_verification_key=True)

        # Circuit compilation success!
        return circuit_id

    def delete_circuit(self, circuit_id: str) -> None:
        """
        Delete a circuit by hitting the `/circuit/<circuit_id>/delete` endpoint.
        This also deletes all of the circuit's proofs.

        Returns `None` if the deletion was successful. Else, raise `Sindri.APIError`.
        """
        response_status_code, response_json = self._hit_api(
            "DELETE", f"circuit/{circuit_id}/delete"
        )
        if response_status_code != 200:
            raise Sindri.APIError(
                f"Unable to delete circuit_id={circuit_id}."
                f" status={response_status_code} response={response_json}"
            )

    def delete_proof(self, proof_id: str) -> None:
        """
        Delete a proof by hitting the `/proof/<proof_id>/delete` endpoint.

        Returns `None` if the deletion was successful. Else, raise `Sindri.APIError`.
        """
        response_status_code, response_json = self._hit_api("DELETE", f"proof/{proof_id}/delete")
        if response_status_code != 200:
            raise Sindri.APIError(
                f"Unable to delete proof_id={proof_id}."
                f" status={response_status_code} response={response_json}"
            )

    def get_all_circuit_proofs(self, circuit_id: str) -> list[dict]:
        """Get all proofs for `circuit_id`."""
        if self.verbose_level > 0:
            print(f"Proof: Get all proofs for circuit_id: {circuit_id}")
        response_status_code, response_json = self._hit_api(
            "GET",
            f"circuit/{circuit_id}/proofs",
        )
        if response_status_code != 200:
            raise Sindri.APIError(
                f"Unable to fetch proofs for circuit_id={circuit_id}."
                f" status={response_status_code} response={response_json}"
            )
        if not isinstance(response_json, list):
            raise Sindri.APIError("Received unexpected type for proof list response.")

        if self.verbose_level > 0:
            proof_detail_list = response_json.copy()
            if self.verbose_level == 1:
                proof_detail_list = []
                for proof_detail in response_json:
                    proof_detail_list.append(self._get_verbose_1_proof_detail(proof_detail))
            print(f"{pformat(proof_detail_list, indent=4)}\n")

        return response_json

    def get_all_circuits(self) -> list[dict]:
        """Get all circuits."""
        if self.verbose_level > 0:
            print("Circuit: Get all circuits")
        response_status_code, response_json = self._hit_api(
            "GET",
            "circuit/list",
        )
        if response_status_code != 200:
            raise Sindri.APIError(
                f"Unable to fetch circuits."
                f" status={response_status_code} response={response_json}"
            )
        if not isinstance(response_json, list):
            raise Sindri.APIError("Received unexpected type for circuit list response.")

        if self.verbose_level > 0:
            circuit_detail_list = response_json.copy()
            if self.verbose_level == 1:
                circuit_detail_list = []
                for circuit_detail in response_json:
                    circuit_detail_list.append(self._get_verbose_1_circuit_detail(circuit_detail))
            print(f"{pformat(circuit_detail_list, indent=4)}\n")

        return response_json

    def get_circuit(self, circuit_id: str, include_verification_key: bool = True) -> dict:
        """Get circuit for `circuit_id`."""
        if self.verbose_level > 0:
            print(f"Circuit: Get circuit detail for circuit_id: {circuit_id}")
        circuit = self._get_circuit(circuit_id, include_verification_key=include_verification_key)
        if self.verbose_level > 0:
            circuit_detail = circuit.copy()
            if self.verbose_level == 1:
                circuit_detail = self._get_verbose_1_circuit_detail(circuit_detail)
            print(f"{pformat(circuit_detail, indent=4)}\n")
        return circuit

    def get_smart_contract_verifier(self, circuit_id: str) -> str:
        """Get the circuit's smart contract verifier code for `circuit_id`.

        Returns:

        - `str`: the smart contract verifier code

        Raises `Sindri.APIError` if:

        - the circuit's circuit type does not support smart contract verifier generation
        """
        if self.verbose_level > 0:
            print(f"Circuit: Get circuit smart contract verifier for circuit_id: {circuit_id}")
        response_status_code, response_json = self._hit_api(
            "GET", f"circuit/{circuit_id}/smart_contract_verifier"
        )
        if response_status_code != 200:
            raise Sindri.APIError(
                f"Unable to fetch smart contract verifier code for circuit_id={circuit_id}."
                f" status={response_status_code} response={response_json}"
            )
        # Extract smart_contract_verifier_code from response and check types
        if not isinstance(response_json, dict):
            raise Sindri.APIError(
                "Received unexpected type for circuit smart contract verifier response."
            )
        try:
            smart_contract_verifier_code: str = response_json["contract_code"]
        except KeyError:
            raise Sindri.APIError(
                "Received unexpected type for circuit smart contract verifier response."
            )
        if not isinstance(smart_contract_verifier_code, str):
            raise Sindri.APIError(
                "Received unexpected type for circuit smart contract verifier response."
            )

        if self.verbose_level == 2:
            print(smart_contract_verifier_code)

        return smart_contract_verifier_code

    def get_proof(
        self,
        proof_id: str,
        include_proof: bool = True,
        include_public: bool = True,
        include_smart_contract_calldata: bool = False,
        include_verification_key: bool = False,
    ) -> dict:
        """
        Get proof for `proof_id`.

        Parameters:

        - `include_smart_contract_calldata: bool` specifies if the proof + public formated as
        calldata for the circuit's smart contract verifier should also be returned.

        Raises `Sindri.APIError` if:

        - `include_smart_contract_calldata=True` and the proof's circuit type does not support
        generating calldata for its circuit's smart contract verifier
        """
        if self.verbose_level > 0:
            print(f"Proof: Get proof detail for proof_id: {proof_id}")
        proof = self._get_proof(
            proof_id,
            include_proof=include_proof,
            include_public=include_public,
            include_smart_contract_calldata=include_smart_contract_calldata,
            include_verification_key=include_verification_key,
        )
        if self.verbose_level > 0:
            proof_detail = proof.copy()
            if self.verbose_level == 1:
                proof_detail = self._get_verbose_1_proof_detail(proof_detail)
            print(f"{pformat(proof_detail, indent=4)}\n")
        return proof

    def get_user_team_details(self) -> dict:
        """Get details about the user or team associated with the provided API Key."""
        if self.verbose_level > 0:
            print("User/Team: Get user/team details for the provided API Key.")
        response_status_code, response_json = self._hit_api("GET", "team/me")
        if response_status_code != 200:
            raise Sindri.APIError(
                f"Unable to fetch team details."
                f" status={response_status_code} response={response_json}"
            )
        if not isinstance(response_json, dict):
            raise Sindri.APIError("Received unexpected type for team detail response.")

        if self.verbose_level > 0:
            print(f"{pformat(response_json, indent=4)}\n")

        return response_json

    def prove_circuit(
        self,
        circuit_id: str,
        proof_input: str,
        prover_implementation: str | None = None,
        perform_verify: bool = False,
        wait: bool = True,
    ) -> str:
        """
        Prove a circuit given a `circuit_id` and a `proof_input` and, if `wait=True`, poll the
        detail endpoint until the proof has a `status` of `Ready` or `Failed`.

        Return
        - str: proof_id

        Raises `Sindri.APIError` if

        - Invalid API Key
        - Unable to connect to the API
        - Circuit does not exist
        - If `wait=True`, circuit does not have a `status` of `Ready`

        NOTE: `prover_implementation` is currently only supported for Sindri internal usage.
        The default value, `None`, chooses the best supported prover implementation based on a
        variety of factors including the available hardware, proving scheme, circuit size, and
        framework.
        """

        # Return values
        proof_id = ""

        # 1. Submit a proof, obtain a proof_id.
        if self.verbose_level > 0:
            print("Prove circuit")
        # Hit the circuit/<circuit_id>/prove endpoint
        response_status_code, response_json = self._hit_api(
            "POST",
            f"circuit/{circuit_id}/prove",
            data={
                "proof_input": proof_input,
                "perform_verify": perform_verify,
                "prover_implementation": prover_implementation,
            },
        )
        if response_status_code != 201:
            raise Sindri.APIError(
                f"Unable to prove circuit."
                f" status={response_status_code} response={response_json}"
            )
        if not isinstance(response_json, dict):
            raise Sindri.APIError("Received unexpected type for proof detail response.")
        # Obtain proof_id from response
        proof_id = response_json.get("proof_id", "")
        if self.verbose_level > 0:
            print(f"    proof_id:     {proof_id}")

        if wait:
            # 2. Poll proof detail until it has a status of Ready/Failed
            if self.verbose_level > 0:
                print("Proof: Poll until Ready/Failed")
            for _ in range(self.max_polling_iterations):
                proof = self._get_proof(
                    proof_id,
                    include_proof=False,
                    include_public=False,
                    include_smart_contract_calldata=False,
                    include_verification_key=False,
                )
                proof_status = proof.get("status", "")
                if proof_status == "Failed":
                    raise Sindri.APIError(f"Prove circuit failed. error={proof.get('error', '')}")
                if proof_status == "Ready":
                    break
                time.sleep(self.polling_interval_sec)
            else:
                raise Sindri.APIError("Prove circuit polling timed out.")

        if self.verbose_level > 0:
            self.get_proof(proof_id)

        # Prove circuit success!
        return proof_id

    def set_api_key(self, api_key: str) -> None:
        """Set the API Key and headers for the Sindri instance."""
        if not isinstance(api_key, str):
            raise Sindri.APIError("Invalid API Key")
        if api_key == "":
            raise Sindri.APIError("Invalid API Key")
        self.api_key = api_key
        self._set_json_request_headers()
        if self.verbose_level > 0:
            print(f"Sindri API Key: {self.api_key}")

    def set_api_url(self, api_url: str) -> None:
        """
        Set the API Url for the Sindri instance.

        NOTE: `v1/` is appended to the Sindri API Url if it is not present.
        - Example: `https://sindri.app/api/` becomes `https://sindri.app/api/v1/`
        """
        if not isinstance(api_url, str):
            raise Sindri.APIError("Invalid API Url")
        if api_url == "":
            raise Sindri.APIError("Invalid API Url")
        if not api_url.endswith(self.API_VERSION) or not api_url.endswith(f"{self.API_VERSION}/"):
            # Append f"{self.API_VERSION}/" to api_url
            self.api_url = os.path.join(api_url, f"{self.API_VERSION}/")
        if self.verbose_level > 0:
            print(f"Sindri API Url: {self.api_url}")

    def set_verbose_level(self, level: int) -> None:
        """
        Set the verbosity level for stdout printing.

        Parameters:

        - `level: int` must be in `[0,1,2]`

        Levels:

        - `0`: Do not print anything to stdout
        - `1`: Print only necesessary information from Circuit/Proof objects
        - `2`: Print everything

        Raises `Sindri.APIError` if

        - `level` is invalid.
        """
        error_msg = "Invalid verbose_level. Must be an int in [0,1,2]."
        if not isinstance(level, int):
            raise Sindri.APIError(error_msg)
        elif level not in [0, 1, 2]:
            raise Sindri.APIError(error_msg)
        self.verbose_level = level
