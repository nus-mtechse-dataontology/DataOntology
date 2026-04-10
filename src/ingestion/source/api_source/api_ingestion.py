from abc import ABC, abstractmethod
from datetime import datetime
import hashlib
import logging
import os
from pathlib import Path
from typing import Callable
import uuid

import requests
from requests import PreparedRequest

from ingestion.gateway.api_gateway import ApiGateway


class ApiIngestion(ABC):
	def __init__(self, api_gateway: ApiGateway, config: dict):
		self._log = logging.getLogger("data_ontology")
		self._root = os.getenv("PROJECT_PATH", os.getcwd())
		self._config = config
		self._context = self._generate_context()
		self._api_gateway = api_gateway
		
		self._payload: PreparedRequest | None = None
		self._result: dict | None = None
		self._ingestion_name = ""
	
	def ingest(self):
		"""
		Starting point for the ingestion API.
		"""
		dataset = self._config["dataset"]
		self._prepare_payload(dataset["source"], dataset["name"])
		self._get_data()
		self._upload_to_db(self._result)
	
	def _prepare_payload(self, source: dict[str, str | dict], name: str):
		"""
		Prepares the payload for API call.

		:param source: The source payload mapping
		:param name: Name of the API
		:return: A prepared payload
		"""
		self._log.info("API Ingestion: Preparing payload for: %s", name)
		
		self._payload = (
			requests
			.Request(
				method=source["method"],
				url=source["url"],
				headers=self._replace_context(source.get("headers")) if source.get("headers") else {},
				params=self._replace_context(source.get("params")) if source.get("params") else {},
				json=self._replace_context(source.get("body")) if source.get("body") else {}
			)
			.prepare()
		)
	
	def _get_data(self):
		"""
		Calls the API gateway to get data.

		:return: The API response
		"""
		self._log.info("API Ingestion: Getting data")
		self._result = self._api_gateway.call_api(self._payload)
		self._log.info("API Ingestion: Finished getting data")
	
	def _generate_context(self) -> dict[str, Callable[..., str]]:
		"""
		Generates the context to map context values in YAML file
		:return: context mapping
		"""
		return {
			"client_uuid": self._generate_client_id,
			"client_signature": self._generate_signature,
			"api_key": self._get_api_key
		}
	
	def _replace_context(self, payload: dict) -> dict:
		"""
		Replace the context in the payload.

		:param payload: The payload with context to be updated.
		:return: Updated payload, with options removed.
		"""
		for key, value in payload.items():
			if not isinstance(value, dict):
				if value in self._context:
					payload[key] = self._context[value](**payload["options"].get("context", {}))
		
		del payload["options"]
		return payload
	
	def _get_vault(self, vault_name: str) -> str:
		"""
		Gets the API key from the environment variables for given apiKey value in YAML file
		:param vault_name: The name of vault to load
		:return: the vault string
		"""
	
		try:
			self._log.debug("Ingestion: Attempting to get vault: %s", vault_name)
			with open(Path(self._root, "vault", vault_name)) as kf:
				return kf.read()
		
		except FileNotFoundError as e:
			self._log.error("Ingestion: No vault found for: %s...", vault_name)
			raise e
		
		except Exception as e:
			self._log.error("Ingestion: Unknown error when attempting to get %s...", vault_name)
			raise e
		
	def _get_api_key(self, **kwargs) -> str:
		"""
		Gets the API key from the environment variables for given apiKey value in YAML file
		:param kwargs: The source mapping in YAML file
		:return: The API key string
		"""
		api_key = kwargs["apiKey"]
		self._log.info("Ingestion: Attempting to get key...")
		
		if api_key:
			return self._get_vault(api_key)
		else:
			raise AssertionError("Ensure apiKey value is not empty or null in YAML file.")
	
	def _generate_signature(self, **kwargs):
		"""
		Generates the client signature
		:param kwargs: The source mapping in YAML file
		:return: The Client signature string
		"""
		self._log.info("Ingestion: Attempting to generate client signature...")
		
		client_secret = (f"{self._get_vault(kwargs['apiKey'])}"
		                 f"{self._get_vault(kwargs['secret'])}"
		                 f"{int(datetime.now().timestamp())}")
		
		encoded_client_secret = client_secret.encode("utf-8")
		
		client_signature = hashlib.sha256(encoded_client_secret).hexdigest()
		return client_signature
	
	def _generate_client_id(self, **kwargs):
		"""
		Generates the client ID for API Call
		:param kwargs:
		:return:
		"""
		self._log.info("Ingestion: Attempting to generate client id...")
		return str(uuid.uuid4())
	
	
	@abstractmethod
	def _upload_to_db(self, response_payload: dict):
		"""
		Inserted data into the database.
		
		:param response_payload: the response payload
		:return:
		"""
		pass
	