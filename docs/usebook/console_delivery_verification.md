# Console 交付验收

这套验收面向维护者，不改变用户的 `aitest console` 使用方式。

## 三平台 clean-wheel smoke

GitHub Actions 的 `install-smoke` 使用 GitHub 提供的 Ubuntu、macOS、Windows
runner，使用 Python 3.11，不安装 Node 或 Pi Runtime。原有 Linux Python 3.9/3.11
单元测试继续保留。不是每次都要由维护者准备三台机器。

本地复现（从仓库根执行，选择一个新的 wheel 输出目录）：

```bash
python3 -m pip install build
python3 -m build --wheel --outdir dist/install-smoke
python3 scripts/verify_wheel_install.py --wheel-dir dist/install-smoke --output dist/install-smoke-result.json
```

Windows 将 `python3` 换成当前 Python 的 `python` 命令。输出目录必须只有一个
aitest-kit wheel，避免验收到历史产物。

注意：新的 `--outdir` **不等于干净构建**。setuptools 可能复用旧 `build/lib`，把源码中已删除的
Agent 文件带回 wheel。正式验收应先提交待测代码，再从独立、无历史构建产物的 checkout/worktree
执行上述命令。例如使用 `git worktree add --detach /path/to/new-clean-build HEAD` 创建一个全新目录，
然后在其中构建；该 worktree 不包含当前目录的未提交修改。不要为验收自动删除现有缓存或用户数据。

安装脚本先读取 wheel 清单，拒绝旧 Agent 模块、Worker/seed、Agent 页面资源和 node_modules；
失败时报告 `stage: inspect_wheel`，不会启动 venv、pip 或 Console。CI 的 wheel/sdist 检查和发布
构建检查复用同一检查函数；它只读归档清单，不解压文件。`embedded_agent: absent` 表示包内容检查通过，
HTTP 探针另外用 `agent_api: absent` 表示旧 API 返回 404。

内容检查通过后，脚本使用临时 venv 和含空格路径的临时 workspace，验证安装包导入、CLI init/doctor、
实际 Console HTTP 服务、认证和静态 JS。原有 workspace、Runtime、session 和凭证不被修改。

安装会访问 PyPI。脚本故意不继承代理凭证、私有 registry 配置、PYTHONPATH
或模型环境变量；无法直连公共 registry 的环境需要先解决测试网络条件，不应把
真实凭证塞进报告。临时 venv 和 workspace 在结束时清理。

成功输出 `status: passed`。失败报告提供 `stage`、`error_type` 和可用的退出码；
probe 子进程失败可附带最多 2,000 字符的过滤诊断，删除含会话地址、token、密钥等
字段的行，不保存原始完整日志。CI 为每个平台
上传一份独立报告。构建失败发生在 probe 前时可能没有 JSON，查看对应构建步骤。

## 视觉回归

```bash
npm --prefix console_web run test:e2e
```

截图按 OS 分开保存。Linux 测试由现有 Ubuntu job 执行；本机 macOS 通过不等于
Linux 通过。来源和更新规则见 [截图说明](../../console_web/e2e/__screenshots__/README.md)。
发生失败时先看 expected/actual/diff，不自动接受新截图，不通过扩大阈值消除失败。

## 历史 Pi 测量

原 Agent 持久化 benchmark 随内置 Pi Runtime 移除。历史结果保留在 [测量报告](../benchmarks/agent_persistence.md)，适用 v0.5.0，不代表当前工作台仍提供 Agent 会话服务。
