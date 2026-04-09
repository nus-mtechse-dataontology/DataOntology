from dao.fact_flight_info_dao import FactFlightInfoDAO
from execution.sql_executor import SQLExecutor

import pytest


@pytest.fixture
def sql_executor(fact_flight_info_dao: FactFlightInfoDAO) -> SQLExecutor:
	"""
	SQLExecutor instance configured with test database.

	Args:
		fact_flight_info_dao: The Fact Flight Info DAO (from test_db_path fixture)

	Returns:
		SQLExecutor: Instance ready to execute queries against test DB
	"""
	return SQLExecutor(fact_flight_info_dao)


