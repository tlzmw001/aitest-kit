"""Bounded, single-attempt HTTP calls to the log platform."""
from __future__ import annotations

import asyncio
import base64
import json
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import httpx

from .config import normalize_platform_url
from .values import decimal_number

_MAX_BYTES = 8000000
_MAX_EVENTS = 10000
_MAX_PAGES = 1000
_CAPTURE_STATES = {"COMPLETE", "COLLECTING", "INCOMPLETE", "TIMED_OUT", "OBSERVED"}
_AVAILABILITY = {"AVAILABLE", "DELETE_PENDING", "DELETED", "EXPIRED"}
SINGLE_PARTITION = "single_partition"
PARTITIONED = "partitioned"


def source_evidence_view(source):
    if source is None:
        return None
    view = source.get("evidence_view", SINGLE_PARTITION if source["completion_supported"] else None)
    return view if view in (SINGLE_PARTITION, PARTITIONED) else None


class LogPlatformError(RuntimeError):
    def __init__(self, code, *, status=None, retryable=False, refresh_snapshot=False,
                 retry_after=None, availability=None, limit=None):
        super().__init__(f"log platform: {code}" + (f" (HTTP {status})" if status else ""))
        self.code = code
        self.status = status
        self.retryable = retryable
        self.refresh_snapshot = refresh_snapshot
        self.retry_after = retry_after
        self.availability = availability
        self.limit = limit


def _require(condition):
    if not condition:
        raise LogPlatformError("PLATFORM_PROTOCOL_ERROR")


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _request_segment(req_id):
    if "/" in req_id or req_id in (".", "..") or req_id.startswith("~"):
        return "~" + base64.urlsafe_b64encode(req_id.encode("utf-8")).decode("ascii").rstrip("=")
    return quote(req_id, safe="")


def _retry_after(raw, remaining):
    if not raw:
        return None
    try:
        seconds = float(raw) if raw.isascii() and raw.isdecimal() else (
            parsedate_to_datetime(raw).astimezone(timezone.utc) - datetime.now(timezone.utc)
        ).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return None
    if math.isfinite(seconds):
        return max(0, min(seconds, max(0, remaining)))
    return None


def _http_error(status, response, retry_after, remaining):
    error = response.get("error") if isinstance(response, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    details = error.get("details") if isinstance(error, dict) else None
    details = details if isinstance(details, dict) else {}
    retryable = status in (408, 429) or 500 <= status <= 599
    refresh = (status, code) in ((409, "VERSION_CONFLICT"), (422, "INVALID_CURSOR"))
    allowed = ("VERSION_CONFLICT", "INVALID_CURSOR", "IDEMPOTENCY_CONFLICT", "INVALID_ARGUMENT",
               "TOO_MANY_TARGETS", "EMPTY_TARGETS", "BUSY", "UNAVAILABLE")
    availability = details.get("availability")
    limit = details.get("limit")
    return LogPlatformError(
        code if code in allowed else "EVIDENCE_UNAVAILABLE" if status == 410 else "PLATFORM_HTTP_ERROR",
        status=status, retryable=retryable, refresh_snapshot=refresh,
        retry_after=_retry_after(retry_after, remaining) if status in (429, 503) else None,
        availability=availability if availability in tuple(_AVAILABILITY) else None,
        limit=limit if (status, code) == (422, "TOO_MANY_TARGETS") and _integer(limit, 1) else None,
    )


def _check_request(request, source_id, req_id):
    _require(isinstance(request, dict))
    _require(request.get("source_id") == source_id and request.get("reqId") == req_id)
    _require("capture_state" in request)
    capture = request.get("capture_state")
    availability = request.get("availability")
    _require(availability in tuple(_AVAILABILITY))
    _require(capture is None or capture in tuple(_CAPTURE_STATES))
    _require(capture is not None or availability != "AVAILABLE")
    _require(_integer(request.get("event_count")))
    count = request.get("expected_event_count")
    _require(count is None or _integer(count, 1))
    if capture is not None:
        _require(_integer(request.get("version")))
    request_expiry(request)


def request_expiry(request):
    raw = request.get("expires_at")
    if raw is None:
        return None
    _require(isinstance(raw, str))
    try:
        date = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        _require(date.tzinfo is not None)
        return date.timestamp()
    except (ValueError, OverflowError, OSError):
        raise LogPlatformError("PLATFORM_PROTOCOL_ERROR") from None


def _offset(value):
    _require(isinstance(value, str) and value.isascii() and value.isdecimal() and len(value) <= 19)
    return int(value)


class LogPlatformClient:
    def __init__(self, base_url, token, *, http_timeout_seconds=5, snapshot_max_bytes=_MAX_BYTES,
                 snapshot_max_events=_MAX_EVENTS, snapshot_max_pages=_MAX_PAGES, transport=None):
        url = normalize_platform_url(str(base_url) if isinstance(base_url, httpx.URL) else base_url)
        if not _text(token):
            raise ValueError("log platform token is required")
        if type(http_timeout_seconds) not in (float, int) or not math.isfinite(http_timeout_seconds) or http_timeout_seconds <= 0:
            raise ValueError("invalid HTTP timeout")
        if any(not _integer(value, 1) or value > maximum for value, maximum in (
            (snapshot_max_bytes, _MAX_BYTES), (snapshot_max_events, _MAX_EVENTS), (snapshot_max_pages, _MAX_PAGES),
        )):
            raise ValueError("invalid snapshot budget")
        self.timeout = http_timeout_seconds
        self.snapshot_max_bytes = snapshot_max_bytes
        self.snapshot_max_events = snapshot_max_events
        self.snapshot_max_pages = snapshot_max_pages
        self.batch_size = 200
        self.page_size = 100
        self._limits_loaded = False
        self.readiness_batch_supported = False
        self._client = httpx.AsyncClient(
            base_url=url, headers={"Authorization": f"Bearer {token}"},
            transport=transport if transport is not None else httpx.AsyncHTTPTransport(),
            trust_env=False, follow_redirects=False,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.aclose()

    async def aclose(self):
        await self._client.aclose()

    async def _read(self, method, path, *, deadline, status=200, byte_limit=_MAX_BYTES,
                    parse_float=None, **kwargs):
        loop = asyncio.get_running_loop()
        left = deadline - loop.time()
        if not math.isfinite(left) or left <= 0:
            raise LogPlatformError("DEADLINE_EXCEEDED")
        timeout = min(self.timeout, left)

        async def receive():
            async with self._client.stream(method, path, timeout=timeout, **kwargs) as response:
                body = bytearray()
                cap = byte_limit if response.status_code == status else _MAX_BYTES
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > cap:
                        raise LogPlatformError("EVIDENCE_LIMIT")
                    body.extend(chunk)
                try:
                    data = await asyncio.to_thread(json.loads, body, parse_constant=_reject_nonfinite,
                                      parse_float=parse_float or _finite_float)
                except (ValueError, RecursionError):
                    data = None
                if response.status_code != status:
                    raise _http_error(response.status_code, data, response.headers.get("Retry-After"), deadline - loop.time())
                _require(isinstance(data, dict))
                return data, len(body)

        try:
            result = await asyncio.wait_for(receive(), timeout=timeout)
            if loop.time() >= deadline:
                raise LogPlatformError("DEADLINE_EXCEEDED")
            return result
        except asyncio.TimeoutError:
            if loop.time() < deadline:
                raise LogPlatformError("PLATFORM_NETWORK_ERROR", retryable=True) from None
            raise LogPlatformError("DEADLINE_EXCEEDED") from None
        except httpx.RequestError:
            raise LogPlatformError("PLATFORM_NETWORK_ERROR", retryable=True) from None

    async def list_sources(self, *, deadline):
        data, _ = await self._read("GET", "/v1/sources", deadline=deadline)
        items = data.get("items")
        _require(isinstance(items, list))
        seen = set()
        for item in items:
            _require(isinstance(item, dict) and _text(item.get("source_id")))
            _require(item["source_id"] not in seen and type(item.get("enabled")) is bool
                     and type(item.get("completion_supported")) is bool
                     and isinstance(item.get("actions"), list) and all(_text(a) for a in item["actions"]))
            seen.add(item["source_id"])
        return items

    async def get_limits(self, *, deadline):
        if not self._limits_loaded:
            data, _ = await self._read("GET", "/v1/ui-settings", deadline=deadline)
            batch, page = data.get("batch_reqids_max"), data.get("page_size_max")
            readiness = data.get("readiness_batch_supported", False)
            _require(_integer(batch, 1) and _integer(page, 1) and type(readiness) is bool)
            self.batch_size, self.page_size = min(200, batch), min(100, page)
            self.readiness_batch_supported = readiness
            self._limits_loaded = True
        return {"batch_reqids_max": self.batch_size, "page_size_max": self.page_size}

    async def get_statuses(self, source_id, correlation_values, *, deadline):
        payload = _batch(source_id, correlation_values, self.batch_size)
        data, _ = await self._read("POST", "/v1/requests/status", deadline=deadline, json=payload)
        return self._check_statuses(data, [(source_id, req_id) for req_id in payload["reqIds"]])

    async def get_readiness(self, pairs, *, deadline):
        if (not isinstance(pairs, (list, tuple)) or not 1 <= len(pairs) <= self.batch_size
                or not all(isinstance(pair, (list, tuple)) and len(pair) == 2
                           and all(_text(value) for value in pair) for pair in pairs)
                or len({tuple(pair) for pair in pairs}) != len(pairs)):
            raise ValueError("expected a bounded batch of unique source and request ID pairs")
        payload = {"items": [{"source_id": source, "reqId": req_id} for source, req_id in pairs]}
        data, _ = await self._read("POST", "/v1/requests/readiness", deadline=deadline, json=payload)
        return self._check_statuses(data, pairs, require_source=True)

    @staticmethod
    def _check_statuses(data, pairs, *, require_source=False):
        items = data.get("items")
        _require(isinstance(items, list) and len(items) == len(pairs))
        for item, (source_id, req_id) in zip(items, pairs):
            _require(isinstance(item, dict) and item.get("reqId") == req_id and "request" in item)
            if require_source:
                _require(item.get("source_id") == source_id)
            if item.get("result") == "FOUND":
                _check_request(item["request"], source_id, req_id)
            else:
                _require(item.get("result") == "NOT_FOUND" and item["request"] is None)
        return items

    async def read_snapshot(self, source_id, correlation_value, expected_version, *, deadline,
                            evidence_view=SINGLE_PARTITION):
        if (not _text(source_id) or not _text(correlation_value) or not _integer(expected_version)
                or evidence_view not in (SINGLE_PARTITION, PARTITIONED)):
            raise ValueError("invalid snapshot request")
        path = f"/v1/requests/{_request_segment(correlation_value)}/events"
        params = {"source_id": source_id, "expected_version": expected_version,
                  "include_data": "true", "page_size": self.page_size}
        partitioned = evidence_view == PARTITIONED
        if partitioned:
            params["evidence_view"] = evidence_view
        events, event_ids, cursors = [], set(), set()
        previous_position = upper_offset = upper_number = event_count = None
        budget = self.snapshot_max_bytes
        for page in range(self.snapshot_max_pages):
            data, size = await self._read("GET", path, deadline=deadline, byte_limit=budget,
                                          parse_float=decimal_number, params=params)
            budget -= size
            request = data.get("request")
            _check_request(request, source_id, correlation_value)
            _require(request["capture_state"] == "COMPLETE" and request["availability"] == "AVAILABLE"
                     and request["version"] == expected_version)
            if partitioned:
                _require(data.get("evidence_view") == PARTITIONED and "upper_offset" not in data)
            else:
                _require(data.get("evidence_view", SINGLE_PARTITION) == SINGLE_PARTITION and "upper_offset" in data)
            if page == 0:
                upper_offset, event_count = data.get("upper_offset"), request["event_count"]
                if event_count > self.snapshot_max_events:
                    raise LogPlatformError("EVIDENCE_LIMIT")
                upper_number = None if upper_offset is None else _offset(upper_offset)
            _require(data.get("upper_offset") == upper_offset and request["event_count"] == event_count)
            items, cursor = data.get("items"), data.get("next_cursor")
            _require(isinstance(items, list) and "next_cursor" in data)
            if len(events) + len(items) > self.snapshot_max_events:
                raise LogPlatformError("EVIDENCE_LIMIT")
            for event in items:
                _require(isinstance(event, dict) and _text(event.get("event_id")) and _integer(event.get("partition")))
                offset = _offset(event.get("offset"))
                position = (event["partition"], offset)
                if not partitioned:
                    _require(upper_number is not None and offset <= upper_number)
                    _require(previous_position is None or position[0] == previous_position[0])
                _require(previous_position is None or position > previous_position)
                _require(event["event_id"] not in event_ids)
                event_ids.add(event["event_id"])
                previous_position = position
                events.append(event)
            if cursor is None:
                if asyncio.get_running_loop().time() >= deadline:
                    raise LogPlatformError("DEADLINE_EXCEEDED")
                _require(len(events) == event_count)
                if partitioned:
                    return {"request": request, "evidence_view": PARTITIONED, "items": events}
                _require((previous_position[1] if previous_position else None) == upper_number)
                return {"request": request, "upper_offset": upper_offset, "items": events}
            _require(items and _text(cursor) and cursor not in cursors and len(events) < event_count)
            cursors.add(cursor)
            params["cursor"] = cursor
        raise LogPlatformError("EVIDENCE_LIMIT")

    async def submit_cleanup(self, source_id, correlation_values, idempotency_key, *, deadline):
        if not _text(idempotency_key):
            raise ValueError("cleanup requires an idempotency key")
        payload = _batch(source_id, correlation_values, self.batch_size)
        data, _ = await self._read("POST", "/v1/cleanup", deadline=deadline, status=202, json=payload,
                                   headers={"Idempotency-Key": idempotency_key})
        _require(data.get("source_id") == source_id and _text(data.get("job_id"))
                 and _text(data.get("state")) and _text(data.get("accepted_at"))
                 and _integer(data.get("target_count"), 1) and data["target_count"] == len(payload["reqIds"]))
        return data

    async def get_cleanup(self, source_id, job_id, cursor=None, *, deadline):
        if not _text(source_id) or not _text(job_id) or (cursor is not None and not _text(cursor)):
            raise ValueError("invalid cleanup receipt request")
        params = {"source_id": source_id}
        if cursor is not None:
            params["cursor"] = cursor
        data, _ = await self._read("GET", f"/v1/cleanup/{_request_segment(job_id)}", deadline=deadline, params=params)
        job = data.get("job")
        _require(isinstance(job, dict) and job.get("source_id") == source_id and job.get("job_id") == job_id
                 and isinstance(data.get("items"), list) and "next_cursor" in data
                 and (data["next_cursor"] is None or _text(data["next_cursor"])))
        return data


def _batch(source, ids, maximum):
    if (not _text(source) or not isinstance(ids, (tuple, list)) or not 1 <= len(ids) <= maximum
            or not all(_text(req_id) for req_id in ids) or len(set(ids)) != len(ids)):
        raise ValueError("expected a source and a bounded batch of unique request IDs")
    return {"source_id": source, "reqIds": list(ids)}


def _reject_nonfinite(value):
    raise ValueError("invalid JSON number")


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        _reject_nonfinite(value)
    return result
