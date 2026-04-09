import logging

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from models.users import UserModel


class JWTAuth(HTTPBearer):
	"""
	Callable class dependency.
	Usage: Depends(JWTAuth())
	"""
	def __init__(self):
		super().__init__()
		self._log = logging.getLogger("data_ontology")
	
	async def __call__(self, request: Request) -> UserModel:
		"""
        This method is executed when the class is used as a dependency.
        It extracts credentials, validates the token, and returns the user model.
		
		:param request: The request object.
		:return: User object.
		"""
		credentials: HTTPAuthorizationCredentials = await super().__call__(request)
		
		token = credentials.credentials
		jwt_handler = request.app.state.jwt_handler
		
		try:
			self._log.info("JWT Auth: Validating JWT Token..")
			payload = jwt_handler.verify_token(token)
			self._log.info("JWT Auth: Token is valid...")
			return UserModel(**payload)
		
		except jwt.ExpiredSignatureError:
			self._log.error("JWT Auth: Expired JWT Token..")
			raise HTTPException(
				status_code=status.HTTP_401_UNAUTHORIZED,
				detail="Access token expired",
			)
		
		except jwt.InvalidTokenError:
			self._log.error("JWT Auth: Invalid JWT Token..")
			raise HTTPException(
				status_code=status.HTTP_401_UNAUTHORIZED,
				detail="Invalid token",
			)
