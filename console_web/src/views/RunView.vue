<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Ban, Check, Play, Square, Terminal } from '@lucide/vue'
import { api } from '../api/client'
import { messageFrom, useWorkspaceStore } from '../stores/workspace'
import type { EnvironmentMetadata, Job, SelectorPayload } from '../types'

const store = useWorkspaceStore()
const scope = ref<'case' | 'suite' | 'module' | 'task'>('case')
const operation = ref<'validate_profile' | 'codegen' | 'freshness' | 'run'>('run')
const targetName = ref('')
const moduleName = ref('')
const suiteName = ref('')
const caseId = ref('')
const taskName = ref('')
const env = ref<EnvironmentMetadata | null>(null)
const envFile = ref('')
const job = ref<Job | null>(null)
const error = ref('')
let pollTimer: number | undefined
let pollingActive = false
let consecutivePollFailures = 0
const POLL_INTERVAL_MS = 650
const MAX_CONSECUTIVE_POLL_FAILURES = 5

const targets = computed(() => store.targets)
const target = computed(() => targets.value.find((item) => item.name === targetName.value) ?? targets.value[0])
const modules = computed(() => target.value?.modules ?? [])
const module = computed(() => modules.value.find((item) => item.name === moduleName.value) ?? modules.value[0])
const suites = computed(() => module.value?.suites ?? [])
const suite = computed(() => suites.value.find((item) => item.name === suiteName.value) ?? suites.value[0])
const cases = computed(() => suite.value?.cases ?? [])
const task = computed(() => store.tasks.find((item) => item.name === taskName.value) ?? store.tasks[0])
const running = computed(() => job.value?.status === 'queued' || job.value?.status === 'running')

const selector = computed<SelectorPayload | null>(() => {
  if (scope.value === 'task') return task.value ? { type: 'task', task_file: task.value.path } : null
  if (scope.value === 'module') return module.value && target.value ? { type: 'module', target: target.value.name, module: module.value.name } : null
  if (!suite.value) return null
  if (scope.value === 'case' && operation.value === 'run') {
    const selectedCase = caseId.value || cases.value[0]?.id
    return selectedCase ? { type: 'case', suite_file: suite.value.manifest_path, case_ids: [selectedCase] } : null
  }
  return { type: 'suite', suite_file: suite.value.manifest_path }
})

const commandPreview = computed(() => {
  const current = selector.value
  if (!current) return '没有可执行 selector'
  const command = operation.value === 'run' ? 'aitest run' : 'aitest codegen'
  const flags = operation.value === 'validate_profile' ? ' --validate-profile' : operation.value === 'freshness' ? ' --check' : ''
  if (current.type === 'case') return `${command} --suite-file ${current.suite_file} --case-id ${current.case_ids?.[0]}`
  if (current.type === 'suite') return `${command} --suite-file ${current.suite_file}${flags}`
  if (current.type === 'module') return `${command} --target ${current.target} --module ${current.module}${flags}`
  return `${command} --task-file ${current.task_file}${flags}`
})

function normalizeSelections(): void {
  targetName.value = target.value?.name ?? ''
  moduleName.value = module.value?.name ?? ''
  suiteName.value = suite.value?.name ?? ''
  caseId.value = cases.value.some((item) => item.id === caseId.value) ? caseId.value : cases.value[0]?.id ?? ''
  taskName.value = task.value?.name ?? ''
}

watch([targetName, moduleName, suiteName], normalizeSelections)
watch(operation, () => {
  if (operation.value !== 'run' && scope.value === 'case') scope.value = 'suite'
})

async function loadEnvironment(): Promise<void> {
  try {
    env.value = await api.environment()
    envFile.value = env.value.sources.find((source) => source.active && source.exists)?.path ?? ''
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

async function restoreJob(): Promise<void> {
  try {
    const jobs = await api.jobs()
    job.value = jobs.jobs[0] ?? null
    store.setCurrentJob(job.value)
    if (running.value) startPolling()
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

async function start(): Promise<void> {
  if (!selector.value) return
  error.value = ''
  try {
    job.value = await api.startJob(operation.value, selector.value, envFile.value || undefined)
    store.setCurrentJob(job.value)
    startPolling()
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

function startPolling(): void {
  stopPolling()
  pollingActive = true
  consecutivePollFailures = 0
  schedulePoll()
}

function schedulePoll(): void {
  if (!pollingActive) return
  pollTimer = window.setTimeout(() => void pollJob(), POLL_INTERVAL_MS)
}

function stopPolling(): void {
  pollingActive = false
  window.clearTimeout(pollTimer)
  pollTimer = undefined
}

async function pollJob(): Promise<void> {
  if (!pollingActive || !job.value) return
  try {
    const nextJob = await api.job(job.value.id)
    if (!pollingActive) return
    job.value = nextJob
    store.setCurrentJob(nextJob)
    if (consecutivePollFailures) error.value = ''
    consecutivePollFailures = 0
    if (!running.value) {
      stopPolling()
      await store.refresh()
      return
    }
  } catch (cause) {
    if (!pollingActive) return
    consecutivePollFailures += 1
    const pollError = messageFrom(cause)
    if (consecutivePollFailures >= MAX_CONSECUTIVE_POLL_FAILURES) {
      error.value = `${pollError}；轮询连续 ${MAX_CONSECUTIVE_POLL_FAILURES} 次失败，已停止自动更新。任务可能仍在后端运行。`
      stopPolling()
      return
    }
    error.value = `${pollError}；将在下一次轮询时重试（${consecutivePollFailures}/${MAX_CONSECUTIVE_POLL_FAILURES}）`
  }
  schedulePoll()
}

async function cancel(): Promise<void> {
  if (!job.value) return
  try {
    job.value = await api.cancelJob(job.value.id)
    store.setCurrentJob(job.value)
    if (!running.value) {
      stopPolling()
      await store.refresh()
    }
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

onMounted(() => {
  normalizeSelections()
  void loadEnvironment()
  void restoreJob()
})
onBeforeUnmount(stopPolling)
</script>

<template>
  <section class="run-view">
    <div class="run-header">
      <div><span class="eyebrow">DETERMINISTIC EXECUTION</span><h1>选择运行范围</h1><p>操作从 registry 和 manifest 解析，不接受任意 Shell 参数。</p></div>
      <span class="status-chip" :class="{ ok: !error, danger: error }"><i />{{ error ? 'blocked' : 'preflight ready' }}</span>
    </div>

    <div class="operation-strip">
      <button v-for="item in ['validate_profile', 'codegen', 'freshness', 'run'] as const" :key="item" :class="{ active: operation === item }" :disabled="running" @click="operation = item">
        {{ { validate_profile: 'Profile 校验', codegen: '生成 pytest', freshness: '生成同步', run: '执行测试' }[item] }}
      </button>
    </div>

    <div class="run-layout">
      <section class="run-form">
        <div class="scope-switch">
          <button v-for="item in ['case', 'suite', 'module', 'task'] as const" :key="item" :disabled="running || (operation !== 'run' && item === 'case')" :class="{ active: scope === item }" @click="scope = item">{{ item }}</button>
        </div>

        <template v-if="scope !== 'task'">
          <div class="form-grid">
            <label class="form-section">Target<select v-model="targetName"><option v-for="item in targets" :key="item.name">{{ item.name }}</option></select></label>
            <label class="form-section">Module<select v-model="moduleName"><option v-for="item in modules" :key="item.name">{{ item.name }}</option></select></label>
          </div>
          <label v-if="scope === 'suite' || scope === 'case'" class="form-section">Suite<select v-model="suiteName"><option v-for="item in suites" :key="item.name">{{ item.name }}</option></select></label>
          <label v-if="scope === 'case'" class="form-section">Case<select v-model="caseId"><option v-for="item in cases" :key="item.id" :value="item.id">{{ item.id }} · {{ item.title }}</option></select></label>
        </template>
        <label v-else class="form-section">Task<select v-model="taskName"><option v-for="item in store.tasks" :key="item.name">{{ item.name }}</option></select></label>

        <label class="form-section">运行 env 文件
          <select v-model="envFile"><option value="">仅使用 Shell / workspace 默认</option><option v-for="source in env?.sources.filter((item) => item.exists)" :key="source.path" :value="source.path">{{ source.path }}{{ source.external ? ' · external' : '' }}</option></select>
        </label>
        <div class="execution-note"><span class="provenance env">ENV</span><p>运行环境只在此显示来源、变量名和存在状态，值不会进入命令预览或任务日志。</p></div>
      </section>

      <aside class="run-summary">
        <span class="eyebrow">COMMAND PREVIEW</span>
        <div class="command-preview"><Terminal :size="16" /><code>{{ commandPreview }}</code></div>
        <div class="preflight-list">
          <div class="done"><span>1</span><div><strong>Registry</strong><small>selector 由当前 workspace 解析</small></div><Check :size="15" /></div>
          <div><span>2</span><div><strong>生成同步</strong><small>Run 会自动执行 freshness gate</small></div><Check :size="15" /></div>
          <div><span>3</span><div><strong>Environment</strong><small>{{ envFile || 'Shell / workspace default' }}</small></div><Check :size="15" /></div>
        </div>
        <button v-if="!running" class="run-btn" :disabled="!selector" @click="start"><Play :size="16" />开始{{ operation === 'run' ? '执行' : '操作' }}</button>
        <button v-else class="danger-btn" @click="cancel"><Square :size="14" />终止任务</button>
        <p v-if="error" class="inline-error"><Ban :size="15" />{{ error }}</p>
      </aside>
    </div>

    <section class="job-output">
      <div class="job-output-head"><span>OUTPUT</span><strong>{{ job?.status ?? 'idle' }}</strong><code v-if="job">{{ job.command_summary }}</code></div>
      <pre>{{ job?.output || '启动一个操作后，结构化任务输出会显示在这里。' }}</pre>
    </section>
  </section>
</template>
