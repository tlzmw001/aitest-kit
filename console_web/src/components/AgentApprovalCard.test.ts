import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'
import { ApiError, api } from '../api/client'
import AgentApprovalCard from './AgentApprovalCard.vue'
import type { AgentEvent } from '../types'

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return { ...actual, api: { ...actual.api, readFile: vi.fn() } }
})

function mountCard(tool: string, input: Record<string, unknown>) {
  const event: AgentEvent = {
    event_id: 'p', seq: 1, session_id: 's', timestamp: 'now', correlation_id: '', type: 'permission_requested',
    payload: { request_id: 'p', tool_name: tool, target: 'suite.md', tool_event: { input } },
  }
  return mount(AgentApprovalCard, { props: { event, pending: true }, global: {
    plugins: [createPinia()], stubs: { DiffEditor: {
      props: ['original', 'modified'], template: '<div class="diff-stub" :data-original="original" :data-modified="modified" />',
    } },
  } })
}

beforeEach(() => vi.resetAllMocks())

test('empty edit replacement still offers a deletion Diff', async () => {
  const wrapper = mountCard('edit', { old_text: 'remove me', new_text: '' })
  await wrapper.get('.diff-toggle').trigger('click')
  expect(wrapper.get('.diff-stub').attributes('data-modified')).toBe('')
  expect(wrapper.get('.diff-stub').attributes('data-original')).toBe('remove me')
})

test('write Diff exposes IO errors and retries without pretending the file is empty', async () => {
  vi.mocked(api.readFile).mockRejectedValueOnce(new ApiError('READ_FAILED', '磁盘读取失败', 500))
  const wrapper = mountCard('write', { workspace_path: 'suite.md', content: 'new' })
  await flushPromises()
  expect(wrapper.text()).toContain('磁盘读取失败')
  expect(wrapper.find('.diff-stub').exists()).toBe(false)
  vi.mocked(api.readFile).mockResolvedValueOnce({ path: 'suite.md', name: 'suite.md', content: 'old', sha256: 'h', owner: 'CASE', read_only: false })
  await wrapper.get('[data-test="retry-diff"]').trigger('click')
  await flushPromises()
  await wrapper.get('.diff-toggle').trigger('click')
  expect(wrapper.get('.diff-stub').attributes('data-original')).toBe('old')
})

test('only an explicit missing file is treated as a new empty file', async () => {
  vi.mocked(api.readFile).mockRejectedValueOnce(new ApiError('FILE_NOT_FOUND', '文件不存在', 404))
  const wrapper = mountCard('write', { workspace_path: 'suite.md', content: '' })
  await flushPromises()
  await wrapper.get('.diff-toggle').trigger('click')
  expect(wrapper.get('.diff-stub').attributes('data-original')).toBe('')
})

test('external write does not fabricate an empty disk baseline', async () => {
  const wrapper = mountCard('write', { path: '/external/file.md', content: 'new' })
  await flushPromises()
  expect(wrapper.text()).toContain('无法通过普通文件接口读取')
  expect(api.readFile).not.toHaveBeenCalled()
  expect(wrapper.find('.diff-toggle').exists()).toBe(false)
})
