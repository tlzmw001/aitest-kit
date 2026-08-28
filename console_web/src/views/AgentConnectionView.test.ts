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

describe('AgentConnectionView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(api.agentConnection).mockResolvedValue(connection)
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
})
