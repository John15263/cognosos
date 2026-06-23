from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models.enums import TriggerModuleType
from backend.app.models.schemas import ModuleRunRequest
from backend.app.services.module_service import run_module


def run_module_graph(db: Session, module_type: TriggerModuleType, request: ModuleRunRequest):
    """Run the accepted specialist module through the service layer."""

    return run_module(db, module_type, request)

