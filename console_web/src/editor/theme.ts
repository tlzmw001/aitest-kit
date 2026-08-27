import { HighlightStyle, syntaxHighlighting } from '@codemirror/language'
import type { Extension } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { tags } from '@lezer/highlight'

export const editorPalette = {
  background: '#1e1e1e',
  gutter: '#181818',
  foreground: '#d4d4d4',
  muted: '#858585',
  selection: '#264f78',
  syntax: {
    keyword: '#c586c0',
    string: '#ce9178',
    number: '#b5cea8',
    function: '#dcdcaa',
    type: '#4ec9b0',
    property: '#9cdcfe',
    comment: '#6a9955',
    control: '#569cd6',
  },
} as const

const highlightStyle = HighlightStyle.define([
  { tag: [tags.keyword, tags.operatorKeyword, tags.modifier, tags.controlKeyword], color: editorPalette.syntax.keyword },
  { tag: [tags.string, tags.special(tags.string), tags.regexp, tags.character], color: editorPalette.syntax.string },
  { tag: [tags.number, tags.bool, tags.null], color: editorPalette.syntax.number },
  { tag: [tags.function(tags.variableName), tags.function(tags.propertyName), tags.labelName], color: editorPalette.syntax.function },
  { tag: [tags.typeName, tags.className, tags.namespace], color: editorPalette.syntax.type },
  { tag: [tags.propertyName, tags.attributeName, tags.variableName, tags.definition(tags.variableName)], color: editorPalette.syntax.property },
  { tag: [tags.comment, tags.lineComment, tags.blockComment, tags.docComment], color: editorPalette.syntax.comment, fontStyle: 'italic' },
  { tag: [tags.link, tags.url, tags.heading, tags.meta, tags.atom], color: editorPalette.syntax.control },
  { tag: [tags.emphasis], fontStyle: 'italic' },
  { tag: [tags.strong], fontWeight: '700' },
  { tag: [tags.invalid], color: '#f48771', textDecoration: 'underline wavy #f48771' },
])

const surfaceTheme = EditorView.theme({
  '&': { height: '100%', backgroundColor: editorPalette.background, color: editorPalette.foreground },
  '.cm-scroller': { fontFamily: 'var(--mono)', fontSize: '13px', lineHeight: '1.6' },
  '.cm-content': { padding: '11px 0 44px', caretColor: '#f0f0f0' },
  '.cm-line': { padding: '0 16px 0 9px' },
  '.cm-gutters': {
    backgroundColor: editorPalette.gutter,
    color: editorPalette.muted,
    borderRight: '1px solid rgb(255 255 255 / 7.5%)',
  },
  '.cm-lineNumbers .cm-gutterElement': { padding: '0 12px 0 10px' },
  '.cm-activeLine': { backgroundColor: 'rgb(255 255 255 / 4%)' },
  '.cm-activeLineGutter': { backgroundColor: 'rgb(255 255 255 / 5%)', color: '#c6c6c6' },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': { backgroundColor: `${editorPalette.selection} !important` },
  '.cm-cursor, .cm-dropCursor': { borderLeftColor: '#f0f0f0' },
  '.cm-matchingBracket': { backgroundColor: '#0e639c66', outline: '1px solid #8f8f8f' },
  '.cm-tooltip': {
    backgroundColor: '#252526',
    border: '1px solid rgb(255 255 255 / 12%)',
    borderRadius: '6px',
    color: '#d4d4d4',
    boxShadow: '0 10px 28px rgb(0 0 0 / 28%)',
    overflow: 'hidden',
  },
  '.cm-tooltip-autocomplete > ul > li': { minHeight: '26px', padding: '3px 9px' },
  '.cm-tooltip-autocomplete > ul > li[aria-selected]': { backgroundColor: '#37373d', color: '#f0f0f0' },
  '.cm-completionLabel': { color: '#d4d4d4' },
  '.cm-completionDetail': { color: '#9d9d9d', fontStyle: 'normal' },
  '.cm-diagnostic': { padding: '6px 9px' },
  '.cm-diagnosticText': { color: '#d4d4d4' },
  '.cm-lintRange-error': { backgroundImage: 'none', textDecoration: 'underline wavy #f48771 1px' },
  '.cm-lintRange-warning': { backgroundImage: 'none', textDecoration: 'underline wavy #cca700 1px' },
  '&.cm-focused': { outline: 'none' },
}, { dark: true })

export const aitestEditorTheme: Extension = [surfaceTheme, syntaxHighlighting(highlightStyle)]

export function relativeContrast(foreground: string, background: string): number {
  const brighter = Math.max(relativeLuminance(foreground), relativeLuminance(background))
  const darker = Math.min(relativeLuminance(foreground), relativeLuminance(background))
  return (brighter + 0.05) / (darker + 0.05)
}

function relativeLuminance(hex: string): number {
  const channels = hex.replace('#', '').match(/.{2}/g)?.map((part) => Number.parseInt(part, 16) / 255) ?? []
  const [red = 0, green = 0, blue = 0] = channels.map((value) => (
    value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  ))
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue
}
