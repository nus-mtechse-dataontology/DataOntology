from sqlalchemy.exc import NoResultFound

from entities.accounts import Accounts
from services.registration.registration_service import RegistrationService
from models.register_model import RegisterModel

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


register_router = APIRouter(prefix='/register', tags=['Account Registration'])


@register_router.post('/new')
async def register_account(request: Request, user: RegisterModel):
	result = await create_account(request.app.state.registration, user)
	
	return JSONResponse(
		status_code=200,
		content={
			**result
		}
	)


async def create_account(reg: RegistrationService, user: RegisterModel):
	return reg.register_user(user)
