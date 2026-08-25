import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import ExplorerTree from './ExplorerTree.vue'
import { useWorkspaceStore } from '../stores/workspace'

describe('ExplorerTree', () => {
  it('highlights only the asset selected by its full path', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useWorkspaceStore()
    store.snapshot = {
      name: 'workspace',
      path: '/workspace',
      branch: 'main',
      counts: { targets: 1, modules: 1, suites: 1, cases: 0, tasks: 0 },
      tasks: [],
      recent_reports: [],
      targets: [{
        name: 'target',
        diagnostics: [],
        config_path: null,
        modules: [{
          name: 'module',
          module_type: 'standard_http',
          diagnostics: [],
          assets: [],
          suites: [{
            name: 'suite',
            manifest_path: 'test_workspace/suites/target/suite/suite.yaml',
            profile_path: 'test_workspace/suites/target/suite/profile_suite.md',
            diagnostics: [],
            cases: [],
            assets: [
              { name: 'business.md', path: 'test_workspace/suites/target/suite/business.md', owner: 'CASE', exists: true },
              { name: 'boundary.md', path: 'test_workspace/suites/target/suite/boundary.md', owner: 'CASE', exists: true },
            ],
          }],
        }],
      }],
    }
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/editor', component: { template: '<div />' } }],
    })
    await router.push({ path: '/editor', query: { path: 'test_workspace/suites/target/suite/business.md' } })
    await router.isReady()

    const wrapper = mount(ExplorerTree, { global: { plugins: [pinia, router] } })
    const links = wrapper.findAll('.tree-link')

    expect(links).toHaveLength(2)
    expect(links[0].classes()).toContain('active')
    expect(links[1].classes()).not.toContain('active')
  })
})
