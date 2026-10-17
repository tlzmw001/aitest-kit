import { expect, test, type Page } from '@playwright/test'

const path = 'test_workspace/suites/demo/smoke/cases.md'
const initial = '# original'
const workspace = {
  name: 'Stability test workspace', path: '/tmp/aitest-stability', branch: '',
  counts: { targets: 0, modules: 0, suites: 0, cases: 0, tasks: 0 }, targets: [], tasks: [], recent_reports: [],
}
const document = (content: string, sha256 = 'initial') => ({ path, name: 'cases.md', content, sha256, owner: 'CASE', read_only: false })

async function setup(page: Page) {
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const url = new URL(route.request().url())
    const payloads: Record<string, unknown> = {
      '/api/workspace': workspace,
      '/api/files': document(initial),
      '/api/editor/validate': { diagnostics: [] },
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payloads[url.pathname] ?? {}) })
  })
  await page.goto('/#/token=stability-test-session')
  await expect(page.getByText(workspace.name, { exact: true }).first()).toBeVisible()
}

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
