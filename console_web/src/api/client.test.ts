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

  it('consumes the one-time launch parameter while preserving unrelated query parameters', () => {
    window.history.replaceState({}, '', '/?launch=one-time&view=compact#token=launch-token')

    configureTokenFromUrl()

    expect(hasSessionToken()).toBe(true)
    expect(window.location.search).toBe('?view=compact')
    expect(window.location.hash).toBe('#/')
  })

  it('captures the token before hash router initialization can normalize the fragment', async () => {
    vi.resetModules()
    sessionStorage.clear()
    window.history.replaceState({}, '', '/#token=router-order-token')

    const { createConsoleRouter } = await import('../router')
    expect(window.location.hash).toBe('#token=router-order-token')
    configureTokenFromUrl()
    createConsoleRouter()

    expect(hasSessionToken()).toBe(true)
    expect(window.location.hash).toBe('#/')
  })

  it('recovers a token fragment normalized by hash history', () => {
    sessionStorage.clear()
    window.history.replaceState({}, '', '/#/token=normalized-token')

    configureTokenFromUrl()

    expect(hasSessionToken()).toBe(true)
    expect(window.location.hash).toBe('#/')
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

  it('does not store an agent API key while saving a connection', async () => {
    configureTokenFromUrl()
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ has_api_key: true, credential_source: 'session' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await api.saveAgentConnection({
      connection_name: 'Gateway',
      protocol: 'auto',
      base_url: 'https://gateway.example.test',
      model: 'gpt-5.5',
      api_key_env: 'GATEWAY_API_KEY',
      api_key: 'session-secret',
    })

    expect(fetchMock.mock.calls[0][0]).toBe('/api/agent/connection')
    expect(fetchMock.mock.calls[0][1]?.method).toBe('PUT')
    expect(localStorage.length).toBe(0)
    const sessionValues = Array.from(
      { length: sessionStorage.length },
      (_, index) => sessionStorage.getItem(sessionStorage.key(index) || ''),
    )
    expect(sessionValues).not.toContain('session-secret')
  })

  it('starts Runtime setup only through the confirmed fixed endpoint', async () => {
    configureTokenFromUrl()
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 'setup-1', status: 'queued' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await api.setupAgentRuntime()

    expect(fetchMock.mock.calls[0][0]).toBe('/api/agent/runtime/setup')
    expect(fetchMock.mock.calls[0][1]?.method).toBe('POST')
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ confirmed: true })
  })
})
