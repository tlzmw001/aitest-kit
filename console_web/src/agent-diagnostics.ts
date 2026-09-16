import type { AgentDiagnosticsSnapshot, AgentEvent, AgentRequestDiagnostic, AgentRetryDiagnostic } from './types'

export function projectDiagnostics(previous: AgentDiagnosticsSnapshot | undefined, event: AgentEvent): AgentDiagnosticsSnapshot {
  const state: AgentDiagnosticsSnapshot = previous ?? { requests: [], retry: null, message_id: '' }
  if (event.type === 'request_diagnostic') {
    const row = event.payload as unknown as AgentRequestDiagnostic
    const index = state.requests.findIndex((item) => item.request_id === row.request_id)
    if (index >= 0) state.requests[index] = row
    else state.requests.push(row)
    state.requests = state.requests.slice(-20)
    state.message_id = row.message_id
    if (row.phase === 'preparing' && state.retry) state.retry.waiting = false
  } else if (event.type === 'agent_retry') {
    state.retry = { ...event.payload, waiting: event.payload.phase === 'start' } as AgentRetryDiagnostic
  } else if (event.type === 'user_message') {
    state.message_id = event.correlation_id
    state.retry = null
  }
  return state
}
