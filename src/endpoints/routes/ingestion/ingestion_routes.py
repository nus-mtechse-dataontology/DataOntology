import asyncio

from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import JSONResponse
import json

from sqlalchemy import inspect
from sqlalchemy.schema import MetaData
from sqlmodel import Session

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


@ingestion_router.get("/view/{table}")
async def view(request: Request, table: str, user: UserModel = Depends(JWTAuth())) -> JSONResponse:
	if not user.disabled:
		session = request.app.state.session
		task = await asyncio.gather(
			asyncio.to_thread(
				get_table_data,
				session=session,
				table=table
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


def get_table_data(session: DBSession, table: str):
	metadata = MetaData(schema=None)
	metadata.reflect(
		bind=session.engine,
		only=[table],
		views=True
	)
	
	db_table = metadata.tables[table]
	statement = db_table.select()
	
	with Session(bind=session.engine) as db_session:
		results = db_session.exec(statement)
		rows = [dict(r) for r in results.mappings().all()]
		return json.loads(json.dumps(rows, default=str))


async def get_schema_from_db(session: DBSession) -> list[dict[str, str | bool | None]]:
	inspector = inspect(session.engine)
	tables = inspector.get_table_names()
	
	table_lists = []
	
	for table in tables:
		if table == "dim_accounts":
			continue
		
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
