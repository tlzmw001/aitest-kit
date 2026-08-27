import { readFileSync } from 'node:fs'
import { describe, expect, it, vi } from 'vitest'
import {
  DEFAULT_EDITOR_THEME,
  editorThemeCatalog,
  relativeContrast,
  resolveEditorTheme,
} from './themeCatalog'
import { applyEditorTheme, registerEditorThemes } from './theme'

const editorChromeStyles = readFileSync('src/styles/views.css', 'utf8')

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

  it('keeps text selections visibly distinct from the editor background', () => {
    for (const theme of editorThemeCatalog) {
      expect(
        relativeContrast(theme.palette.selection, theme.palette.background),
        `${theme.id}:selection`,
      ).toBeGreaterThanOrEqual(3)
    }
  })

  it('limits the tab close hover fill to a compact rounded surface', () => {
    expect(editorChromeStyles).toMatch(
      /\.tab-close::before\s*\{[^}]*width:\s*22px;[^}]*height:\s*22px;[^}]*border-radius:\s*var\(--r1\)/s,
    )
    expect(editorChromeStyles).toMatch(/\.tab-close\s*\{[^}]*background:\s*transparent\s*!important/s)
    expect(editorChromeStyles).toMatch(/\.tab-close:hover\s*\{[^}]*background:\s*transparent\s*!important/s)
  })

  it('registers all presets as Monaco themes and applies the safe fallback', () => {
    const defineTheme = vi.fn()
    const setTheme = vi.fn()
    const runtime = { editor: { defineTheme, setTheme } } as never

    registerEditorThemes(runtime)
    applyEditorTheme(runtime, 'unknown-theme')

    expect(defineTheme.mock.calls.map(([id]) => id)).toEqual([
      'aitest-dark',
      'vscode-dark-modern',
      'high-contrast-dark',
    ])
    expect(setTheme).toHaveBeenCalledWith(DEFAULT_EDITOR_THEME)
  })

  it('falls back to the default theme for an unknown id', () => {
    expect(resolveEditorTheme('unknown-theme').id).toBe(DEFAULT_EDITOR_THEME)
  })
})
