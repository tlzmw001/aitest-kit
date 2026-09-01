export type Owner = 'CONFIG' | 'CASE' | 'SCAFFOLD' | 'ENV' | 'SUT' | 'GENERATED' | 'REPORT' | 'SOURCE'

export interface Asset {
  path: string
  name: string
  owner: Owner
  exists: boolean
}

export interface TestCase {
  id: string
  title: string
  priority: string
  source_path: string
  source_line: number | null
}

export interface Suite {
  name: string
  manifest_path: string
  profile_path: string
  diagnostics: string[]
  assets: Asset[]
  cases: TestCase[]
}

export interface Module {
  name: string
  module_type: string
  diagnostics: string[]
  assets: Asset[]
  suites: Suite[]
}

export interface Target {
  name: string
  diagnostics: string[]
  config_path: string | null
  modules: Module[]
}

export interface Task {
  name: string
  path: string
  description: string
  unit_count: number
  env_files: string[]
  diagnostics: string[]
}

export interface ReportSummary {
  run_id: string
  status: string
  timestamp: string
  duration_seconds: number
  summary: Record<string, number>
  scope: Record<string, unknown>
  target: string
  module: string
  suite: string
  result_path: string
  report_path: string | null
}

export interface WorkspaceSnapshot {
  name: string
  path: string
  branch: string
  counts: {
    targets: number
    modules: number
    suites: number
    cases: number
    tasks: number
  }
  targets: Target[]
  tasks: Task[]
  recent_reports: ReportSummary[]
}

export interface FileDocument {
  path: string
  name: string
  content: string
  sha256: string
  owner: Owner
  read_only: boolean
  exists?: boolean
  external?: boolean
}

export interface EditorDiagnostic {
  severity: 'error' | 'warning'
  code: string
  message: string
  line: number
  column: number
  end_line: number
  end_column: number
  source: string
}

export interface EditorValidationResult {
  diagnostics: EditorDiagnostic[]
}

export interface EnvSource {
  path: string
  absolute_path: string | null
  exists: boolean
  external: boolean
  active: boolean
  keys: string[]
  error: string
  git_status: 'tracked' | 'ignored' | 'untracked' | 'external' | 'unknown'
}

export interface EnvironmentMetadata {
  sources: EnvSource[]
  shell_keys: string[]
  precedence: string[]
}

export interface Job {
  id: string
  operation: 'validate_profile' | 'codegen' | 'freshness' | 'run' | string
  command_summary: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  output: string
  exit_code: number | null
  started_at: string
  finished_at: string
  cancel_requested: boolean
}

export interface SelectorPayload {
  type: 'case' | 'suite' | 'module' | 'target' | 'task'
  suite_file?: string
  task_file?: string
  target?: string
  module?: string
  case_ids?: string[]
}

export interface ReportDetail {
  summary: ReportSummary
  result: Record<string, unknown>
  report_markdown: string
}

export interface DirectoryEntry {
  name: string
  path: string
  initialized: boolean
}

export interface DirectoryListing {
  path: string
  parent: string | null
  initialized: boolean
  directories: DirectoryEntry[]
}

export interface ModuleTypeOption {
  name: string
  description: string
}

export type AssetIdentity =
  | { kind: 'target'; target: string }
  | { kind: 'module'; target: string; module: string }
  | { kind: 'suite'; target: string; module: string; suite: string }
  | { kind: 'task'; task: string }

export interface DeletePreview {
  kind: AssetIdentity['kind']
  identity: AssetIdentity
  paths: string[]
  modified_files: string[]
  blockers: string[]
  can_delete: boolean
  recoverable: boolean
  message: string
}

export interface TrashEntry {
  entry_id: string
  created_at: string
  kind: AssetIdentity['kind']
  identity: AssetIdentity
  paths: string[]
}

export type AgentProtocol =
  | 'auto'
  | 'openai_responses'
  | 'openai_chat_completions'
  | 'anthropic_messages'

export interface AgentConnection {
  connection_name: string
  protocol: AgentProtocol
  base_url: string
  model: string
  api_key_env: string
  has_api_key: boolean
  credential_source: 'session' | 'environment' | 'missing'
}

export interface AgentConnectionInput {
  connection_name: string
  protocol: AgentProtocol
  base_url: string
  model: string
  api_key_env: string
  api_key: string
}

export interface AgentConnectionTestResult {
  status: 'connected'
  detected_protocol: Exclude<AgentProtocol, 'auto'>
  internal_provider: string
  model: string
  response_text: string
  latency_ms: number
}

export type AgentRuntimeState = 'ready' | 'missing' | 'node_missing' | 'node_unsupported' | 'invalid'

export interface AgentRuntimeStatus {
  state: AgentRuntimeState
  source: 'source' | 'user' | null
  message: string
  runtime_dir: string
  bundle_hash: string
  minimum_node_version: string
  node_version: string
  npm_version: string
  registry: string
  dependencies: Array<{ name: string; version: string }>
  setup_command: string
}

export type AgentPermissionMode = 'approval' | 'full_trust'
export type AgentSessionStatus = 'created' | 'running' | 'awaiting_approval' | 'succeeded' | 'failed' | 'aborted' | 'interrupted'

export interface AgentSessionSnapshot {
  session_id: string
  pi_session_id: string
  permission_mode: AgentPermissionMode
  title: string
  status: AgentSessionStatus
  active_prompt: boolean
  pending_approval_ids: string[]
  last_seq: number
  created_at: string
  updated_at: string
  is_active: boolean
}

export interface AgentEvent {
  event_id: string
  seq: number
  session_id: string
  type: string
  timestamp: string
  correlation_id: string
  payload: Record<string, unknown>
}

export interface AgentSessionHistory {
  events: AgentEvent[]
  last_seq: number
  resync_required: boolean
}

export type AgentApprovalDecision = 'allow_once' | 'allow_session' | 'deny'
