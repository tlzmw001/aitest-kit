import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import DirectoryPicker from './DirectoryPicker.vue'

describe('DirectoryPicker', () => {
  it('browses directories and emits only the explicitly selected current directory', async () => {
    const directories = vi.spyOn(api, 'directories')
      .mockResolvedValueOnce({
        path: '/Users/test', parent: '/Users', initialized: false,
        directories: [{ name: 'workspace', path: '/Users/test/workspace', initialized: true }],
      })
      .mockResolvedValueOnce({
        path: '/Users/test/workspace', parent: '/Users/test', initialized: true, directories: [],
      })
    const wrapper = mount(DirectoryPicker, { props: { initialPath: '/Users/test' } })
    await flushPromises()

    expect(wrapper.text()).toContain('workspace')
    expect(wrapper.text()).toContain('AITest workspace')
    expect(wrapper.emitted('select')).toBeUndefined()

    await wrapper.get('.directory-list button').trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="select-directory"]').trigger('click')

    expect(directories).toHaveBeenNthCalledWith(2, '/Users/test/workspace')
    expect(wrapper.emitted('select')).toEqual([['/Users/test/workspace']])
  })
})
