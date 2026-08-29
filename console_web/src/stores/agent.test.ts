import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import { api } from '../api/client'
import { useAgentStore } from './agent'
import type { AgentEvent, AgentSessionSnapshot } from '../types'

vi.mock('../api/client', () => ({
  api: {
    agentSession: vi.fn(),
    createAgentSession: vi.fn(),
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
  status: 'created',
  active_prompt: false,
  pending_approval_ids: [],
  last_seq: 0,
  created_at: 'now',
  updated_at: 'now',
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
