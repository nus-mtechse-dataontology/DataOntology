from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import JSONResponse

from sqlalchemy import inspect

from dependencies.jwt_auth import JWTAuth
from ingestion.source.manual_source.manual_ingestion import ManualIngestion
from models.ingestion_model import IngestionModel
from models.users import UserModel
from session.db_session import DBSession

ingestion_router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@ingestion_router.get('/get_schema')
async def get_schema(request: Request, user: UserModel = Depends(JWTAuth())) -> JSONResponse:
	session = request.app.state.session
	
	if not user.disabled:
		result = await get_schema_from_db(session)
	else:
		result = []
	
	return JSONResponse(
		status_code=status.HTTP_200_OK,
		content={
			"tables": result
		}
	)


@ingestion_router.post('/upload')
async def upload(request: Request, payload: IngestionModel, user: UserModel = Depends(JWTAuth())) -> JSONResponse:
	if not user.disabled:
		upload_status = await upload_data(request.app.state.session, payload)
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


async def get_schema_from_db(session: DBSession) -> list[dict[str, str | bool | None]]:
	inspector = inspect(session.engine)
	tables = inspector.get_table_names()
	
	table_lists = []
	
	for table in tables:
		table_schema = {
			"name": table,
			"description": "",
			"cols": []
		}
		for col in inspector.get_columns(table):
			if not col["autoincrement"]:
				table_schema["cols"].append(
					{
						"name": col["name"],
						"type": str(col["type"]),
						"nullable": col["nullable"],
						"default": col["default"],
						"autoincrement": col["autoincrement"],
						"comment": col["comment"]
					}
				)
			else:
				continue
		
		table_lists.append(table_schema)
	
	return table_lists


async def upload_data(session: DBSession, payload: IngestionModel) -> dict[str, str | int]:
	manual_ingestion = ManualIngestion(session, payload)
	upload_status = manual_ingestion.ingest()
	return upload_status
