import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import { api } from '../api/client'
import { useAgentStore } from './agent'
import type { AgentEvent, AgentSessionSnapshot } from '../types'

vi.mock('../api/client', () => ({
  api: {
    agentSession: vi.fn(),
    agentSessions: vi.fn(),
    agentSessionHistory: vi.fn(),
    createAgentSession: vi.fn(),
    activateAgentSession: vi.fn(),
    streamAgentEvents: vi.fn(() => new Promise(() => undefined)),
    sendAgentMessage: vi.fn(),
    resolveAgentApproval: vi.fn(),
    abortAgent: vi.fn(),
    closeAgentSession: vi.fn(),
  },
}))

const snapshot: AgentSessionSnapshot = {
  session_id: 'session-1',
  pi_session_id: 'pi-1',
  permission_mode: 'approval',
  title: '检查 suite',
  status: 'created',
  active_prompt: false,
  pending_approval_ids: [],
  last_seq: 0,
  created_at: 'now',
  updated_at: 'now',
  is_active: true,
}

function event(seq: number, type: string, payload: Record<string, unknown> = {}): AgentEvent {
  return { event_id: `e-${seq}`, seq, session_id: 'session-1', type, payload, timestamp: 'now', correlation_id: '' }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

test('event projection is idempotent and tracks pending approval', () => {
  const store = useAgentStore()
  store.session = structuredClone(snapshot)

  store.applyEvent(event(1, 'permission_requested', { request_id: 'p-1' }))
  store.applyEvent(event(1, 'permission_requested', { request_id: 'p-1' }))

  expect(store.events).toHaveLength(1)
  expect(store.pendingApprovals).toHaveLength(1)
  expect(store.session?.status).toBe('awaiting_approval')
})

test('resync replaces stale projection without adding a normal event', () => {
  const store = useAgentStore()
  store.session = structuredClone(snapshot)
  store.applyEvent(event(1, 'text_delta', { delta: 'old' }))

  store.applyEvent(event(7, 'resync_required', { session: { ...snapshot, last_seq: 7, status: 'running' } }))

  expect(store.events).toEqual([])
  expect(store.lastSeq).toBe(7)
  expect(store.session?.status).toBe('running')
})

test('full trust confirmation is forwarded only when requested', async () => {
  vi.mocked(api.createAgentSession).mockResolvedValue({ ...snapshot, permission_mode: 'full_trust' })
  const store = useAgentStore()

  await store.createSession('full_trust', true)

  expect(api.createAgentSession).toHaveBeenCalledWith('full_trust', true)
})

test('startup selects persisted history without starting an inactive event stream', async () => {
  const historical = { ...snapshot, is_active: false, status: 'interrupted' as const }
  vi.mocked(api.agentSession).mockResolvedValue(null)
  vi.mocked(api.agentSessions).mockResolvedValue({ sessions: [historical] })
  vi.mocked(api.agentSessionHistory).mockResolvedValue({ events: [event(1, 'user_message')], last_seq: 1, resync_required: false })
  const store = useAgentStore()

  await store.loadSession()

  expect(store.session?.session_id).toBe('session-1')
  expect(store.events).toHaveLength(1)
  expect(api.streamAgentEvents).not.toHaveBeenCalled()
})

test('activating a stored session attaches the worker and event stream', async () => {
  const historical = { ...snapshot, is_active: false }
  vi.mocked(api.agentSession).mockResolvedValue(null)
  vi.mocked(api.agentSessions).mockResolvedValue({ sessions: [historical] })
  vi.mocked(api.agentSessionHistory).mockResolvedValue({ events: [], last_seq: 0, resync_required: false })
  vi.mocked(api.activateAgentSession).mockResolvedValue({ ...snapshot, is_active: true })
  const store = useAgentStore()
  await store.loadSession()

  await store.activateSession('session-1')

  expect(api.activateAgentSession).toHaveBeenCalledWith('session-1', false)
  expect(api.streamAgentEvents).toHaveBeenCalled()
})

test('full trust activation forwards the renewed confirmation', async () => {
  vi.mocked(api.activateAgentSession).mockResolvedValue({ ...snapshot, permission_mode: 'full_trust' })
  const store = useAgentStore()
  store.session = { ...snapshot, permission_mode: 'full_trust', is_active: false }

  await store.activateSession('session-1', true)

  expect(api.activateAgentSession).toHaveBeenCalledWith('session-1', true)
})

test('failed activation preserves the selected session and its history', async () => {
  const historical = { ...snapshot, is_active: false, status: 'interrupted' as const }
  vi.mocked(api.activateAgentSession).mockRejectedValue(new Error('worker busy'))
  const store = useAgentStore()
  store.session = historical
  store.events = [event(1, 'user_message')]
  store.lastSeq = 1

  await expect(store.activateSession('session-1')).rejects.toThrow('worker busy')

  expect(store.session).toEqual(historical)
  expect(store.events).toEqual([event(1, 'user_message')])
  expect(store.lastSeq).toBe(1)
})

test('archiving the selected session falls back to the next stored history', async () => {
  const next = { ...snapshot, session_id: 'session-2', title: '第二个会话', is_active: false }
  vi.mocked(api.agentSessionHistory).mockResolvedValue({ events: [], last_seq: 0, resync_required: false })
  const store = useAgentStore()
  store.session = structuredClone(snapshot)
  store.sessions = [structuredClone(snapshot), next]

  await store.closeSession()

  expect(api.closeAgentSession).toHaveBeenCalledWith('session-1')
  expect(store.session?.session_id).toBe('session-2')
  expect(api.agentSessionHistory).toHaveBeenCalledWith('session-2')
})
