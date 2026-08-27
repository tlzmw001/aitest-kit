import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useWorkspaceStore } from '../stores/workspace'
import type { WorkspaceSnapshot } from '../types'
import AssetManager from './AssetManager.vue'

const passthroughStub = { template: '<div><slot /></div>' }
const rootDialogStub = { props: ['open'], template: '<div v-if="open"><slot /></div>' }
const dialogStubs = {
  DialogRoot: rootDialogStub,
  DialogPortal: passthroughStub,
  DialogOverlay: passthroughStub,
  DialogContent: passthroughStub,
  DialogDescription: passthroughStub,
  DialogTitle: passthroughStub,
  DialogClose: passthroughStub,
}

function snapshot(): WorkspaceSnapshot {
  return {
    name: 'workspace', path: '/workspace', branch: 'main',
    counts: { targets: 1, modules: 1, suites: 1, cases: 0, tasks: 0 },
    recent_reports: [], tasks: [],
    targets: [{
      name: 'demo', diagnostics: [], config_path: 'test_workspace/targets/demo/target.yaml',
      modules: [{
        name: 'orders', module_type: 'standard_http', diagnostics: [], assets: [],
        suites: [{
          name: 'smoke', manifest_path: 'test_workspace/suites/demo/smoke/suite.yaml',
          profile_path: 'test_workspace/suites/demo/smoke/profile_smoke_suite.md',
          diagnostics: [], cases: [], assets: [],
        }],
      }],
    }],
  }
}

describe('AssetManager', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('creates a suite as one managed unit and does not expose case CRUD', async () => {
    const store = useWorkspaceStore()
    store.snapshot = snapshot()
    vi.spyOn(api, 'assetOptions').mockResolvedValue({ module_types: [{ name: 'standard_http', description: 'HTTP' }] })
    const created = snapshot()
    created.targets[0].modules[0].suites.push({
      name: 'refund-smoke', manifest_path: 'test_workspace/suites/demo/refund-smoke/suite.yaml',
      profile_path: 'test_workspace/suites/demo/refund-smoke/profile_refund-smoke_suite.md', diagnostics: [], cases: [],
      assets: [{ name: 'cases.md', path: 'test_workspace/suites/demo/refund-smoke/cases.md', owner: 'CASE', exists: true }],
    })
    const createSuite = vi.spyOn(api, 'createSuite').mockResolvedValue(created)
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/editor', component: { template: '<div />' } }] })
    const wrapper = mount(AssetManager, { global: { plugins: [router], stubs: dialogStubs } })

    await (wrapper.vm as unknown as { openCreate: (kind: string, defaults: object) => Promise<void> })
      .openCreate('suite', { target: 'demo', module: 'orders' })
    await flushPromises()
    await wrapper.get('input[placeholder="例如 orders-smoke"]').setValue('refund-smoke')

    expect(wrapper.text()).toContain('suite.yaml、cases.md 和 suite profile')
    expect(wrapper.text()).not.toContain('新增 case')
    expect(wrapper.text()).not.toContain('删除 case')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(createSuite).toHaveBeenCalledWith({
      target: 'demo', module: 'orders', name: 'refund-smoke', register: true,
    })
    expect(router.currentRoute.value.query.path).toBe('test_workspace/suites/demo/refund-smoke/cases.md')
  })

  it('shows delete blockers and disables confirmation', async () => {
    const store = useWorkspaceStore()
    store.snapshot = snapshot()
    vi.spyOn(api, 'deletePreview').mockResolvedValue({
      kind: 'suite', identity: { kind: 'suite', target: 'demo', module: 'orders', suite: 'smoke' },
      paths: ['test_workspace/suites/demo/smoke'], modified_files: [],
      blockers: ['suite 被 task nightly 引用'], can_delete: false, recoverable: true, message: '可恢复删除',
    })
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { template: '<div />' } }] })
    const wrapper = mount(AssetManager, { global: { plugins: [router], stubs: dialogStubs } })

    await (wrapper.vm as unknown as { openDelete: (identity: object) => Promise<void> })
      .openDelete({ kind: 'suite', target: 'demo', module: 'orders', suite: 'smoke' })
    await flushPromises()

    expect(wrapper.text()).toContain('suite 被 task nightly 引用')
    expect(wrapper.get('[data-test="confirm-delete"]').attributes('disabled')).toBeDefined()
  })
})
