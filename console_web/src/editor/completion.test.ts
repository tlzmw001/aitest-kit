import { describe, expect, it } from 'vitest'
import {
  completionKeysForPath,
  insideSupportedYaml,
  isYamlKeyPosition,
} from './completion'

describe('AITest editor completions', () => {
  it('offers suite manifest fields without inventing business values', () => {
    const keys = completionKeysForPath('test_workspace/suites/demo/smoke/suite.yaml')

    expect(keys.map((item) => item.label)).toEqual(expect.arrayContaining([
      'target',
      'module',
      'suite',
      'case_files',
    ]))
    expect(keys.some((item) => item.apply.includes('demo'))).toBe(false)
  })

  it('recognizes YAML key positions but not value positions', () => {
    expect(isYamlKeyPosition('  case_f')).toBe(true)
    expect(isYamlKeyPosition('target: demo')).toBe(false)
    expect(isYamlKeyPosition('  - business.md')).toBe(false)
  })

  it('offers profile keys only for profile Markdown', () => {
    expect(completionKeysForPath('modules/orders/profile.md').map((item) => item.label)).toContain('case_flows')
    expect(completionKeysForPath('suites/orders/business.md')).toEqual([])
  })

  it('limits profile suggestions to an open YAML fence', () => {
    const path = 'modules/orders/profile.md'

    expect(insideSupportedYaml(path, '# Profile\n\n```yaml\ncase_f')).toBe(true)
    expect(insideSupportedYaml(path, '# Profile\n\n```yaml\ncase_flows:\n```\n')).toBe(false)
    expect(insideSupportedYaml(path, '# Profile\n\ncase_f')).toBe(false)
    expect(insideSupportedYaml('suites/orders/suite.yaml', 'case_f')).toBe(true)
  })
})
