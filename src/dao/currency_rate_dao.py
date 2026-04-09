from dao.base_dao import BaseDAO


class CurrencyRateDAO(BaseDAO):
	def __init__(self, engine):
		super().__init__(engine)
