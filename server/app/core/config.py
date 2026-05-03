from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]
LEGACY_ROOT = ROOT_DIR.parents[1] / "Project"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "FraudShield 2026 API"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
            "http://tauri.localhost",
            "https://tauri.localhost",
            "tauri://localhost",
        ]
    )
    legacy_model_dir: str = str(LEGACY_ROOT / "final" / "model")
    legacy_static_data_path: str = str(LEGACY_ROOT / "final" / "data" / "静态.xlsx")
    legacy_torch_python: str = "python"
    legacy_result_dir: str = str(LEGACY_ROOT / "final" / "result")
    legacy_report_file: str = str(LEGACY_ROOT / "final" / "result" / "report.html")
    realtime_light_model_path: str = str(ROOT_DIR / "data" / "models" / "realtime_light_model.joblib")
    auth_db_path: str = str(ROOT_DIR / "data" / "auth.db")
    auth_session_hours: int = 12
    auth_totp_issuer: str = "FraudShield2026"
    analysis_db_path: str = str(ROOT_DIR / "data" / "analysis.db")
    analysis_storage_dir: str = str(ROOT_DIR / "data" / "analysis")
    focus_db_path: str = str(ROOT_DIR / "data" / "focus.db")
    params_db_path: str = str(ROOT_DIR / "data" / "params.db")
    mineru_api_base: str = "https://mineru.net/api/v4"
    mineru_api_token: str = ""
    mineru_poll_interval_seconds: float = 2.0
    mineru_poll_timeout_seconds: int = 180
    analysis_llm_base_url: str = "https://api.siliconflow.cn/v1"
    analysis_llm_api_key: str = ""
    analysis_llm_model: str = "Qwen/Qwen2.5-7B-Instruct"
    analysis_llm_timeout_seconds: int = 90
    analysis_enable_llm_normalization: bool = True
    analysis_http_trust_env: bool = False
    auth_dev_totp_bypass: str = ""


settings = Settings()
