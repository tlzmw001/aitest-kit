import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkbenchView from './WorkbenchView.vue'
import { useWorkspaceStore } from '../stores/workspace'

describe('WorkbenchView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('shows the workspace picker when no workspace is open', () => {
    const wrapper = mount(WorkbenchView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })

    expect(wrapper.find('#workspace-path').exists()).toBe(true)
    expect(wrapper.text()).toContain('打开只读取 workspace 结构')
  })

  it('shows honest empty states when the workspace has no assets or reports', () => {
    const store = useWorkspaceStore()
    store.snapshot = {
      name: 'empty-workspace',
      path: '/tmp/empty-workspace',
      branch: 'main',
      counts: { targets: 0, modules: 0, suites: 0, cases: 0, tasks: 0 },
      targets: [],
      tasks: [],
      recent_reports: [],
    }
    const wrapper = mount(WorkbenchView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })

    expect(wrapper.text()).toContain('没有可展示的 module')
    expect(wrapper.text()).toContain('尚无执行记录')
  })

  it('requires an explicit action before initializing a selected directory', async () => {
    const store = useWorkspaceStore()
    store.snapshot = {
      name: 'current-workspace',
      path: '/tmp/current-workspace',
      branch: 'main',
      counts: { targets: 0, modules: 0, suites: 0, cases: 0, tasks: 0 },
      targets: [],
      tasks: [],
      recent_reports: [],
    }
    store.pendingInitializationPath = '/tmp/new-workspace'
    store.error = 'WORKSPACE_NOT_INITIALIZED: 该目录尚未初始化'
    const initialize = vi.spyOn(store, 'initialize').mockResolvedValue(true)
    const wrapper = mount(WorkbenchView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await wrapper.get('.view-heading .primary-btn').trigger('click')

    expect(wrapper.text()).toContain('尚未初始化')
    expect(wrapper.text()).toContain('/tmp/new-workspace')
    expect(initialize).not.toHaveBeenCalled()

    await wrapper.get('[data-test="initialize-workspace"]').trigger('click')

    expect(initialize).toHaveBeenCalledWith('/tmp/new-workspace')
  })
})
