<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Eye, FileDiff, ShieldAlert } from '@lucide/vue'
import DiffEditor from './DiffEditor.vue'
import { ApiError, api } from '../api/client'
import { usePreferencesStore } from '../stores/preferences'
import type { AgentApprovalDecision, AgentEvent } from '../types'

const props = defineProps<{ event: AgentEvent; pending: boolean }>()
const emit = defineEmits<{ decide: [requestId: string, decision: AgentApprovalDecision] }>()
const preferences = usePreferencesStore()
const diffOpen = ref(false)
const diskContent = ref('')
const loadingDisk = ref(false)
const diskError = ref('')
const diskReady = ref(false)
const requestId = computed(() => String(props.event.payload.request_id ?? ''))
const toolName = computed(() => String(props.event.payload.tool_name ?? props.event.payload.surface ?? 'tool'))
const target = computed(() => String(props.event.payload.command ?? props.event.payload.target ?? ''))
const toolEvent = computed(() => props.event.payload.tool_event as Record<string, unknown> | undefined)
const input = computed(() => (toolEvent.value?.input ?? {}) as Record<string, unknown>)
const workspacePath = computed(() => String(input.value.workspace_path ?? ''))
const original = computed(() => String(input.value.old_text ?? diskContent.value))
const modified = computed(() => String(input.value.new_text ?? input.value.content ?? ''))
const canDiff = computed(() => toolName.value === 'edit'
  ? typeof input.value.old_text === 'string' && typeof input.value.new_text === 'string'
  : toolName.value === 'write' && typeof input.value.content === 'string' && diskReady.value)
const language = computed(() => languageFor(workspacePath.value))

async function loadDisk(): Promise<void> {
  if (toolName.value !== 'write' || typeof input.value.content !== 'string') return
  if (!workspacePath.value) {
    diskError.value = '无法通过普通文件接口读取此外部或未解析路径；不提供磁盘 Diff，请自行核验后审批。'
    return
  }
  diskError.value = ''
  diskReady.value = false
  loadingDisk.value = true
  try {
    diskContent.value = (await api.readFile(workspacePath.value)).content
    diskReady.value = true
  } catch (cause) {
    if (cause instanceof ApiError && cause.code === 'FILE_NOT_FOUND') {
      diskContent.value = ''
      diskReady.value = true
    } else {
      diskError.value = `无法读取磁盘版本：${cause instanceof Error ? cause.message : String(cause)}`
      console.warn('Agent approval Diff read failed', cause instanceof ApiError ? cause.code : 'READ_FAILED')
    }
  } finally {
    loadingDisk.value = false
  }
}

onMounted(loadDisk)

function decide(decision: AgentApprovalDecision): void {
  if (props.pending) emit('decide', requestId.value, decision)
}

function languageFor(path: string): string {
  if (/\.md$/i.test(path)) return 'markdown'
  if (/\.ya?ml$/i.test(path)) return 'yaml'
  if (/\.py$/i.test(path)) return 'python'
  if (/\.json$/i.test(path)) return 'json'
  return 'text'
}
</script>

<template>
  <article class="agent-approval" :class="{ resolved: !pending }" data-test="agent-approval-card">
    <header>
      <span class="approval-symbol"><ShieldAlert :size="17" /></span>
      <div><span class="section-label">PERMISSION REQUEST</span><strong>{{ toolName }} 需要授权</strong></div>
      <span class="approval-state">{{ pending ? '等待决定' : '已处理' }}</span>
    </header>
    <code class="approval-target">{{ target }}</code>
    <p>{{ String(event.payload.summary ?? 'Pi 请求执行这个本地工具。') }}</p>
    <p v-if="toolName === 'grep'">递归搜索可能读取敏感文件。批准后按本地权限执行，不提供逐文件隔离。</p>
    <p v-if="diskError" role="alert">{{ diskError }} <button v-if="workspacePath" type="button" data-test="retry-diff" :disabled="loadingDisk" @click="loadDisk">重试读取</button></p>
    <button v-if="canDiff" class="diff-toggle" type="button" :disabled="loadingDisk" @click="diffOpen = !diffOpen">
      <FileDiff :size="14" />{{ loadingDisk ? '正在读取磁盘版本' : diffOpen ? '收起变更' : '查看 Monaco Diff' }}
    </button>
    <div v-if="diffOpen && canDiff" class="approval-diff">
      <DiffEditor :original="original" :modified="modified" :path="workspacePath || target" :language="language" :theme="preferences.editorTheme" />
    </div>
    <footer v-if="pending">
      <button class="deny-btn" type="button" data-test="deny-approval" @click="decide('deny')">拒绝</button>
      <button class="secondary-btn" type="button" @click="decide('allow_once')"><Eye :size="14" />允许一次</button>
      <button class="primary-btn" type="button" data-test="allow-session" @click="decide('allow_session')">本会话允许</button>
    </footer>
  </article>
</template>
