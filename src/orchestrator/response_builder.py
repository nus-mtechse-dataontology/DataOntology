"""Builds final user-facing responses from execution results."""

from models.pipeline import QuestionResponse, ResultSet


class ResponseBuilder:
    def build(self, result_set: ResultSet) -> QuestionResponse:
        del result_set
        raise NotImplementedError("ResponseBuilder.build is not implemented yet.")
