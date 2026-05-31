from pathlib import Path

from app.core.config import settings
from app.features.realtime.service import service as realtime_service


class SystemService:
    def overview(self):
        return {
            "server_name": settings.app_name,
            "legacy_model_dir": "",
            "legacy_model_exists": False,
            "realtime_mode": "disabled",
            "detection_engine": "analysis-service",
        }
