"""
## Usage

```python
# Download some sample data
# git clone https://github.com/Sindri-Labs/sindri-resources.git

# pip install sindri
from sindri import Sindri

# Initialize
sindri = Sindri("<YOUR_API_KEY>", verbose_level=2)

# Upload a Circuit
circuit_upload_path: str = "sindri-resources/circuit_database/circom/multiplier2"
circuit_id: str = sindri.create_circuit(circuit_upload_path)

# Generate a Proof
proof_input_file_path = "sindri-resources/circuit_database/circom/multiplier2/input.json"
with open(proof_input_file_path, "r") as f:
    proof_id: str = sindri.prove_circuit(circuit_id, f.read())
```
"""

import io
import json
import os
import pathlib
import platform
import tarfile
import time
from pprint import pformat
from typing import List, Tuple, Union
from urllib.parse import urlparse

import requests  # type: ignore
from requests.adapters import HTTPAdapter, Retry

__version__ = "v0.0.0"


class Sindri:
    """A utility class for interacting with the [Sindri API](https://www.sindri.app)."""

    class APIError(Exception):
        """Custom Exception for Sindri API Errors"""

        pass

    DEFAULT_SINDRI_API_URL = "https://sindri.app/api/v1/"

    VERBOSE_LEVELS = [0, 1, 2]

    def __init__(self, api_key: str, verbose_level: int = 0, **kwargs):
        """Initialize an instance of the Sindri SDK.

        Args:
        - `api_key`: Your Sindri API Key.
        - `verbose_level`: Must be either `0`, `1`, or `2`.
            - `0`: Do not print anything to stdout.
            - `1`: Print only necesessary information from Circuit/Proof objects.
            - `2`: Print everything.

        Returns:
        - `sindri`: An instance of the class configured with your Sindri API Key.

        Raises:
        - `Sindri.APIError`:
            - Your API Key is improperly formatted.
        """
        # Obtain version from module
        self.version = __version__

        self.headers_json: dict = {}  # set in set_api_key()

        # Do not print anything during initial setup.
        self.set_verbose_level(0)

        self.polling_interval_sec: int = 1  # polling interval for circuit compilation & proving
        self.max_polling_iterations: int = 172800  # 2 days with polling interval 1 second

        self._api_url = self._get_api_url(**kwargs)
        self.set_api_key(api_key)

        # With initial setup complete, set desired verbose level.
        self.set_verbose_level(verbose_level)
        if self.verbose_level > 0:
            self._print_sindri_logo()
            print(f"Sindri API Url: {self._api_url}")
            print(f"Sindri API Key: {self.api_key}\n")

    def _get_api_url(self, **kwargs) -> str:
        """Examine `**kwargs` for `base_url` and `api_url`, in that order.
        If `base_url` is found and valid, return that. If not valid, raise an error.
        If `base_url` is not found then check for `api_url`.
        If `api_url` is found and valid, return that. If not valid, raise an error.
        If neither keyword is found in `**kwargs`, return the default API URL.
        """

        def is_url(url: str) -> bool:
            """Validate a provided str is a url."""
            try:
                result = urlparse(url)
                return all([result.scheme, result.netloc])
            except ValueError:
                return False

        # Order of precedence for obtaining the API URL:
        # 1. `base_url` is in kwargs
        url = kwargs.get("base_url", None)
        if url is not None:
            error_msg: str = "Invalid 'base_url' provided."
            if not isinstance(url, str):
                raise Sindri.APIError(error_msg)
            # Remove all trailing slashes "/"
            url = url.rstrip("/")
            # Validate str is a url
            if not is_url(url):
                raise Sindri.APIError(error_msg)
            # We assume a provided "base_url" has no path on the end
            path = urlparse(url).path
            if path != "":
                raise Sindri.APIError(error_msg)
            return os.path.join(url, "api", "v1", "")

        # 2. `api_url` is in kwargs
        url = kwargs.get("api_url", None)
        if url is not None:
            print("\nWARNING: 'api_url' is deprecated. Please use 'base_url' instead.\n")
            error_msg = "Invalid 'api_url' provided."
            if not isinstance(url, str):
                raise Sindri.APIError(error_msg)
            # Remove all trailing slashes "/"
            url = url.rstrip("/")
            # Validate str is a url
            if not is_url(url):
                raise Sindri.APIError(error_msg)
            # We assume a provided "api_url" has "/api" as the path on the end
            path = urlparse(url).path
            if path != "/api":
                raise Sindri.APIError(error_msg)
            return os.path.join(url, "v1", "")

        # 3. Use default
        return self.DEFAULT_SINDRI_API_URL

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

    def _get_circuit_status(self, circuit_id: str) -> str:
        """Hit the circuit_status API endpoint and validate the response. Do not print anything.
        This may raise `Sindri.APIError` if the response is invalid."""
        return self._get_circuit_finished_status(circuit_id)[1]

    def _get_circuit_finished_status(self, circuit_id: str) -> Tuple[bool, str]:
        """Hit the circuit_status API endpoint and validate the response. Do not print anything.
        This may raise `Sindri.APIError` if the response is invalid."""
        response_status_code, response_json = self._hit_api(
            "GET",
            f"circuit/{circuit_id}/status",
        )
        if response_status_code != 200:
            raise Sindri.APIError(
                f"Unable to fetch circuit_id={circuit_id}."
                f" status={response_status_code} response={response_json}"
            )
        if not isinstance(response_json, dict):
            raise Sindri.APIError("Received unexpected type for circuit status response.")
        finished_processing = response_json.get("finished_processing", False)
        status = response_json.get("status", "")
        if status == "":
            raise Sindri.APIError("Received unexpected type for circuit status response.")
        return finished_processing, status

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

    def _get_proof_status(self, proof_id: str) -> str:
        """Hit the proof_status API endpoint and validate the response. Do not print anything.
        This may raise `Sindri.APIError` if the response is invalid."""
        return self._get_proof_finished_status(proof_id)[1]

    def _get_proof_finished_status(self, proof_id: str) -> Tuple[bool, str]:
        """Hit the proof_status API endpoint and validate the response. Do not print anything.
        This may raise `Sindri.APIError` if the response is invalid."""
        response_status_code, response_json = self._hit_api(
            "GET",
            f"proof/{proof_id}/status",
        )
        if response_status_code != 200:
            raise Sindri.APIError(
                f"Unable to fetch proof_id={proof_id}."
                f" status={response_status_code} response={response_json}"
            )
        if not isinstance(response_json, dict):
            raise Sindri.APIError("Received unexpected type for proof status response.")
        finished_processing = response_json.get("finished_processing", False)
        status = response_json.get("status", "")
        if status == "":
            raise Sindri.APIError("Received unexpected type for proof status response.")
        return finished_processing, status

    def _get_verbose_1_circuit_detail(self, circuit_detail: dict) -> dict:
        """Return a slim circuit detail object for printing."""
        return {
            "status": circuit_detail.get("status", None),
            "project_name": circuit_detail.get("project_name", None),
            "circuit_id": circuit_detail.get("circuit_id", None),
            "tags": circuit_detail.get("tags", None),
            "circuit_type": circuit_detail.get("circuit_type", None),
            "compute_time": circuit_detail.get("compute_time", None),
        }

    def _get_verbose_1_proof_detail(self, proof_detail: dict) -> dict:
        """Return a slim proof detail object for printing."""
        return {
            "status": proof_detail.get("status", None),
            "proof_id": proof_detail.get("proof_id", None),
            "project_name": proof_detail.get("project_name", None),
            "circuit_id": proof_detail.get("circuit_id", None),
            "tags": proof_detail.get("tags", None),
            "circuit_type": proof_detail.get("circuit_type", None),
            "compute_time": proof_detail.get("compute_time", None),
        }

    def _hit_api(
        self, method: str, path: str, data=None, files=None
    ) -> Tuple[int, Union[dict, list]]:
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
        full_path = os.path.join(self._api_url, path)

        # Create a custom request session that will make all HTTP requests from the same session
        # retry for a total of 5 times, sleeping between retries with an increasing backoff of
        # 0s, 2s, 4s, 8s, 16s (the first retry is done immediately). It will retry on basic
        # connectivity issues (including DNS lookup failures), and HTTP status codes of 502, 503
        # and 504.
        session = requests.Session()
        max_retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
        adapter = HTTPAdapter(max_retries=max_retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Hit the API
        try:
            if method == "POST":
                response = session.post(
                    full_path, headers=self.headers_json, data=data, files=files
                )
            elif method == "GET":
                response = session.get(full_path, headers=self.headers_json, params=data)
            elif method == "DELETE":
                response = session.delete(full_path, headers=self.headers_json, data=data)
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
      -++++++-
    -+.
      +******=
             .*-
     -*******="""
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
        self,
        circuit_upload_path: str,
        tags: Union[List[str], None] = None,
        wait: bool = True,
        meta: Union[dict, None] = None,
    ) -> str:
        """Create a circuit. For information, refer to the
        [API docs](https://sindri.app/docs/reference/api/circuit-create/).

        Args:
        - `circuit_upload_path`: The path to either
            - A directory containing your circuit files
            - A compressed file (`.tar.gz` or `.zip`) of your circuit directory
        - `meta`: An arbitrary mapping of metadata keys to string values.
        This can be used to track additional information about the circuit such as an ID
        from an external system.
        - `tags`: A list of tags to assign the circuit. Defaults to `["latest"]` if not
        sepecified.
        - `wait`:
            - If `True`, block until the circuit is finished compiling.
            - If `False`, submit the circuit and return immediately.

        Returns:
        - `circuit_id`: The UUID4 identifier associated with this circuit. This is generated by
        Sindri.

        Raises:
        - `Sindri.APIError`:
            - Your API Key is invalid.
            - There is an error connecting to the Sindri API.
            - There is an error with your circuit upload.
            - The circuit has a compilation error (if `wait=True`).
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

        data = {
            "tags": tags,
        }
        if meta is not None:
            data["meta"] = json.dumps(meta)  # type: ignore
        # Hit circuit/create API endpoint
        response_status_code, response_json = self._hit_api(
            "POST",
            "circuit/create",
            data=data,
            files=files,
        )
        if response_status_code != 201:
            raise Sindri.APIError(
                f"Unable to create a new circuit."
                f" status={response_status_code} response={response_json}"
            )
        if not isinstance(response_json, dict):
            raise Sindri.APIError("Received unexpected type for circuit detail response.")
        # Obtain circuit_id
        circuit = response_json
        circuit_id = circuit.get("circuit_id", "")
        if self.verbose_level > 0:
            print(f"    circuit_id:   {circuit_id}")

        if wait:
            # 2. Poll circuit detail until it is finished processing
            if self.verbose_level > 0:
                print("Circuit: Poll until Finished")
            for _ in range(self.max_polling_iterations):
                finished_processing, _ = self._get_circuit_finished_status(circuit_id)
                if finished_processing:
                    break
                time.sleep(self.polling_interval_sec)
            else:
                raise Sindri.APIError("Circuit compile polling timed out.")

            # Done polling. Fetch the full detail.
            circuit = self._get_circuit(circuit_id, include_verification_key=True)
            circuit_status = circuit.get("status", "")
            if circuit_status == "Failed":
                raise Sindri.APIError(
                    f"Circuit compilation failed." f" error={circuit.get('error', '')}"
                )

        if self.verbose_level > 0:
            circuit_detail = circuit.copy()
            if self.verbose_level == 1:
                circuit_detail = self._get_verbose_1_circuit_detail(circuit_detail)
            print(f"{pformat(circuit_detail, indent=4)}\n")

        # Circuit compilation success!
        return circuit_id

    def delete_circuit(self, circuit_id: str) -> None:
        """Mark the specified circuit and any of its related proofs as deleted. For information,
        refer to the [API docs](https://sindri.app/docs/reference/api/circuit-delete/).

        Args:
        - `circuit_id`: The circuit identifier of the circuit.

        Returns:
        - `None`

        Raises:
        - `Sindri.APIError`:
            - Your API Key is invalid.
            - There is an error connecting to the Sindri API.
            - The specified circuit does not exist.
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
        """Mark the specified proof as deleted. For information, refer to the
        [API docs](https://sindri.app/docs/reference/api/proof-delete/).

        Args:
        - `proof_id`: The UUID4 identifier associated with this proof.

        Returns:
        - `None`

        Raises:
        - `Sindri.APIError`:
            - Your API Key is invalid.
            - There is an error connecting to the Sindri API.
            - The specified proof does not exist.
        """
        response_status_code, response_json = self._hit_api("DELETE", f"proof/{proof_id}/delete")
        if response_status_code != 200:
            raise Sindri.APIError(
                f"Unable to delete proof_id={proof_id}."
                f" status={response_status_code} response={response_json}"
            )

    def get_all_circuit_proofs(self, circuit_id: str) -> List[dict]:
        """Return a list of proof infos for the provided circuit_id. For information, refer to the
        [API docs](https://sindri.app/docs/reference/api/circuit-proofs/).

        Args:
        - `circuit_id`: The circuit identifier of the circuit.

        Returns:
        - `proofs`: A list of proof infos.

        Raises:
        - `Sindri.APIError`:
            - Your API Key is invalid.
            - There is an error connecting to the Sindri API.
            - The specified circuit does not exist.
        """
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

    def get_all_circuits(self) -> List[dict]:
        """Return a list of all circuit infos. For information, refer to the
        [API docs](https://sindri.app/docs/reference/api/circuit-list/).

        Args:
        - `None`

        Returns:
        - `circuits`: A list of circuit infos.

        Raises:
        - `Sindri.APIError`:
            - Your API Key is invalid.
            - There is an error connecting to the Sindri API.
        """
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
        """Get info for an existing circuit. For information, refer to the
        [API docs](https://sindri.app/docs/reference/api/circuit-detail/).

        Args:
        - `circuit_id`: The circuit identifier of the circuit.
        - `include_verification_key`: Indicates whether to include the verification key in the
        response.

        Returns:
        - `circuit`: The info for a circuit.

        Raises:
        - `Sindri.APIError`:
            - Your API Key is invalid.
            - There is an error connecting to the Sindri API.
            - The specified circuit does not exist.
        """
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
        """Get the smart contract verifier for an existing circuit.

        NOTE: This method wraps an experimental Sindri API endpoint is subject to change at
        any time.

        Args:
        - `circuit_id`: The circuit identifier of the circuit.

        Returns:
        - `smart_contract_verifier_code`: The smart contract verifier code for the circuit.

        Raises:
        - `Sindri.APIError`:
            - Your API Key is invalid.
            - There is an error connecting to the Sindri API.
            - The specified circuit does not exist.
            - The circuit's type does not support this feature.
            - The circuit was compiled before this feature was released.
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
        include_smart_contract_calldata: bool = True,
        include_verification_key: bool = True,
    ) -> dict:
        """Get info for an existing proof. For information, refer to the
        [API docs](https://sindri.app/docs/reference/api/proof-detail/).

        Args:
        - `proof_id`: The UUID4 identifier associated with this proof.
        - `include_proof`: Indicates whether to include the proof in the response.
        - `include_public`: Indicates whether to include the public inputs in the response.
        - `include_smart_contract_calldata`: Indicates whether to include the proof and public
        formatted as smart contract calldata in the response.
        - `include_verification_key`: Indicates whether to include the verification key in the
        response.

        Returns:
        - `proof`: The info for a proof.

        Raises:
        - `Sindri.APIError`:
            - Your API Key is invalid.
            - There is an error connecting to the Sindri API.
            - The specified proof does not exist.
            - `include_smart_contract_calldata=True` and the proof's circuit type does not support
            generating calldata for its circuit's smart contract verifier or the proof was
            generated before this feature was released.
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
        """Get details about the user or team associated with the configured API Key.

        Args:
        - `None`

        Returns:
        - `team`: The info for the user/team.

        Raises:
        - `Sindri.APIError`:
            - Your API Key is invalid.
            - There is an error connecting to the Sindri API.
        """
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
        perform_verify: bool = False,
        wait: bool = True,
        meta: Union[dict, None] = None,
        **kwargs,
    ) -> str:
        """Prove a circuit with specified inputs. For information, refer to the
        [API docs](https://sindri.app/docs/reference/api/proof-create/).

        Args:
        - `circuit_id`: The circuit identifier of the circuit.
        - `meta`: An arbitrary mapping of metadata keys to string values. This can be used to
        track additional information about the proof such as an ID from an external system.
        - `proof_input`: A string representing proof input which may be formatted as JSON for any
        framework. Noir circuits optionally accept TOML formatted proof input.
        - `perform_verify`: A boolean indicating whether to perform an internal verification check
        during the proof creation.
        - `wait`:
            - If `True`, block until the proof is finished generating.
            - If `False`, submit the proof and return immediately.

        Returns:
        - `proof_id`: The UUID4 identifier associated with this proof. This is generated by Sindri.

        Raises:
        - `Sindri.APIError`:
            - Your API Key is invalid.
            - There is an error connecting to the Sindri API.
            - The specified circuit does not exist.
            - The proof input is improperly formatted.
            - The proof generation fails. (if `wait=True`).
        """
        # Return values
        proof_id = ""

        # Grab prover_implementation from **kwargs
        prover_implementation = kwargs.get("prover_implementation", None)

        # 1. Submit a proof, obtain a proof_id.
        if self.verbose_level > 0:
            print("Prove circuit")

        data = {
            "proof_input": proof_input,
            "perform_verify": perform_verify,
            "prover_implementation": prover_implementation,
        }
        if meta is not None:
            data["meta"] = json.dumps(meta)

        # Hit the circuit/<circuit_id>/prove endpoint
        response_status_code, response_json = self._hit_api(
            "POST", f"circuit/{circuit_id}/prove", data=data
        )
        if response_status_code != 201:
            raise Sindri.APIError(
                f"Unable to prove circuit."
                f" status={response_status_code} response={response_json}"
            )
        if not isinstance(response_json, dict):
            raise Sindri.APIError("Received unexpected type for proof detail response.")
        # Obtain proof_id
        proof = response_json
        proof_id = proof.get("proof_id", "")
        if self.verbose_level > 0:
            print(f"    proof_id:     {proof_id}")

        if wait:
            # 2. Poll proof detail until it is finished processing
            if self.verbose_level > 0:
                print("Proof: Poll until Finished")
            for _ in range(self.max_polling_iterations):
                finished_processing, _ = self._get_proof_finished_status(proof_id)
                if finished_processing:
                    break
                time.sleep(self.polling_interval_sec)
            else:
                raise Sindri.APIError("Prove circuit polling timed out.")

            # Done polling. Fetch the full detail.
            proof = self._get_proof(
                proof_id,
                include_proof=True,
                include_public=True,
                include_smart_contract_calldata=True,
                include_verification_key=True,
            )
            proof_status = proof.get("status", "")
            if proof_status == "Failed":
                raise Sindri.APIError(f"Prove circuit failed." f" error={proof.get('error', '')}")

        if self.verbose_level > 0:
            proof_detail = proof.copy()
            if self.verbose_level == 1:
                proof_detail = self._get_verbose_1_proof_detail(proof_detail)
            print(f"{pformat(proof_detail, indent=4)}\n")

        # Prove circuit success!
        return proof_id

    def set_api_key(self, api_key: str) -> None:
        """Set the API Key for the Sindri instance.

        Args:
        - `api_key`: Your Sindri API Key.

        Returns:
        - `None`

        Raises:
        - `Sindri.APIError`:
            - Your API Key is improperly formatted.
        """
        if not isinstance(api_key, str):
            raise Sindri.APIError("Invalid API Key")
        if api_key == "":
            raise Sindri.APIError("Invalid API Key")
        self.api_key = api_key
        self._set_json_request_headers()
        if self.verbose_level > 0:
            print(f"Sindri API Key: {self.api_key}")

    def set_verbose_level(self, verbose_level: int) -> None:
        """Set the verbosity level for stdout printing.

        Args:
        - `verbose_level`: Must be either `0`, `1`, or `2`.
            - `0`: Do not print anything to stdout.
            - `1`: Print only necesessary information from Circuit/Proof objects.
            - `2`: Print everything.

        Returns:
        - `None`

        Raises:
        - `Sindri.APIError`:
            - `verbose_level` is invalid.
        """
        if verbose_level not in Sindri.VERBOSE_LEVELS:
            raise Sindri.APIError(
                f"Invalid verbose_level. Must be an int in {Sindri.VERBOSE_LEVELS}."
            )
        self.verbose_level = verbose_level
