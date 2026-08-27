import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { monaco } from '../editor/monacoEnvironment'
import DiffEditor from './DiffEditor.vue'

describe('DiffEditor', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    for (const model of monaco.editor.getModels()) model.dispose()
  })

  it('reuses one read-only diff editor and updates both models', async () => {
    const createDiffEditor = vi.spyOn(monaco.editor, 'createDiffEditor')
    const wrapper = mount(DiffEditor, {
      props: {
        original: 'target: disk',
        modified: 'target: local',
        path: 'test_workspace/targets/demo/target.yaml',
        language: 'yaml',
        theme: 'aitest-dark',
      },
    })

    try {
      const instance = createDiffEditor.mock.results[0]?.value
      expect(instance?.getOriginalEditor().getOption(monaco.editor.EditorOption.readOnly)).toBe(true)
      expect(instance?.getModifiedEditor().getOption(monaco.editor.EditorOption.readOnly)).toBe(true)
      expect(instance?.getModel()?.original.getValue()).toBe('target: disk')
      expect(instance?.getModel()?.modified.getValue()).toBe('target: local')

      await wrapper.setProps({ original: 'target: disk-v2', modified: 'target: local-v2' })
      await flushPromises()

      expect(createDiffEditor).toHaveBeenCalledTimes(1)
      expect(instance?.getModel()?.original.getValue()).toBe('target: disk-v2')
      expect(instance?.getModel()?.modified.getValue()).toBe('target: local-v2')
    } finally {
      wrapper.unmount()
    }
  })

  it('disposes the editor and both models on unmount', () => {
    const createDiffEditor = vi.spyOn(monaco.editor, 'createDiffEditor')
    const wrapper = mount(DiffEditor, {
      props: { original: 'disk', modified: 'local', path: 'cases.md', language: 'markdown' },
    })
    const instance = createDiffEditor.mock.results[0]?.value
    const original = instance?.getModel()?.original
    const modified = instance?.getModel()?.modified
    const disposeEditor = instance ? vi.spyOn(instance, 'dispose') : null
    const disposeOriginal = original ? vi.spyOn(original, 'dispose') : null
    const disposeModified = modified ? vi.spyOn(modified, 'dispose') : null

    wrapper.unmount()

    expect(disposeEditor).toHaveBeenCalledOnce()
    expect(disposeOriginal).toHaveBeenCalledOnce()
    expect(disposeModified).toHaveBeenCalledOnce()
  })
})
