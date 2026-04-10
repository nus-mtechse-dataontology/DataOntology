import logging

from pwdlib import PasswordHash

from sqlalchemy.exc import NoResultFound
from entities.accounts import Accounts
from dao.accounts_dao import AccountsDAO
from dao.registration_dao import RegistrationDAO
from models.register_model import RegisterModel


class RegistrationService:
	def __init__(self, registration_dao: RegistrationDAO, accounts_dao: AccountsDAO):
		self._password_hash = PasswordHash.recommended()
		self._registration_dao = registration_dao
		self._accounts_dao = accounts_dao
		self._log = logging.getLogger("data_ontology")
	
	def register_user(self, user: RegisterModel) -> dict[str, str | int]:
		"""
		Registers a new user
		
		:param user: The user to be registered
		:return: User information
		"""
		if not self._check_username_exist(user.username):
			account = Accounts(
				f_username=user.username,
				f_hashed_password=self._get_password_hash(user.password),
				f_email=user.email,
				f_full_name=user.full_name,
			)
			self._registration_dao.register_user(account)
			return {
				"status": 0,
				"message": "User registered",
				**user.model_dump(include={"username", "full_name"})
			}
		else:
			return {
				"status": 1,
				"message": "User already exists",
				"username": user.username
			}
			
	def _check_username_exist(self, username: str) -> Accounts | bool:
		"""
		Checks if a user exists based on username
		
		:param username: The username to be checked
		:return: Accounts or False if user do not exist
		"""
		self._log.info("Registration: Checking if username exists...")
		try:
			user = self._accounts_dao.get_user(username)
			self._log.error("Registration: User exist...")
			return user
		
		except NoResultFound:
			self._log.info("Registration: User not found, proceeding with registration...")
			return False
	
	def _get_password_hash(self, password: str) -> str:
		"""
		Hashes the password
		:param password: The user password
		:return: The hashed password
		"""
		return self._password_hash.hash(password)
