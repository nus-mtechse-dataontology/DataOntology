from formatter.base_formatter import BaseFormatter
from models import ResultSet
from models.common import SuccessResponse

import logging


class TelegramFormatter(BaseFormatter):
    def __init__(self):
        super().__init__()
        self._log = logging.getLogger("data_ontology")
        
    def format_response(self, response: ResultSet) -> SuccessResponse:
        """
        Formats the response for telegram message.
        :param response: The response from DB.
        :return: The formatted response.
        """
        self._log.info("Telegram Formatter: Formatting result for Telegram Message..")
        if isinstance(response, ResultSet):
            return self._build_telegram_text_from_response(response)
        
        return SuccessResponse(
            request_id=response.request_id,
            status="SUCCESS",
            data="Beep boop\\! 🤖 Our circuits are a little tangled right now\\. "
                 "Give us a moment to untie the knots and try again soon\\!"
        )
    
    def _build_telegram_text_from_response(self, response: ResultSet) -> SuccessResponse:
        """
        The builder for telegram message response.
        :param response: The response from DB.
        :return: The formatted telegram message.
        """
        self._log.info("Telegram Formatter: Building Telegram Message...")
        
        res = response
        row_count = len(res.result_set)
        
        self._log.debug("res is %s", res)
        
        if row_count == 0:
            return SuccessResponse(
                request_id=response.request_id,
                status="SUCCESS",
                data="Ready or not\\.\\.\\. we couldn't find 'em\\! 🙈 Our records are playing hard to get today\\. "
                     "Want to try another search?"
            )
        
        if res.type_ == "flights":
            record_lines = []
            
            for index, row in enumerate(res.result_set, start=1):
                airline = row['f_airline_name']
                dep_date = str(row['f_departure_date']).replace('-', '\\-')
                trip_type = "One Way" if row['f_trip_type'] == 'normal' else 'Return'
                cabin = row['f_cabin_class']
                price = row.get('cheapest_fare')
                dep_code = row.get("f_departure_airport_code")
                arr_code = row.get("f_destination_airport_code")
                
                route = f"*{dep_code}* 🛫️ ➔ *{arr_code}* 🛬\n" if dep_code and arr_code else ""
                price = f"*Price* 🤑: {str(price).replace('.', '\\.')}\n" if price else ""
                
                record_lines.append(
                    f"*{index}\\. ✈️ {airline}*\n\n"
                    f"{route}"
                    f"{price}"
                    f"*Departure Date* 🗓️: {dep_date}\n"
                    f"*Trip Type* 🧑🏻‍✈️: {trip_type}\n"
                    f"*Cabin* 💺: {cabin}\n\n"
                )
            
            header = "record" if row_count == 1 else "records"
            response_text = f"I found {row_count} matching {header}:\n\n" + "\n".join(record_lines)
        
            return SuccessResponse(
                request_id=response.request_id,
                status="SUCCESS",
                data=response_text,
            )
        
        return SuccessResponse(
            request_id=response.request_id,
            status="SUCCESS",
            data=res.result_set[0],
        )
