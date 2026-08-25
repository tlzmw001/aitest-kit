import type {
  EnvironmentMetadata,
  FileDocument,
  Job,
  ReportDetail,
  ReportSummary,
  SelectorPayload,
  WorkspaceSnapshot,
} from '../types'

const TOKEN_KEY = 'aitest-console-session-token'

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message)
  }
}

export function configureTokenFromUrl(): void {
  const url = new URL(window.location.href)
  const fragment = new URLSearchParams(url.hash.startsWith('#') ? url.hash.slice(1) : '')
  const token = fragment.get('token') || import.meta.env.VITE_CONSOLE_TOKEN
  if (token) {
    sessionStorage.setItem(TOKEN_KEY, token)
    url.hash = '#/'
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`)
  }
}

export function hasSessionToken(): boolean {
  return Boolean(sessionStorage.getItem(TOKEN_KEY))
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = sessionStorage.getItem(TOKEN_KEY)
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('X-AITest-Console-Token', token)
  const response = await fetch(path, { ...init, headers, cache: 'no-store' })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = data?.error ?? {}
    throw new ApiError(error.code || 'REQUEST_FAILED', error.message || `HTTP ${response.status}`, response.status)
  }
  return data as T
}

const json = (value: unknown) => JSON.stringify(value)

export const api = {
  workspace: () => request<WorkspaceSnapshot>('/api/workspace'),
  openWorkspace: (path: string) =>
    request<WorkspaceSnapshot>('/api/workspace/open', { method: 'POST', body: json({ path }) }),
  initializeWorkspace: (path: string) =>
    request<WorkspaceSnapshot>('/api/workspace/initialize', {
      method: 'POST',
      body: json({ path, confirmed: true }),
    }),
  readFile: (path: string) => request<FileDocument>(`/api/files?path=${encodeURIComponent(path)}`),
  saveFile: (document: FileDocument, content: string) =>
    request<FileDocument>('/api/files', {
      method: 'PUT',
      body: json({ path: document.path, content, sha256: document.sha256 }),
    }),
  environment: () => request<EnvironmentMetadata>('/api/environment'),
  revealEnv: (path: string) =>
    request<FileDocument>('/api/environment/reveal', {
      method: 'POST',
      body: json({ path, confirmed: true }),
    }),
  saveEnv: (document: FileDocument, content: string) =>
    request<FileDocument>('/api/environment/files', {
      method: 'PUT',
      body: json({ path: document.path, content, sha256: document.sha256, confirmed: true }),
    }),
  grantEnv: (path: string) =>
    request<{ path: string; granted: boolean }>('/api/environment/grants', {
      method: 'POST',
      body: json({ path, confirmed: true }),
    }),
  setActiveEnv: (path: string) =>
    request<{ path: string | null }>('/api/environment/active', {
      method: 'PUT',
      body: json({ path, confirmed: true }),
    }),
  reports: () => request<{ reports: ReportSummary[] }>('/api/reports'),
  reportDetail: (path: string) =>
    request<ReportDetail>(`/api/reports/detail?path=${encodeURIComponent(path)}`),
  startJob: (operation: string, selector: SelectorPayload, envFile?: string) =>
    request<Job>('/api/jobs', {
      method: 'POST',
      body: json({ operation, selector, env_file: envFile || null }),
    }),
  jobs: () => request<{ jobs: Job[] }>('/api/jobs'),
  job: (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}`),
  cancelJob: (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
}
