from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.enums import TriggerModuleType
from backend.app.models.schemas import ModuleRunRead, ModuleRunRequest
from backend.app.services.module_service import run_module

router = APIRouter(prefix="/modules", tags=["modules"])


@router.post("/{module_type}/run", response_model=ModuleRunRead)
def run_module_endpoint(
    module_type: TriggerModuleType,
    payload: ModuleRunRequest,
    db: Session = Depends(get_db),
) -> ModuleRunRead:
    module_run = run_module(db, module_type, payload)
    return ModuleRunRead.model_validate(module_run)

