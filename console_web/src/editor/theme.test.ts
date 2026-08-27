import { describe, expect, it } from 'vitest'
import {
  DEFAULT_EDITOR_THEME,
  editorThemeCatalog,
  relativeContrast,
  resolveEditorTheme,
} from './themeCatalog'

describe('editor theme', () => {
  it('publishes the three approved presets in a stable order', () => {
    expect(editorThemeCatalog.map((theme) => theme.id)).toEqual([
      'aitest-dark',
      'vscode-dark-modern',
      'high-contrast-dark',
    ])
  })

  it('keeps every syntax foreground above the WCAG AA contrast threshold', () => {
    for (const theme of editorThemeCatalog) {
      for (const [role, color] of Object.entries(theme.palette.syntax)) {
        expect(relativeContrast(color, theme.palette.background), `${theme.id}:${role}`).toBeGreaterThanOrEqual(4.5)
      }
    }
  })

  it('does not reuse the selection blue as a syntax foreground', () => {
    for (const theme of editorThemeCatalog) {
      expect(Object.values(theme.palette.syntax)).not.toContain(theme.palette.selection)
    }
  })

  it('falls back to the default theme for an unknown id', () => {
    expect(resolveEditorTheme('unknown-theme').id).toBe(DEFAULT_EDITOR_THEME)
  })
})
