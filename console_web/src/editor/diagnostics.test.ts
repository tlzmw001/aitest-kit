import { EditorState } from '@codemirror/state'
import { describe, expect, it } from 'vitest'
import { positionToOffset, toCodeMirrorDiagnostics } from './diagnostics'

describe('editor diagnostics mapping', () => {
  it('maps one-based backend positions into CodeMirror offsets', () => {
    const state = EditorState.create({ doc: 'first\nsecond\n' })

    expect(positionToOffset(state, 2, 3)).toBe(8)
    expect(toCodeMirrorDiagnostics(state, [{
      severity: 'warning',
      code: 'PROFILE_FIELD_UNKNOWN',
      message: 'unknown field',
      line: 2,
      column: 1,
      end_line: 2,
      end_column: 7,
      source: 'aitest-profile',
    }])[0]).toMatchObject({ from: 6, to: 12, severity: 'warning' })
  })

  it('clamps stale locations to the current document', () => {
    const state = EditorState.create({ doc: 'one line' })

    expect(positionToOffset(state, 99, 99)).toBe(state.doc.length)
  })
})
