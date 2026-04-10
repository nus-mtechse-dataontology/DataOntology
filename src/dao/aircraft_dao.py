from dao.base_dao import BaseDAO


class AircraftDAO(BaseDAO):
	def __init__(self, engine):
		super().__init__(engine)
