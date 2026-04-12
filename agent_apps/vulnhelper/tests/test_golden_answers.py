import json
from pathlib import Path


def test_golden_files_exist() -> None:
    root = Path(__file__).resolve().parent
    assert json.loads((root / "vuln_agent_cases.json").read_text(encoding="utf-8"))
    assert json.loads((root / "vuln_golden_answers.json").read_text(encoding="utf-8"))

