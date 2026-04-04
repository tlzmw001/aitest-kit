"""优惠券策略系统启动入口 — 同时启动 FastAPI (HTTP) 和 gRPC 服务"""

import json
import os
import sys
import signal
import subprocess
from pathlib import Path

import uvicorn

from ab_experiment_sdk import ConfigBasedABExperimentSDK
from coupon_system.config import (
    load_config,
    load_scene_routing_config,
    load_experiment_config,
    load_scene_experiment_mapping_config,
)
from coupon_system.services.redis_store import RedisStore
from coupon_system.services.scene_router import SceneRouter
from coupon_system.services.coarse_ranker import CoarseRanker
from coupon_system.services.feature_store import FeatureStore
from coupon_system.services.scoring_client import ScoringClient
from coupon_system.services.calibrator import Calibrator
from coupon_system.services.coupon_service import CouponBizService
from coupon_system.http_app import set_biz_service


def _load_ab_sdk_whitelist_from_env() -> dict:
    """
    读取业务侧传给 SDK 的白名单配置（可选）。

    环境变量格式：
    AB_SDK_WHITELIST_JSON='{"user_1":{"coarse_rank_exp_game":"cr_off"}}'
    """
    raw = os.environ.get("AB_SDK_WHITELIST_JSON", "").strip()
    if not raw:
        return {}
    try:
        val = json.loads(raw)
        return val if isinstance(val, dict) else {}
    except json.JSONDecodeError:
        print("Invalid AB_SDK_WHITELIST_JSON, ignore whitelist.")
        return {}


def compile_protos():
    """编译所有 proto 文件"""
    proto_dir = Path(__file__).parent / "protos"
    proto_files = [
        ("coupon.proto", "coupon_pb2.py", "coupon_pb2_grpc.py", "coupon_pb2"),
        ("scoring.proto", "scoring_pb2.py", "scoring_pb2_grpc.py", "scoring_pb2"),
    ]

    for proto_name, pb2_name, grpc_name, module_name in proto_files:
        proto_file = proto_dir / proto_name
        pb2_file = proto_dir / pb2_name

        if not proto_file.exists():
            print(f"Proto file not found: {proto_file}")
            sys.exit(1)

        if pb2_file.exists() and pb2_file.stat().st_mtime >= proto_file.stat().st_mtime:
            continue

        print(f"Compiling {proto_name}...")
        result = subprocess.run(
            [
                sys.executable, "-m", "grpc_tools.protoc",
                f"--proto_path={proto_dir}",
                f"--python_out={proto_dir}",
                f"--grpc_python_out={proto_dir}",
                str(proto_file),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Proto compilation failed: {result.stderr}")
            sys.exit(1)

        # 修复 grpc import 路径
        grpc_file = proto_dir / grpc_name
        if grpc_file.exists():
            content = grpc_file.read_text()
            old_import = f"import {module_name} as {module_name.replace('_', '__')}"
            new_import = f"from coupon_system.protos import {module_name} as {module_name.replace('_', '__')}"
            content = content.replace(old_import, new_import)
            grpc_file.write_text(content)

    # 确保 __init__.py 存在
    init_file = proto_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("")

    print("Proto compilation done.")


def start_grpc_server(biz_service: CouponBizService, port: int = 50051):
    """启动 gRPC 服务器（在单独线程中）"""
    from coupon_system.services.grpc_servicer import create_grpc_server

    server = create_grpc_server(biz_service, port)
    server.start()
    print(f"gRPC server started on port {port}")
    return server


def main():
    http_port = int(os.environ.get("HTTP_PORT", "8000"))
    grpc_port = int(os.environ.get("GRPC_PORT", "50051"))
    config_path = os.environ.get("COUPON_CONFIG_PATH", None)

    # 1. 编译 proto
    compile_protos()

    # 2. 加载配置
    config = load_config(config_path)
    scene_routing_config = load_scene_routing_config()
    experiment_config = load_experiment_config()
    scene_experiment_mapping_config = load_scene_experiment_mapping_config()
    print(f"Config loaded: scoring_service={config.scoring_service.host}:{config.scoring_service.port}")

    # 3. 初始化依赖
    redis_store = RedisStore(config.redis.url, config.redis.key_prefix)
    experiment_sdk = ConfigBasedABExperimentSDK(experiment_config)
    # 白名单属于 SDK 能力，业务侧通过 SDK 接口注入。
    experiment_sdk.set_whitelist(_load_ab_sdk_whitelist_from_env())
    scene_router = SceneRouter(scene_routing_config)
    coarse_ranker = CoarseRanker()
    feature_store = FeatureStore(
        redis_store=redis_store,
        user_feature_keys=config.user_feature_keys,
        item_feature_file=config.item_feature_file,
    )
    scoring_client = ScoringClient(
        host=config.scoring_service.host,
        port=config.scoring_service.port,
        timeout=config.scoring_service.timeout,
        enabled=config.scoring_service.enabled,
        external_host=config.external_scoring_service.host,
        external_port=config.external_scoring_service.port,
        external_timeout=config.external_scoring_service.timeout,
        external_enabled=config.external_scoring_service.enabled,
        external_path=config.external_scoring_service.path,
        external_user_id_salt=config.external_scoring_service.user_id_salt,
    )
    calibrator = Calibrator()

    biz_service = CouponBizService(
        config=config,
        redis_store=redis_store,
        experiment_sdk=experiment_sdk,
        scene_experiment_mapping=scene_experiment_mapping_config.scene_experiments,
        default_scene_experiments=scene_experiment_mapping_config.default_experiments,
        scene_router=scene_router,
        coarse_ranker=coarse_ranker,
        feature_store=feature_store,
        scoring_client=scoring_client,
        calibrator=calibrator,
    )

    # 4. 注入 FastAPI
    set_biz_service(biz_service)

    # 5. 启动 gRPC（后台线程）
    grpc_server = start_grpc_server(biz_service, grpc_port)

    # 6. 信号处理
    def shutdown(signum, frame):
        print("\nShutting down...")
        scoring_client.close()
        grpc_server.stop(grace=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 7. 启动 FastAPI（主线程）
    print(f"HTTP server starting on port {http_port}")
    print(f"API docs: http://localhost:{http_port}/docs")
    uvicorn.run(
        "coupon_system.http_app:app",
        host="0.0.0.0",
        port=http_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
