from __future__ import annotations

import os
import signal
import subprocess
import time

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/shutdown")
def shutdown(
    request: Request,
    background_tasks: BackgroundTasks,
    x_cognosos_shutdown: str | None = Header(default=None),
) -> dict[str, str]:
    if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Local shutdown only")
    if x_cognosos_shutdown != "1":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing shutdown header")
    background_tasks.add_task(_shutdown_local_app)
    return {"status": "stopping"}


def _shutdown_local_app() -> None:
    time.sleep(0.2)
    launcher_pid = os.environ.get("COGNOSOS_LAUNCHER_PID")
    if launcher_pid and launcher_pid.isdigit():
        os.kill(int(launcher_pid), signal.SIGTERM)
        return
    _kill_port(5173)
    _kill_port(8000)


def _kill_port(port: int) -> None:
    result = subprocess.run(["lsof", "-tiTCP:%d" % port, "-sTCP:LISTEN"], check=False, capture_output=True, text=True)
    for raw_pid in result.stdout.splitlines():
        if raw_pid.isdigit():
            os.kill(int(raw_pid), signal.SIGTERM)
