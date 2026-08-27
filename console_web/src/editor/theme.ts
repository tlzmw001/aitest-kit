import { HighlightStyle, syntaxHighlighting } from '@codemirror/language'
import type { Extension } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { tags } from '@lezer/highlight'
import { resolveEditorTheme, type EditorPalette, type EditorThemeId } from './themeCatalog'

const extensionCache = new Map<EditorThemeId, Extension>()

function createEditorTheme(palette: EditorPalette): Extension {
  const highlightStyle = HighlightStyle.define([
    { tag: [tags.keyword, tags.operatorKeyword, tags.modifier, tags.controlKeyword], color: palette.syntax.keyword },
    { tag: [tags.string, tags.special(tags.string), tags.regexp, tags.character], color: palette.syntax.string },
    { tag: [tags.number, tags.bool, tags.null], color: palette.syntax.number },
    { tag: [tags.function(tags.variableName), tags.function(tags.propertyName), tags.labelName], color: palette.syntax.function },
    { tag: [tags.typeName, tags.className, tags.namespace], color: palette.syntax.type },
    { tag: [tags.propertyName, tags.attributeName, tags.variableName, tags.definition(tags.variableName)], color: palette.syntax.property },
    { tag: [tags.comment, tags.lineComment, tags.blockComment, tags.docComment], color: palette.syntax.comment, fontStyle: 'italic' },
    { tag: [tags.link, tags.url, tags.heading, tags.meta, tags.atom], color: palette.syntax.control },
    { tag: [tags.emphasis], fontStyle: 'italic' },
    { tag: [tags.strong], fontWeight: '700' },
    {
      tag: [tags.invalid],
      color: palette.diagnostic.error,
      textDecoration: `underline wavy ${palette.diagnostic.error}`,
    },
  ])

  const surfaceTheme = EditorView.theme({
    '&': { height: '100%', backgroundColor: palette.background, color: palette.foreground },
    '.cm-scroller': { fontFamily: 'var(--mono)', fontSize: '13px', lineHeight: '1.6' },
    '.cm-content': { padding: '11px 0 44px', caretColor: palette.surface.caret },
    '.cm-line': { padding: '0 16px 0 9px' },
    '.cm-gutters': {
      backgroundColor: palette.gutter,
      color: palette.muted,
      borderRight: '1px solid rgb(255 255 255 / 7.5%)',
    },
    '.cm-lineNumbers .cm-gutterElement': { padding: '0 12px 0 10px' },
    '.cm-activeLine': { backgroundColor: palette.surface.activeLine },
    '.cm-activeLineGutter': { backgroundColor: palette.surface.activeGutter, color: palette.foreground },
    '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': { backgroundColor: `${palette.selection} !important` },
    '.cm-cursor, .cm-dropCursor': { borderLeftColor: palette.surface.caret },
    '.cm-matchingBracket': { backgroundColor: '#0e639c66', outline: '1px solid #8f8f8f' },
    '.cm-tooltip': {
      backgroundColor: palette.surface.tooltip,
      border: `1px solid ${palette.surface.tooltipBorder}`,
      borderRadius: '6px',
      color: palette.foreground,
      boxShadow: '0 10px 28px rgb(0 0 0 / 28%)',
      overflow: 'hidden',
    },
    '.cm-tooltip-autocomplete > ul > li': { minHeight: '26px', padding: '3px 9px' },
    '.cm-tooltip-autocomplete > ul > li[aria-selected]': { backgroundColor: palette.surface.tooltipSelected, color: palette.foreground },
    '.cm-completionLabel': { color: palette.foreground },
    '.cm-completionDetail': { color: palette.muted, fontStyle: 'normal' },
    '.cm-diagnostic': { padding: '6px 9px' },
    '.cm-diagnosticText': { color: palette.foreground },
    '.cm-lintRange-error': { backgroundImage: 'none', textDecoration: `underline wavy ${palette.diagnostic.error} 1px` },
    '.cm-lintRange-warning': { backgroundImage: 'none', textDecoration: `underline wavy ${palette.diagnostic.warning} 1px` },
    '&.cm-focused': { outline: 'none' },
  }, { dark: true })

  return [surfaceTheme, syntaxHighlighting(highlightStyle)]
}

export function editorThemeExtension(themeId: unknown): Extension {
  const definition = resolveEditorTheme(themeId)
  const cached = extensionCache.get(definition.id)
  if (cached) return cached
  const extension = createEditorTheme(definition.palette)
  extensionCache.set(definition.id, extension)
  return extension
}
