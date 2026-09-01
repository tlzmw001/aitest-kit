import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AgentView from './AgentView.vue'
import { api } from '../api/client'

vi.mock('../api/client', () => ({
  api: {
    agentSession: vi.fn(),
    agentConnection: vi.fn(),
    agentRuntime: vi.fn(),
    streamAgentEvents: vi.fn(() => new Promise(() => undefined)),
    createAgentSession: vi.fn(),
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
})
