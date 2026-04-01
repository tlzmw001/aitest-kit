"""优惠券系统启动入口 — 同时启动 FastAPI (HTTP) 和 gRPC 服务"""

import os
import sys
import signal
import subprocess
from pathlib import Path

import uvicorn

from coupon_system.config import load_config
from coupon_system.services.redis_store import RedisStore
from coupon_system.services.model_service import MockModelService
from coupon_system.services.coupon_service import CouponBizService
from coupon_system.http_app import set_biz_service


def compile_proto():
    """编译 proto 文件"""
    proto_dir = Path(__file__).parent / "protos"
    proto_file = proto_dir / "coupon.proto"

    if not proto_file.exists():
        print(f"Proto file not found: {proto_file}")
        sys.exit(1)

    # 检查是否已编译
    pb2_file = proto_dir / "coupon_pb2.py"
    if pb2_file.exists():
        if pb2_file.stat().st_mtime >= proto_file.stat().st_mtime:
            return  # 已是最新

    print("Compiling proto files...")
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

    # 创建 __init__.py
    init_file = proto_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("")

    # 修复 grpc import 路径
    grpc_file = proto_dir / "coupon_pb2_grpc.py"
    if grpc_file.exists():
        content = grpc_file.read_text()
        content = content.replace(
            "import coupon_pb2 as coupon__pb2",
            "from coupon_system.protos import coupon_pb2 as coupon__pb2",
        )
        grpc_file.write_text(content)

    print("Proto compilation done.")


def init_stock(redis_store: RedisStore, config):
    """初始化优惠券库存"""
    for coupon_id, template in config.coupon_templates.items():
        current = redis_store.get_stock(coupon_id)
        if current == 0:
            redis_store.init_stock(coupon_id, template.total_stock, config.redis.stock_ttl)
            print(f"  Initialized stock: {coupon_id} = {template.total_stock}")
        else:
            print(f"  Stock exists: {coupon_id} = {current}")


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
    compile_proto()

    # 2. 加载配置
    config = load_config(config_path)
    print(f"Config loaded: {len(config.scenes)} scenes, {len(config.coupon_templates)} templates")

    # 3. 初始化依赖
    redis_store = RedisStore(config.redis.url, config.redis.key_prefix)
    model_service = MockModelService(
        timeout=config.model_service.timeout,
        enabled=config.model_service.enabled,
    )
    biz_service = CouponBizService(config, redis_store, model_service)

    # 4. 初始化库存
    print("Initializing coupon stock...")
    init_stock(redis_store, config)

    # 5. 注入 FastAPI
    set_biz_service(biz_service)

    # 6. 启动 gRPC（后台线程）
    grpc_server = start_grpc_server(biz_service, grpc_port)

    # 7. 信号处理
    def shutdown(signum, frame):
        print("\nShutting down...")
        grpc_server.stop(grace=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 8. 启动 FastAPI（主线程）
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
