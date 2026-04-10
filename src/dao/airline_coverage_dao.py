from sqlmodel import Session, select

from entities.airline_coverage import AirlineCoverage
from dao.base_dao import BaseDAO


class AirlineCoverageDAO(BaseDAO):
	def __init__(self, engine):
		super().__init__(engine)
	
	def get_all_coverage(self) -> list[AirlineCoverage]:
		with Session(self._engine) as session:
			coverages = []
			statement = select(AirlineCoverage)
			results = session.exec(statement)
			
			for cov in results:
				coverages.append(cov)
				
			return coverages
