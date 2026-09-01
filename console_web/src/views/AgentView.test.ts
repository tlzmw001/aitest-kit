import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AgentView from './AgentView.vue'
import { api } from '../api/client'

vi.mock('../api/client', () => ({
  api: {
    agentSession: vi.fn(),
    agentSessions: vi.fn(),
    agentSessionHistory: vi.fn(),
    agentConnection: vi.fn(),
    agentRuntime: vi.fn(),
    streamAgentEvents: vi.fn(() => new Promise(() => undefined)),
    createAgentSession: vi.fn(),
    activateAgentSession: vi.fn(),
    closeAgentSession: vi.fn(),
  },
}))

const runtime = {
  state: 'ready' as const,
  source: 'user' as const,
  message: 'ready',
  runtime_dir: '/tmp/runtime',
  bundle_hash: 'a'.repeat(64),
  minimum_node_version: '22.19.0',
  node_version: 'v24.14.0',
  npm_version: '11.9.0',
  registry: 'https://registry.npmjs.org/',
  dependencies: [],
  setup_command: 'aitest agent setup',
}

describe('AgentView Runtime gate', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    vi.mocked(api.agentSession).mockResolvedValue(null)
    vi.mocked(api.agentSessions).mockResolvedValue({ sessions: [] })
    vi.mocked(api.agentConnection).mockResolvedValue({
      connection_name: 'Gateway', protocol: 'auto', base_url: '', model: 'gpt-5.5',
      api_key_env: 'AITEST_AGENT_API_KEY', has_api_key: true, credential_source: 'environment',
    })
    vi.mocked(api.agentRuntime).mockResolvedValue(runtime)
  })

  it('does not offer session creation while the Runtime is missing', async () => {
    vi.mocked(api.agentRuntime).mockResolvedValue({ ...runtime, state: 'missing', source: null, message: 'not installed' })
    const wrapper = mount(AgentView, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
    await flushPromises()

    expect(wrapper.get('[data-test="agent-runtime-required"]').text()).toContain('Agent Runtime 尚未就绪')
    expect(wrapper.find('[data-test="create-approval-session"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('模型连接')
  })

  it('offers both permission modes when the Runtime is ready', async () => {
    const wrapper = mount(AgentView, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
    await flushPromises()

    expect(wrapper.find('[data-test="agent-runtime-required"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="create-approval-session"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="create-full-trust-session"]').exists()).toBe(true)
  })

  it('shows persisted sessions as history without attaching a worker', async () => {
    vi.mocked(api.agentSessions).mockResolvedValue({
      sessions: [{
        session_id: 'session-1', pi_session_id: 'pi-1', permission_mode: 'approval', title: '检查订单用例',
        status: 'interrupted', active_prompt: false, pending_approval_ids: [], last_seq: 2,
        created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:01:00Z', is_active: false,
      }],
    })
    vi.mocked(api.agentSessionHistory).mockResolvedValue({ events: [], last_seq: 2, resync_required: false })
    const wrapper = mount(AgentView, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
    await flushPromises()

    expect(wrapper.get('[data-test="agent-session-list"]').text()).toContain('检查订单用例')
    expect(wrapper.get('[data-test="activate-agent-session"]').text()).toContain('继续会话')
    expect(wrapper.text()).toContain('最后持久化位置')
  })
})
