from fastapi import FastAPI

app = FastAPI(title="DataLens")

@app.get("/health")
def health():
    return {"status": "ok"}
