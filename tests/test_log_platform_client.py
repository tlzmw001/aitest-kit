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
            assert client.readiness_batch_supported is False
        with pytest.raises(ValueError):
            await client.get_statuses("demo", ["1", "2", "3", "4"], deadline=deadline)
        with pytest.raises(LogPlatformError) as error:
            await client.get_statuses("demo", ["1", "2"], deadline=deadline)
        assert error.value.status == 403 and not error.value.retryable

    run_http(handle, operation)
    assert calls == ["/v1/ui-settings", "/v1/requests/status"]


def test_readiness_capability_requires_a_boolean():
    def handle(request):
        return httpx.Response(200, json={"batch_reqids_max": 3, "page_size_max": 2,
                                         "readiness_batch_supported": 1})

    async def operation(client, deadline):
        await client.get_limits(deadline=deadline)

    with pytest.raises(LogPlatformError, match="PLATFORM_PROTOCOL_ERROR"):
        run_http(handle, operation)


@pytest.mark.parametrize("failure", [None, "order", "missing", "duplicate", "identity", "count", "expiry", 403, 404, 422])
def test_cross_source_readiness(failure):
    pairs = [("main", "same"), ("perf", "same")]
    calls = []

    def handle(request):
        calls.append(request.url.path)
        if request.url.path.endswith("ui-settings"):
            return httpx.Response(200, json={"readiness_batch_supported": True, "batch_reqids_max": 2, "page_size_max": 10})
        assert request.url.path == "/v1/requests/readiness"
        keys = [{"source_id": source, "reqId": key} for source, key in pairs]
        assert json.loads(request.content) == {"items": keys}
        if isinstance(failure, int):
            return httpx.Response(failure, json={"error": {"code": "TOO_MANY_TARGETS", "details": {"limit": 1}}})
        items = [
            {**keys[0], "result": "NOT_FOUND", "request": None},
            {**keys[1], "result": "FOUND", "request": {
                **keys[1], "capture_state": "COLLECTING", "availability": "AVAILABLE",
                "version": 1, "event_count": 2, "expected_event_count": 2,
            }},
        ]
        if failure == "order":
            items.reverse()
        elif failure == "missing":
            items.pop()
        elif failure == "duplicate":
            items[1] = items[0]
        elif failure == "identity":
            items[1]["request"]["source_id"] = "main"
        elif failure == "count":
            items[1]["request"]["expected_event_count"] = True
        elif failure == "expiry":
            items[1]["request"]["expires_at"] = "invalid"
        return httpx.Response(200, json={"items": items})

    async def operation(client, deadline):
        await client.get_limits(deadline=deadline)
        assert client.readiness_batch_supported is True
        for invalid in ([], pairs + [("perf", "other")], pairs[:1] * 2, [("perf", "")]):
            with pytest.raises(ValueError):
                await client.get_readiness(invalid, deadline=deadline)
        if failure is None:
            return await client.get_readiness(pairs, deadline=deadline)
        with pytest.raises(LogPlatformError) as error:
            await client.get_readiness(pairs, deadline=deadline)
        if isinstance(failure, int):
            assert error.value.status == failure
            assert error.value.limit == (1 if failure == 422 else None)
        else:
            assert error.value.code == "PLATFORM_PROTOCOL_ERROR"

    result = run_http(handle, operation)
    if failure is None:
        assert [item["result"] for item in result] == ["NOT_FOUND", "FOUND"]
    assert calls == ["/v1/ui-settings", "/v1/requests/readiness"]


@pytest.mark.parametrize("failure", [None, "order", "duplicate", "missing", "view", "cursor", "budget"])
def test_partitioned_snapshot(failure):
    def handle(request):
        assert request.url.params["evidence_view"] == "partitioned"
        cursor = request.url.params.get("cursor")
        first = [{"event_id": "a", "partition": 0, "offset": "9"},
                 {"event_id": "b", "partition": 0, "offset": "10"}]
        last = [{"event_id": "c", "partition": 1, "offset": "9", "data": {"mediaId": "123"}}]
        if cursor and failure == "cursor":
            return httpx.Response(422, json={"error": {"code": "INVALID_CURSOR"}})
        if failure == "order":
            last[0]["partition"] = 0
        if failure == "duplicate":
            last[0]["event_id"] = "a"
        return httpx.Response(200, json={
            "evidence_view": "single_partition" if cursor and failure == "view" else "partitioned",
            "request": {"source_id": "perf", "reqId": "r", "version": 1, "event_count": 3,
                        "capture_state": "COMPLETE", "availability": "AVAILABLE"},
            "items": ([] if failure == "missing" else last) if cursor else first,
            "next_cursor": None if cursor else "next",
        })

    async def operation(client, deadline):
        return await client.read_snapshot("perf", "r", 1, deadline=deadline, evidence_view="partitioned")

    if failure:
        with pytest.raises(LogPlatformError) as error:
            run_http(handle, operation, **({"snapshot_max_pages": 1} if failure == "budget" else {}))
        assert error.value.code == {"cursor": "INVALID_CURSOR", "budget": "EVIDENCE_LIMIT"}.get(
            failure, "PLATFORM_PROTOCOL_ERROR")
    else:
        assert run_http(handle, operation)["items"][-1]["data"] == {"mediaId": "123"}


def test_snapshot_checks_use_exact_decimal_values():
    from aitest_kit.log_assertions.rules import evaluate_request

    def handle(request):
        return httpx.Response(200, content=b'''{
            "evidence_view":"partitioned","next_cursor":null,
            "request":{"source_id":"perf","reqId":"r","version":1,"event_count":1,
                       "capture_state":"COMPLETE","availability":"AVAILABLE"},
            "items":[{"event_id":"e","partition":0,"offset":"1",
                      "data":{"p":1.0000000000000001,"t":0.3}}]}''')

    async def operation(client, deadline):
        return await client.read_snapshot("perf", "r", 1, deadline=deadline, evidence_view="partitioned")

    events = run_http(handle, operation)["items"]
    result = evaluate_request([{"checks": ['assert events[0]["data"]["p"] == 1']}], events, [{}])
    assert result["state"] == "FAILED"
    result = evaluate_request([{"checks": [
        'assert events[0]["data"]["p"] == 1.0000000000000001',
        'assert events[0]["data"]["t"] == 0.1 + 0.2',
        'assert events[0]["data"]["t"] == expected["t"]',
    ]}], events, [{"t": 0.3}])
    assert result["state"] == "PASSED"


def test_snapshot_without_capture_state_is_a_protocol_error():
    def handle(request):
        return httpx.Response(200, json={
            "evidence_view": "partitioned", "next_cursor": None, "items": [],
            "request": {"source_id": "perf", "reqId": "r", "event_count": 0, "availability": "EXPIRED"},
        })

    async def operation(client, deadline):
        return await client.read_snapshot("perf", "r", 1, deadline=deadline, evidence_view="partitioned")

    with pytest.raises(LogPlatformError, match="PLATFORM_PROTOCOL_ERROR"):
        run_http(handle, operation)
