import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../api/client'
import type {
  AgentApprovalDecision,
  AgentEvent,
  AgentPermissionMode,
  AgentSessionSnapshot,
} from '../types'
import { useWorkspaceStore } from './workspace'

export type AgentConnectionState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'failed'

export const useAgentStore = defineStore('agent', () => {
  const session = ref<AgentSessionSnapshot | null>(null)
  const events = ref<AgentEvent[]>([])
  const lastSeq = ref(0)
  const connectionState = ref<AgentConnectionState>('idle')
  const error = ref('')
  const draft = ref('')
  let streamController: AbortController | null = null

  const pendingApprovals = computed(() => {
    const pending = new Set(session.value?.pending_approval_ids ?? [])
    return events.value.filter(
      (event) => event.type === 'permission_requested' && pending.has(String(event.payload.request_id ?? '')),
    )
  })

  async function loadSession(): Promise<void> {
    const loaded = await api.agentSession()
    if (!loaded) {
      reset()
      return
    }
    if (session.value?.session_id !== loaded.session_id) {
      events.value = []
      lastSeq.value = 0
    }
    session.value = loaded
    connectEvents()
  }

  async function createSession(mode: AgentPermissionMode, confirmed = false): Promise<void> {
    disconnectEvents()
    events.value = []
    lastSeq.value = 0
    error.value = ''
    session.value = await api.createAgentSession(mode, confirmed)
    connectEvents()
  }

  function connectEvents(): void {
    if (!session.value || streamController) return
    const controller = new AbortController()
    streamController = controller
    connectionState.value = 'connecting'
    void runEventLoop(session.value.session_id, controller)
  }

  async function runEventLoop(sessionId: string, controller: AbortController): Promise<void> {
    let failures = 0
    while (!controller.signal.aborted && streamController === controller) {
      try {
        await api.streamAgentEvents(
          sessionId,
          lastSeq.value,
          controller.signal,
          (event) => {
            failures = 0
            applyEvent(event)
          },
          () => {
            connectionState.value = 'connected'
          },
          () => {
            failures = 0
          },
        )
        if (controller.signal.aborted) return
        failures += 1
      } catch (caught) {
        if (controller.signal.aborted || (caught instanceof DOMException && caught.name === 'AbortError')) return
        failures += 1
        error.value = caught instanceof Error ? caught.message : String(caught)
      }
      if (failures >= 5) {
        connectionState.value = 'failed'
        streamController = null
        return
      }
      connectionState.value = 'reconnecting'
      await reconnectDelay(250 * 2 ** (failures - 1), controller.signal)
    }
  }

  function applyEvent(event: AgentEvent): void {
    if (event.type === 'resync_required') {
      const snapshot = event.payload.session as AgentSessionSnapshot | undefined
      if (snapshot) session.value = snapshot
      events.value = []
      lastSeq.value = event.seq
      connectionState.value = 'connected'
      return
    }
    if (event.seq <= lastSeq.value || (session.value && event.session_id !== session.value.session_id)) return
    events.value.push(event)
    if (events.value.length > 1000) events.value.splice(0, events.value.length - 1000)
    lastSeq.value = event.seq
    connectionState.value = 'connected'
    error.value = ''
    projectSession(event)
  }

  function projectSession(event: AgentEvent): void {
    if (!session.value) return
    session.value.last_seq = event.seq
    session.value.updated_at = event.timestamp
    if (event.type === 'user_message') {
      session.value.active_prompt = true
      session.value.status = 'running'
    } else if (event.type === 'permission_requested') {
      const requestId = String(event.payload.request_id ?? '')
      if (requestId && !session.value.pending_approval_ids.includes(requestId)) {
        session.value.pending_approval_ids.push(requestId)
      }
      session.value.status = 'awaiting_approval'
    } else if (['permission_resolved', 'approval_submitted', 'permission_invalid'].includes(event.type)) {
      const requestId = String(event.payload.request_id ?? '')
      session.value.pending_approval_ids = session.value.pending_approval_ids.filter((item) => item !== requestId)
      session.value.status = session.value.pending_approval_ids.length ? 'awaiting_approval' : 'running'
    } else if (event.type === 'agent_finished' || event.type === 'aborted' || event.type === 'error') {
      const eventStatus = String(event.payload.status ?? '')
      session.value.status = event.type === 'agent_finished' && ['succeeded', 'failed', 'aborted'].includes(eventStatus)
        ? eventStatus as AgentSessionSnapshot['status']
        : event.type === 'aborted' ? 'aborted' : 'failed'
      session.value.active_prompt = false
      session.value.pending_approval_ids = []
      void useWorkspaceStore().refresh()
    }
  }

  async function sendMessage(text = draft.value): Promise<void> {
    if (!session.value) return
    session.value = await api.sendAgentMessage(session.value.session_id, text)
    draft.value = ''
  }

  async function resolveApproval(requestId: string, decision: AgentApprovalDecision): Promise<void> {
    if (!session.value) return
    session.value = await api.resolveAgentApproval(session.value.session_id, requestId, decision)
  }

  async function abort(): Promise<void> {
    if (!session.value) return
    session.value = await api.abortAgent(session.value.session_id)
  }

  async function closeSession(): Promise<void> {
    if (!session.value) return
    const sessionId = session.value.session_id
    disconnectEvents()
    await api.closeAgentSession(sessionId)
    reset()
  }

  function disconnectEvents(): void {
    streamController?.abort()
    streamController = null
    connectionState.value = session.value ? 'idle' : 'idle'
  }

  function reset(): void {
    disconnectEvents()
    session.value = null
    events.value = []
    lastSeq.value = 0
    error.value = ''
    draft.value = ''
  }

  return {
    session,
    events,
    lastSeq,
    connectionState,
    pendingApprovals,
    error,
    draft,
    loadSession,
    createSession,
    connectEvents,
    disconnectEvents,
    applyEvent,
    sendMessage,
    resolveApproval,
    abort,
    closeSession,
  }
})

function reconnectDelay(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = window.setTimeout(resolve, Math.min(milliseconds, 4000))
    signal.addEventListener('abort', () => {
      window.clearTimeout(timer)
      resolve()
    }, { once: true })
  })
}
