import logging

from pwdlib import PasswordHash
from sqlalchemy.exc import NoResultFound

from dao.accounts_dao import AccountsDAO
from services.auth.jwt_handler import JWTHandler


class AuthenticationService:
	def __init__(
			self,
			accounts_dao: AccountsDAO,
			jwt_handler: JWTHandler
	):
		self._password_hash = PasswordHash.recommended()
		self._account_dao = accounts_dao
		self._jwt_handler = jwt_handler
		self._log = logging.getLogger("data_ontology")
	
	def authenticate_user(self, username: str, password: str) -> dict[str, str | int]:
		"""
		Authenticates User and return JWT token if username and password is valid

		:param username: The username to authenticate
		:param password: The password to authenticate
		:return: The authenticated user object
		"""
		self._log.info("Authentication: Authenticating User...")
		access_token = None
		try:
			user = self._get_user(username)
			if self._verify_password(password, user.f_hashed_password):
				access_token = self._create_access_token(user.model_dump(exclude={"f_hashed_password"}))
				
				return {
					"verified": True,
					"message": "Success",
					"access_token": access_token,
					"token_type": "bearer",
					**user.model_dump(exclude={"f_hashed_password"})
				}
		
		except NoResultFound:
			self._verify_password(password, self._get_password_hash(password))
		
		return {
			"verified": False,
			"message": "Authentication Failed",
			"access_token": access_token,
			"f_full_name": "",
			"token_type": None,
		}
	
	def _verify_password(self, password, hashed_password) -> bool:
		"""
		Verifies password against hashed password
		
		:param password: user's password
		:param hashed_password: user's hashed password
		:return: True or False
		"""
		return self._password_hash.verify(password, hashed_password)
	
	def _get_password_hash(self, password: str) -> str:
		"""
		Hashes the password
		
		:param password: The password to hash
		:return: The hashed password
		"""
		return self._password_hash.hash(password)
	
	def _get_user(self, username: str):
		"""
		Checks if username exist
		
		:param username: The username to check
		:return: The user object if exists, else raise NoResultFound
		"""
		return self._account_dao.get_user(username)
	
	def _create_access_token(self, data: dict) -> str:
		"""
		Gets the access token
		
		:param data: the user data
		:return: The JWT token
		"""
		self._log.info("Authentication: Getting Access Token...")
		return self._jwt_handler.get_token(data)
