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
  const sessions = ref<AgentSessionSnapshot[]>([])
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
    const [listed, active] = await Promise.all([api.agentSessions(), api.agentSession()])
    sessions.value = listed.sessions
    const selected = active ?? sessions.value[0] ?? null
    if (!selected) return resetSelection()
    await selectSnapshot(selected)
  }

  async function createSession(mode: AgentPermissionMode, confirmed = false): Promise<void> {
    disconnectEvents()
    events.value = []
    lastSeq.value = 0
    error.value = ''
    session.value = await api.createAgentSession(mode, confirmed)
    syncSession(session.value)
    connectEvents()
  }

  async function selectSession(sessionId: string): Promise<void> {
    if (session.value?.session_id === sessionId) return
    const selected = sessions.value.find((item) => item.session_id === sessionId)
      ?? await api.agentSessionDetail(sessionId)
    await selectSnapshot(selected)
  }

  async function selectSnapshot(selected: AgentSessionSnapshot): Promise<void> {
    disconnectEvents()
    session.value = selected
    const history = await api.agentSessionHistory(selected.session_id)
    events.value = history.events
    lastSeq.value = history.last_seq
    error.value = ''
    if (selected.is_active) connectEvents()
  }

  async function activateSession(sessionId = session.value?.session_id, confirmed = false): Promise<void> {
    if (!sessionId) return
    const activated = await api.activateAgentSession(sessionId, confirmed)
    disconnectEvents()
    session.value = activated
    syncSession(session.value)
    connectEvents()
  }

  function connectEvents(): void {
    if (!session.value?.is_active || streamController) return
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
      if (snapshot) {
        session.value = snapshot
        syncSession(snapshot)
      }
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
    } else if (event.type === 'session_interrupted') {
      session.value.status = 'interrupted'
      session.value.active_prompt = false
      session.value.pending_approval_ids = []
    }
    syncSession(session.value)
  }

  async function sendMessage(text = draft.value): Promise<void> {
    if (!session.value?.is_active) return
    session.value = await api.sendAgentMessage(session.value.session_id, text)
    syncSession(session.value)
    draft.value = ''
  }

  async function resolveApproval(requestId: string, decision: AgentApprovalDecision): Promise<void> {
    if (!session.value?.is_active) return
    session.value = await api.resolveAgentApproval(session.value.session_id, requestId, decision)
    syncSession(session.value)
  }

  async function abort(): Promise<void> {
    if (!session.value?.is_active) return
    session.value = await api.abortAgent(session.value.session_id)
    syncSession(session.value)
  }

  async function closeSession(): Promise<void> {
    if (!session.value) return
    const sessionId = session.value.session_id
    disconnectEvents()
    await api.closeAgentSession(sessionId)
    sessions.value = sessions.value.filter((item) => item.session_id !== sessionId)
    const next = sessions.value[0]
    if (next) await selectSnapshot(next)
    else resetSelection()
  }

  function disconnectEvents(): void {
    streamController?.abort()
    streamController = null
    connectionState.value = 'idle'
  }

  function resetSelection(): void {
    disconnectEvents()
    session.value = null
    events.value = []
    lastSeq.value = 0
    error.value = ''
    draft.value = ''
  }

  function syncSession(value: AgentSessionSnapshot): void {
    sessions.value = sessions.value.map((item) => ({ ...item, is_active: false }))
    const index = sessions.value.findIndex((item) => item.session_id === value.session_id)
    if (index >= 0) sessions.value[index] = { ...value }
    else sessions.value.unshift({ ...value })
  }

  function prepareNewSession(): void {
    resetSelection()
  }

  return {
    sessions,
    session,
    events,
    lastSeq,
    connectionState,
    pendingApprovals,
    error,
    draft,
    loadSession,
    createSession,
    selectSession,
    activateSession,
    prepareNewSession,
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
