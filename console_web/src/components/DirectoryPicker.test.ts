import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import DirectoryPicker from './DirectoryPicker.vue'

describe('DirectoryPicker', () => {
  afterEach(() => vi.restoreAllMocks())

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

  it('falls back to the home directory when the initial path is invalid', async () => {
    const directories = vi.spyOn(api, 'directories')
      .mockRejectedValueOnce(new Error('目录不存在'))
      .mockResolvedValueOnce({
        path: '/Users/test', parent: '/Users', initialized: false,
        directories: [{ name: 'workspace', path: '/Users/test/workspace', initialized: false }],
      })

    const wrapper = mount(DirectoryPicker, { props: { initialPath: '/Users/test/missing' } })
    await flushPromises()

    expect(directories).toHaveBeenNthCalledWith(1, '/Users/test/missing')
    expect(directories).toHaveBeenNthCalledWith(2, '~')
    expect(wrapper.text()).toContain('/Users/test')
    expect(wrapper.get('[data-test="select-directory"]').attributes('disabled')).toBeUndefined()
  })
})
