from services.auth.authentication_service import AuthenticationService

from typing import Annotated

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm


auth_router = APIRouter(prefix='/auth', tags=['Auth'])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='login')

@auth_router.post('/login')
async def login(request: Request, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
	result = await authenticate_user(request.app.state.auth, form_data.username, form_data.password)
	return JSONResponse(
		status_code=result['status_code'],
		content={
			'message': result['message'],
			'access_token': result.get('access_token'),
			'token_type': result.get('token_type'),
		}
	)


async def authenticate_user(auth: AuthenticationService, username: str, password: str) -> dict[str, str | int]:
	auth_details = auth.authenticate_user(username, password)
	
	return {
		'status_code': 200 if auth_details['verified'] else 401,
		'message': auth_details["message"],
		'access_token': auth_details['access_token'],
		'full_name': auth_details['full_name'],
		'token_type': auth_details['token_type']
	}
	