import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { monaco } from '../editor/monacoEnvironment'
import type { EditorDiagnostic } from '../types'
import CodeEditor from './CodeEditor.vue'

describe('CodeEditor Monaco runtime', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    for (const model of monaco.editor.getModels()) model.dispose()
  })

  it('switches theme without recreating the editor or model', async () => {
    const create = vi.spyOn(monaco.editor, 'create')
    const setTheme = vi.spyOn(monaco.editor, 'setTheme')
    const wrapper = mount(CodeEditor, {
      props: {
        modelValue: 'target: coupon_system',
        path: 'test_workspace/targets/coupon_system/target.yaml',
        language: 'yaml',
        theme: 'aitest-dark',
      },
    })
    try {
      expect(wrapper.get('.code-editor').classes()).toContain('monaco-host')
      expect(wrapper.find('.cm-editor').exists()).toBe(false)
      const editor = create.mock.results[0]?.value
      const model = editor?.getModel()

      await wrapper.setProps({ theme: 'high-contrast-dark' })
      await flushPromises()

      expect(create).toHaveBeenCalledTimes(1)
      expect(editor?.getModel()).toBe(model)
      expect(model?.getValue()).toBe('target: coupon_system')
      expect(setTheme).toHaveBeenLastCalledWith('high-contrast-dark')
    } finally {
      wrapper.unmount()
    }
  })

  it('reuses the editor and restores each path model and view state', async () => {
    const create = vi.spyOn(monaco.editor, 'create')
    const wrapper = mount(CodeEditor, {
      props: {
        modelValue: 'target: coupon_system',
        path: 'test_workspace/targets/coupon_system/target.yaml',
        language: 'yaml',
      },
    })
    try {
      const editor = create.mock.results[0]?.value
      const targetModel = editor?.getModel()
      editor?.setPosition({ lineNumber: 1, column: 4 })
      expect(editor?.getPosition()).toMatchObject({ lineNumber: 1, column: 4 })
      const saveViewState = editor ? vi.spyOn(editor, 'saveViewState') : null
      const restoreViewState = editor ? vi.spyOn(editor, 'restoreViewState') : null

      await wrapper.setProps({
        path: 'test_workspace/suites/coupon/smoke/cases.md',
        language: 'markdown',
        modelValue: '# Smoke cases',
      })
      const markdownModel = editor?.getModel()
      editor?.setPosition({ lineNumber: 1, column: 8 })

      await wrapper.setProps({
        path: 'test_workspace/targets/coupon_system/target.yaml',
        language: 'yaml',
        modelValue: 'target: coupon_system',
      })
      await flushPromises()

      expect(create).toHaveBeenCalledTimes(1)
      expect(markdownModel).not.toBe(targetModel)
      expect(editor?.getModel()).toBe(targetModel)
      expect(saveViewState).toHaveBeenCalled()
      expect(restoreViewState).toHaveBeenCalled()
      expect(saveViewState?.mock.results[0]?.value).toMatchObject({
        cursorState: [{ position: { lineNumber: 1, column: 4 } }],
      })
      expect(restoreViewState?.mock.calls.at(-1)?.[0]).toMatchObject({
        cursorState: [{ position: { lineNumber: 1, column: 4 } }],
      })
      expect(editor?.getPosition()).toMatchObject({ lineNumber: 1, column: 4 })

      targetModel?.setValue('target: changed')
      expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['target: changed'])
    } finally {
      wrapper.unmount()
    }
  })

  it('syncs external content without echo and updates read-only and diagnostic state in place', async () => {
    const create = vi.spyOn(monaco.editor, 'create')
    const wrapper = mount(CodeEditor, {
      props: {
        modelValue: 'target: coupon_system',
        path: 'test_workspace/targets/coupon_system/target.yaml',
        language: 'yaml',
      },
    })
    try {
      const editor = create.mock.results[0]?.value
      const diagnostic: EditorDiagnostic = {
        severity: 'error',
        code: 'TARGET_INVALID',
        message: 'invalid target',
        line: 1,
        column: 2,
        end_line: 1,
        end_column: 8,
        source: 'aitest-target',
      }

      await wrapper.setProps({ modelValue: 'target: externally_changed' })
      expect(wrapper.emitted('update:modelValue')).toBeUndefined()
      expect(editor?.getModel()?.getValue()).toBe('target: externally_changed')

      await wrapper.setProps({ readOnly: true, diagnostics: [diagnostic] })
      expect(editor?.getOption(monaco.editor.EditorOption.readOnly)).toBe(true)
      expect(monaco.editor.getModelMarkers({ resource: editor?.getModel()?.uri })).toHaveLength(1)

      ;(wrapper.vm as unknown as { focusDiagnostic(value: EditorDiagnostic): void }).focusDiagnostic(diagnostic)
      expect(editor?.getPosition()).toMatchObject({ lineNumber: 1, column: 2 })
      expect(create).toHaveBeenCalledTimes(1)
    } finally {
      wrapper.unmount()
    }
  })
})
