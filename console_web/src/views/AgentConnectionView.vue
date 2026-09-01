<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Check, CircleAlert, Download, KeyRound, LoaderCircle, PackageCheck, PlugZap, Save, ShieldCheck, Square, X } from '@lucide/vue'
import { DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from 'reka-ui'
import { api, ApiError } from '../api/client'
import type {
  AgentConnection,
  AgentConnectionInput,
  AgentConnectionTestResult,
  AgentProtocol,
  AgentRuntimeStatus,
  Job,
} from '../types'

const protocols: Array<{ value: AgentProtocol; label: string; description: string }> = [
  { value: 'auto', label: '自动检测', description: '优先 Responses，仅在明确协议不兼容时尝试 Chat Completions' },
  { value: 'openai_responses', label: 'OpenAI Responses', description: '适合 GPT-5、Codex 和支持 /responses 的兼容网关' },
  { value: 'openai_chat_completions', label: 'OpenAI Chat Completions', description: '适合只支持 /chat/completions 的兼容服务' },
  { value: 'anthropic_messages', label: 'Anthropic Messages', description: '适合 Claude 官方接口和 Anthropic 兼容网关' },
]

const connectionName = ref('')
const protocol = ref<AgentProtocol>('auto')
const baseUrl = ref('')
const model = ref('')
const apiKeyEnv = ref('AITEST_AGENT_API_KEY')
const apiKey = ref('')
const connection = ref<AgentConnection | null>(null)
const testResult = ref<AgentConnectionTestResult | null>(null)
const loading = ref(true)
const testing = ref(false)
const saving = ref(false)
const loadError = ref('')
const testError = ref('')
const saveMessage = ref('')
const runtime = ref<AgentRuntimeStatus | null>(null)
const runtimeDialog = ref(false)
const setupJob = ref<Job | null>(null)
const setupError = ref('')
let setupTimer: ReturnType<typeof setTimeout> | null = null

const canSubmit = computed(() => Boolean(connectionName.value.trim() && model.value.trim()))
const canTestConnection = computed(() => canSubmit.value && runtime.value?.state === 'ready')
const runtimeInstalling = computed(() => setupJob.value?.status === 'queued' || setupJob.value?.status === 'running')
const runtimeSetupDisabled = computed(() => {
  if (!runtime.value || runtimeInstalling.value) return true
  return runtime.value.state === 'ready' || runtime.value.state === 'node_missing' || runtime.value.state === 'node_unsupported'
})
const runtimeSource = computed(() => runtime.value?.source === 'source' ? '源码 checkout' : '用户级安装')
const credentialLabel = computed(() => {
  if (connection.value?.credential_source === 'session') return '当前 Console 会话已提供 Key'
  if (connection.value?.credential_source === 'environment') return `已读取环境变量 ${connection.value.api_key_env}`
  return '尚未提供 API Key'
})

watch([connectionName, protocol, baseUrl, model], () => {
  testResult.value = null
  testError.value = ''
})

onMounted(async () => {
  try {
    const [savedConnection, runtimeStatus] = await Promise.all([api.agentConnection(), api.agentRuntime()])
    applyConnection(savedConnection)
    runtime.value = runtimeStatus
  } catch (cause) {
    loadError.value = messageFrom(cause)
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  apiKey.value = ''
  if (setupTimer) clearTimeout(setupTimer)
})

function applyConnection(value: AgentConnection): void {
  connection.value = value
  connectionName.value = value.connection_name
  protocol.value = value.protocol
  baseUrl.value = value.base_url
  model.value = value.model
  apiKeyEnv.value = value.api_key_env
}

function payload(): AgentConnectionInput {
  return {
    connection_name: connectionName.value.trim(),
    protocol: protocol.value,
    base_url: baseUrl.value.trim(),
    model: model.value.trim(),
    api_key_env: apiKeyEnv.value,
    api_key: apiKey.value,
  }
}

async function testConnection(): Promise<void> {
  testing.value = true
  testError.value = ''
  testResult.value = null
  try {
    testResult.value = await api.testAgentConnection(payload())
  } catch (cause) {
    testError.value = messageFrom(cause)
  } finally {
    testing.value = false
  }
}

async function saveConnection(): Promise<void> {
  saving.value = true
  saveMessage.value = ''
  try {
    applyConnection(await api.saveAgentConnection(payload()))
    apiKey.value = ''
    saveMessage.value = '配置已保存，API Key 未写入 workspace 文件。'
  } catch (cause) {
    saveMessage.value = messageFrom(cause)
  } finally {
    saving.value = false
  }
}

async function startRuntimeSetup(): Promise<void> {
  setupError.value = ''
  try {
    setupJob.value = await api.setupAgentRuntime()
    if (isTerminal(setupJob.value)) await finishRuntimeSetup()
    else scheduleRuntimePoll()
  } catch (cause) {
    setupError.value = messageFrom(cause)
  }
}

function scheduleRuntimePoll(): void {
  if (!setupJob.value || isTerminal(setupJob.value)) return
  setupTimer = setTimeout(async () => {
    try {
      setupJob.value = await api.agentRuntimeSetupJob(setupJob.value!.id)
      if (isTerminal(setupJob.value)) await finishRuntimeSetup()
      else scheduleRuntimePoll()
    } catch (cause) {
      setupError.value = messageFrom(cause)
      scheduleRuntimePoll()
    }
  }, 750)
}

async function finishRuntimeSetup(): Promise<void> {
  if (setupJob.value?.status === 'failed') setupError.value = 'Agent Runtime 安装失败，请查看安装日志。'
  try {
    runtime.value = await api.agentRuntime()
  } catch (cause) {
    setupError.value = messageFrom(cause)
  }
}

async function cancelRuntimeSetup(): Promise<void> {
  if (!setupJob.value) return
  try {
    setupJob.value = await api.cancelAgentRuntimeSetup(setupJob.value.id)
  } catch (cause) {
    setupError.value = messageFrom(cause)
  }
}

function isTerminal(job: Job): boolean {
  return ['succeeded', 'failed', 'cancelled'].includes(job.status)
}

function protocolLabel(value: AgentConnectionTestResult['detected_protocol']): string {
  return protocols.find((item) => item.value === value)?.label ?? value
}

function formatLatency(milliseconds: number): string {
  return milliseconds >= 1000 ? `${(milliseconds / 1000).toFixed(2)} s` : `${milliseconds} ms`
}

function messageFrom(cause: unknown): string {
  if (cause instanceof ApiError) return `${cause.code}: ${cause.message}`
  return cause instanceof Error ? cause.message : '无法完成操作'
}
</script>

<template>
  <section class="agent-connection-view">
    <header class="agent-connection-header">
      <div>
        <span class="eyebrow">LOCAL AGENT / CONNECTION</span>
        <h1>模型连接</h1>
        <p>填写你从模型服务商拿到的信息即可，无需查找 Pi Provider。内部适配器由测试结果自动确定。</p>
      </div>
      <span class="status-chip" :class="{ ok: connection?.has_api_key, danger: !connection?.has_api_key }">
        <i />{{ credentialLabel }}
      </span>
    </header>

    <div v-if="loading" class="loading-state"><span class="spinner" /><span>正在读取连接配置</span></div>
    <p v-else-if="loadError" class="inline-error"><CircleAlert :size="15" />{{ loadError }}</p>

    <template v-else>
      <section v-if="runtime" class="agent-runtime-card" :class="runtime.state" data-test="agent-runtime-card">
        <div class="runtime-mark"><PackageCheck v-if="runtime.state === 'ready'" :size="19" /><CircleAlert v-else :size="19" /></div>
        <div class="runtime-copy">
          <span class="section-label">PI AGENT RUNTIME</span>
          <strong>{{ runtime.state === 'ready' ? `已就绪 · ${runtimeSource}` : '需要安装本地运行时' }}</strong>
          <p>{{ runtime.message }}</p>
          <dl>
            <div><dt>Node</dt><dd>{{ runtime.node_version || `需要 ≥ ${runtime.minimum_node_version}` }}</dd></div>
            <div><dt>Bundle</dt><dd><code>{{ runtime.bundle_hash ? runtime.bundle_hash.slice(0, 12) : '—' }}</code></dd></div>
            <div><dt>目录</dt><dd><code>{{ runtime.runtime_dir || '—' }}</code></dd></div>
          </dl>
        </div>
        <div class="runtime-action">
          <span class="status-chip" :class="{ ok: runtime.state === 'ready', danger: runtime.state !== 'ready' }"><i />{{ runtime.state }}</span>
          <button class="secondary-btn" type="button" data-test="open-runtime-setup" :disabled="runtimeSetupDisabled" @click="runtimeDialog = true">
            <Download :size="15" />{{ runtime.state === 'ready' ? '运行时已就绪' : '安装 Agent Runtime' }}
          </button>
          <a v-if="runtime.state === 'node_missing' || runtime.state === 'node_unsupported'" href="https://nodejs.org/en/download" target="_blank" rel="noreferrer">安装 Node.js 24 LTS</a>
        </div>
      </section>

      <div class="agent-connection-layout">
        <form class="connection-form" @submit.prevent="saveConnection">
        <div class="connection-section-head">
          <div><span class="section-label">连接信息</span><strong>你需要提供的内容</strong></div>
          <span>非敏感配置会写入 workspace</span>
        </div>

        <label>
          <span>连接名称</span>
          <input v-model="connectionName" data-test="connection-name" maxlength="80" autocomplete="off" placeholder="例如：团队模型网关" />
        </label>

        <label>
          <span>接口类型</span>
          <select v-model="protocol" data-test="connection-protocol">
            <option v-for="item in protocols" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <small>{{ protocols.find((item) => item.value === protocol)?.description }}</small>
        </label>

        <label>
          <span>Base URL</span>
          <input v-model="baseUrl" data-test="connection-base-url" maxlength="2048" autocomplete="url" spellcheck="false" placeholder="https://api.example.com/v1" />
          <small>官方接口可以留空；兼容网关填写服务商给你的地址。</small>
        </label>

        <label>
          <span>模型名称</span>
          <input v-model="model" data-test="connection-model" maxlength="160" autocomplete="off" spellcheck="false" placeholder="gpt-5.5" />
        </label>

        <label>
          <span>API Key</span>
          <span class="secret-input"><KeyRound :size="15" /><input v-model="apiKey" type="password" data-test="connection-api-key" maxlength="4096" autocomplete="off" spellcheck="false" placeholder="仅保存在当前 Console 会话" /></span>
          <small>留空时复用当前会话 Key 或 {{ apiKeyEnv }}。页面不会把 Key 写入浏览器存储。</small>
        </label>

        <footer class="connection-actions">
          <button class="secondary-btn" type="button" data-test="test-connection" :disabled="!canTestConnection || testing || saving" @click="testConnection">
            <LoaderCircle v-if="testing" class="spin-icon" :size="16" /><PlugZap v-else :size="16" />
            {{ testing ? '正在真实请求' : '测试连接' }}
          </button>
          <button class="primary-btn" type="button" data-test="save-connection" :disabled="!canSubmit || testing || saving" @click="saveConnection">
            <LoaderCircle v-if="saving" class="spin-icon" :size="16" /><Save v-else :size="16" />
            {{ saving ? '正在保存' : '保存连接' }}
          </button>
        </footer>
        <p v-if="saveMessage" class="connection-save-message" :class="{ error: saveMessage.includes(':') }">{{ saveMessage }}</p>
        </form>

        <aside class="connection-result" aria-live="polite">
        <div class="connection-section-head">
          <div><span class="section-label">连接状态</span><strong>最近一次真实测试</strong></div>
          <ShieldCheck :size="18" />
        </div>

        <div v-if="testing" class="connection-result-state">
          <LoaderCircle class="spin-icon" :size="24" />
          <strong>正在请求 {{ model }}</strong>
          <small>通过 Pi Worker 验证鉴权、协议和模型响应</small>
        </div>
        <div v-else-if="testError" class="connection-result-state failed" data-test="connection-test-error">
          <CircleAlert :size="24" />
          <strong>连接测试失败</strong>
          <small>{{ testError }}</small>
        </div>
        <div v-else-if="testResult" class="connection-result-success">
          <div class="connection-success-title"><span><Check :size="17" /></span><div><strong>连接测试成功</strong><small>模型已返回真实响应</small></div></div>
          <dl>
            <div><dt>接口类型</dt><dd>{{ protocolLabel(testResult.detected_protocol) }}</dd></div>
            <div><dt>模型</dt><dd>{{ testResult.model }}</dd></div>
            <div><dt>响应耗时</dt><dd>{{ formatLatency(testResult.latency_ms) }}</dd></div>
            <div><dt>内部适配器</dt><dd><code>{{ testResult.internal_provider }}</code></dd></div>
          </dl>
          <div class="model-response"><span>MODEL RESPONSE</span><pre>{{ testResult.response_text }}</pre></div>
        </div>
        <div v-else class="connection-result-state idle">
          <PlugZap :size="24" />
          <strong>尚未测试当前配置</strong>
          <small>测试会产生一次最小模型请求，不读取 workspace 文件，也不调用工具。</small>
        </div>
        </aside>
      </div>
    </template>
  </section>

  <DialogRoot v-model:open="runtimeDialog">
    <DialogPortal>
      <DialogOverlay class="asset-modal-backdrop">
        <DialogContent class="runtime-setup-dialog" data-test="runtime-setup-dialog">
          <header><div><span class="eyebrow">LOCAL RUNTIME SETUP</span><DialogTitle>安装 Pi Agent Runtime</DialogTitle></div><button aria-label="关闭" @click="runtimeDialog = false"><X :size="17" /></button></header>
          <DialogDescription>将使用精确 lockfile 安装 Pi Worker。该操作与 Agent 的工具审批权限相互独立。</DialogDescription>
          <dl v-if="runtime" class="runtime-install-details">
            <div><dt>网络访问</dt><dd><code>{{ runtime.registry || 'npm 当前 registry' }}</code></dd></div>
            <div><dt>写入目录</dt><dd><code>{{ runtime.runtime_dir }}</code></dd></div>
            <div><dt>工作空间</dt><dd>不修改 workspace</dd></div>
            <div><dt>模型凭证</dt><dd>不读取模型 API Key</dd></div>
          </dl>
          <div v-if="runtime" class="runtime-dependencies">
            <span>锁定依赖</span>
            <code v-for="dependency in runtime.dependencies" :key="dependency.name">{{ dependency.name }}@{{ dependency.version }}</code>
          </div>
          <div v-if="setupJob" class="runtime-setup-output" aria-live="polite">
            <div><span>{{ setupJob.status }}</span><code>{{ setupJob.command_summary }}</code></div>
            <pre>{{ setupJob.output || '等待安装日志…' }}</pre>
          </div>
          <p v-if="setupError" class="inline-error"><CircleAlert :size="15" />{{ setupError }}</p>
          <footer>
            <button class="secondary-btn" type="button" @click="runtimeDialog = false">关闭</button>
            <button v-if="runtimeInstalling" class="danger-btn compact" type="button" @click="cancelRuntimeSetup"><Square :size="14" />取消安装</button>
            <button v-else class="primary-btn" type="button" data-test="confirm-runtime-setup" :disabled="runtime?.state === 'ready'" @click="startRuntimeSetup"><Download :size="15" />确认安装</button>
          </footer>
        </DialogContent>
      </DialogOverlay>
    </DialogPortal>
  </DialogRoot>
</template>
