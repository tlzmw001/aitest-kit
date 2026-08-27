import { describe, expect, it } from 'vitest'
import { editorPalette, relativeContrast } from './theme'

describe('editor theme', () => {
  it('keeps every syntax foreground above the WCAG AA contrast threshold', () => {
    for (const [role, color] of Object.entries(editorPalette.syntax)) {
      expect(relativeContrast(color, editorPalette.background), role).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('does not reuse the selection blue as a syntax foreground', () => {
    expect(Object.values(editorPalette.syntax)).not.toContain(editorPalette.selection)
  })
})
