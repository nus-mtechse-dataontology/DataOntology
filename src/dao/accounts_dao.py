from dao.base_dao import BaseDAO
from entities.accounts import Accounts

import traceback

from sqlmodel import Session, select
from sqlalchemy.exc import SQLAlchemyError, NoResultFound


class AccountsDAO(BaseDAO):
	def __init__(self, engine):
		super().__init__(engine)
		
	def get_user(self, username) -> Accounts:
		with Session(self._engine) as session:
			try:
				stmt = select(Accounts).where(Accounts.f_username == username)
				result = session.exec(stmt).one()
				return result
			
			except NoResultFound:
				self._log.error("Accounts: No user found...")
				raise NoResultFound
			
			except SQLAlchemyError as e:
				self._log.error("Accounts: Error when getting user information, %s", e)
				self._log.error(traceback.format_exc())
				raise e
