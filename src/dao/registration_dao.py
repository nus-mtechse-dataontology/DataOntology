from sqlmodel import Session

from dao.base_dao import BaseDAO
from entities import Accounts


class RegistrationDAO(BaseDAO):
	def __init__(self, engine):
		super().__init__(engine)
	
	def register_user(self, user: Accounts):
		with Session(self._engine) as session:
			session.add(user)
			session.commit()
			return {
				"message": "User registration successful",
			}
