from __future__ import annotations

from pathlib import Path

import pytest
from scripts.serve import acquire_server_lock


def test_server_lock_prevents_a_second_coordinator(tmp_path: Path) -> None:
    lock_path = tmp_path / "server.lock"
    first = acquire_server_lock(lock_path)
    try:
        with pytest.raises(SystemExit, match="already running"):
            acquire_server_lock(lock_path)
    finally:
        first.close()

    replacement = acquire_server_lock(lock_path)
    replacement.close()
