"""Verify durable claims and run-owner fencing."""
from dataclasses import asdict
import pytest

from aitest_kit.log_assertions.config import RunSettings
from aitest_kit.log_assertions.run import owner_lock
from aitest_kit.log_assertions.store import RunStore


def test_recovery_preserves_frozen_input_and_rejects_stale_owner(tmp_path):
    path = tmp_path / "log-assertions.sqlite3"
    first = RunStore(path)
    first.create("example", tmp_path, asdict(RunSettings()), {})
    with owner_lock(tmp_path):
        first.own()
        with pytest.raises(ValueError, match="another process"), owner_lock(tmp_path):
            pytest.fail("two coordinators hold the same run lock")
        first.update("INSERT INTO unit VALUES(?,?,?,?)", (0, str(tmp_path), "[]", "[]"))
        attempt = first.start_attempt(0, "test_a.py::test_query[param]", "gw0")
        request = first.register(attempt, "reply", "source", [{"executor_version": 1}], [{}], 123456, 10)
        first.bind(request, "example")
        first.freeze(request, [{"score": 1}])
        first.update("UPDATE request SET state='READY' WHERE id=?", (request,))
        claim = first.claim(request)

    with owner_lock(tmp_path):
        second = RunStore(path)
        second.own()
        second.recover()
        row, = second.read("SELECT * FROM request")
        assert (row["state"], row["correlation"], row["deadline"], row["inputs"]) == (
            "WAITING", "example", 123456, '[{"score": 1}]',
        )
        with pytest.raises(RuntimeError, match="stale"):
            first.complete(request, "PASSED", {"state": "PASSED"}, claim=claim)
        second.update("UPDATE request SET state='READY' WHERE id=?", (request,))
        live_claim = second.claim(request)
        assert live_claim != claim
        assert not second.complete(request, "PASSED", {"state": "PASSED"}, claim=claim)
        assert second.complete(request, "PASSED", {"state": "PASSED"}, claim=live_claim)
        assert len(second.read("SELECT * FROM result")) == 1
