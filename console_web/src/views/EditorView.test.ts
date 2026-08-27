import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { defineComponent, h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EditorView from './EditorView.vue'
import { ApiError, api } from '../api/client'
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

const disposeDocument = vi.fn()
const reloadDocument = vi.fn()
const CodeEditorStub = defineComponent({
  name: 'CodeEditor',
  props: ['modelValue', 'theme'],
  emits: ['update:modelValue', 'save'],
  setup(props, { expose }) {
    expose({ disposeDocument, focusDiagnostic: vi.fn(), reloadDocument })
    return () => h('div', {
      class: 'editor-stub',
      'data-theme': props.theme,
    }, String(props.modelValue ?? ''))
  },
})

const passthroughStub = { template: '<div><slot /></div>' }
const rootDialogStub = {
  props: ['open'],
  template: '<div v-if="open"><slot /></div>',
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
        CodeEditor: CodeEditorStub,
        DiffEditor: {
          props: ['original', 'modified', 'path'],
          template: '<div data-test="diff-stub" :data-path="path"><span class="original">{{ original }}</span><span class="modified">{{ modified }}</span></div>',
        },
        DialogRoot: rootDialogStub,
        DialogPortal: passthroughStub,
        DialogOverlay: passthroughStub,
        DialogContent: passthroughStub,
        DialogDescription: passthroughStub,
        DialogTitle: passthroughStub,
        SplitterGroup: passthroughStub,
        SplitterPanel: passthroughStub,
        SplitterResizeHandle: { template: '<div />' },
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
    disposeDocument.mockClear()
    reloadDocument.mockClear()
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

  it('keeps the editor instance mounted while a second file is loading', async () => {
    const { wrapper, router } = await mountEditor('cases/first.md')
    const editorElement = wrapper.get('.editor-stub').element
    let finishLoading: ((document: FileDocument) => void) | undefined
    vi.mocked(api.readFile).mockImplementation((path) => (
      path === 'cases/second.md'
        ? new Promise((resolve) => { finishLoading = resolve })
        : Promise.resolve(documentFor(path))
    ))

    await router.push({ path: '/editor', query: { path: 'cases/second.md' } })
    await nextTick()

    expect(wrapper.get('.editor-stub').element).toBe(editorElement)
    expect(wrapper.get('.editor-loading').text()).toContain('读取文件')

    finishLoading?.(documentFor('cases/second.md'))
    await flushPromises()
    expect(wrapper.find('.editor-loading').exists()).toBe(false)
  })

  it('replaces the active clean tab when reuse mode is enabled', async () => {
    const { wrapper, router } = await mountEditor('cases/first.md')
    usePreferencesStore().editorOpenMode = 'reuse'

    await router.push({ path: '/editor', query: { path: 'cases/second.md' } })
    await flushPromises()

    const tabs = wrapper.findAll('[data-test="editor-tab"]')
    expect(tabs).toHaveLength(1)
    expect(tabs[0].text()).toContain('second.md')
    expect(disposeDocument).toHaveBeenCalledWith('cases/first.md')
  })

  it('releases the Monaco document when a clean tab closes', async () => {
    const { wrapper, router } = await mountEditor('cases/first.md')
    await router.push({ path: '/editor', query: { path: 'cases/second.md' } })
    await flushPromises()

    await wrapper.findAll('.tab-close')[0].trigger('click')

    expect(disposeDocument).toHaveBeenCalledWith('cases/first.md')
    expect(wrapper.findAll('[data-test="editor-tab"]')).toHaveLength(1)
  })

  it('opens a disk-versus-local Diff on save conflict and can load the disk version', async () => {
    const path = 'cases/conflict.md'
    const disk = { ...documentFor(path), content: '# disk v2', sha256: 'sha-disk-v2' }
    vi.mocked(api.readFile)
      .mockResolvedValueOnce(documentFor(path))
      .mockResolvedValueOnce(disk)
    vi.mocked(api.saveFile).mockRejectedValue(new ApiError('FILE_CONFLICT', '文件已变化', 409))
    const { wrapper } = await mountEditor(path)

    wrapper.getComponent(CodeEditorStub).vm.$emit('update:modelValue', '# local edit')
    await nextTick()
    await wrapper.get('.tab-action').trigger('click')
    await flushPromises()

    const diff = wrapper.get('[data-test="diff-stub"]')
    expect(diff.get('.original').text()).toBe('# disk v2')
    expect(diff.get('.modified').text()).toBe('# local edit')
    expect(wrapper.text()).toContain('AITest 不会自动覆盖任何一侧')

    const loadDisk = wrapper.findAll('button').find((button) => button.text().includes('载入磁盘版本'))
    expect(loadDisk).toBeDefined()
    await loadDisk?.trigger('click')
    await flushPromises()

    expect(wrapper.get('.editor-stub').text()).toBe('# disk v2')
    expect(reloadDocument).toHaveBeenCalledOnce()
    expect(wrapper.find('[data-test="diff-stub"]').exists()).toBe(false)
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
