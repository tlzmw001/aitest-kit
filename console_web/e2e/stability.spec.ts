import { expect, test, type Page } from '@playwright/test'

const path = 'test_workspace/suites/demo/smoke/cases.md'
const initial = '# original'
const workspace = {
  name: 'Stability test workspace', path: '/tmp/aitest-stability', branch: '',
  counts: { targets: 0, modules: 0, suites: 0, cases: 0, tasks: 0 }, targets: [], tasks: [], recent_reports: [],
}
const document = (content: string, sha256 = 'initial') => ({ path, name: 'cases.md', content, sha256, owner: 'CASE', read_only: false })
const session = {
  session_id: 'stability', pi_session_id: 'pi-stability', permission_mode: 'approval', title: 'Recovery test',
  status: 'running', active_prompt: true, pending_approval_ids: [], last_seq: 1,
  created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z', is_active: true,
}

async function setup(page: Page) {
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const url = new URL(route.request().url())
    const payloads: Record<string, unknown> = {
      '/api/workspace': workspace,
      '/api/files': document(initial),
      '/api/editor/validate': { diagnostics: [] },
      '/api/agent/session': session,
      '/api/agent/sessions': { sessions: [session] },
      '/api/agent/sessions/stability/history': { events: [], last_seq: 1, resync_required: false, session },
      '/api/agent/connection': { model: 'test-model' },
      '/api/agent/runtime': { state: 'ready' },
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payloads[url.pathname] ?? {}) })
  })
  await page.goto('/#/token=stability-test-session')
  await expect(page.getByText(workspace.name, { exact: true }).first()).toBeVisible()
}

test('returning from history reconnects the still-active session stream', async ({ page }) => {
  await setup(page)
  const active = { ...session, status: 'succeeded', active_prompt: false }
  const historical = { ...session, session_id: 'historical', title: 'Archived conversation',
    is_active: false, status: 'succeeded', active_prompt: false }
  await page.route('**/api/agent/session', (route) => route.fulfill({ json: active }))
  await page.route('**/api/agent/sessions', (route) => route.fulfill({ json: { sessions: [active, historical] } }))
  await page.route('**/api/agent/sessions/historical/history?*', (route) => route.fulfill({
    json: { session: historical, events: [], last_seq: 1, resync_required: false },
  }))
  let historyVisits = 0
  await page.route('**/api/agent/sessions/stability/history?*', (route) => {
    historyVisits += 1
    return route.fulfill({ json: { session: active, events: [], last_seq: 1, resync_required: false } })
  })
  await page.route('**/api/agent/sessions/stability/events*', (route) => {
    const event = { event_id: 'after-return', seq: 2, type: 'text_delta', payload: { delta: 'Stream resumed after history' },
      session_id: session.session_id, timestamp: session.updated_at, correlation_id: '' }
    return route.fulfill({ status: 200, contentType: 'text/event-stream',
      body: historyVisits > 1 ? `id: 2\nevent: text_delta\ndata: ${JSON.stringify(event)}\n\n` : ': heartbeat\n\n' })
  })
  await page.getByRole('link', { name: 'Agent', exact: true }).click()
  const running = page.locator('.agent-session-items button').filter({ hasText: session.title })
  await expect(running).toHaveClass(/active/)
  await page.locator('.agent-session-items button').filter({ hasText: historical.title }).click()
  await expect(page.locator('.agent-stage h1')).toHaveText(historical.title)
  await expect(running).toHaveClass(/active/)
  await running.click()
  await expect(page.getByText('Stream resumed after history')).toBeVisible()
})

test('Monaco keeps input typed while a save response is in flight', async ({ page }) => {
  await setup(page)
  let finish!: () => void
  const responseGate = new Promise<void>((resolve) => { finish = resolve })
  let requestStarted!: () => void
  const started = new Promise<void>((resolve) => { requestStarted = resolve })
  let written = ''
  await page.route('**/api/files', async (route) => {
    if (route.request().method() !== 'PUT') return route.fallback()
    written = route.request().postDataJSON().content
    requestStarted()
    await responseGate
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(document(written, 'saved')) })
  })
  await page.goto(`/#/editor?path=${encodeURIComponent(path)}`)
  const editor = page.locator('.code-editor-stage .monaco-editor')
  await expect(editor).toBeVisible()
  // Monaco follows the emulated browser platform, not Playwright's host OS.
  const selectAll = await page.evaluate(() => navigator.userAgent.includes('Macintosh') ? 'Meta+A' : 'Control+A')
  await editor.click()
  await page.keyboard.press(selectAll)
  await page.keyboard.type('# sent')
  await page.getByRole('button', { name: /保存/ }).click()
  await started
  await editor.click()
  await page.keyboard.press(selectAll)
  await page.keyboard.type('# newer unsaved')
  finish()
  await expect(page.getByText('已保存并更新文件 hash')).toBeVisible()
  await expect(page.locator('.code-editor-stage .view-lines')).toContainText('newer unsaved')
  await expect(page.getByRole('button', { name: /保存/ })).toBeEnabled()
  expect(written).toBe('# sent')
})

test('expired replay still renders an actionable approval and an honest Diff error', async ({ page }) => {
  await setup(page)
  let approved = false
  const envelope = (seq: number, type: string, payload: Record<string, unknown>) => ({
    event_id: `e-${seq}`, seq, type, payload, session_id: session.session_id, timestamp: session.updated_at, correlation_id: '',
  })
  const current = () => ({ ...session, last_seq: approved ? 1005 : 1004,
    status: approved ? 'succeeded' : 'awaiting_approval', active_prompt: !approved,
    pending_approval_ids: approved ? [] : ['pending'],
  })
  await page.route('**/api/agent/sessions/stability/events*', (route) => {
    const seq = Number(new URL(route.request().url()).searchParams.get('after_seq'))
    const events = seq < 1004 ? [envelope(1004, 'resync_required', {
      session: current(),
      events: [envelope(1003, 'tool_call_requested', {
        tool_call_id: 'write-1', tool_name: 'write', input: { path, workspace_path: path, content: '' },
      }), envelope(1004, 'text_delta', { delta: 'Retained history' })],
      pending_approvals: [{ request_id: 'pending', tool_name: 'write', surface: 'write', target: path }],
    })] : approved && seq < 1005 ? [envelope(1005, 'agent_finished', { status: 'succeeded' })] : []
    const body = events.map((event) => `id: ${event.seq}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`).join('') || ': heartbeat\n\n'
    return route.fulfill({ status: 200, contentType: 'text/event-stream', body })
  })
  await page.route('**/api/files?*', (route) => route.fulfill({ status: 500, contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'READ_FAILED', message: '磁盘读取失败' } }),
  }))
  await page.route('**/api/agent/sessions/stability/approvals/pending', (route) => {
    approved = true
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(current()) })
  })
  await page.getByRole('link', { name: 'Agent', exact: true }).click()
  const card = page.locator('[data-test="agent-approval-card"]')
  await expect(card).toBeVisible()
  await expect(page.getByText('Retained history')).toBeVisible()
  await expect(card.getByRole('alert')).toContainText('磁盘读取失败')
  await expect(card.locator('.monaco-diff-editor')).toHaveCount(0)
  await page.route('**/api/files?*', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(document(initial)) }))
  await card.getByRole('button', { name: '重试读取' }).click()
  await card.getByRole('button', { name: '查看 Monaco Diff' }).click()
  await expect(card.locator('.monaco-diff-editor')).toBeVisible()
  await expect(card.locator('[role="code"]')).toHaveCount(2)
  await expect(card.locator('.approval-diff')).toContainText('original')
  await page.screenshot({ path: 'test-results/stability-approval-deletion-diff.png' })
  await card.getByRole('button', { name: '允许一次' }).click()
  await expect(page.getByText('本轮完成')).toBeVisible()
  const input = page.locator('[data-test="agent-composer"]')
  await input.fill('你好')
  let messages = 0
  page.on('request', (request) => { if (request.url().endsWith('/messages')) messages += 1 })
  await input.dispatchEvent('compositionstart')
  await input.dispatchEvent('keydown', { key: 'Enter', isComposing: true })
  await input.dispatchEvent('compositionend')
  await input.dispatchEvent('keydown', { key: 'Enter', keyCode: 229 })
  await expect(input).toHaveValue('你好')
  expect(messages).toBe(0)
})
