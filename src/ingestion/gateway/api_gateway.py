import logging
from typing import Any

import requests
from requests import HTTPError
from requests.models import PreparedRequest


class ApiGateway:
	def __init__(self):
		self._log = logging.getLogger("data_ontology")
		self._session = requests.session()
	
	def call_api(self, request: PreparedRequest) -> dict[str, Any] | list[Any]:
		"""
		Calls the API with the given request and returns the JSON response as a dictionary.
		:param request: The prepared request to be sent to the API.
		:return: Dictionary or List containing the JSON response from the API.
		:raises HTTPError: If the API call fails with a non-200 status code
		"""
		self._log.info("API Gateway: Calling API at %s", request.url)
		
		response = self._session.send(request)
		
		if response.status_code == 200:
			return response.json()
		else:
			raise HTTPError(response.status_code)
