export interface AITestCompletion {
  label: string
  apply: string
  type: 'property'
  detail: string
}

const suiteKeys = entries({
  target: '绑定的 target 名称',
  module: '绑定的 module 名称',
  suite: 'suite 标识',
  case_files: 'Markdown 用例文件列表',
  knowledge_refs: 'suite 级知识库引用',
})

const targetKeys = entries({
  target: 'target 标识',
  source_root: '待测系统源码路径',
  docs: '开发文档路径列表',
  knowledge_refs: 'target 级知识库引用',
  defaults: 'target 默认目录',
  module_dir: 'module 目录',
  helper_dir: 'target helper 目录',
  suite_dir: 'suite 目录',
  generated_dir: 'generated pytest 目录',
  reports_dir: '执行报告目录',
})

const moduleKeys = entries({
  target: '所属 target',
  module: 'module 标识',
  module_type: 'aitest.yaml 声明的能力类型',
  knowledge_refs: 'module 级知识库引用',
  registered_suites: '参与聚合执行的 suite',
  suite: '注册项中的 suite 标识',
  manifest: 'suite manifest 路径',
  status: 'active 或 paused',
})

const taskKeys = entries({
  schema_version: 'task schema 版本',
  name: 'task 名称',
  description: 'task 说明',
  defaults: 'task 默认执行选项',
  include_manual: '是否包含 manual 用例',
  pytest_args: '受支持的 pytest 参数列表',
  env_files: '运行时 env 文件列表',
  units: 'suite 执行单元列表',
  target: 'unit target',
  module: 'unit module',
  suite: 'unit suite',
  suite_file: 'unit suite manifest 路径',
})

const profileKeys = entries({
  profile_scope: 'module 或 suite',
  parent_module: '父 module 标识',
  parent_profile: '父 profile 路径',
  suite: 'suite 标识',
  knowledge_refs: '测试知识引用',
  assertion_rules: 'module 级断言规则',
  structured_assertions: '结构化断言',
  variables: '运行变量声明',
  requests: 'case 请求覆盖',
  case_bodies: '复杂 case 逃生实现',
  case_flows: '结构化多步骤流程',
})

export function completionKeysForPath(path: string): AITestCompletion[] {
  const normalized = path.replaceAll('\\', '/').toLowerCase()
  const name = normalized.split('/').at(-1) ?? ''
  if (name === 'suite.yaml' || name === 'suite.yml') return suiteKeys
  if (name === 'target.yaml' || name === 'target.yml') return targetKeys
  if (name === 'module.yaml' || name === 'module.yml') return moduleKeys
  if (normalized.includes('/tasks/') && (name.endsWith('.yaml') || name.endsWith('.yml'))) return taskKeys
  if (name === 'profile.md' || (name.startsWith('profile_') && name.endsWith('_suite.md'))) return profileKeys
  return []
}

export function isYamlKeyPosition(lineBeforeCursor: string): boolean {
  return /^\s*[A-Za-z_][A-Za-z0-9_-]*$/.test(lineBeforeCursor)
    || /^\s*$/.test(lineBeforeCursor)
}

export function insideSupportedYaml(path: string, documentBeforeCursor: string): boolean {
  if (!path.toLowerCase().endsWith('.md')) return true
  const lines = documentBeforeCursor.split('\n')
  let inside = false
  for (const line of lines) {
    if (/^\s*```(?:yaml|yml)\s*$/i.test(line)) inside = true
    else if (inside && /^\s*```\s*$/.test(line)) inside = false
  }
  return inside
}

function entries(items: Record<string, string>): AITestCompletion[] {
  return Object.entries(items).map(([label, detail]) => ({
    label,
    apply: `${label}: `,
    type: 'property',
    detail,
  }))
}
