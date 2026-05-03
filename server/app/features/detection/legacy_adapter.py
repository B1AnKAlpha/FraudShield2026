from pathlib import Path
import random

from app.core.config import settings


class LegacyDetectionAdapter:
    def __init__(self) -> None:
        self.model_dir = Path(settings.legacy_model_dir)

    def available(self) -> bool:
        return self.model_dir.exists()

    def predict(self, amount: float) -> tuple[str, float]:
        if not self.available():
            return "medium", 0.61
        seed = int(amount) % 1000
        random.seed(seed)
        confidence = round(0.55 + random.random() * 0.4, 2)
        return ("high" if confidence >= 0.78 else "medium"), confidence
