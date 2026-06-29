"""External Api Client"""

import requests

from typing import Any
from .errors import InternalApiError
from .helpers import create_logger

logger = create_logger(__name__)


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
                    raise InternalApiError(err_json["message"], code=response.status_code, payload=err_json) from e

                # Optionally, handle cases where the error structure might differ
                raise InternalApiError("An unknown error occurred", code=response.status_code, payload=err_json) from e
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
        response = requests.get(url, params=params, headers=merged_headers, timeout=30)
        return self._handle_response(response)

    def _post(
        self, endpoint: str, data: Any | None = None, headers: dict | None = None, get_response: bool = True
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

        response = requests.post(url, json=json_data, data=str_data, headers=merged_headers, timeout=30)
        
        if get_response:
            return {
                **self._handle_response(response),
                "status_code": response.status_code
            }
        else:
            return {
                "status_code": response.status_code
            }

    def _put(
        self, endpoint: str, data: dict | None = None, headers: dict | None = None, get_response: bool = True
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
        response = requests.put(url, json=data, headers=merged_headers, timeout=60)
        
        if get_response:
            return {
                **self._handle_response(response),
                "status_code": response.status_code
            }
        else:
            return {
                "status_code": response.status_code
            }

    def _delete(self, endpoint: str, data: dict | None = None, headers: dict | None = None):
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
        response = requests.delete(url, headers=merged_headers, json=data, timeout=60)
        return self._handle_response(response)
