from formatter.base_formatter import BaseFormatter
from models.common import SuccessResponse
from models import ResultSet

import logging


class WebFormatter(BaseFormatter):
	def __init__(self):
		super().__init__()
		self._log = logging.getLogger("data_ontology")
	
	def format_response(self, response: ResultSet) -> SuccessResponse:
		"""
        Formats the response for Web message.
        :param response: The response from DB.
        :return: The formatted response.
        """
		self._log.info("Web Formatter: Formatting result for Web Message..")
		if isinstance(response, ResultSet):
			return self._build_web_html_from_response(response)
		
		return SuccessResponse(
			request_id=response.request_id,
			status="SUCCESS",
			data=["Beep boop! 🤖 Our circuits are a little tangled right now. "
			      "Give us a moment to untie the knots and try again soon!"]
		)
	
	def _build_web_html_from_response(self, response: ResultSet) -> SuccessResponse:
		res = response
		row_count = len(res.result_set)
		
		self._log.info("Web Formatter: Building Web Message...")
		
		if row_count == 0:
			return SuccessResponse(
				request_id=response.request_id,
				status="SUCCESS",
				data=["Ready or not... we couldn't find 'em! 🙈 Our records are playing hard to get today. "
				      "Want to try another search?"]
			)
		
		if res.type_ == "flights":
			header = "record" if row_count == 1 else "records"
			record_lines = [f"I found {row_count} matching {header}:\n\n" + "\n"]
			
			for index, row in enumerate(res.result_set, start=1):
				airline = row['f_airline_name']
				dep_date = str(row['f_departure_date']).replace('-', '-')
				trip_type = "One Way" if row['f_trip_type'] == 'normal' else 'Return'
				cabin = row['f_cabin_class']
				price = row.get('cheapest_fare')
				dep_code = row.get("f_departure_airport_code")
				arr_code = row.get("f_destination_airport_code")
				
				route = f"<p><b>{dep_code}</b> 🛫️ ➔ <b>{arr_code}</b> 🛬\n</p>" if dep_code and arr_code else ""
				price = f"<p><b>Price</b> 🤑: {str(price).replace('.', '.')}\n</p>" if price else ""
				
				record_lines.append(
					f"<p><b>{index}. ✈️ {airline}</b>\n\n</p>"
					f"<p>{route}</p>"
					f"<p>{price}</p>"
					f"<p><b>Departure Date</b> 🗓️: {dep_date}\n</p>"
					f"<p><b>Trip Type</b> 🧑🏻‍✈️: {trip_type}\n</p>"
					f"<p><b>Cabin</b> 💺: {cabin}\n\n</p>"
				)
			
			return SuccessResponse(
				request_id=response.request_id,
				status="SUCCESS",
				data=record_lines
			)
		
		return SuccessResponse(
			request_id=response.request_id,
			status="SUCCESS",
			data=[res.result_set[0]['answer']]
		)
