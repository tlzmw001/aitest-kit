import { MarkerSeverity } from 'monaco-editor/editor/editor.api.js'
import { describe, expect, it } from 'vitest'
import { toMonacoMarkers } from './diagnostics'

function textModel(lines: string[]) {
  return {
    getLineCount: () => lines.length,
    getLineMaxColumn: (lineNumber: number) => (lines[lineNumber - 1]?.length ?? 0) + 1,
  }
}

describe('editor diagnostics mapping', () => {
  it('maps one-based backend positions into Monaco markers', () => {
    const markers = toMonacoMarkers(textModel(['first', 'second']), [{
      severity: 'warning',
      code: 'PROFILE_FIELD_UNKNOWN',
      message: 'unknown field',
      line: 2,
      column: 1,
      end_line: 2,
      end_column: 7,
      source: 'aitest-profile',
    }])

    expect(markers[0]).toMatchObject({
      startLineNumber: 2,
      startColumn: 1,
      endLineNumber: 2,
      endColumn: 7,
      severity: MarkerSeverity.Warning,
      source: 'aitest-profile · PROFILE_FIELD_UNKNOWN',
    })
  })

  it('clamps stale locations to the current document', () => {
    const [marker] = toMonacoMarkers(textModel(['one line']), [{
      severity: 'error',
      code: 'STALE',
      message: 'stale range',
      line: 99,
      column: 99,
      end_line: 99,
      end_column: 99,
      source: 'aitest',
    }])

    expect(marker).toMatchObject({
      startLineNumber: 1,
      startColumn: 8,
      endLineNumber: 1,
      endColumn: 9,
      severity: MarkerSeverity.Error,
    })
  })
})
