import { MarkerSeverity, type editor } from 'monaco-editor/editor/editor.api.js'
import type { EditorDiagnostic } from '../types'

interface PositionModel {
  getLineCount(): number
  getLineMaxColumn(lineNumber: number): number
}

export function toMonacoMarkers(
  model: PositionModel,
  diagnostics: EditorDiagnostic[],
): editor.IMarkerData[] {
  return diagnostics.map((item) => {
    let start = clampPosition(model, item.line, item.column)
    let end = clampPosition(model, item.end_line, item.end_column)
    if (positionOrder(end, start) <= 0) {
      const maxColumn = model.getLineMaxColumn(start.lineNumber)
      if (start.column < maxColumn) end = { lineNumber: start.lineNumber, column: start.column + 1 }
      else if (start.column > 1) {
        start = { lineNumber: start.lineNumber, column: start.column - 1 }
        end = { lineNumber: start.lineNumber, column: start.column + 1 }
      }
    }
    return {
      startLineNumber: start.lineNumber,
      startColumn: start.column,
      endLineNumber: end.lineNumber,
      endColumn: end.column,
      severity: item.severity === 'error' ? MarkerSeverity.Error : MarkerSeverity.Warning,
      message: item.message,
      source: `${item.source} · ${item.code}`,
      code: item.code,
    }
  })
}

export function clampPosition(model: PositionModel, lineNumber: number, column: number) {
  const safeLine = Math.max(1, Math.min(lineNumber, model.getLineCount()))
  const safeColumn = Math.max(1, Math.min(column, model.getLineMaxColumn(safeLine)))
  return { lineNumber: safeLine, column: safeColumn }
}

function positionOrder(
  left: { lineNumber: number; column: number },
  right: { lineNumber: number; column: number },
): number {
  return left.lineNumber === right.lineNumber
    ? left.column - right.column
    : left.lineNumber - right.lineNumber
}
