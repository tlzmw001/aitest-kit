<script setup lang="ts">
import { computed } from 'vue'
import { Bot, CircleAlert, UserRound } from '@lucide/vue'
import AgentApprovalCard from './AgentApprovalCard.vue'
import AgentToolEvent from './AgentToolEvent.vue'
import SafeMarkdown from './SafeMarkdown.vue'
import type { AgentApprovalDecision, AgentEvent } from '../types'

const props = defineProps<{ events: AgentEvent[]; pendingIds: string[] }>()
const emit = defineEmits<{ decide: [requestId: string, decision: AgentApprovalDecision] }>()
const items = computed(() => projectActivities(props.events, new Set(props.pendingIds)))
</script>

<template>
  <div class="agent-stream" aria-live="polite" data-test="agent-stream">
    <div v-if="!items.length" class="agent-stream-empty">
      <Bot :size="28" />
      <strong>Agent session 已准备</strong>
      <span>可以让 Pi 阅读测试资产、运行 Skill 或调用 AITest CLI。</span>
    </div>
    <template v-for="item in items" :key="item.key">
      <article v-if="item.kind === 'user'" class="agent-message user-message">
        <UserRound :size="15" /><div><span>YOU</span><p>{{ item.text }}</p></div>
      </article>
      <article v-else-if="item.kind === 'assistant'" class="agent-message assistant-message">
        <Bot :size="15" /><div><span>PI AGENT</span><SafeMarkdown :source="item.text" /></div>
      </article>
      <AgentToolEvent v-else-if="item.kind === 'tool'" :event="item.event" />
      <AgentApprovalCard
        v-else-if="item.kind === 'approval'"
        :event="item.event"
        :pending="item.pending"
        @decide="(requestId, decision) => emit('decide', requestId, decision)"
      />
      <p v-else class="agent-system-event" :class="item.tone"><CircleAlert :size="13" />{{ item.text }}</p>
    </template>
  </div>
</template>

<script lang="ts">
type ActivityItem =
  | { key: string; kind: 'user' | 'assistant' | 'system'; text: string; tone?: string }
  | { key: string; kind: 'tool'; event: AgentEvent }
  | { key: string; kind: 'approval'; event: AgentEvent; pending: boolean }

export function projectActivities(events: AgentEvent[], pendingIds: Set<string>): ActivityItem[] {
  const items: ActivityItem[] = []
  const tools = new Map<string, Extract<ActivityItem, { kind: 'tool' }>>()
  const approvals = new Map<string, Extract<ActivityItem, { kind: 'approval' }>>()
  for (const event of events) {
    if (event.type === 'user_message') {
      items.push({ key: event.event_id, kind: 'user', text: String(event.payload.text ?? '') })
    } else if (event.type === 'text_delta') {
      const previous = items.at(-1)
      if (previous?.kind === 'assistant') previous.text += String(event.payload.delta ?? '')
      else items.push({ key: event.event_id, kind: 'assistant', text: String(event.payload.delta ?? '') })
    } else if (event.type === 'tool_call_requested') {
      const tool = {
        key: event.event_id,
        kind: 'tool' as const,
        event: { ...event, payload: { ...event.payload } },
      }
      tools.set(String(event.payload.tool_call_id ?? ''), tool)
      items.push(tool)
    } else if (['tool_call_updated', 'tool_call_finished'].includes(event.type)) {
      const tool = tools.get(String(event.payload.tool_call_id ?? ''))
      if (tool) {
        tool.event.payload = { ...tool.event.payload, ...event.payload, state: event.type === 'tool_call_updated' ? 'running' : event.payload.is_error ? 'failed' : 'finished' }
      }
    } else if (event.type === 'permission_requested') {
      const requestId = String(event.payload.request_id ?? '')
      const permissionTarget = String(event.payload.command ?? event.payload.target ?? '')
      const related = tools.get(String(event.payload.tool_call_id ?? ''))
        ?? [...tools.values()].reverse().find((item) => {
          const input = item.event.payload.input as Record<string, unknown> | undefined
          const toolTarget = String(input?.command ?? input?.path ?? '')
          return item.event.payload.tool_name === event.payload.tool_name
            && (!permissionTarget || toolTarget === permissionTarget)
        })
      const approval = {
        key: event.event_id,
        kind: 'approval' as const,
        event: { ...event, payload: { ...event.payload, tool_event: related?.event.payload } },
        pending: pendingIds.has(requestId),
      }
      approvals.set(requestId, approval)
      items.push(approval)
    } else if (['permission_resolved', 'approval_submitted'].includes(event.type)) {
      const approval = approvals.get(String(event.payload.request_id ?? ''))
      if (approval) approval.pending = false
    } else if (event.type === 'permission_invalid') {
      items.push({ key: event.event_id, kind: 'system', tone: 'danger', text: '权限请求字段不完整，已自动拒绝。' })
    } else if (event.type === 'error') {
      items.push({ key: event.event_id, kind: 'system', tone: 'danger', text: String(event.payload.message ?? 'Agent 运行失败') })
    } else if (event.type === 'aborted') {
      items.push({ key: event.event_id, kind: 'system', text: '本轮任务已中止。' })
    }
  }
  return items
}
</script>
