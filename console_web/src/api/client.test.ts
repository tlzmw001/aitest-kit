import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, configureTokenFromUrl, hasSessionToken } from './client'

describe('console API session', () => {
  beforeEach(() => {
    sessionStorage.clear()
    window.history.replaceState({}, '', '/#token=test-session-token')
    vi.restoreAllMocks()
  })

  it('moves the URL token into session storage and removes it from the URL', () => {
    configureTokenFromUrl()

    expect(hasSessionToken()).toBe(true)
    expect(window.location.search).toBe('')
    expect(window.location.hash).toBe('#/')
    expect(localStorage.length).toBe(0)
  })

  it('sends the session token in a header', async () => {
    configureTokenFromUrl()
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ reports: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    await api.reports()

    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers)
    expect(headers.get('X-AITest-Console-Token')).toBe('test-session-token')
  })
})
