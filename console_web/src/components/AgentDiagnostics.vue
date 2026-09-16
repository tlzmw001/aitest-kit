<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import type { AgentSessionSnapshot } from '../types'

const props = defineProps<{ session: AgentSessionSnapshot }>()
const now = ref(Date.now())
const timer = window.setInterval(() => { now.value = Date.now() }, 1000)
onBeforeUnmount(() => window.clearInterval(timer))
const rows = computed(() => props.session.diagnostics?.requests ?? [])
const current = computed(() => rows.value.filter((row) => row.message_id === props.session.diagnostics?.message_id).at(-1))
const retry = computed(() => props.session.diagnostics?.retry)
const phases: Record<string, string> = {
  preparing: '正在准备请求', waiting_response: '等待模型服务响应', waiting_text: '已连接，等待回复',
  receiving: '正在接收回复', thinking: '已收到思考事件，等待回复', completed: '模型调用完成', failed: '模型调用失败', aborted: '模型调用已中止',
}
const status = computed(() => {
  if (props.session.pending_approval_ids.length) return '等待你的审批'
  if (!props.session.active_prompt) return ({ created: '已就绪', succeeded: '本轮完成', failed: '本轮失败', aborted: '已中止', interrupted: '已中断' } as Record<string, string>)[props.session.status] ?? '未在运行'
  if (retry.value?.waiting) return `自动重试 ${retry.value.attempt ?? '?'}/${retry.value.max_attempts ?? '?'} · 退避 ${duration(retry.value.delay_ms)}`
  if (!current.value) return '正在准备请求'
  if (current.value.phase === 'completed') return '正在处理工具或后续步骤'
  return phases[current.value.phase] ?? '正在运行'
})
const elapsed = computed(() => {
  if (!props.session.active_prompt || props.session.pending_approval_ids.length || retry.value?.waiting || !current.value || ['completed', 'failed', 'aborted'].includes(current.value.phase)) return ''
  const start = Date.parse(current.value.phase_started_at)
  return Number.isFinite(start) ? ` · ${Math.max(0, Math.floor((now.value - start) / 1000))} 秒` : ''
})
function duration(value: number | undefined): string {
  return typeof value === 'number' && Number.isFinite(value) ? `${(value / 1000).toFixed(2)} s` : '未采集'
}
</script>

<template>
  <section v-if="session.active_prompt || rows.length" class="request-diagnostics" aria-label="Agent 请求诊断">
    <p data-test="agent-request-stage"><span role="status">{{ status }}</span><span class="elapsed">{{ elapsed }}</span></p>
    <details v-if="rows.length">
      <summary>请求诊断 <span>{{ rows.length }} 次调用 · 最近记录</span></summary>
      <p class="diagnostic-note">时间从每次模型调用开始计。基础模式不是网络抓包；未采集不等于耗时为零。</p>
      <p v-if="retry">自动重试：第 {{ retry.attempt ?? '未采集' }} 次 · {{ retry.phase === 'start' ? (retry.waiting ? '等待重试' : '已开始下一次调用') : retry.success ? '恢复成功' : '重试结束' }} <code v-if="retry.error_category">{{ retry.error_category }}</code></p>
      <article v-for="row in [...rows].reverse()" :key="row.request_id">
        <header><span>{{ phases[row.phase] || row.phase }}</span><code :title="row.request_id">{{ row.request_id.slice(0, 8) }}</code></header>
        <dl>
          <div><dt>请求准备完成</dt><dd>{{ duration(row.request_ms) }}</dd></div>
          <div><dt>HTTP 响应头</dt><dd>{{ duration(row.headers_ms) }}</dd></div>
          <div><dt>HTTP 状态</dt><dd>{{ row.http_status ?? '未采集' }}</dd></div>
          <div><dt>Pi 首字</dt><dd>{{ duration(row.first_text_ms) }}</dd></div>
          <div><dt>调用完成</dt><dd>{{ duration(row.complete_ms) }}</dd></div>
          <div><dt>错误分类</dt><dd>{{ row.error_category || '无' }}</dd></div>
        </dl>
        <p v-if="row.detail !== 'enabled'" class="diagnostic-note">详细流诊断：{{ row.detail === 'unsupported' ? '当前模型协议不支持（仅支持 OpenAI Responses）' : '未开启' }}</p>
        <template v-else>
          <dl>
            <div><dt>原始首字节</dt><dd>{{ duration(row.first_byte_ms) }}</dd></div>
            <div><dt>原始首个 SSE</dt><dd>{{ duration(row.first_sse_event_ms) }}</dd></div>
            <div><dt>原始首字</dt><dd>{{ duration(row.raw_first_text_ms) }}</dd></div>
            <div><dt>流终止事件</dt><dd>{{ row.raw_terminal || '未采集' }}</dd></div>
            <div><dt>HTTP 尝试数</dt><dd>{{ row.http_attempts ?? '未采集' }}</dd></div>
          </dl>
          <p v-if="row.raw_missing_terminal || row.raw_invalid_json || row.raw_incomplete_frame_at_eof || row.observer_oversized_frame" class="diagnostic-warning">流诊断标志：{{ row.raw_missing_terminal ? '缺少终止事件 ' : '' }}{{ row.raw_invalid_json ? '无效 JSON ' : '' }}{{ row.raw_incomplete_frame_at_eof ? 'EOF 帧不完整 ' : '' }}{{ row.observer_oversized_frame ? '超大帧未采集' : '' }}</p>
          <ul class="raw-events">
            <li v-for="(stat, type) in row.raw_event_types" :key="type"><code>{{ type }}</code><span>{{ stat.count }} 次 · 首 {{ duration(stat.first_ms) }} / 末 {{ duration(stat.last_ms) }}</span></li>
          </ul>
        </template>
      </article>
    </details>
  </section>
</template>

<style scoped>
.request-diagnostics { width: min(880px, calc(100% - 48px)); margin: 0 auto 18px; color: var(--text-2); font-size: 12px; overflow-wrap: anywhere; }
.request-diagnostics > p { padding: 8px 0; }
.elapsed, summary > span, .diagnostic-note { color: var(--muted); }
.elapsed, dd, .raw-events span { font-variant-numeric: tabular-nums; }
details { border-top: 1px solid var(--line); }
summary { min-height: 40px; padding: 10px 0; cursor: pointer; color: var(--text-2); }
summary > span { margin-left: 8px; font-size: 10px; }
summary:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; }
article { padding: 12px 0; border-bottom: 1px solid var(--line); }
article header { display: flex; justify-content: space-between; gap: 8px; }
article header code { color: var(--muted); }
dl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 12px 0; }
dt { color: var(--muted); font-size: 10px; }
dd { margin: 3px 0 0; }
.diagnostic-note { font-size: 11px; }
.diagnostic-warning { color: var(--warning); }
.raw-events { padding: 0; list-style: none; font-size: 10px; }
.raw-events li { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 4px 12px; padding-top: 6px; }
@media (max-width: 760px) { .request-diagnostics { width: calc(100% - 24px); } dl { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
