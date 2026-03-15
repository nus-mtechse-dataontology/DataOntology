from datetime import datetime, timedelta, timezone
import jwt
import logging


class JWTHandler:
	def __init__(self, secret: str, expire_mins: int, algo: str):
		self._algo = algo
		self._expire_mins = expire_mins
		self._secret = secret
		self._log = logging.getLogger("data_ontology")
		
	def get_token(self, data: dict) -> str:
		"""
		Creates the access token
		
		:param data: The user data to be encoded
		:return: The Access Token
		"""
		self._log.info("JWT: Generating Access Token...")
		
		to_encode = data.copy()
		expire = datetime.now(timezone.utc) + timedelta(minutes=self._expire_mins)
		to_encode.update({"exp": expire})
		
		encoded_jwt = jwt.encode(to_encode, self._secret, algorithm=self._algo)
		
		return encoded_jwt
	
	def verify_token(self, token: str) -> bool:
		"""
		Verifies the access token expiry
		
		:param token: The access token to be verified
		:return: True or False
		"""
		data = jwt.decode(token, self._secret, algorithms=[self._algo])
		return data["exp"] - datetime.now(timezone.utc).timestamp() > 0
