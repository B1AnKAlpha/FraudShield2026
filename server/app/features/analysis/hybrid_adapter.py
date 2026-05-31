from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.core.config import settings


class HybridAnalysisAdapter:
    def __init__(self) -> None:
        self.python_executable = Path(settings.legacy_torch_python)
        self.model_dir = Path(settings.legacy_model_dir)
        self.static_data_path = Path(settings.legacy_static_data_path)
        self.script_path = Path(__file__).resolve().parents[3] / "scripts" / "legacy_hybrid_infer.py"
        try:
            self.conda_executable = self.python_executable.parents[2] / "Scripts" / "conda.exe"
            self.conda_env_name = self.python_executable.parent.name
        except IndexError:
            self.conda_executable = Path("conda")
            self.conda_env_name = ""

    def available(self) -> bool:
        return (
            (self.conda_executable.exists() or self.python_executable.exists())
            and self.model_dir.exists()
            and self.static_data_path.exists()
            and self.script_path.exists()
        )

    def _build_command(self, input_path: Path, output_path: Path) -> list[str]:
        if self.conda_executable.exists() and self.conda_env_name:
            return [
                str(self.conda_executable),
                "run",
                "-n",
                self.conda_env_name,
                "python",
                str(self.script_path),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--static-data",
                str(self.static_data_path),
                "--model-dir",
                str(self.model_dir),
            ]
        return [
            str(self.python_executable),
            str(self.script_path),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--static-data",
            str(self.static_data_path),
            "--model-dir",
            str(self.model_dir),
        ]

    def predict(self, *, transactions: list[dict], work_dir: Path, inference_params: dict | None = None) -> dict:
        if not transactions:
            raise RuntimeError("没有可用于旧版混合模型推理的结构化交易数据")
        if not self.available():
            raise RuntimeError("旧版混合模型依赖不完整")

        work_dir.mkdir(parents=True, exist_ok=True)
        input_path = work_dir / "hybrid_input.json"
        output_path = work_dir / "hybrid_output.json"
        input_path.write_text(
            json.dumps(
                {
                    "transactions": transactions,
                    "inference_params": inference_params or {},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        completed = subprocess.run(
            self._build_command(input_path, output_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=180,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(detail or "旧版混合模型推理失败")
        if not output_path.exists():
            raise RuntimeError("旧版混合模型未生成输出文件")
        return json.loads(output_path.read_text(encoding="utf-8"))


hybrid_adapter = HybridAnalysisAdapter()
