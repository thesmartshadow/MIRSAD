from __future__ import annotations

from enum import StrEnum


class AcquisitionMode(StrEnum):
    DIRECT_API = "DIRECT_API"
    PUBLIC_API = "PUBLIC_API"
    PUBLIC_TIMELINE = "PUBLIC_TIMELINE"
    WEB_INDEX = "WEB_INDEX"
    HISTORICAL_INDEX = "HISTORICAL_INDEX"
    OFFICIAL_EMBED = "OFFICIAL_EMBED"
    MANUAL_IMPORT = "MANUAL_IMPORT"
    LOCAL_MEMORY = "LOCAL_MEMORY"


DIRECT_ACQUISITION_MODES = (
    AcquisitionMode.DIRECT_API,
    AcquisitionMode.PUBLIC_API,
    AcquisitionMode.PUBLIC_TIMELINE,
)
