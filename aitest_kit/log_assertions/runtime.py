"""Record request steps under the actual pytest case attempt."""
import time


class SQLiteRecorder:
    def __init__(self, store, attempt, request_timeout, pending_limit):
        self.store = store
        self.attempt = attempt
        self.request_timeout = request_timeout
        self.pending_limit = pending_limit

    def register(self, request_step, source_id, rules, inputs):
        return self.store.register(self.attempt, request_step, source_id, rules, inputs,
                                   time.time() + self.request_timeout, self.pending_limit)

    def bind(self, handle, correlation_value):
        self.store.bind(handle, correlation_value)

    def freeze(self, handle, inputs):
        self.store.freeze(handle, inputs)

    def fail(self, handle, code):
        self.store.complete(handle, "ERROR", {"state": "ERROR", "code": code})
