import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EnvironmentView from './EnvironmentView.vue'
import { api } from '../api/client'

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return {
    ...actual,
    api: {
      ...actual.api,
      environment: vi.fn(),
      revealEnv: vi.fn(),
    },
  }
})

describe('EnvironmentView', () => {
  beforeEach(() => {
    vi.mocked(api.environment).mockResolvedValue({
      sources: [{ path: '.env', absolute_path: null, exists: true, external: false, active: true, keys: ['DEMO_TOKEN'], error: '', git_status: 'ignored' }],
      shell_keys: [],
      precedence: ['shell', 'explicit_env_files', 'workspace_dotenv'],
    })
    vi.mocked(api.revealEnv).mockResolvedValue({ path: '.env', name: '.env', content: 'DEMO_TOKEN=secret\n', sha256: 'hash', owner: 'ENV', read_only: false })
  })

  it('requires a second explicit action before revealing env content', async () => {
    const wrapper = mount(EnvironmentView, {
      global: { stubs: { CodeEditor: { template: '<div class="editor-stub" />' } } },
    })
    await flushPromises()

    await wrapper.get('.env-source').trigger('click')
    expect(wrapper.text()).toContain('显示敏感 env 内容')
    expect(api.revealEnv).not.toHaveBeenCalled()

    await wrapper.get('.sensitive-gate .primary-btn').trigger('click')
    await flushPromises()
    expect(api.revealEnv).toHaveBeenCalledWith('.env')
  })
})
