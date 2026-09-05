<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { Bot, CircleAlert, Clock3, LoaderCircle, OctagonX, Play, Plus, Send, Shield, ShieldCheck, Trash2, X } from '@lucide/vue'
import { DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from 'reka-ui'
import AgentActivityStream from '../components/AgentActivityStream.vue'
import { api } from '../api/client'
import { messageFrom, useWorkspaceStore } from '../stores/workspace'
import { useAgentStore } from '../stores/agent'
import type { AgentApprovalDecision, AgentPermissionMode, AgentRuntimeStatus } from '../types'

const store = useAgentStore()
const workspace = useWorkspaceStore()
const loading = ref(true)
const creating = ref(false)
const acting = ref(false)
const pageError = ref('')
const fullTrustDialog = ref(false)
const fullTrustAction = ref<'create' | 'activate'>('create')
const streamHost = ref<HTMLElement | null>(null)
const modelName = ref('')
const runtime = ref<AgentRuntimeStatus | null>(null)
const composing = ref(false)
const statusLabel = computed(() => ({
  created: '已就绪',
  running: '正在运行',
  awaiting_approval: '等待审批',
  succeeded: '本轮完成',
  failed: '本轮失败',
  aborted: '已中止',
  interrupted: '已中断',
}[store.session?.status ?? 'created']))
const canSend = computed(() => Boolean(store.session?.is_active && store.draft.trim() && !store.session.active_prompt && !acting.value))

onMounted(async () => {
  try {
    const [, connection, runtimeStatus] = await Promise.all([
      store.loadSession(),
      api.agentConnection(),
      api.agentRuntime(),
    ])
    modelName.value = connection.model
    runtime.value = runtimeStatus
  } catch (cause) {
    pageError.value = messageFrom(cause)
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(store.disconnectEvents)

async function createSession(mode: AgentPermissionMode, confirmed = false): Promise<void> {
  creating.value = true
  pageError.value = ''
  try {
    await store.createSession(mode, confirmed)
    fullTrustDialog.value = false
  } catch (cause) {
    pageError.value = messageFrom(cause)
  } finally {
    creating.value = false
  }
}

async function selectSession(sessionId: string): Promise<void> {
  if (store.session?.active_prompt || store.session?.pending_approval_ids.length) {
    pageError.value = 'Agent 运行或等待审批期间不能切换会话，请先中止或完成审批。'
    return
  }
  acting.value = true
  pageError.value = ''
  try {
    await store.selectSession(sessionId)
  } catch (cause) {
    pageError.value = messageFrom(cause)
  } finally {
    acting.value = false
  }
}

function prepareNewSession(): void {
  if (store.session?.active_prompt || store.session?.pending_approval_ids.length) {
    pageError.value = 'Agent 运行或等待审批期间不能新建会话。'
    return
  }
  store.prepareNewSession()
}

async function activateSession(confirmed = false): Promise<void> {
  if (!store.session) return
  acting.value = true
  pageError.value = ''
  try {
    await store.activateSession(store.session.session_id, confirmed)
    fullTrustDialog.value = false
  } catch (cause) {
    pageError.value = messageFrom(cause)
  } finally {
    acting.value = false
  }
}

function requestFullTrust(action: 'create' | 'activate'): void {
  fullTrustAction.value = action
  fullTrustDialog.value = true
}

async function confirmFullTrust(): Promise<void> {
  if (fullTrustAction.value === 'activate') await activateSession(true)
  else await createSession('full_trust', true)
}

function sessionTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function send(): Promise<void> {
  if (!canSend.value) return
  acting.value = true
  pageError.value = ''
  try {
    await store.sendMessage()
    await nextTick()
    streamHost.value?.scrollTo({ top: streamHost.value.scrollHeight, behavior: 'smooth' })
  } catch (cause) {
    pageError.value = messageFrom(cause)
  } finally {
    acting.value = false
  }
}

async function decide(requestId: string, decision: AgentApprovalDecision): Promise<void> {
  acting.value = true
  try {
    await store.resolveApproval(requestId, decision)
  } catch (cause) {
    pageError.value = messageFrom(cause)
  } finally {
    acting.value = false
  }
}

async function abort(): Promise<void> {
  acting.value = true
  try {
    await store.abort()
  } catch (cause) {
    pageError.value = messageFrom(cause)
  } finally {
    acting.value = false
  }
}

async function closeSession(): Promise<void> {
  acting.value = true
  try {
    await store.closeSession()
  } catch (cause) {
    pageError.value = messageFrom(cause)
  } finally {
    acting.value = false
  }
}

function handleComposerKey(event: KeyboardEvent): void {
  if (event.isComposing || composing.value || event.keyCode === 229) return
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    void send()
  }
}
</script>

<template>
  <section class="agent-view" :class="{ 'with-session-list': store.sessions.length > 0 }">
    <aside v-if="store.sessions.length" class="agent-session-list" data-test="agent-session-list">
      <header><span>会话</span><button type="button" aria-label="新建 Agent 会话" @click="prepareNewSession"><Plus :size="15" /></button></header>
      <div class="agent-session-items">
        <button
          v-for="item in store.sessions"
          :key="item.session_id"
          type="button"
          :class="{ selected: item.session_id === store.session?.session_id, active: item.is_active }"
          :disabled="acting"
          @click="selectSession(item.session_id)"
        >
          <span><i />{{ item.title }}</span>
          <small><Clock3 :size="11" />{{ sessionTime(item.updated_at) }} · {{ item.status }}</small>
        </button>
      </div>
      <footer>当前 workspace · 单活 Worker</footer>
    </aside>

    <div class="agent-stage">
      <div v-if="loading" class="loading-state"><span class="spinner" /><span>正在恢复 Agent session</span></div>

      <div v-else-if="!store.session && runtime?.state !== 'ready'" class="agent-runtime-required" data-test="agent-runtime-required">
      <span class="agent-mark"><CircleAlert :size="22" /></span>
      <div><span class="eyebrow">LOCAL PI AGENT</span><h1>Agent Runtime 尚未就绪</h1></div>
      <p>{{ runtime?.message || pageError || '无法读取本地 Agent Runtime 状态。' }}</p>
      <p>编辑、codegen、执行与报告功能不受影响。安装完成后才能创建 Pi Agent session。</p>
      <RouterLink class="primary-btn" to="/settings/agent">打开模型连接与 Runtime 设置</RouterLink>
      </div>

      <div v-else-if="!store.session" class="agent-onboarding">
      <header>
        <span class="agent-mark"><Bot :size="24" /></span>
        <div><span class="eyebrow">LOCAL PI AGENT</span><h1>在测试工作台内运行 Agent</h1></div>
      </header>
      <p>Pi 可以读取测试资产、运行仓库 Skill、调用 AITest CLI，并在需要写文件或执行 Shell 时走权限审批。</p>
      <div class="agent-mode-options">
        <button type="button" data-test="create-approval-session" @click="createSession('approval')">
          <ShieldCheck :size="19" /><span><strong>审批模式</strong><small>读取和检索直接执行，写文件、Shell 和外部目录逐次审批</small></span><b>推荐</b>
        </button>
        <button type="button" data-test="create-full-trust-session" @click="requestFullTrust('create')">
          <Shield :size="19" /><span><strong>完全信任</strong><small>所有原生工具直接执行，适合明确可信的本地研发 workspace</small></span>
        </button>
      </div>
      <p v-if="pageError" class="inline-error"><CircleAlert :size="15" />{{ pageError }} <RouterLink to="/settings/agent">检查模型连接</RouterLink></p>
      <RouterLink class="agent-connection-link" to="/settings/agent">模型、Base URL 或 API Key 尚未配置？打开模型连接</RouterLink>
      </div>

      <template v-else>
      <header class="agent-session-header">
        <div class="agent-session-title">
          <span class="agent-mark"><Bot :size="20" /></span>
          <div><span class="eyebrow">PI AGENT / {{ modelName || 'MODEL' }} / {{ store.session.permission_mode.toUpperCase() }}</span><h1>{{ store.session.title }}</h1></div>
        </div>
        <div class="agent-session-meta">
          <button class="secondary-btn agent-new-session" type="button" :disabled="acting || store.session.active_prompt" @click="prepareNewSession"><Plus :size="14" />新会话</button>
          <span v-if="store.session.is_active" class="agent-stream-state" :class="store.connectionState"><i />{{ store.connectionState }}</span>
          <span v-else class="agent-stream-state"><i />历史</span>
          <span class="agent-run-state" :class="store.session.status">{{ statusLabel }}</span>
          <span v-if="store.session.permission_mode === 'full_trust'" class="full-trust-badge"><Shield :size="13" />完全信任</span>
          <button class="icon-btn" type="button" aria-label="归档 Agent session" :disabled="acting || store.session.active_prompt" @click="closeSession"><Trash2 :size="15" /></button>
        </div>
      </header>

      <div class="agent-notices">
        <p v-if="store.session.permission_mode === 'full_trust'" class="full-trust-banner">
          <Shield :size="14" />{{ store.session.is_active ? '当前 session 继承本地权限，读取到的文件内容可能进入模型上下文。' : '该历史 session 上次使用完全信任模式；继续前需要重新确认。' }}
        </p>
        <p v-if="store.session.status === 'interrupted'" class="agent-interrupted"><CircleAlert :size="14" />已恢复到最后持久化位置；最后一次工具执行结果可能未知，不会自动重试。</p>
        <p v-if="pageError || store.error" class="agent-error"><CircleAlert :size="14" />{{ pageError || store.error }}</p>
      </div>

      <div ref="streamHost" class="agent-stream-host">
        <AgentActivityStream
          :events="store.activityEvents"
          :pending-ids="store.session.pending_approval_ids"
          @decide="decide"
        />
      </div>

      <form v-if="store.session.is_active" class="agent-composer" @submit.prevent="send">
        <textarea
          v-model="store.draft"
          data-test="agent-composer"
          maxlength="65536"
          :disabled="store.session.status === 'awaiting_approval'"
          placeholder="让 Pi 检查 suite、运行 Skill，或生成新的测试资产…"
          @keydown="handleComposerKey"
          @compositionstart="composing = true"
          @compositionend="composing = false"
        />
        <div>
          <span>Enter 发送 · Shift Enter 换行</span>
          <button v-if="store.session.active_prompt" class="abort-agent-btn" type="button" :disabled="acting" @click="abort"><OctagonX :size="15" />中止</button>
          <button v-else class="primary-btn" type="submit" data-test="send-agent-message" :disabled="!canSend">
            <LoaderCircle v-if="acting" class="spin-icon" :size="15" /><Send v-else :size="15" />发送
          </button>
        </div>
      </form>
      <div v-else class="agent-resume-bar">
        <span>历史只读 · 继续后会启动本地 Pi Worker</span>
        <button
          class="primary-btn"
          data-test="activate-agent-session"
          type="button"
          :disabled="acting"
          @click="store.session.permission_mode === 'full_trust' ? requestFullTrust('activate') : activateSession()"
        ><Play :size="15" />继续会话</button>
      </div>
      </template>
    </div>
  </section>

  <DialogRoot v-model:open="fullTrustDialog">
    <DialogPortal>
      <DialogOverlay class="asset-modal-backdrop">
        <DialogContent class="full-trust-dialog" data-test="full-trust-dialog">
          <header><div><span class="eyebrow">EXPLICIT TRUST</span><DialogTitle>启用完全信任模式</DialogTitle></div><button aria-label="关闭" @click="fullTrustDialog = false"><X :size="17" /></button></header>
          <DialogDescription>
            Pi 将继承 Console 进程在本机的文件和 Shell 权限，不再逐次询问。读取到的文件内容可能发送给当前模型服务。
          </DialogDescription>
          <div class="trust-workspace"><span>当前 workspace</span><code>{{ workspace.snapshot?.path }}</code></div>
          <p>该确认只对本次 session 生效，不会保存为下次默认授权。</p>
          <footer><button class="secondary-btn" @click="fullTrustDialog = false">取消</button><button class="danger-btn compact" data-test="confirm-full-trust" :disabled="creating || acting" @click="confirmFullTrust"><Shield :size="15" />{{ fullTrustAction === 'activate' ? '确认并继续' : '确认并创建' }}</button></footer>
        </DialogContent>
      </DialogOverlay>
    </DialogPortal>
  </DialogRoot>
</template>
