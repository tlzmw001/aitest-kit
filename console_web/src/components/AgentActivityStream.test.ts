import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import AgentActivityStream, { projectActivities } from './AgentActivityStream.vue'
import type { AgentEvent } from '../types'

function event(seq: number, type: string, payload: Record<string, unknown>): AgentEvent {
  return { event_id: `e-${seq}`, seq, session_id: 'session-1', type, payload, timestamp: 'now', correlation_id: '' }
}

describe('AgentActivityStream', () => {
  it('groups text deltas and correlates tool completion by tool id', () => {
    const items = projectActivities([
      event(1, 'text_delta', { delta: '你好' }),
      event(2, 'text_delta', { delta: '，正在检查。' }),
      event(3, 'tool_call_requested', { tool_call_id: 't-1', tool_name: 'bash', input: { command: 'aitest run --all' } }),
      event(4, 'tool_call_finished', { tool_call_id: 't-1', tool_name: 'bash', is_error: false, result: { output: 'ok' } }),
    ], new Set())

    expect(items).toHaveLength(2)
    expect(items[0]).toMatchObject({ kind: 'assistant', text: '你好，正在检查。' })
    expect(items[1]).toMatchObject({ kind: 'tool', event: { payload: { state: 'finished' } } })
  })

  it('renders an inline pending approval with all three decisions', () => {
    const request = event(1, 'permission_requested', {
      request_id: 'p-1', tool_name: 'bash', surface: 'bash', command: 'aitest run --all',
    })
    const wrapper = mount(AgentActivityStream, {
      props: { events: [request], pendingIds: ['p-1'] },
      global: { plugins: [createPinia()] },
    })

    expect(wrapper.get('[data-test="agent-approval-card"]').text()).toContain('aitest run --all')
    expect(wrapper.text()).toContain('允许一次')
    expect(wrapper.text()).toContain('本会话允许')
    expect(wrapper.text()).toContain('拒绝')
  })
})
