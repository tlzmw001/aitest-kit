"""外部 Mock 打分 HTTP 服务（非 RPC）"""
from __future__ import annotations

import json
import logging
import os
import random
import signal
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger(__name__)


class ExternalMockScorer:
    """外部评分逻辑：仅用于模拟 HTTP 打分服务"""

    def score(self, user_features: dict, context_features: dict, items: list) -> list:
        results = []
        for item in items:
            score = self._calculate_score(user_features, context_features, item.get("features", {}))
            results.append((item["item_id"], round(score, 4)))
        return results

    def _calculate_score(self, user_features: dict, context_features: dict, item_features: dict) -> float:
        # 外部服务默认基础分要求为 0.2
        base_score = 0.2

        if str(user_features.get("is_member", "")).lower() == "true":
            base_score += 0.1
        if str(context_features.get("channel", "")).lower() == "ad":
            base_score += 0.05

        popularity = float(item_features.get("popularity", 0))
        base_score += popularity * 0.08

        noise = random.uniform(-0.04, 0.04)
        return max(0.0, min(1.0, base_score + noise))


class ExternalScoringHandler(BaseHTTPRequestHandler):
    scorer = ExternalMockScorer()

    def do_POST(self):
        if self.path != "/score":
            self._write_json(404, {"code": 404, "message": "not found", "scores": []})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            request = json.loads(body.decode("utf-8"))

            user_features = dict(request.get("user_features", {}))
            context_features = dict(request.get("context_features", {}))
            items = list(request.get("items", []))

            results = self.scorer.score(user_features, context_features, items)
            payload = {
                "code": 0,
                "message": "success",
                "scores": [{"item_id": item_id, "score": score} for item_id, score in results],
            }
            self._write_json(200, payload)
        except Exception as e:
            logger.exception("external mock scoring failed")
            self._write_json(500, {"code": 5000, "message": str(e), "scores": []})

    def log_message(self, fmt, *args):
        # 统一接入 logging，避免默认 stderr 输出
        logger.info("external-mock %s - %s", self.address_string(), fmt % args)

    def _write_json(self, status_code: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def serve(port: int = 50053):
    server = ThreadingHTTPServer(("0.0.0.0", port), ExternalScoringHandler)
    print(f"External mock scoring server started on port {port}")

    def shutdown(signum, frame):
        print("\nShutting down external mock scoring server...")
        server.shutdown()
        server.server_close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("EXTERNAL_SCORING_PORT", "50053"))
    serve(port)
