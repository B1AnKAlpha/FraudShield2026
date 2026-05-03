from __future__ import annotations

from app.core.config import settings
from app.shared.db import SQLiteRepository
from app.shared.time import utc_now


DEFAULT_STATE = {
    "software_current_version": "1.0.3",
    "software_latest_version": "1.0.3",
    "model_current_version": "1.56",
    "model_latest_version": "1.56",
    "parameter_current_version": "2.5",
    "parameter_latest_version": "2.5",
    "fraud_decision_threshold": "0.5",
    "fraud_meta_weight": "1.0",
    "fraud_gru_weight": "0.0",
    "fraud_xgb_weight": "0.0",
    "advanced_high_risk_score_threshold": "0.5",
    "advanced_medium_risk_score_threshold": "0.3",
    "advanced_high_confidence_threshold": "0.85",
    "advanced_medium_confidence_threshold": "0.7",
    "dynamic_high_risk_threshold": "50000",
    "dynamic_medium_risk_threshold": "10000",
    "dynamic_self_attention_enabled": "1",
    "dynamic_adaptive_threshold_enabled": "1",
    "updated_at": utc_now(),
}


class ParamsRepository(SQLiteRepository):
    def __init__(self, db_path: str):
        super().__init__(db_path)

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS params_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    software_current_version TEXT NOT NULL,
                    software_latest_version TEXT NOT NULL,
                    model_current_version TEXT NOT NULL,
                    model_latest_version TEXT NOT NULL,
                    parameter_current_version TEXT NOT NULL,
                    parameter_latest_version TEXT NOT NULL,
                    fraud_decision_threshold TEXT NOT NULL,
                    fraud_meta_weight TEXT NOT NULL,
                    fraud_gru_weight TEXT NOT NULL,
                    fraud_xgb_weight TEXT NOT NULL,
                    advanced_high_risk_score_threshold TEXT NOT NULL,
                    advanced_medium_risk_score_threshold TEXT NOT NULL,
                    advanced_high_confidence_threshold TEXT NOT NULL,
                    advanced_medium_confidence_threshold TEXT NOT NULL,
                    dynamic_high_risk_threshold TEXT NOT NULL,
                    dynamic_medium_risk_threshold TEXT NOT NULL,
                    dynamic_self_attention_enabled TEXT NOT NULL,
                    dynamic_adaptive_threshold_enabled TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            existing_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(params_state)").fetchall()
            }
            migration_columns = [
                ("fraud_decision_threshold", "TEXT NOT NULL DEFAULT '0.5'"),
                ("fraud_meta_weight", "TEXT NOT NULL DEFAULT '1.0'"),
                ("fraud_gru_weight", "TEXT NOT NULL DEFAULT '0.0'"),
                ("fraud_xgb_weight", "TEXT NOT NULL DEFAULT '0.0'"),
                ("advanced_high_risk_score_threshold", "TEXT NOT NULL DEFAULT '0.5'"),
                ("advanced_medium_risk_score_threshold", "TEXT NOT NULL DEFAULT '0.3'"),
                ("advanced_high_confidence_threshold", "TEXT NOT NULL DEFAULT '0.85'"),
                ("advanced_medium_confidence_threshold", "TEXT NOT NULL DEFAULT '0.7'"),
            ]
            for column_name, ddl in migration_columns:
                if column_name not in existing_columns:
                    connection.execute(f"ALTER TABLE params_state ADD COLUMN {column_name} {ddl}")
            exists = connection.execute("SELECT 1 FROM params_state WHERE id = 1").fetchone()
            if not exists:
                columns = ", ".join(["id", *DEFAULT_STATE.keys()])
                placeholders = ", ".join(["?"] * (len(DEFAULT_STATE) + 1))
                connection.execute(
                    f"INSERT INTO params_state ({columns}) VALUES ({placeholders})",
                    (1, *DEFAULT_STATE.values()),
                )
            else:
                legacy_columns = {
                    "fraud_decision_threshold": "fraud_max_depth",
                    "fraud_meta_weight": "fraud_learning_rate",
                    "fraud_gru_weight": "fraud_subsample",
                    "fraud_xgb_weight": "fraud_colsample_bytree",
                    "advanced_high_risk_score_threshold": "advanced_gamma",
                    "advanced_medium_risk_score_threshold": "advanced_reg_alpha",
                    "advanced_high_confidence_threshold": "advanced_reg_lambda",
                    "advanced_medium_confidence_threshold": "advanced_max_leaves",
                }
                existing_columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(params_state)").fetchall()
                }
                for new_column, old_column in legacy_columns.items():
                    if old_column in existing_columns:
                        connection.execute(
                            f"""
                            UPDATE params_state
                            SET {new_column} = COALESCE(NULLIF(TRIM({new_column}), ''), {old_column})
                            WHERE id = 1
                            """
                        )
            connection.commit()

    def get_state(self) -> dict:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM params_state WHERE id = 1").fetchone()
        return dict(row)

    def update_state(self, updates: dict) -> dict:
        if not updates:
            return self.get_state()

        assignments = []
        values: list[object] = []
        for key, value in updates.items():
            assignments.append(f"{key} = ?")
            values.append(value)
        assignments.append("updated_at = ?")
        values.append(utc_now())
        values.append(1)

        with self.connect() as connection:
            connection.execute(
                f"UPDATE params_state SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
            connection.commit()
        return self.get_state()


repository = ParamsRepository(settings.params_db_path)
