from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .connectors import BaseConnector
from .database import get_db

DbSession = Annotated[Session, Depends(get_db)]


async def get_app_settings() -> Settings:
    return get_settings()


AppSettings = Annotated[Settings, Depends(get_app_settings)]


async def get_connectors(request: Request) -> dict[str, BaseConnector]:
    return request.app.state.connectors


Connectors = Annotated[dict[str, BaseConnector], Depends(get_connectors)]
