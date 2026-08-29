import type {
  EnvironmentMetadata,
  AssetIdentity,
  DeletePreview,
  DirectoryListing,
  EditorValidationResult,
  FileDocument,
  Job,
  ReportDetail,
  ReportSummary,
  ModuleTypeOption,
  TrashEntry,
  SelectorPayload,
  WorkspaceSnapshot,
  AgentConnection,
  AgentConnectionInput,
  AgentConnectionTestResult,
  AgentApprovalDecision,
  AgentEvent,
  AgentPermissionMode,
  AgentSessionSnapshot,
} from '../types'
import { consumeSseStream } from './sse'

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
  const rawFragment = url.hash.startsWith('#') ? url.hash.slice(1) : ''
  const tokenFragment = rawFragment.startsWith('/token=') ? rawFragment.slice(1) : rawFragment
  const fragment = new URLSearchParams(tokenFragment)
  const token = fragment.get('token') || import.meta.env.VITE_CONSOLE_TOKEN
  if (token) {
    sessionStorage.setItem(TOKEN_KEY, token)
    url.searchParams.delete('launch')
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
  directories: (path?: string) =>
    request<DirectoryListing>(`/api/directories${path ? `?path=${encodeURIComponent(path)}` : ''}`),
  assetOptions: () => request<{ module_types: ModuleTypeOption[] }>('/api/assets/options'),
  createTarget: (payload: { name: string; source_root?: string }) =>
    request<WorkspaceSnapshot>('/api/assets/targets', { method: 'POST', body: json(payload) }),
  createModule: (payload: { target: string; name: string; module_type: string }) =>
    request<WorkspaceSnapshot>('/api/assets/modules', { method: 'POST', body: json(payload) }),
  createSuite: (payload: { target: string; module: string; name: string; register: boolean }) =>
    request<WorkspaceSnapshot>('/api/assets/suites', { method: 'POST', body: json(payload) }),
  createTask: (payload: { name: string; description: string; suite_files: string[] }) =>
    request<WorkspaceSnapshot>('/api/assets/tasks', { method: 'POST', body: json(payload) }),
  deletePreview: (identity: AssetIdentity) =>
    request<DeletePreview>('/api/assets/delete-preview', { method: 'POST', body: json(identity) }),
  deleteAsset: (identity: AssetIdentity) =>
    request<{ entry: TrashEntry; workspace: WorkspaceSnapshot }>('/api/assets/delete', {
      method: 'POST',
      body: json({ ...identity, confirmed: true }),
    }),
  trash: () => request<{ entries: TrashEntry[] }>('/api/trash'),
  restoreTrash: (entryId: string) =>
    request<WorkspaceSnapshot>(`/api/trash/${encodeURIComponent(entryId)}/restore`, { method: 'POST' }),
  readFile: (path: string) => request<FileDocument>(`/api/files?path=${encodeURIComponent(path)}`),
  saveFile: (document: FileDocument, content: string) =>
    request<FileDocument>('/api/files', {
      method: 'PUT',
      body: json({ path: document.path, content, sha256: document.sha256 }),
    }),
  validateEditor: (path: string, content: string, signal?: AbortSignal) =>
    request<EditorValidationResult>('/api/editor/validate', {
      method: 'POST',
      body: json({ path, content }),
      signal,
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
  agentConnection: () => request<AgentConnection>('/api/agent/connection'),
  testAgentConnection: (payload: AgentConnectionInput) =>
    request<AgentConnectionTestResult>('/api/agent/connection/test', {
      method: 'POST',
      body: json(payload),
    }),
  saveAgentConnection: (payload: AgentConnectionInput) =>
    request<AgentConnection>('/api/agent/connection', {
      method: 'PUT',
      body: json(payload),
    }),
  agentSession: () => request<AgentSessionSnapshot | null>('/api/agent/session'),
  createAgentSession: (permissionMode: AgentPermissionMode, confirmed = false) =>
    request<AgentSessionSnapshot>('/api/agent/sessions', {
      method: 'POST',
      body: json({ permission_mode: permissionMode, confirmed }),
    }),
  sendAgentMessage: (sessionId: string, text: string) =>
    request<AgentSessionSnapshot>(`/api/agent/sessions/${encodeURIComponent(sessionId)}/messages`, {
      method: 'POST',
      body: json({ text }),
    }),
  resolveAgentApproval: (sessionId: string, requestId: string, decision: AgentApprovalDecision) =>
    request<AgentSessionSnapshot>(
      `/api/agent/sessions/${encodeURIComponent(sessionId)}/approvals/${encodeURIComponent(requestId)}`,
      { method: 'POST', body: json({ decision }) },
    ),
  abortAgent: (sessionId: string) =>
    request<AgentSessionSnapshot>(`/api/agent/sessions/${encodeURIComponent(sessionId)}/abort`, { method: 'POST' }),
  closeAgentSession: (sessionId: string) =>
    request<void>(`/api/agent/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' }),
  streamAgentEvents: async (
    sessionId: string,
    afterSeq: number,
    signal: AbortSignal,
    onEvent: (event: AgentEvent) => void,
    onOpen?: () => void,
    onActivity?: () => void,
  ) => {
    const token = sessionStorage.getItem(TOKEN_KEY)
    const headers = new Headers()
    if (token) headers.set('X-AITest-Console-Token', token)
    const response = await fetch(
      `/api/agent/sessions/${encodeURIComponent(sessionId)}/events?after_seq=${afterSeq}`,
      { headers, signal, cache: 'no-store' },
    )
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      const error = data?.error ?? {}
      throw new ApiError(error.code || 'AGENT_STREAM_FAILED', error.message || `HTTP ${response.status}`, response.status)
    }
    if (!response.body) throw new ApiError('AGENT_STREAM_UNAVAILABLE', '浏览器未提供事件流', 502)
    onOpen?.()
    await consumeSseStream(response.body, onEvent, onActivity)
  },
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
