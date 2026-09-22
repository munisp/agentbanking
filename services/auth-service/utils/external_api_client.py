"""External Api Client"""

import os
import requests

from typing import Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .errors import InternalApiError
from .helpers import create_logger

logger = create_logger(__name__)

# Module-level shared session: keep-alive connection pooling so we don't pay
# a fresh TCP+TLS handshake on every external call (Keycloak, CoA, etc.).
_POOL_MAXSIZE = int(os.getenv("EXTERNAL_API_POOL_MAXSIZE", "32"))


def _build_session() -> requests.Session:
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=8,
        pool_maxsize=_POOL_MAXSIZE,
        max_retries=Retry(
            total=2, backoff_factor=0.1, status_forcelist=(502, 503, 504)
        ),
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


_SESSION = _build_session()


class ExternalAPIClient:
    """
    A generic base class for making external API calls.
    Inherit this class and customize as needed for specific APIs.
    """

    def __init__(self, base_url: str, headers: dict | None = None):
        """
        Initialize the ExternalAPIClient.

        Args:
            base_url (str): The base URL for the external API.
            headers (dict): Default headers to include with every request.
        """
        self.base_url = base_url
        self.headers = headers

    def _get_url(self, endpoint: str) -> str:
        """
        Constructs the full URL for an API request.

        Args:
            endpoint (str): The API endpoint.

        Returns:
            str: The full URL.
        """
        return f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    def _handle_response(self, response: requests.Response):
        """
        Handles the response from an API call. Raise exceptions for errors.

        Args:
            response (requests.Response): The HTTP response object.

        Returns:
            dict: The parsed JSON response.

        Raises:
            Exception: For non-2xx HTTP responses.
        """
        try:
            response.raise_for_status()
            return response.json()  # Assuming JSON response
        except requests.exceptions.HTTPError as e:
            try:
                # Attempt to parse and log JSON response if available
                err_json = response.json()
                logger.error("HTTP error occurred: %s, Response JSON: %s", e, err_json)

                # Raise a custom error with the error message if it's a string
                if isinstance(err_json.get("message"), str):
                    raise InternalApiError(
                        err_json["message"], code=response.status_code, payload=err_json
                    ) from e

                if isinstance(err_json.get("error_description"), str):
                    raise InternalApiError(
                        err_json["error_description"],
                        code=response.status_code,
                        payload=err_json,
                    ) from e

                if isinstance(err_json.get("error"), str):
                    raise InternalApiError(
                        err_json["error"],
                        code=response.status_code,
                        payload=err_json,
                    ) from e

                # Optionally, handle cases where the error structure might differ
                raise InternalApiError(
                    "An unknown error occurred",
                    code=response.status_code,
                    payload=err_json,
                ) from e
            except (ValueError, AttributeError):
                # If the response is not JSON or cannot be parsed
                logger.error("HTTP Error: %s, Response Text: %s", e, response.text)
            raise
        except ValueError as e:
            # Handle JSON decoding errors
            logger.error("JSON Decode Error: %s, Response Text: %s", e, response.text)
            raise

    def _get(
        self, endpoint: str, params: dict | None = None, headers: dict | None = None
    ):
        """
        Sends a GET request to the external API.

        Args:
            endpoint (str): The API endpoint.
            params (dict): Query parameters for the request.
            headers (dict): Additional headers for the request.

        Returns:
            dict: The parsed JSON response.
        """
        url = self._get_url(endpoint)
        merged_headers = {**(self.headers or {}), **(headers or {})}
        response = _SESSION.get(url, params=params, headers=merged_headers, timeout=30)
        return self._handle_response(response)

    def _post(
        self,
        endpoint: str,
        data: Any | None = None,
        headers: dict | None = None,
        get_response: bool = True,
    ):
        """
        Sends a POST request to the external API.

        Args:
            endpoint (str): The API endpoint.
            data (dict): Data to send in the request body.
            headers (dict): Additional headers for the request.

        Returns:
            dict: The parsed JSON response.
        """
        url = self._get_url(endpoint)
        merged_headers = {**(self.headers or {}), **(headers or {})}

        json_data, str_data = None, None

        if isinstance(data, (dict, list)):
            json_data = data
        elif isinstance(data, str):
            str_data = data

        response = _SESSION.post(
            url, json=json_data, data=str_data, headers=merged_headers, timeout=30
        )

        if get_response:
            return {
                **self._handle_response(response),
                "status_code": response.status_code,
            }
        else:
            # Still need to handle HTTP errors even when not returning response body
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                # Log the error but don't raise - let caller check status_code
                try:
                    err_json = response.json()
                    logger.error(
                        "HTTP error occurred: %s, Response JSON: %s", e, err_json
                    )
                except (ValueError, AttributeError):
                    logger.error("HTTP Error: %s, Response Text: %s", e, response.text)

            return {"status_code": response.status_code}

    def _put(
        self,
        endpoint: str,
        data: dict | None = None,
        headers: dict | None = None,
        get_response: bool = True,
    ):
        """
        Sends a PUT request to the external API.

        Args:
            endpoint (str): The API endpoint.
            data (dict): Data to send in the request body.
            headers (dict): Additional headers for the request.

        Returns:
            dict: The parsed JSON response.
        """
        url = self._get_url(endpoint)
        merged_headers = {**(self.headers or {}), **(headers or {})}
        response = _SESSION.put(url, json=data, headers=merged_headers, timeout=60)

        if get_response:
            return {
                **self._handle_response(response),
                "status_code": response.status_code,
            }
        else:
            # Still need to handle HTTP errors even when not returning response body
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                # Log the error but don't raise - let caller check status_code
                try:
                    err_json = response.json()
                    logger.error(
                        "HTTP error occurred: %s, Response JSON: %s", e, err_json
                    )
                except (ValueError, AttributeError):
                    logger.error("HTTP Error: %s, Response Text: %s", e, response.text)

            return {"status_code": response.status_code}

    def _patch(
        self,
        endpoint: str,
        data: dict | None = None,
        headers: dict | None = None,
        get_response: bool = True,
    ):
        """
        Sends a PATCH request to the external API.

        Args:
            endpoint (str): The API endpoint.
            data (dict): Data to send in the request body.
            headers (dict): Additional headers for the request.

        Returns:
            dict: The parsed JSON response.
        """
        url = self._get_url(endpoint)
        merged_headers = {**(self.headers or {}), **(headers or {})}
        response = _SESSION.patch(url, json=data, headers=merged_headers, timeout=60)

        if get_response:
            return {
                **self._handle_response(response),
                "status_code": response.status_code,
            }
        else:
            return {"status_code": response.status_code}

    def _delete(
        self, endpoint: str, data: dict | None = None, headers: dict | None = None
    ):
        """
        Sends a DELETE request to the external API.

        Args:
            endpoint (str): The API endpoint.
            headers (dict): Additional headers for the request.

        Returns:
            dict: The parsed JSON response.
        """
        url = self._get_url(endpoint)
        merged_headers = {**(self.headers or {}), **(headers or {})}
        response = _SESSION.delete(url, headers=merged_headers, json=data, timeout=60)
        return self._handle_response(response)
