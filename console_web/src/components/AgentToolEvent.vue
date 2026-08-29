<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown, ChevronRight, CircleCheck, CircleX, FileCode2, TerminalSquare } from '@lucide/vue'
import type { AgentEvent } from '../types'

const props = defineProps<{ event: AgentEvent }>()
const expanded = ref(false)
const payload = computed(() => props.event.payload)
const input = computed(() => isRecord(payload.value.input) ? payload.value.input : {})
const toolName = computed(() => String(payload.value.tool_name ?? 'tool'))
const toolPath = computed(() => String(input.value.workspace_path ?? ''))
const command = computed(() => String(input.value.command ?? ''))
const state = computed(() => String(payload.value.state ?? 'running'))
const detail = computed(() => payload.value.result ?? payload.value.partial_result ?? input.value)
</script>

<template>
  <article class="agent-tool" :class="state" data-test="agent-tool-event">
    <button class="agent-tool-summary" type="button" :aria-expanded="expanded" @click="expanded = !expanded">
      <TerminalSquare v-if="toolName === 'bash'" :size="15" />
      <FileCode2 v-else :size="15" />
      <span><b>{{ toolName }}</b><code v-if="command">{{ command }}</code><code v-else-if="toolPath">{{ toolPath }}</code></span>
      <CircleX v-if="state === 'failed'" class="bad" :size="14" />
      <CircleCheck v-else-if="state === 'finished'" class="ok" :size="14" />
      <ChevronDown v-if="expanded" :size="14" />
      <ChevronRight v-else :size="14" />
    </button>
    <div v-if="expanded" class="agent-tool-detail">
      <pre>{{ JSON.stringify(detail, null, 2) }}</pre>
      <footer>
        <RouterLink v-if="toolPath" :to="{ path: '/editor', query: { path: toolPath } }">在编辑器打开</RouterLink>
        <RouterLink v-if="['run', 'report'].includes(String(payload.aitest_operation ?? ''))" to="/reports">查看执行报告</RouterLink>
      </footer>
    </div>
  </article>
</template>

<script lang="ts">
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
</script>
