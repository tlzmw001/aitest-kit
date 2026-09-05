# Console / Pi 交付验收

这套验收面向维护者，不改变用户的 `aitest console` 使用方式。

## 三平台 clean-wheel smoke

GitHub Actions 的 `install-smoke` 使用 GitHub 提供的 Ubuntu、macOS、Windows
runner，分别测试 Node 22.19.0 和 24，Python 3.11。原有 Linux Python 3.9/3.11
单元测试继续保留。不是每次都要由维护者准备三台机器。

本地复现（从仓库根执行，选择一个新的 wheel 输出目录）：

```bash
python3 -m pip install build
python3 -m build --wheel --outdir dist/install-smoke
python3 scripts/verify_wheel_install.py --wheel-dir dist/install-smoke --output dist/install-smoke-result.json
```

Windows 将 `python3` 换成当前 Python 的 `python` 命令。输出目录必须只有一个
aitest-kit wheel，避免验收到历史产物。脚本只使用临时 venv 和含空格路径的临时
workspace，验证安装包导入、CLI init/doctor、两次 setup、原生 Pi self-test、实际
Console HTTP 服务、认证和静态 JS。不会调用模型，不需要 API key。

安装会访问 PyPI 和 npm。脚本故意不继承代理凭证、私有 registry 配置、PYTHONPATH
或模型环境变量；无法直连公共 registry 的环境需要先解决测试网络条件，不应把
真实凭证塞进报告。临时 Runtime、npm cache 和 workspace 在结束时清理。

成功输出 `status: passed`。失败报告提供 `stage`、`error_type` 和可用的退出码；
不保存原始子进程输出，以免 Console 会话地址进入日志。CI 为每个平台/Node 组合
上传一份独立报告。构建失败发生在 probe 前时可能没有 JSON，查看对应构建步骤。

## 视觉回归

```bash
npm --prefix console_web run test:e2e
```

截图按 OS 分开保存。Linux 测试由现有 Ubuntu job 执行；本机 macOS 通过不等于
Linux 通过。来源和更新规则见 [截图说明](../../console_web/e2e/__screenshots__/README.md)。
发生失败时先看 expected/actual/diff，不自动接受新截图，不通过扩大阈值消除失败。

## 持久化测量

```bash
python3 scripts/benchmark_agent_persistence.py --events 1000 --payload-bytes 128 --repeats 3 --output dist/persistence-1000.json
python3 scripts/benchmark_agent_persistence.py --events 10000 --payload-bytes 128 --repeats 3 --output dist/persistence-10000.json
```

不需要启动 Console、Worker 或模型。使用真实 journal append、metadata save 和
fsync，测量每事件延迟、吞吐、fsync 成本、文件体积及重开耗时。先让其他构建和测试
结束，以减少测量干扰。它不覆盖网络、SSE、浏览器渲染、慢盘或掉电持久性；不设置
CI 毫秒级性能门禁。若用户实际使用中出现延迟，再在相同机器/文件系统复测。

本次测量及是否优化的结论见 [测量报告](../benchmarks/agent_persistence.md)。
