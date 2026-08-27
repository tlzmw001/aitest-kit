import { flushPromises, mount } from '@vue/test-utils'
import { EditorView } from '@codemirror/view'
import { describe, expect, it, vi } from 'vitest'
import CodeEditor from './CodeEditor.vue'

describe('CodeEditor theme switching', () => {
  it('reconfigures the theme without destroying the editor or changing its content', async () => {
    const destroy = vi.spyOn(EditorView.prototype, 'destroy')
    const wrapper = mount(CodeEditor, {
      props: {
        modelValue: 'target: coupon_system',
        path: 'test_workspace/targets/coupon_system/target.yaml',
        language: 'yaml',
        theme: 'aitest-dark',
      },
    })
    try {
      await vi.waitFor(() => {
        expect(wrapper.find('.cm-content').exists()).toBe(true)
      })

      await wrapper.setProps({ theme: 'high-contrast-dark' })
      await flushPromises()

      expect(destroy).not.toHaveBeenCalled()
      expect(wrapper.get('.cm-content').text()).toContain('target: coupon_system')
    } finally {
      wrapper.unmount()
      destroy.mockRestore()
    }
  })
})
