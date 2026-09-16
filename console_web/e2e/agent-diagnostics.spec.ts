import { expect, test } from '@playwright/test'

for (const width of [1440, 375]) {
  test(`request diagnostics is visible, bounded and one-shot at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const row = {
      request_id: '98ce7351-request', message_id: 'm', phase: 'waiting_text',
      detail: 'enabled', started_at: new Date().toISOString(), phase_started_at: new Date().toISOString(),
      request_ms: 12, headers_ms: 3109, http_status: 200, first_sse_event_ms: 3200,
      raw_event_types: { 'response.created': { count: 1, first_ms: 3200, last_ms: 3200 } },
    }
    let session = {
      session_id: 'diagnostics', pi_session_id: 'pi', permission_mode: 'approval', title: '请求诊断验证',
      status: 'running', active_prompt: true, pending_approval_ids: [] as string[], last_seq: 10,
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(), is_active: true,
      diagnostics: { requests: [row], retry: null, message_id: 'm' },
    }
    let sent: unknown;
    await page.route((url) => url.pathname.startsWith('/api/'), (route) => {
      const url = new URL(route.request().url())
      if (url.pathname.endsWith('/events')) return route.fulfill({ contentType: 'text/event-stream', body: ': heartbeat\n\n' })
      if (url.pathname.endsWith('/messages')) {
        sent = route.request().postDataJSON()
        session = { ...session, active_prompt: true, status: 'running' }
        return route.fulfill({ json: session })
      }
      const responses: Record<string, unknown> = {
        '/api/workspace': { name: '诊断验证工作区', path: '/tmp/diagnostics', counts: { targets: 0, modules: 0, suites: 0, cases: 0, tasks: 0 }, targets: [], tasks: [], recent_reports: [] },
        '/api/agent/session': session,
        '/api/agent/sessions': { sessions: [session] },
        '/api/agent/sessions/diagnostics/history': { session, events: [], last_seq: 10, resync_required: false },
        '/api/agent/connection': { model: 'fixture-model' },
        '/api/agent/runtime': { state: 'ready' },
      }
      return route.fulfill({ json: responses[url.pathname] ?? {} })
    })
    await page.goto('/#/token=diagnostic-fixture-session')
    await expect(page.getByText('诊断验证工作区', { exact: true }).first()).toBeVisible()
    await page.goto('/#/agent')
    const stage = page.locator('[data-test="agent-request-stage"]')
    await expect(stage).toContainText('已连接，等待回复')
    await expect(stage).toBeInViewport()
    await page.locator('.request-diagnostics summary').click()
    await expect(page.locator('.request-diagnostics')).toContainText('未采集')
    await expect(page.locator('.request-diagnostics')).toContainText('response.created')
    expect(await page.locator('.request-diagnostics').evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true)
    await expect(page.getByRole('button', { name: '中止', exact: true })).toBeInViewport()
    await page.screenshot({ path: info.outputPath(`diagnostics-${width}.png`), fullPage: true })
    session = { ...session, status: 'succeeded', active_prompt: false }
    await page.reload()
    const toggle = page.getByLabel('仅下一条消息采集详细流诊断')
    await toggle.check()
    await page.locator('[data-test="agent-composer"]').fill('本地测试')
    await page.locator('[data-test="send-agent-message"]').click()
    await expect.poll(() => sent).toEqual({ text: '本地测试', diagnostics: 'stream' })
    await expect(toggle).not.toBeChecked()
  })
}
