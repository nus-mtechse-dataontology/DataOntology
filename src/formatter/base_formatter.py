from abc import ABC
from models.pipeline import QuestionResponse


class BaseFormatter(ABC):
	def __init__(self):
		pass
	
	def format_response(self, response: QuestionResponse,):
		pass
