import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useWorkspaceStore } from '../stores/workspace'
import type { ReportDetail, ReportSummary, WorkspaceSnapshot } from '../types'
import DiagnosticsView from './DiagnosticsView.vue'

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return { ...actual, api: { ...actual.api, reports: vi.fn(), reportDetail: vi.fn() } }
})

const report: ReportSummary = {
  run_id: 'run-1', status: 'failed', timestamp: '2026-08-27T12:00:00Z', duration_seconds: 1,
  summary: { passed: 0, failed: 1, error: 0 }, scope: {}, target: 'demo', module: 'orders', suite: 'smoke',
  result_path: 'test_workspace/reports/run-1/result.json', report_path: 'test_workspace/reports/run-1/report.md',
}

const sourcePath = 'test_workspace/suites/demo/orders-smoke/business.md'
const snapshot: WorkspaceSnapshot = {
  name: 'workspace', path: '/workspace', branch: 'main',
  counts: { targets: 2, modules: 2, suites: 2, cases: 2, tasks: 0 },
  targets: [{ name: 'other', diagnostics: [], config_path: null, modules: [{
    name: 'orders', module_type: 'multi_endpoint', diagnostics: [], assets: [], suites: [{
      name: 'smoke', manifest_path: 'other-suite.yaml', profile_path: 'other-profile.md', diagnostics: [], assets: [],
      cases: [{ id: 'TC-ORD-001', title: '同名 case', priority: 'P0', source_path: 'other/wrong.md', source_line: 4 }],
    }],
  }] }, { name: 'demo', diagnostics: [], config_path: null, modules: [{
    name: 'orders', module_type: 'multi_endpoint', diagnostics: [], assets: [], suites: [{
      name: 'smoke', manifest_path: 'suite.yaml', profile_path: 'profile.md', diagnostics: [], assets: [],
      cases: [{ id: 'TC-ORD-001', title: '创建订单', priority: 'P0', source_path: sourcePath, source_line: 4 }],
    }],
  }] }],
  tasks: [], recent_reports: [report],
}

describe('DiagnosticsView source navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.reports).mockResolvedValue({ reports: [report] })
    vi.mocked(api.reportDetail).mockResolvedValue({
      summary: report,
      result: { cases: [{ case_id: 'TC-ORD-001', outcome: 'failed', failure_type: 'ASSERTION_FAILURE' }] },
      report_markdown: '',
    } satisfies ReportDetail)
  })

  it('links a failed case to its Markdown source path', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useWorkspaceStore().setSnapshot(snapshot)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/diagnostics', component: DiagnosticsView },
        { path: '/editor', component: { template: '<div />' } },
        { path: '/reports', component: { template: '<div />' } },
      ],
    })
    await router.push('/diagnostics')
    await router.isReady()
    const wrapper = mount(DiagnosticsView, { global: { plugins: [pinia, router] } })
    await flushPromises()

    const href = wrapper.get('.detail-head a').attributes('href')
    expect(href).toBeDefined()
    expect(new URL(href!, 'http://console.local').searchParams.get('path')).toBe(sourcePath)
  })
})
