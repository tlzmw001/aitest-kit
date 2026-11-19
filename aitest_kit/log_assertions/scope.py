"""Request-scoped bridge between generated calls and a run recorder."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from threading import get_ident
from typing import Any, Protocol

from .values import LogInputError, freeze_expected, resolve_pointer

_logger = logging.getLogger(__name__)


class LogBindingError(RuntimeError):
    code = "LOG_BINDING_ERROR"


class RequestRecorder(Protocol):
    def register(self, request_step: str, source_id: str, rules: list[dict], inputs: list[dict]) -> Any: ...
    def bind(self, handle: Any, correlation_value: str) -> None: ...
    def freeze(self, handle: Any, inputs: list[dict]) -> None: ...
    def fail(self, handle: Any, code: str) -> None: ...


_recorder: ContextVar[RequestRecorder | None] = ContextVar("log_request_recorder", default=None)
_scope: ContextVar[RequestScope | None] = ContextVar("log_request_scope", default=None)


@contextmanager
def use_request_recorder(recorder: RequestRecorder):
    token = _recorder.set(recorder)
    try:
        yield
    finally:
        _recorder.reset(token)


class RequestScope:
    def __init__(self, recorder, handle, source_id, inputs, pointers):
        self.recorder = recorder
        self.handle = handle
        self.source_id = source_id
        self.inputs = inputs
        self.pointers = pointers
        self.correlation_value = None
        self.frozen = False
        self.active = True
        self.thread = get_ident()

    def freeze_response(self, response: Any) -> None:
        if not self.active or self.thread != get_ident() or self.frozen:
            raise LogBindingError("request scope is closed or was already frozen")
        if self.correlation_value is None:
            raise LogBindingError("Harness did not bind a log request")
        inputs = [{**static, **{key: resolve_pointer(response, pointer) for key, pointer in dynamic.items()}}
                  for static, dynamic in zip(self.inputs, self.pointers)]
        frozen = freeze_expected(inputs)
        try:
            self.recorder.freeze(self.handle, frozen)
        except Exception as exc:
            raise LogBindingError("could not persist frozen log assertion inputs") from exc
        self.frozen = True


def log_capture_requested() -> bool:
    scope = _scope.get()
    return scope is not None and scope.active and scope.thread == get_ident()


def bind_log_request(source_id: str, correlation_value: str) -> bool:
    if not log_capture_requested():
        return False
    scope = _scope.get()
    if source_id != scope.source_id or not isinstance(correlation_value, str) or not correlation_value.strip():
        raise LogBindingError("invalid log request source or correlation value")
    if scope.correlation_value == correlation_value:
        return True
    if scope.correlation_value is not None:
        raise LogBindingError("log request already has a different correlation value")
    try:
        scope.recorder.bind(scope.handle, correlation_value)
    except Exception as exc:
        raise LogBindingError("could not persist log request binding") from exc
    scope.correlation_value = correlation_value
    return True


@contextmanager
def log_request_step(*, request_step, source_id, rules, expected_inputs):
    recorder = _recorder.get()
    if recorder is None:
        raise LogBindingError("log assertion requires an active AITest run coordinator")
    inputs, pointers = [], []
    for rule in rules:
        static, dynamic = {}, {}
        for key, provider in rule["expected"].items():
            if "from_response" in provider:
                dynamic[key] = provider["from_response"]
            elif "from_var" in provider:
                try:
                    static[key] = expected_inputs[provider["from_var"]]
                except KeyError as exc:
                    raise LogInputError("missing expected profile variable") from exc
            else:
                static[key] = provider["literal"]
        inputs.append(static)
        pointers.append(dynamic)
    inputs = freeze_expected(inputs)
    try:
        handle = recorder.register(request_step, source_id, rules, inputs)
    except Exception as exc:
        raise LogBindingError("could not register log request") from exc
    scope = RequestScope(recorder, handle, source_id, inputs, pointers)
    token = _scope.set(scope)
    try:
        yield scope
        if not scope.frozen:
            scope.freeze_response(None)
    except BaseException as original:
        try:
            if not scope.frozen:
                if scope.correlation_value is None or isinstance(original, LogBindingError):
                    recorder.fail(handle, "LOG_BINDING_ERROR")
                elif not any(pointers) and not isinstance(original, (LogBindingError, LogInputError)):
                    scope.freeze_response(None)
                else:
                    recorder.fail(handle, "LOG_INPUT_ERROR")
        except Exception:
            _logger.error("could not persist log assertion failure")
        raise
    finally:
        scope.active = False
        _scope.reset(token)
