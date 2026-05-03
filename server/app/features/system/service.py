from pathlib import Path

from app.core.config import settings
from app.features.realtime.service import service as realtime_service


class SystemService:
    def overview(self):
        model_dir = Path(settings.legacy_model_dir)
        return {
            "server_name": settings.app_name,
            "legacy_model_dir": str(model_dir),
            "legacy_model_exists": model_dir.exists(),
            "realtime_mode": realtime_service.mode(),
            "detection_engine": "legacy-adapter" if model_dir.exists() else "mock-engine",
        }
