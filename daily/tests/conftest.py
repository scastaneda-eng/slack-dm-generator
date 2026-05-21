"""Make repo root + daily/ importable for tests."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "daily"))


@pytest.fixture(autouse=True)
def _stub_audit_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """audit_log() reads tokens.json at call time; stub it for unit tests."""
    import config as _config
    import refresh as _refresh
    monkeypatch.setattr(_config, "audit_log", lambda *_a, **_k: None)
    monkeypatch.setattr(_refresh, "audit_log", lambda *_a, **_k: None)
