import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { ReportDetail, ReportSummary } from '../types'
import ReportsView from './ReportsView.vue'

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return {
    ...actual,
    api: { ...actual.api, reports: vi.fn(), reportDetail: vi.fn() },
  }
})

const summary: ReportSummary = {
  run_id: 'run-20260827-1',
  status: 'passed',
  timestamp: '2026-08-27T12:00:00Z',
  duration_seconds: 1.27,
  summary: { passed: 1, failed: 0, error: 0 },
  scope: { type: 'suite' },
  target: 'demo',
  module: 'orders',
  suite: 'orders-smoke',
  result_path: 'test_workspace/reports/run-20260827-1/result.json',
  report_path: 'test_workspace/reports/run-20260827-1/report.md',
}

const detail: ReportDetail = {
  summary,
  result: { run_id: summary.run_id, summary: summary.summary },
  report_markdown: '# Orders smoke\n\n<script>alert(1)</script>\n\n- TC-001 passed',
}

describe('ReportsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    vi.mocked(api.reports).mockResolvedValue({ reports: [summary] })
    vi.mocked(api.reportDetail).mockResolvedValue(detail)
  })

  it('uses safe Markdown for report.md and a read-only JSON Monaco view', async () => {
    const wrapper = mount(ReportsView, {
      global: {
        plugins: [createPinia()],
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
          CodeEditor: {
            props: ['modelValue', 'language', 'readOnly', 'path'],
            template: '<div class="code-editor-stub" :data-language="language" :data-read-only="readOnly" :data-path="path">{{ modelValue }}</div>',
          },
          SafeMarkdown: {
            props: ['source'],
            template: '<div class="markdown-preview" :data-source="source"><h1>Orders smoke</h1></div>',
          },
        },
      },
    })
    await flushPromises()

    expect(wrapper.get('.markdown-preview h1').text()).toBe('Orders smoke')
    expect(wrapper.find('.markdown-preview script').exists()).toBe(false)

    ;(wrapper.vm as unknown as { tab: 'report' | 'json' }).tab = 'json'
    await flushPromises()

    const editor = wrapper.get('.code-editor-stub')
    expect(editor.attributes('data-language')).toBe('json')
    expect(editor.attributes()).toHaveProperty('data-read-only')
    expect(editor.attributes('data-path')).toContain('result.json')
    expect(editor.text()).toContain('run-20260827-1')
  })
})
