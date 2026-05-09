import asyncio

from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import JSONResponse

from dependencies.jwt_auth import JWTAuth
from ingestion.services.ingestion_service import IngestionService
from models.ingestion_model import IngestionModel
from models.users import UserModel


ingestion_router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@ingestion_router.get('/get_schema')
async def get_schema(request: Request, user: UserModel = Depends(JWTAuth())) -> JSONResponse:
	if not user.disabled:
		task = await asyncio.gather(
			asyncio.to_thread(
				get_schema_from_db,
				ingestion_service=request.app.state.ingestion_service
			)
		)
		result = task[0]
	else:
		result = []
	
	return JSONResponse(
		status_code=status.HTTP_200_OK,
		content={
			"tables": result
		}
	)


@ingestion_router.get("/view/{table}")
async def view(request: Request, table: str, user: UserModel = Depends(JWTAuth())) -> JSONResponse:
	if not user.disabled:
		task = await asyncio.gather(
			asyncio.to_thread(
				get_table_data,
				ingestion_service=request.app.state.ingestion_service,
				table_name=table
			)
		)
		
		results = task[0]
		
		return JSONResponse(
			status_code=status.HTTP_200_OK,
			content={
				"tables": results
			}
		)
	else:
		return JSONResponse(
			status_code=status.HTTP_403_FORBIDDEN,
			content={
				"tables": []
			}
		)


@ingestion_router.post('/upload')
async def upload(request: Request, payload: IngestionModel, user: UserModel = Depends(JWTAuth())) -> JSONResponse:
	if not user.disabled:
		task = await asyncio.gather(
			asyncio.to_thread(
				upload_data,
				ingestion_service=request.app.state.ingestion_service,
				payload=payload
			)
		)
		
		upload_status = task[0]
		
		return JSONResponse(
			status_code=status.HTTP_200_OK,
			content={
				**upload_status
			}
		)
	else:
		return JSONResponse(
			status_code=status.HTTP_403_FORBIDDEN,
			content={
				"message": "User does not have permission to perform this action"
			}
		)


def get_table_data(ingestion_service: IngestionService, table_name: str):
	return ingestion_service.get_table_data(table_name)


def get_schema_from_db(ingestion_service: IngestionService) -> list[dict[str, str | bool | None]]:
	return ingestion_service.get_schema_from_db()


def upload_data(ingestion_service: IngestionService, payload: IngestionModel) -> dict[str, str | int]:
	return ingestion_service.upload_to_db(payload)
