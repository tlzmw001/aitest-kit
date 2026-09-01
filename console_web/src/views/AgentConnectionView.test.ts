import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AgentConnectionView from './AgentConnectionView.vue'
import { api } from '../api/client'

vi.mock('../api/client', () => ({
  ApiError: class ApiError extends Error {
    code = 'TEST_ERROR'
  },
  api: {
    agentConnection: vi.fn(),
    testAgentConnection: vi.fn(),
    saveAgentConnection: vi.fn(),
    agentRuntime: vi.fn(),
    setupAgentRuntime: vi.fn(),
    agentRuntimeSetupJob: vi.fn(),
    cancelAgentRuntimeSetup: vi.fn(),
  },
}))

const connection = {
  connection_name: 'Gateway',
  protocol: 'auto' as const,
  base_url: 'https://gateway.example.test',
  model: 'gpt-5.5',
  api_key_env: 'GATEWAY_API_KEY',
  has_api_key: false,
  credential_source: 'missing' as const,
}

const runtime = {
  state: 'ready' as const,
  source: 'source' as const,
  message: 'ready',
  runtime_dir: '/repo/agent_runtime/pi_worker',
  bundle_hash: 'a'.repeat(64),
  minimum_node_version: '22.19.0',
  node_version: 'v24.14.0',
  npm_version: '11.9.0',
  registry: 'https://registry.npmjs.org/',
  dependencies: [
    { name: '@earendil-works/pi-coding-agent', version: '0.84.3' },
    { name: '@gotgenes/pi-permission-system', version: '27.1.1' },
  ],
  setup_command: 'aitest agent setup',
}

describe('AgentConnectionView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(api.agentConnection).mockResolvedValue(connection)
    vi.mocked(api.agentRuntime).mockResolvedValue(runtime)
  })

  it('loads user-facing fields without exposing provider as an input', async () => {
    const wrapper = mount(AgentConnectionView)
    await flushPromises()

    expect(wrapper.get<HTMLInputElement>('[data-test="connection-name"]').element.value).toBe('Gateway')
    expect(wrapper.get<HTMLInputElement>('[data-test="connection-model"]').element.value).toBe('gpt-5.5')
    expect(wrapper.find('[name="provider"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('无需查找 Pi Provider')
  })

  it('runs a real connection test and shows detected protocol details', async () => {
    vi.mocked(api.testAgentConnection).mockResolvedValue({
      status: 'connected',
      detected_protocol: 'openai_responses',
      internal_provider: 'openai',
      model: 'gpt-5.5',
      response_text: 'OK',
      latency_ms: 6218,
    })
    const wrapper = mount(AgentConnectionView)
    await flushPromises()
    await wrapper.get('[data-test="connection-api-key"]').setValue('session-secret')

    await wrapper.get('[data-test="test-connection"]').trigger('click')
    await flushPromises()

    expect(api.testAgentConnection).toHaveBeenCalledWith(expect.objectContaining({
      protocol: 'auto',
      model: 'gpt-5.5',
      api_key: 'session-secret',
    }))
    expect(wrapper.text()).toContain('OpenAI Responses')
    expect(wrapper.text()).toContain('openai')
    expect(wrapper.text()).toContain('6.22 s')
    expect(wrapper.text()).toContain('OK')
  })

  it('invalidates a previous success when connection fields change', async () => {
    vi.mocked(api.testAgentConnection).mockResolvedValue({
      status: 'connected',
      detected_protocol: 'openai_responses',
      internal_provider: 'openai',
      model: 'gpt-5.5',
      response_text: 'OK',
      latency_ms: 100,
    })
    const wrapper = mount(AgentConnectionView)
    await flushPromises()
    await wrapper.get('[data-test="test-connection"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('连接测试成功')

    await wrapper.get('[data-test="connection-model"]').setValue('gpt-5.6')

    expect(wrapper.text()).toContain('尚未测试当前配置')
    expect(wrapper.text()).not.toContain('连接测试成功')
  })

  it('saves non-sensitive config, clears the key field, and keeps status meanings separate', async () => {
    vi.mocked(api.saveAgentConnection).mockResolvedValue({
      ...connection,
      has_api_key: true,
      credential_source: 'session',
    })
    const wrapper = mount(AgentConnectionView)
    await flushPromises()
    await wrapper.get('[data-test="connection-api-key"]').setValue('session-secret')

    await wrapper.get('[data-test="save-connection"]').trigger('click')
    await flushPromises()

    expect(wrapper.get<HTMLInputElement>('[data-test="connection-api-key"]').element.value).toBe('')
    expect(wrapper.text()).toContain('配置已保存')
    expect(wrapper.text()).toContain('当前 Console 会话已提供 Key')
    expect(wrapper.text()).not.toContain('连接测试成功')
  })

  it('shows a backend test failure next to the test result surface', async () => {
    vi.mocked(api.testAgentConnection).mockRejectedValue(new Error('API Key 无效'))
    const wrapper = mount(AgentConnectionView)
    await flushPromises()
    await wrapper.get('[data-test="connection-api-key"]').setValue('bad-key')

    await wrapper.get('[data-test="test-connection"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-test="connection-test-error"]').text()).toContain('API Key 无效')
  })

  it('shows the ready Runtime source separately from model credentials', async () => {
    const wrapper = mount(AgentConnectionView)
    await flushPromises()

    expect(wrapper.get('[data-test="agent-runtime-card"]').text()).toContain('源码 checkout')
    expect(wrapper.get('[data-test="agent-runtime-card"]').text()).toContain('v24.14.0')
    expect(wrapper.get('[data-test="agent-runtime-card"]').text()).toContain('aaaaaaaaaaaa')
  })

  it('requires a dialog confirmation before starting Runtime setup', async () => {
    vi.mocked(api.agentRuntime).mockResolvedValue({ ...runtime, state: 'missing', source: null, message: 'missing' })
    vi.mocked(api.setupAgentRuntime).mockResolvedValue({
      id: 'setup-1', operation: 'agent_runtime_setup', command_summary: 'aitest agent setup',
      status: 'succeeded', output: 'installed', exit_code: 0, started_at: '', finished_at: '', cancel_requested: false,
    })
    vi.mocked(api.agentRuntimeSetupJob).mockResolvedValue({
      id: 'setup-1', operation: 'agent_runtime_setup', command_summary: 'aitest agent setup',
      status: 'succeeded', output: 'installed', exit_code: 0, started_at: '', finished_at: '', cancel_requested: false,
    })
    const wrapper = mount(AgentConnectionView, { attachTo: document.body })
    await flushPromises()

    await wrapper.get('[data-test="open-runtime-setup"]').trigger('click')
    expect(api.setupAgentRuntime).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('不修改 workspace')
    const confirm = document.body.querySelector('[data-test="confirm-runtime-setup"]') as HTMLButtonElement
    confirm.click()
    await flushPromises()

    expect(api.setupAgentRuntime).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('disables Runtime setup until a supported Node is installed', async () => {
    vi.mocked(api.agentRuntime).mockResolvedValue({
      ...runtime,
      state: 'node_unsupported',
      source: null,
      message: 'Node v20.0.0 低于最低版本 22.19.0',
      node_version: 'v20.0.0',
    })
    const wrapper = mount(AgentConnectionView)
    await flushPromises()

    expect(wrapper.get<HTMLButtonElement>('[data-test="open-runtime-setup"]').element.disabled).toBe(true)
    expect(wrapper.text()).toContain('Node v20.0.0')
  })

  it('shows bounded setup output and can cancel an installing Runtime job', async () => {
    vi.mocked(api.agentRuntime).mockResolvedValue({ ...runtime, state: 'missing', source: null, message: 'missing' })
    vi.mocked(api.setupAgentRuntime).mockResolvedValue({
      id: 'setup-2', operation: 'agent_runtime_setup', command_summary: 'aitest agent setup',
      status: 'running', output: 'Installing locked npm dependencies...', exit_code: null,
      started_at: 'now', finished_at: '', cancel_requested: false,
    })
    vi.mocked(api.cancelAgentRuntimeSetup).mockResolvedValue({
      id: 'setup-2', operation: 'agent_runtime_setup', command_summary: 'aitest agent setup',
      status: 'cancelled', output: 'Installing locked npm dependencies...', exit_code: 143,
      started_at: 'now', finished_at: 'later', cancel_requested: true,
    })
    const wrapper = mount(AgentConnectionView, { attachTo: document.body })
    await flushPromises()
    await wrapper.get('[data-test="open-runtime-setup"]').trigger('click')
    const confirm = document.body.querySelector('[data-test="confirm-runtime-setup"]') as HTMLButtonElement
    confirm.click()
    await flushPromises()

    expect(document.body.textContent).toContain('Installing locked npm dependencies')
    const cancel = Array.from(document.body.querySelectorAll('button')).find((button) => button.textContent?.includes('取消安装'))
    cancel?.click()
    await flushPromises()

    expect(api.cancelAgentRuntimeSetup).toHaveBeenCalledWith('setup-2')
    wrapper.unmount()
  })

  it('keeps a failed Runtime setup retryable with its log visible', async () => {
    vi.mocked(api.agentRuntime).mockResolvedValue({ ...runtime, state: 'missing', source: null, message: 'missing' })
    vi.mocked(api.setupAgentRuntime).mockResolvedValue({
      id: 'setup-3', operation: 'agent_runtime_setup', command_summary: 'aitest agent setup',
      status: 'failed', output: 'AGENT_RUNTIME_INSTALL_FAILED', exit_code: 1,
      started_at: 'now', finished_at: 'later', cancel_requested: false,
    })
    const wrapper = mount(AgentConnectionView, { attachTo: document.body })
    await flushPromises()
    await wrapper.get('[data-test="open-runtime-setup"]').trigger('click')
    const confirm = document.body.querySelector('[data-test="confirm-runtime-setup"]') as HTMLButtonElement
    confirm.click()
    await flushPromises()

    expect(document.body.textContent).toContain('Agent Runtime 安装失败')
    expect(document.body.textContent).toContain('AGENT_RUNTIME_INSTALL_FAILED')
    expect(document.body.querySelector('[data-test="confirm-runtime-setup"]')).not.toBeNull()
    wrapper.unmount()
  })
})
