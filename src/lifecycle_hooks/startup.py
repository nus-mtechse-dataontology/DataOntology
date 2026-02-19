from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def startup(app: FastAPI):
    """
    Initialise all dependencies for the Application
    todo: update this method too initialise app dependencies
    """
    yield
