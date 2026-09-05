import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { defineComponent, h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EditorView from './EditorView.vue'
import { ApiError, api } from '../api/client'
import { usePreferencesStore } from '../stores/preferences'
import { useWorkspaceStore } from '../stores/workspace'
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
      workspace: vi.fn(),
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
    vi.unstubAllGlobals()
    vi.clearAllMocks()
    disposeDocument.mockClear()
    reloadDocument.mockClear()
    localStorage.clear()
    vi.mocked(api.readFile).mockImplementation(async (path) => documentFor(path))
    vi.mocked(api.validateEditor).mockResolvedValue({ diagnostics: [] })
    vi.mocked(api.workspace).mockResolvedValue({
      name: 'workspace',
      path: '/workspace',
      branch: 'main',
      counts: { targets: 0, modules: 0, suites: 0, cases: 0, tasks: 0 },
      targets: [],
      tasks: [],
      recent_reports: [],
    })
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

  it('lets the user explicitly discard a dirty tab before closing it', async () => {
    const confirm = vi.fn().mockReturnValue(true)
    vi.stubGlobal('confirm', confirm)
    const { wrapper } = await mountEditor('cases/dirty.md')
    wrapper.getComponent(CodeEditorStub).vm.$emit('update:modelValue', '# unsaved')
    await nextTick()

    await wrapper.get('.tab-close').trigger('click')
    await flushPromises()

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('放弃修改并关闭'))
    expect(wrapper.findAll('[data-test="editor-tab"]')).toHaveLength(0)
  })

  it('keeps an explicitly closed last tab empty instead of reopening the first case', async () => {
    const path = 'cases/only.md'
    const { wrapper } = await mountEditor(path)
    useWorkspaceStore().setSnapshot({
      name: 'workspace', path: '/workspace', branch: 'main',
      counts: { targets: 1, modules: 1, suites: 1, cases: 1, tasks: 0 },
      targets: [{ name: 'demo', diagnostics: [], config_path: null, modules: [{
        name: 'orders', module_type: 'multi_endpoint', diagnostics: [], assets: [], suites: [{
          name: 'smoke', manifest_path: 'suite.yaml', profile_path: 'profile.md', diagnostics: [],
          assets: [{ path, name: 'only.md', owner: 'CASE', exists: true }],
          cases: [{ id: 'TC-001', title: 'only', priority: 'P0', source_path: path, source_line: 1 }],
        }],
      }] }],
      tasks: [], recent_reports: [],
    })

    await wrapper.get('.tab-close').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('[data-test="editor-tab"]')).toHaveLength(0)
    expect(api.readFile).toHaveBeenCalledTimes(1)
  })

  it('returns a cancelled tab validation state to idle', async () => {
    vi.useFakeTimers()
    try {
      const { wrapper, router } = await mountEditor('cases/first.md')
      await router.push({ path: '/editor', query: { path: 'cases/second.md' } })
      await flushPromises()

      const tabs = (wrapper.vm as unknown as { tabs: Array<{ document: FileDocument; validationState: string }> }).tabs
      expect(tabs.find((tab) => tab.document.path === 'cases/first.md')?.validationState).toBe('idle')
    } finally {
      vi.useRealTimers()
    }
  })

  it('renders repeated breadcrumb segments without duplicate-key warnings', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const { wrapper } = await mountEditor('cases/repeated/cases/file.md')
    await nextTick()

    expect(wrapper.findAll('.breadcrumb span').map((item) => item.text())).toEqual(['cases', 'repeated', 'cases', 'file.md'])
    expect(warning.mock.calls.flat().join(' ')).not.toContain('Duplicate keys')
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

  it('can keep the local edit and retry a conflicted save with the latest disk hash', async () => {
    const path = 'cases/conflict.md'
    const original = documentFor(path)
    const disk = { ...original, content: '# disk v2', sha256: 'sha-disk-v2' }
    const saved = { ...disk, content: '# local edit', sha256: 'sha-saved' }
    vi.mocked(api.readFile)
      .mockResolvedValueOnce(original)
      .mockResolvedValueOnce(disk)
    vi.mocked(api.saveFile)
      .mockRejectedValueOnce(new ApiError('FILE_CONFLICT', '文件已变化', 409))
      .mockResolvedValueOnce(saved)
    const { wrapper } = await mountEditor(path)

    wrapper.getComponent(CodeEditorStub).vm.$emit('update:modelValue', '# local edit')
    await nextTick()
    await wrapper.get('.tab-action').trigger('click')
    await flushPromises()

    const keepLocal = wrapper.findAll('button').find((button) => button.text().includes('保留我的修改'))
    expect(keepLocal).toBeDefined()
    await keepLocal?.trigger('click')
    await flushPromises()

    expect(api.saveFile).toHaveBeenNthCalledWith(2, disk, '# local edit')
    expect(wrapper.get('.editor-stub').text()).toBe('# local edit')
    expect(wrapper.find('[data-test="diff-stub"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('已保存并更新文件 hash')
  })

  it('passes the selected theme to the code editor', async () => {
    localStorage.setItem('aitest-console-preferences', JSON.stringify({
      editorOpenMode: 'tabs',
      editorTheme: 'high-contrast-dark',
    }))

    const { wrapper } = await mountEditor('cases/first.md')

    expect(wrapper.get('.editor-stub').attributes('data-theme')).toBe('high-contrast-dark')
  })

  it('preserves edits typed during save and saves them against the new hash', async () => {
    const path = 'cases/saving.md'
    let finish!: (value: FileDocument) => void
    vi.mocked(api.saveFile).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    const { wrapper } = await mountEditor(path)
    const editor = wrapper.getComponent(CodeEditorStub)
    editor.vm.$emit('update:modelValue', '# sent')
    await nextTick()
    await wrapper.get('.tab-action').trigger('click')
    editor.vm.$emit('update:modelValue', '# newer')
    await nextTick()
    const saved = { ...documentFor(path), content: '# sent', sha256: 'new-hash' }
    finish(saved)
    await flushPromises()
    expect(wrapper.get('.editor-stub').text()).toBe('# newer')
    vi.mocked(api.saveFile).mockResolvedValue({ ...saved, content: '# newer' })
    await wrapper.get('.tab-action').trigger('click')
    await flushPromises()
    expect(api.saveFile).toHaveBeenLastCalledWith(saved, '# newer')
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
