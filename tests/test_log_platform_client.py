import asyncio
import json

import httpx
import pytest

from aitest_kit.log_assertions.client import LogPlatformClient, LogPlatformError


def run_http(handler, operation, **client_options):
    async def execute():
        async with LogPlatformClient("http://logs.invalid", "fixture-token",
                                     transport=httpx.MockTransport(handler), **client_options) as client:
            return await operation(client, asyncio.get_running_loop().time() + 2)
    return asyncio.run(execute())


@pytest.mark.parametrize("failure", [None, "duplicate", "version", "expired", "budget"])
def test_snapshot_pagination_and_no_partial_success(failure):
    def handle(request):
        assert request.url.path == "/v1/requests/~YS9i/events"
        assert request.url.params["expected_version"] == "8"
        assert request.url.params["include_data"] == "true"
        cursor = request.url.params.get("cursor")
        if cursor and failure in ("version", "expired"):
            if failure == "version":
                return httpx.Response(409, json={"error": {"code": "VERSION_CONFLICT"}})
            return httpx.Response(410, json={"error": {"details": {"availability": "EXPIRED"}}})
        event = {"event_id": "e1" if not cursor or failure == "duplicate" else "e2",
                 "offset": "43" if cursor else "40", "partition": 0}
        if cursor:
            event["data"] = {"large": 9007199254740993, "empty": None, "ok": False}
        return httpx.Response(200, json={
            "request": {"source_id": "demo", "reqId": "a/b", "version": 8,
                        "capture_state": "COMPLETE", "availability": "AVAILABLE", "event_count": 2},
            "upper_offset": "43", "items": [event], "next_cursor": None if cursor else "page2",
        })

    async def operation(client, deadline):
        return await client.read_snapshot("demo", "a/b", 8, deadline=deadline)

    if failure:
        with pytest.raises(LogPlatformError) as error:
            kwargs = {"snapshot_max_events": 1} if failure == "budget" else {}
            run_http(handle, operation, **kwargs)
        assert error.value.code == {
            "duplicate": "PLATFORM_PROTOCOL_ERROR", "version": "VERSION_CONFLICT",
            "expired": "EVIDENCE_UNAVAILABLE", "budget": "EVIDENCE_LIMIT",
        }[failure]
    else:
        response = run_http(handle, operation)
        assert "data" not in response["items"][0]
        assert response["items"][1]["data"] == {"large": 9007199254740993, "empty": None, "ok": False}


def test_status_is_exact_and_cleanup_key_belongs_to_caller():
    sent = []

    def handle(request):
        payload = json.loads(request.content)
        assert payload == {"source_id": "another", "reqIds": ["same"]}
        if request.url.path.endswith("status"):
            return httpx.Response(200, json={"items": [{"reqId": "same", "result": "NOT_FOUND", "request": None}]})
        sent.append(request.headers["idempotency-key"])
        if len(sent) == 1:
            raise httpx.ReadError("response lost", request=request)
        return httpx.Response(202, json={"job_id": "j", "target_count": 1, "source_id": "another",
                                         "accepted_at": "2026-11-19T06:00:00Z", "state": "PENDING"})

    async def operation(client, deadline):
        assert (await client.get_statuses("another", ["same"], deadline=deadline))[0]["result"] == "NOT_FOUND"
        with pytest.raises(LogPlatformError) as error:
            await client.submit_cleanup("another", ["same"], "key", deadline=deadline)
        assert error.value.retryable
        return await client.submit_cleanup("another", ["same"], "key", deadline=deadline)

    assert run_http(handle, operation)["job_id"] == "j"
    assert sent == ["key", "key"]


def test_reads_platform_limits_and_does_not_split_forbidden_batches():
    calls = []

    def handle(request):
        calls.append(request.url.path)
        if request.url.path.endswith("ui-settings"):
            return httpx.Response(200, json={"batch_reqids_max": 3, "page_size_max": 2})
        return httpx.Response(403, json={"error": {"code": "NOT_AUTHORIZED"}})

    async def operation(client, deadline):
        for _ in range(2):
            assert await client.get_limits(deadline=deadline) == {"batch_reqids_max": 3, "page_size_max": 2}
        with pytest.raises(ValueError):
            await client.get_statuses("demo", ["1", "2", "3", "4"], deadline=deadline)
        with pytest.raises(LogPlatformError) as error:
            await client.get_statuses("demo", ["1", "2"], deadline=deadline)
        assert error.value.status == 403 and not error.value.retryable

    run_http(handle, operation)
    assert calls == ["/v1/ui-settings", "/v1/requests/status"]
