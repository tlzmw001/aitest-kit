import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useWorkspaceStore } from '../stores/workspace'
import type { Job, WorkspaceSnapshot } from '../types'
import RunView from './RunView.vue'

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return {
    ...actual,
    api: {
      ...actual.api,
      environment: vi.fn(),
      jobs: vi.fn(),
      job: vi.fn(),
    },
  }
})

const runningJob: Job = {
  id: 'job-1',
  operation: 'run',
  command_summary: 'aitest run --suite-file suite.yaml',
  status: 'running',
  output: '',
  exit_code: null,
  started_at: '2026-08-27T12:00:00Z',
  finished_at: '',
  cancel_requested: false,
}

const snapshot: WorkspaceSnapshot = {
  name: 'workspace',
  path: '/workspace',
  branch: 'main',
  counts: { targets: 1, modules: 1, suites: 1, cases: 1, tasks: 0 },
  targets: [{
    name: 'demo',
    diagnostics: [],
    config_path: 'test_workspace/targets/demo/target.yaml',
    modules: [{
      name: 'orders',
      module_type: 'multi_endpoint',
      diagnostics: [],
      assets: [],
      suites: [{
        name: 'orders-smoke',
        manifest_path: 'test_workspace/suites/demo/orders-smoke/suite.yaml',
        profile_path: 'test_workspace/suites/demo/orders-smoke/profile_orders-smoke_suite.md',
        diagnostics: [],
        assets: [],
        cases: [{ id: 'TC-001', title: 'create order', priority: 'P0', source_path: 'cases.md', source_line: 3 }],
      }],
    }],
  }],
  tasks: [],
  recent_reports: [],
}

async function mountRunningJob() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useWorkspaceStore()
  store.setSnapshot(snapshot)
  const refresh = vi.spyOn(store, 'refresh').mockResolvedValue()
  vi.mocked(api.environment).mockResolvedValue({ sources: [], shell_keys: [], precedence: [] })
  vi.mocked(api.jobs).mockResolvedValue({ jobs: [runningJob] })
  const wrapper = mount(RunView, { global: { plugins: [pinia] } })
  await flushPromises()
  return { wrapper, refresh }
}

describe('RunView polling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('continues polling after a transient request failure', async () => {
    vi.mocked(api.job)
      .mockRejectedValueOnce(new Error('backend busy'))
      .mockResolvedValueOnce(runningJob)
    const { wrapper } = await mountRunningJob()

    await vi.advanceTimersByTimeAsync(650)
    await flushPromises()
    expect(wrapper.text()).toContain('backend busy')

    await vi.advanceTimersByTimeAsync(650)
    await flushPromises()
    expect(api.job).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it.each(['succeeded', 'failed', 'cancelled'] as const)(
    'refreshes the workspace when a job reaches %s',
    async (status) => {
      vi.mocked(api.job).mockResolvedValue({ ...runningJob, status })
      const { wrapper, refresh } = await mountRunningJob()

      await vi.advanceTimersByTimeAsync(650)
      await flushPromises()

      expect(refresh).toHaveBeenCalledOnce()
      wrapper.unmount()
    },
  )

  it('stops only after five consecutive polling failures', async () => {
    vi.mocked(api.job).mockRejectedValue(new Error('backend busy'))
    const { wrapper } = await mountRunningJob()

    for (let index = 0; index < 6; index += 1) {
      await vi.advanceTimersByTimeAsync(650)
      await flushPromises()
    }

    expect(api.job).toHaveBeenCalledTimes(5)
    expect(wrapper.text()).toContain('连续 5 次失败，已停止自动更新')
    wrapper.unmount()
  })
})
