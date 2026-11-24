import httpx

from aitest_kit.log_assertions import bind_log_request, log_capture_requested


class LogDemoHarness:
    def __init__(self, url, source_id):
        self.url = url
        self.source_id = source_id

    def query(self):
        capture = log_capture_requested()
        headers = {"X-Demo-Capture": "true"} if capture else {}
        with httpx.Client(transport=httpx.HTTPTransport()) as client:
            response = client.post(self.url, headers=headers)
            response.raise_for_status()
            reply = response.json()
        if capture:
            bind_log_request(self.source_id, reply["trace_id"])
        return reply
