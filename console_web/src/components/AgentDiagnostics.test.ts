import { mount } from '@vue/test-utils'
import { expect, test } from 'vitest'
import AgentDiagnostics from './AgentDiagnostics.vue'
import type { AgentSessionSnapshot } from '../types'

const session = {
  status: 'running', active_prompt: true, pending_approval_ids: [],
  diagnostics: { message_id: 'm', retry: null, requests: [{
    request_id: 'r', message_id: 'm', phase: 'waiting_text', detail: 'off',
    started_at: new Date().toISOString(), phase_started_at: new Date().toISOString(), headers_ms: 321,
  }] },
} as unknown as AgentSessionSnapshot

test('shows true stage, unavailable metrics and approval precedence', async () => {
  const wrapper = mount(AgentDiagnostics, { props: { session } })
  expect(wrapper.text()).toContain('已连接，等待回复')
  expect(wrapper.text()).toContain('未采集')
  expect(wrapper.text()).not.toContain('正在思考')
  await wrapper.setProps({ session: { ...session, status: 'awaiting_approval', pending_approval_ids: ['p'] } })
  expect(wrapper.get('[data-test="agent-request-stage"]').text()).toContain('等待你的审批')
  await wrapper.setProps({ session: { ...session, active_prompt: false, status: 'interrupted' } })
  expect(wrapper.get('[data-test="agent-request-stage"]').text()).toContain('已中断')
  wrapper.unmount()
})

test('retry backoff is visible and completed old calls cannot masquerade as new requests', async () => {
  const wrapper = mount(AgentDiagnostics, { props: { session: {
    ...session, diagnostics: { ...session.diagnostics!, retry: { phase: 'start', waiting: true, attempt: 1, max_attempts: 2, delay_ms: 2000 } },
  } } })
  expect(wrapper.get('[data-test="agent-request-stage"]').text()).toContain('自动重试 1/2')
  await wrapper.setProps({ session: { ...session, diagnostics: { ...session.diagnostics!, message_id: 'new' } } })
  expect(wrapper.get('[data-test="agent-request-stage"]').text()).toContain('正在准备请求')
  wrapper.unmount()
})
