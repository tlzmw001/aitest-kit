import type { Diagnostic as CodeMirrorDiagnostic } from '@codemirror/lint'
import type { EditorState } from '@codemirror/state'
import type { EditorDiagnostic } from '../types'

export function toCodeMirrorDiagnostics(
  state: EditorState,
  diagnostics: EditorDiagnostic[],
): CodeMirrorDiagnostic[] {
  return diagnostics.map((item) => {
    const from = positionToOffset(state, item.line, item.column)
    const to = Math.max(from + 1, positionToOffset(state, item.end_line, item.end_column))
    return {
      from,
      to: Math.min(to, state.doc.length),
      severity: item.severity,
      message: item.message,
      source: `${item.source} · ${item.code}`,
    }
  })
}

export function positionToOffset(state: EditorState, lineNumber: number, column: number): number {
  const safeLine = Math.max(1, Math.min(lineNumber, state.doc.lines))
  const line = state.doc.line(safeLine)
  return Math.min(line.to, line.from + Math.max(0, column - 1))
}
