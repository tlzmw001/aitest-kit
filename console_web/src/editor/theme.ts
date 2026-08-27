import type * as Monaco from 'monaco-editor/editor/editor.api.js'
import { editorThemeCatalog, resolveEditorTheme, type EditorThemeId } from './themeCatalog'

const registeredRuntimes = new WeakSet<object>()

export function registerEditorThemes(monaco: typeof Monaco): void {
  if (registeredRuntimes.has(monaco)) return
  for (const definition of editorThemeCatalog) {
    const palette = definition.palette
    monaco.editor.defineTheme(definition.id, {
      base: definition.id === 'high-contrast-dark' ? 'hc-black' : 'vs-dark',
      inherit: true,
      colors: {
        'editor.background': palette.background,
        'editor.foreground': palette.foreground,
        'editorGutter.background': palette.gutter,
        'editorLineNumber.foreground': palette.muted,
        'editorLineNumber.activeForeground': palette.foreground,
        'editor.lineHighlightBackground': palette.surface.activeLine,
        'editor.lineHighlightBorder': '#00000000',
        'editor.selectionBackground': palette.selection,
        'editor.inactiveSelectionBackground': withAlpha(palette.selection, '99'),
        'editor.selectionHighlightBackground': withAlpha(palette.selection, '66'),
        'editorCursor.foreground': palette.surface.caret,
        'editorWidget.background': palette.surface.tooltip,
        'editorWidget.border': palette.surface.tooltipBorder,
        'editorSuggestWidget.background': palette.surface.tooltip,
        'editorSuggestWidget.border': palette.surface.tooltipBorder,
        'editorSuggestWidget.selectedBackground': palette.surface.tooltipSelected,
        'editorError.foreground': palette.diagnostic.error,
        'editorWarning.foreground': palette.diagnostic.warning,
      },
      rules: [
        token('keyword', palette.syntax.keyword),
        token('string', palette.syntax.string),
        token('number', palette.syntax.number),
        token('type', palette.syntax.type),
        token('type.identifier', palette.syntax.type),
        token('identifier', palette.syntax.property),
        token('variable', palette.syntax.property),
        token('comment', palette.syntax.comment, 'italic'),
        token('tag', palette.syntax.control),
        token('metatag', palette.syntax.control),
        token('keyword.md', palette.syntax.control),
      ],
    })
  }
  registeredRuntimes.add(monaco)
}

export function applyEditorTheme(monaco: typeof Monaco, themeId: unknown): EditorThemeId {
  registerEditorThemes(monaco)
  const id = resolveEditorTheme(themeId).id
  monaco.editor.setTheme(id)
  return id
}

function token(
  name: string,
  foreground: string,
  fontStyle?: string,
): Monaco.editor.ITokenThemeRule {
  return {
    token: name,
    foreground: foreground.replace('#', ''),
    ...(fontStyle ? { fontStyle } : {}),
  }
}

function withAlpha(color: string, alpha: string): string {
  return color.length === 7 ? `${color}${alpha}` : color
}
