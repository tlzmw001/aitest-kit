export type DisplayOwner = 'CONFIG' | 'CASE' | 'SCAFFOLD' | 'ENV' | 'REVIEW' | 'SUT' | 'CLEANUP' | 'UNKNOWN'

const CONFIG_CODES = ['CONFIG', 'PROFILE', 'REGISTRY', 'SUITE_CONTEXT']

export function displayOwner(raw: string): DisplayOwner {
  const value = raw.toUpperCase()
  if (value === 'PRECONDITION_MISSING' || value === 'ENVIRONMENT_ERROR') return 'ENV'
  if (value === 'TEST_SCAFFOLD_ERROR' || value === 'CODEGEN_ERROR') return 'SCAFFOLD'
  if (value === 'ASSERTION_FAILURE') return 'REVIEW'
  if (value === 'TEARDOWN_ERROR') return 'CLEANUP'
  if (value === 'SUT_ERROR' || value === 'SUT_CONFIRMED') return 'SUT'
  if (value === 'CASE_ERROR' || value === 'PARSER_ERROR') return 'CASE'
  if (CONFIG_CODES.some((marker) => value.includes(marker)) || /^E[567]\d\d/.test(value)) return 'CONFIG'
  return 'UNKNOWN'
}

export function ownerLabel(owner: DisplayOwner): string {
  return {
    CONFIG: '配置',
    CASE: '用例',
    SCAFFOLD: '脚手架',
    ENV: '环境',
    REVIEW: '待确认',
    SUT: '待测系统',
    CLEANUP: '清理',
    UNKNOWN: '未分类',
  }[owner]
}
