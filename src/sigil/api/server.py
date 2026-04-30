import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sigil.api.routes import router
from sigil.db import init_db

app = FastAPI(title="Sigil Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.on_event("startup")
async def startup_event():
    await init_db()

if __name__ == "__main__":
    uvicorn.run("sigil.api.server:app", host="0.0.0.0", port=8000, reload=True)
