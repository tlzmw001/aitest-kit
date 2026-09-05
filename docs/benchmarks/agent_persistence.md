# Agent 持久化阶段测量

结论：本次样本没有显示需要改变逐事件落盘策略的证据。保留 journal fsync +
metadata fsync/replace；不引入异步写队列、批量丢失窗口或数据库。

## 环境与方法

- 测量时间：2026-09-05 04:05–04:06 UTC（本地 2026-09-04）。
- macOS 26.4 / arm64 / Python 3.9.6，本机临时目录的文件系统。
- `scripts/benchmark_agent_persistence.py` 调用真实 `AgentEventLog.append` 与
  `AgentSessionStore.save`，按 `AgentSession._append → _persist` 的现行顺序测量。
- 合成 `text_delta`，`delta` 为指定字节数的 ASCII 文本；每组独立临时会话重复三次。
- 计时包裹真实 `os.fsync`，没有禁用 fsync；初始化不计入写入区间。每事件含脱敏、
  JSON 序列化、journal 打开/写入/flush/fsync、metadata 保存/replace 和权限处理。
- p50/p95 使用 nearest-rank；吞吐是整轮事件数量除以总时间。重开包括 journal 读取、
  解析、内存有界回放加载和 metadata 读取，不是完整 Console/Worker 启动。

## 结果

下表为各组三轮的最小到最大值，不是把三轮混成一个分位数。

| 事件数 × payload | 每事件 p50 | 每事件 p95 | 最大单事件 | 吞吐 / 秒 | 重开耗时 |
| --- | --- | --- | --- | --- | --- |
| 1,000 × 128 B | 0.381–0.400 ms | 0.526–0.585 ms | 7.100 ms | 2,283–2,501 | 5.020–5.378 ms |
| 10,000 × 128 B | 0.378–0.394 ms | 0.529–0.622 ms | 5.572 ms | 2,306–2,557 | 48.124–50.949 ms |
| 1,000 × 4,096 B | 0.480–0.484 ms | 0.602–0.617 ms | 6.683 ms | 1,936–2,043 | 13.540–14.375 ms |

每 1,000 事件实测 2,000 次 fsync，每 10,000 事件实测 20,000 次。
fsync 总计约占写入整轮的 9–10%。三组 journal 分别为 351,893、3,528,894、
4,319,893 字节。所有九轮重开后 journal seq 与 metadata seq 都等于写入事件数。

原始结果（不含会话文本、路径或凭证）：

- [1,000 × 128 B](agent_persistence_1000.json)
- [10,000 × 128 B](agent_persistence_10000.json)
- [1,000 × 4,096 B](agent_persistence_large.json)

复现命令：

```bash
python3 scripts/benchmark_agent_persistence.py --events 1000 --payload-bytes 128 --repeats 3
python3 scripts/benchmark_agent_persistence.py --events 10000 --payload-bytes 128 --repeats 3
python3 scripts/benchmark_agent_persistence.py --events 1000 --payload-bytes 4096 --repeats 3
```

## 决策边界

这不是模型、Worker 队列、SSE 或前端渲染的端到端测速；没有测定真实 provider 的
事件到达率，也没有测外接盘、网络盘、Windows 或 Linux。`os.fsync` 成本不能当作
断电情况下全部数据绝对持久的证明。后台负载可能产生离群值，不建立毫秒级 CI 门禁。

当前本机持久化阶段尚不足以解释明显的流式卡顿。若真实会话发生延迟，先测事件
到达率/积压、持久化耗时和 SSE/浏览器耗时；若慢盘使写入能力低于事件到达率，再
讨论合并 text delta、降低 metadata 写频率等具体方案，并先定义崩溃恢复契约。
长历史重开成本随文件长度增长，当前 10,000 条约 50 ms，不据此提前引入索引。
