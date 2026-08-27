import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
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
    vi.unstubAllGlobals()
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

  it('blocks route navigation while env changes are unsaved', async () => {
    const CodeEditorStub = defineComponent({
      props: ['modelValue'],
      emits: ['update:modelValue'],
      template: '<div class="editor-stub" />',
    })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/environment', component: EnvironmentView },
        { path: '/other', component: { template: '<div class="other-view" />' } },
      ],
    })
    await router.push('/environment')
    await router.isReady()
    const wrapper = mount({ template: '<RouterView />' }, {
      global: { plugins: [router], stubs: { CodeEditor: CodeEditorStub } },
    })
    await flushPromises()
    await wrapper.get('.env-source').trigger('click')
    await wrapper.get('.sensitive-gate .primary-btn').trigger('click')
    await flushPromises()
    wrapper.getComponent(CodeEditorStub).vm.$emit('update:modelValue', 'DEMO_TOKEN=changed\n')
    await flushPromises()

    const confirm = vi.fn().mockReturnValue(false)
    vi.stubGlobal('confirm', confirm)
    await router.push('/other')
    await flushPromises()

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('未保存'))
    expect(router.currentRoute.value.path).toBe('/environment')
    expect(wrapper.findComponent(EnvironmentView).exists()).toBe(true)
  })

  it('keeps dirty env content when switching sources is cancelled', async () => {
    vi.mocked(api.environment).mockResolvedValue({
      sources: [
        { path: '.env', absolute_path: null, exists: true, external: false, active: true, keys: ['DEMO_TOKEN'], error: '', git_status: 'ignored' },
        { path: '.env.local', absolute_path: null, exists: true, external: false, active: false, keys: [], error: '', git_status: 'ignored' },
      ],
      shell_keys: [],
      precedence: ['shell', 'explicit_env_files', 'workspace_dotenv'],
    })
    const CodeEditorStub = defineComponent({
      props: ['modelValue'],
      emits: ['update:modelValue'],
      template: '<div class="editor-stub">{{ modelValue }}</div>',
    })
    const wrapper = mount(EnvironmentView, {
      global: { stubs: { CodeEditor: CodeEditorStub } },
    })
    await flushPromises()
    await wrapper.findAll('.env-source')[0].trigger('click')
    await wrapper.get('.sensitive-gate .primary-btn').trigger('click')
    await flushPromises()
    wrapper.getComponent(CodeEditorStub).vm.$emit('update:modelValue', 'DEMO_TOKEN=changed\n')
    await flushPromises()
    const confirm = vi.fn().mockReturnValue(false)
    vi.stubGlobal('confirm', confirm)

    await wrapper.findAll('.env-source')[1].trigger('click')
    await flushPromises()

    expect(confirm).toHaveBeenCalledOnce()
    expect(wrapper.get('.editor-stub').text()).toContain('DEMO_TOKEN=changed')
    expect(wrapper.findAll('.env-source')[0].classes()).toContain('active')
  })
})
