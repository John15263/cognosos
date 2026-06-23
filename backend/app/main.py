from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import routes_cards, routes_entries, routes_flow_sessions, routes_health, routes_modules, routes_search, routes_time_capsules, routes_triggers
from backend.app.core.logging import configure_logging
from backend.app.db.base import Base
from backend.app.db.session import engine
from backend.app.models import db_models  # noqa: F401

configure_logging()

app = FastAPI(title="CognosOS", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def create_sqlite_demo_tables() -> None:
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)


app.include_router(routes_health.router)
app.include_router(routes_entries.router)
app.include_router(routes_flow_sessions.router)
app.include_router(routes_cards.router)
app.include_router(routes_search.router)
app.include_router(routes_triggers.router)
app.include_router(routes_modules.router)
app.include_router(routes_time_capsules.router)
