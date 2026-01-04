from fastapi import FastAPI
from backend.database import database

app = FastAPI(title="HedgeBot API")

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

@app.get("/")
async def root():
    return {"message": "HedgeBot API is running"}
