import { expect, test, type Page, type Route } from '@playwright/test'

const casesPath = 'test_workspace/suites/demo/orders-smoke/cases.md'
const suitePath = 'test_workspace/suites/demo/orders-smoke/suite.yaml'
const reportResultPath = 'test_workspace/reports/run-20260827-1/result.json'

const workspace = {
  name: 'AITest e2e workspace',
  path: '/tmp/aitest-console-e2e',
  branch: 'codex/e2e',
  counts: { targets: 1, modules: 1, suites: 1, cases: 1, tasks: 0 },
  targets: [{
    name: 'demo',
    diagnostics: [],
    config_path: 'test_workspace/targets/demo/target.yaml',
    modules: [{
      name: 'orders',
      module_type: 'standard_http',
      diagnostics: [],
      assets: [],
      suites: [{
        name: 'orders-smoke',
        manifest_path: suitePath,
        profile_path: 'test_workspace/suites/demo/orders-smoke/profile_orders-smoke_suite.md',
        diagnostics: [],
        cases: [{ id: 'TC-ORD-001', title: '创建订单', priority: 'P0', source_path: casesPath, source_line: 4 }],
        assets: [
          { path: suitePath, name: 'suite.yaml', owner: 'CONFIG', exists: true },
          { path: casesPath, name: 'cases.md', owner: 'CASE', exists: true },
        ],
      }],
    }],
  }],
  tasks: [],
  recent_reports: [],
}

const reportSummary = {
  run_id: 'run-20260827-1',
  status: 'passed',
  timestamp: '2026-08-27T12:00:00Z',
  duration_seconds: 1.27,
  summary: { passed: 1, failed: 0, error: 0 },
  scope: { type: 'suite' },
  target: 'demo',
  module: 'orders',
  suite: 'orders-smoke',
  result_path: reportResultPath,
  report_path: 'test_workspace/reports/run-20260827-1/report.md',
}

const agentConnection = {
  connection_name: 'E2E gateway',
  protocol: 'auto',
  base_url: 'https://gateway.example.test',
  model: 'gpt-5.5',
  api_key_env: 'AITEST_AGENT_API_KEY',
  has_api_key: false,
  credential_source: 'missing',
}

let agentSession: Record<string, unknown> | null = null
let agentPhase = 0
let agentCreatePayload: Record<string, unknown> | null = null

function agentSnapshot(overrides: Record<string, unknown> = {}) {
  return {
    session_id: 'agent-session-1',
    pi_session_id: 'pi-session-1',
    permission_mode: 'approval',
    status: agentPhase === 0 ? 'created' : agentPhase === 1 ? 'awaiting_approval' : 'succeeded',
    active_prompt: agentPhase === 1,
    pending_approval_ids: agentPhase === 1 ? ['permission-1'] : [],
    last_seq: agentPhase === 0 ? 1 : agentPhase === 1 ? 6 : 10,
    created_at: '2026-08-28T12:00:00Z',
    updated_at: '2026-08-28T12:00:01Z',
    ...overrides,
  }
}

function agentEvents() {
  const base = [
    { event_id: 'ae-1', seq: 1, type: 'session_created', payload: { permission_mode: agentSession?.permission_mode ?? 'approval' } },
  ]
  if (agentPhase >= 1) base.push(
    { event_id: 'ae-2', seq: 2, type: 'user_message', payload: { text: '检查并运行当前 suite' } },
    { event_id: 'ae-3', seq: 3, type: 'text_delta', payload: { delta: '我先检查用例和 profile。' } },
    {
      event_id: 'ae-4', seq: 4, type: 'tool_call_requested',
      payload: {
        tool_call_id: 'tool-1', tool_name: 'write', aitest_operation: 'run',
        input: { path: casesPath, workspace_path: casesPath, content: '# Orders smoke\n\nupdated by Agent\n' },
      },
    },
    {
      event_id: 'ae-5', seq: 5, type: 'permission_requested',
      payload: { request_id: 'permission-1', tool_name: 'write', surface: 'write', target: casesPath, summary: '写入 Markdown suite' },
    },
  )
  if (agentPhase >= 2) base.push(
    { event_id: 'ae-6', seq: 6, type: 'approval_submitted', payload: { request_id: 'permission-1', decision: 'allow_once' } },
    { event_id: 'ae-7', seq: 7, type: 'permission_resolved', payload: { request_id: 'permission-1', decision: 'allow_once' } },
    { event_id: 'ae-8', seq: 8, type: 'tool_call_finished', payload: { tool_call_id: 'tool-1', tool_name: 'write', is_error: false, result: {} } },
    { event_id: 'ae-9', seq: 9, type: 'text_delta', payload: { delta: '用例已更新。' } },
    { event_id: 'ae-10', seq: 10, type: 'agent_finished', payload: { status: 'succeeded' } },
  )
  return base.map((event) => ({
    session_id: 'agent-session-1', timestamp: '2026-08-28T12:00:01Z', correlation_id: 'prompt-1', ...event,
  }))
}

async function mockConsoleApi(page: Page): Promise<void> {
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => respond(route))
}

async function respond(route: Route): Promise<void> {
  const request = route.request()
  const url = new URL(request.url())
  const json = (body: unknown, status = 200) => route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })

  if (url.pathname === '/api/workspace') return json(workspace)
  if (url.pathname === '/api/agent/runtime') return json({
    state: 'ready', source: 'source', message: 'ready',
    runtime_dir: '/repo/agent_runtime/pi_worker', bundle_hash: 'a'.repeat(64),
    minimum_node_version: '22.19.0', node_version: 'v24.14.0', npm_version: '11.9.0',
    registry: 'https://registry.npmjs.org/', dependencies: [], setup_command: 'aitest agent setup',
  })
  if (url.pathname === '/api/agent/session') return json(agentSession)
  if (url.pathname === '/api/agent/sessions' && request.method() === 'POST') {
    const input = request.postDataJSON() as { permission_mode: string }
    agentCreatePayload = input as unknown as Record<string, unknown>
    agentPhase = 0
    agentSession = agentSnapshot({ permission_mode: input.permission_mode })
    return json(agentSession)
  }
  if (/^\/api\/agent\/sessions\/[^/]+\/messages$/.test(url.pathname)) {
    agentPhase = 1
    agentSession = agentSnapshot()
    return json(agentSession)
  }
  if (/^\/api\/agent\/sessions\/[^/]+\/approvals\/[^/]+$/.test(url.pathname)) {
    agentPhase = 2
    agentSession = agentSnapshot()
    return json(agentSession)
  }
  if (/^\/api\/agent\/sessions\/[^/]+\/abort$/.test(url.pathname)) {
    agentSession = agentSnapshot({ status: 'aborted', active_prompt: false, pending_approval_ids: [] })
    return json(agentSession)
  }
  if (/^\/api\/agent\/sessions\/[^/]+\/events$/.test(url.pathname)) {
    const afterSeq = Number(url.searchParams.get('after_seq') || '0')
    const body = agentEvents()
      .filter((event) => event.seq > afterSeq)
      .map((event) => `id: ${event.seq}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`)
      .join('')
    return route.fulfill({ status: 200, contentType: 'text/event-stream', body })
  }
  if (/^\/api\/agent\/sessions\/[^/]+$/.test(url.pathname) && request.method() === 'DELETE') {
    agentSession = null
    agentPhase = 0
    return route.fulfill({ status: 204, body: '' })
  }
  if (url.pathname === '/api/agent/connection') {
    if (request.method() === 'PUT') {
      return json({ ...agentConnection, has_api_key: true, credential_source: 'session' })
    }
    return json(agentConnection)
  }
  if (url.pathname === '/api/agent/connection/test') {
    return json({
      status: 'connected',
      detected_protocol: 'openai_responses',
      internal_provider: 'openai',
      model: 'gpt-5.5',
      response_text: 'OK',
      latency_ms: 6218,
    })
  }
  if (url.pathname === '/api/assets/options') {
    return json({ module_types: [{ name: 'standard_http', description: 'HTTP 模块' }] })
  }
  if (url.pathname === '/api/editor/validate') return json({ diagnostics: [] })
  if (url.pathname === '/api/files') {
    const path = url.searchParams.get('path') || ''
    const content = path === casesPath
      ? '# Orders smoke\n\n## TC-ORD-001 创建订单\n\n- 期望：订单创建成功\n'
      : 'target: demo\nmodule: orders\nsuite: orders-smoke\ncase_files:\n  - cases.md\n'
    return json({
      path,
      name: path.split('/').at(-1) || path,
      content,
      sha256: `sha-${path}`,
      owner: path.endsWith('.md') ? 'CASE' : 'CONFIG',
      read_only: false,
    })
  }
  if (url.pathname === '/api/reports') return json({ reports: [reportSummary] })
  if (url.pathname === '/api/reports/detail') {
    return json({
      summary: reportSummary,
      result: { run_id: reportSummary.run_id, status: 'passed', summary: reportSummary.summary },
      report_markdown: [
        '# Orders smoke',
        '',
        '<script>window.__unsafeReport = true</script>',
        '',
        '![remote image](https://example.com/tracker.png)',
        '',
        '| case | status |',
        '| --- | --- |',
        '| TC-ORD-001 | passed |',
      ].join('\n'),
    })
  }
  return json({ error: { code: 'NOT_MOCKED', message: `${request.method()} ${url.pathname}` } }, 404)
}

test.beforeEach(async ({ page }) => {
  agentSession = null
  agentPhase = 0
  agentCreatePayload = null
  await mockConsoleApi(page)
  await page.goto('/?launch=e2e#/token=e2e-local-session')
  await expect(page).toHaveURL(/#\/$/)
  await expect(page).not.toHaveURL(/[?&]launch=/)
  await expect(page.getByText('AITest e2e workspace', { exact: true }).first()).toBeVisible()
  await expect(page.locator('.runtime kbd')).toHaveCount(0)
})

test('runs an approval Agent session, shows Monaco Diff, and recovers after refresh', async ({ page }) => {
  await page.getByRole('link', { name: 'Agent', exact: true }).click()
  await page.locator('[data-test="create-approval-session"]').click()
  await page.locator('[data-test="agent-composer"]').fill('检查并运行当前 suite')
  await page.locator('[data-test="send-agent-message"]').click()

  const approval = page.locator('[data-test="agent-approval-card"]')
  await expect(approval).toBeVisible()
  await expect(approval).toContainText(casesPath)
  await approval.getByRole('button', { name: '查看 Monaco Diff' }).click()
  await expect(page.locator('.approval-diff [role="code"]')).toHaveCount(2)
  const composer = page.locator('[data-test="agent-composer"]')
  await expect(composer).toBeVisible()
  await expect.poll(() => composer.evaluate((element) => element.getBoundingClientRect().bottom < window.innerHeight - 26)).toBe(true)
  await expect(approval.locator('.section-label')).toHaveCSS('display', 'block')
  await expect(page).toHaveScreenshot('agent-approval-workbench.png')

  await page.locator('[data-test="allow-session"]').click()
  await expect(page.getByText('本轮完成')).toBeVisible()
  await expect(page.getByText('用例已更新。')).toBeVisible()
  await page.locator('.agent-tool-summary').click()
  await expect(page.getByRole('link', { name: '在编辑器打开' })).toHaveAttribute('href', /#\/editor\?path=.*cases\.md/)
  await expect(page.getByRole('link', { name: '查看执行报告' })).toHaveAttribute('href', '#/reports')

  await page.reload()
  await expect(page.getByText('本轮完成')).toBeVisible()
  await expect(page.locator('.user-message')).toHaveCount(1)
  await expect(page.getByText('用例已更新。')).toBeVisible()
})

test('requires a workspace-specific confirmation before full trust', async ({ page }) => {
  await page.getByRole('link', { name: 'Agent', exact: true }).click()
  await page.locator('[data-test="create-full-trust-session"]').click()

  const dialog = page.locator('[data-test="full-trust-dialog"]')
  await expect(dialog).toContainText('/tmp/aitest-console-e2e')
  await expect(dialog).toContainText('文件内容可能发送给当前模型服务')
  await page.locator('[data-test="confirm-full-trust"]').click()

  await expect(page.getByText('完全信任', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('该确认只对本次 session 生效')).toBeHidden()
  expect(agentCreatePayload).toMatchObject({ permission_mode: 'full_trust', confirmed: true })
})

test('opens multiple files and preserves the compact close hover surface', async ({ page }) => {
  await page.getByTitle(suitePath).click()
  await expect(page.locator('.monaco-editor')).toHaveCount(1)
  await page.getByTitle(casesPath).click()

  await expect(page.locator('[data-test="editor-tab"]')).toHaveCount(2)
  const closeButton = page.getByRole('button', { name: '关闭 suite.yaml' })
  await closeButton.hover()
  await expect(closeButton).toHaveScreenshot('editor-tab-close-hover.png')
})

test('keeps the editor empty after the last tab is explicitly closed', async ({ page }) => {
  await page.getByTitle(casesPath).click()
  await expect(page.locator('[data-test="editor-tab"]')).toHaveCount(1)

  await page.getByRole('button', { name: '关闭 cases.md' }).click()

  await expect(page.locator('[data-test="editor-tab"]')).toHaveCount(0)
  await expect(page.locator('.tab.empty.active')).toHaveText('没有打开文件')
})

test('recovers from one polling error and refreshes after a failed terminal job', async ({ page }) => {
  let jobPolls = 0
  let workspaceRefreshes = 0
  const job = {
    id: 'job-1', operation: 'run', command_summary: 'aitest run --suite-file suite.yaml',
    status: 'running', output: '', exit_code: null, started_at: '2026-08-27T12:00:00Z',
    finished_at: '', cancel_requested: false,
  }
  await page.route((url) => url.pathname === '/api/environment', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ sources: [], shell_keys: [], precedence: [] }),
  }))
  await page.route((url) => url.pathname === '/api/jobs', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ jobs: [job] }),
  }))
  await page.route((url) => url.pathname === '/api/jobs/job-1', async (route) => {
    jobPolls += 1
    if (jobPolls === 1) {
      return route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'BACKEND_BUSY', message: 'backend busy' } }),
      })
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ...job, status: 'failed', output: '1 failed', exit_code: 1 }),
    })
  })
  await page.route((url) => url.pathname === '/api/workspace', (route) => {
    workspaceRefreshes += 1
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(workspace) })
  })

  await page.getByRole('link', { name: '运行', exact: true }).click()

  await expect(page.locator('.job-output-head strong')).toHaveText('failed', { timeout: 5_000 })
  expect(jobPolls).toBe(2)
  await expect.poll(() => workspaceRefreshes).toBe(1)
})

test('opens the Markdown source selected from a failed diagnostic', async ({ page }) => {
  const failedSummary = { ...reportSummary, status: 'failed', summary: { passed: 0, failed: 1, error: 0 } }
  await page.route((url) => url.pathname === '/api/reports', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ reports: [failedSummary] }),
  }))
  await page.route((url) => url.pathname === '/api/reports/detail', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      summary: failedSummary,
      result: { cases: [{ case_id: 'TC-ORD-001', outcome: 'failed', failure_type: 'ASSERTION_FAILURE' }] },
      report_markdown: '# Failed',
    }),
  }))

  await page.getByRole('link', { name: '诊断', exact: true }).click()
  await page.getByRole('link', { name: '定位 source' }).click()

  await expect(page).toHaveURL(new RegExp(`path=${casesPath.replaceAll('/', '\\/')}`))
  await expect(page.locator('.code-editor-stage .monaco-editor')).toBeVisible()
})

test('Reka dialog restores focus and the editor splitter supports the keyboard', async ({ page }) => {
  const createAsset = page.getByRole('button', { name: '新建资产' })
  await createAsset.click()
  const dialog = page.getByRole('dialog', { name: '新建测试资产' })
  await expect(dialog).toBeVisible()
  expect(await page.evaluate(() => Boolean(document.activeElement?.closest('[role="dialog"]')))).toBe(true)

  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(createAsset).toBeFocused()

  await page.getByTitle(suitePath).click()
  const splitter = page.getByRole('separator', { name: '调整源码与 Inspector 宽度' })
  await expect(splitter).toBeVisible()
  await splitter.focus()
  const before = await splitter.getAttribute('aria-valuenow')
  await splitter.press('ArrowLeft')
  await expect(splitter).not.toHaveAttribute('aria-valuenow', before || '')
})

test('shows the real Monaco Diff and can overwrite with the local edit', async ({ page }) => {
  let readCount = 0
  const writes: Array<Record<string, unknown>> = []
  await page.route((url) => url.pathname === '/api/files', async (route) => {
    if (route.request().method() === 'PUT') {
      const payload = route.request().postDataJSON() as Record<string, unknown>
      writes.push(payload)
      if (writes.length > 1) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            path: casesPath,
            name: 'cases.md',
            content: payload.content,
            sha256: 'sha-overwritten',
            owner: 'CASE',
            read_only: false,
          }),
        })
      }
      return route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'FILE_CONFLICT', message: '文件已在 Console 外发生变化' } }),
      })
    }
    readCount += 1
    const content = readCount === 1 ? '# original content\n' : '# disk changed outside Console\n'
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        path: casesPath,
        name: 'cases.md',
        content,
        sha256: `sha-read-${readCount}`,
        owner: 'CASE',
        read_only: false,
      }),
    })
  })

  await page.getByTitle(casesPath).click()
  const editor = page.locator('.code-editor-stage .monaco-editor')
  await expect(editor).toBeVisible()
  await editor.click()
  await page.keyboard.press('ControlOrMeta+A')
  await page.keyboard.type('# local unsaved edit')
  await page.getByRole('button', { name: /保存/ }).click()

  const dialog = page.getByRole('dialog', { name: '文件已在外部修改' })
  await expect(dialog).toBeVisible()
  await expect(dialog.locator('.monaco-diff-editor')).toBeVisible()
  await expect(dialog).toContainText('左侧是最新磁盘版本')
  await dialog.getByRole('button', { name: '保留我的修改并覆盖磁盘' }).click()
  await expect(dialog).toBeHidden()
  await expect(page.locator('.code-editor-stage .monaco-editor')).toBeVisible()
  await expect(page.locator('.code-editor-stage .view-lines')).toContainText('local unsaved edit')
  expect(writes).toHaveLength(2)
  expect(writes[0].content).toContain('local unsaved edit')
  expect(writes[1]).toMatchObject({ content: writes[0].content, sha256: 'sha-read-2' })
})

test('renders sanitized Markdown and opens result.json with keyboard tabs', async ({ page }) => {
  await page.getByRole('link', { name: '报告', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Orders smoke', level: 1 })).toBeVisible()
  await expect(page.locator('.markdown-preview script')).toHaveCount(0)
  await expect(page.locator('.markdown-preview img')).toHaveCount(0)
  await expect(page.locator('.markdown-preview table')).toContainText('TC-ORD-001')

  const reportTab = page.getByRole('tab', { name: 'report.md' })
  await reportTab.focus()
  await reportTab.press('ArrowRight')

  const jsonTab = page.getByRole('tab', { name: 'result.json' })
  await expect(jsonTab).toHaveAttribute('aria-selected', 'true')
  await expect(page.locator('.json-editor-panel .monaco-editor')).toBeVisible()
  await expect(page.locator('.json-editor-panel')).toContainText('run-20260827-1')
  expect(await page.evaluate(() => sessionStorage.getItem('aitest-console-session-token'))).toBe('e2e-local-session')
  expect(page.url()).not.toContain('e2e-local-session')
})

test('configures an agent connection without asking for a Pi provider', async ({ page }) => {
  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('link', { name: /打开模型连接/ }).click()

  await expect(page).toHaveURL(/#\/settings\/agent$/)
  await expect(page.getByRole('heading', { name: '模型连接' })).toBeVisible()
  await expect(page.locator('[data-test="agent-runtime-card"]')).toContainText('源码 checkout')
  await expect(page.locator('[data-test="agent-runtime-card"]')).toContainText('v24.14.0')
  await expect(page.locator('[name="provider"]')).toHaveCount(0)
  await page.locator('[data-test="connection-api-key"]').fill('e2e-session-key')
  await page.locator('[data-test="test-connection"]').click()

  await expect(page.getByText('连接测试成功')).toBeVisible()
  await expect(page.getByRole('definition').filter({ hasText: 'OpenAI Responses' })).toBeVisible()
  await expect(page.getByText('6.22 s')).toBeVisible()
  await expect(page.locator('.model-response')).toContainText('OK')

  await page.locator('[data-test="save-connection"]').click()
  await expect(page.getByText('配置已保存', { exact: false })).toBeVisible()
  await expect(page.getByText('当前 Console 会话已提供 Key')).toBeVisible()
  await expect(page.locator('[data-test="connection-api-key"]')).toHaveValue('')
  const persistedValues = await page.evaluate(() => {
    const values = (storage: Storage) => Array.from(
      { length: storage.length },
      (_, index) => storage.getItem(storage.key(index) || ''),
    )
    return [...values(localStorage), ...values(sessionStorage)]
  })
  expect(persistedValues).not.toContain('e2e-session-key')
})
