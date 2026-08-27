import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EditorView from './EditorView.vue'
import { api } from '../api/client'
import { usePreferencesStore } from '../stores/preferences'
import type { FileDocument } from '../types'

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return {
    ...actual,
    api: {
      ...actual.api,
      readFile: vi.fn(),
      saveFile: vi.fn(),
      validateEditor: vi.fn(),
    },
  }
})

function documentFor(path: string): FileDocument {
  return {
    path,
    name: path.split('/').at(-1) || path,
    content: `# ${path}`,
    sha256: `sha-${path}`,
    owner: 'CASE',
    read_only: false,
  }
}

async function mountEditor(path: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/editor', name: 'editor', component: EditorView }],
  })
  await router.push({ path: '/editor', query: { path } })
  await router.isReady()
  const wrapper = mount(EditorView, {
    global: {
      plugins: [pinia, router],
      stubs: {
        CodeEditor: {
          props: ['modelValue', 'theme'],
          template: '<div class="editor-stub" :data-theme="theme">{{ modelValue }}</div>',
        },
        RouterLink: { template: '<a><slot /></a>' },
      },
    },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('EditorView tabs', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    vi.mocked(api.readFile).mockImplementation(async (path) => documentFor(path))
    vi.mocked(api.validateEditor).mockResolvedValue({ diagnostics: [] })
  })

  it('keeps multiple opened files as tabs by default', async () => {
    const { wrapper, router } = await mountEditor('cases/first.md')

    await router.push({ path: '/editor', query: { path: 'cases/second.md' } })
    await flushPromises()

    const tabs = wrapper.findAll('[data-test="editor-tab"]')
    expect(tabs).toHaveLength(2)
    expect(tabs[0].text()).toContain('first.md')
    expect(tabs[1].text()).toContain('second.md')
    expect(tabs[1].classes()).toContain('active')
  })

  it('replaces the active clean tab when reuse mode is enabled', async () => {
    const { wrapper, router } = await mountEditor('cases/first.md')
    usePreferencesStore().editorOpenMode = 'reuse'

    await router.push({ path: '/editor', query: { path: 'cases/second.md' } })
    await flushPromises()

    const tabs = wrapper.findAll('[data-test="editor-tab"]')
    expect(tabs).toHaveLength(1)
    expect(tabs[0].text()).toContain('second.md')
  })

  it('passes the selected theme to the code editor', async () => {
    localStorage.setItem('aitest-console-preferences', JSON.stringify({
      editorOpenMode: 'tabs',
      editorTheme: 'high-contrast-dark',
    }))

    const { wrapper } = await mountEditor('cases/first.md')

    expect(wrapper.get('.editor-stub').attributes('data-theme')).toBe('high-contrast-dark')
  })

  it('shows backend diagnostics in the real Problems panel', async () => {
    vi.useFakeTimers()
    vi.mocked(api.validateEditor).mockResolvedValue({
      diagnostics: [{
        severity: 'error',
        code: 'YAML_SYNTAX',
        message: 'expected the node content',
        line: 4,
        column: 1,
        end_line: 4,
        end_column: 2,
        source: 'yaml',
      }],
    })

    try {
      const { wrapper } = await mountEditor('cases/suite.yaml')
      await vi.runOnlyPendingTimersAsync()
      await flushPromises()

      expect(api.validateEditor).toHaveBeenCalled()
      expect(wrapper.text()).toContain('YAML_SYNTAX')
      expect(wrapper.text()).toContain('4:1')
      expect(wrapper.text()).not.toContain('ValidationOutput')
    } finally {
      vi.useRealTimers()
    }
  })
})
