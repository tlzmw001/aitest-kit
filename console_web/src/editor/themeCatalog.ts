export const EDITOR_THEME_IDS = [
  'aitest-dark',
  'vscode-dark-modern',
  'high-contrast-dark',
] as const

export type EditorThemeId = typeof EDITOR_THEME_IDS[number]

export interface EditorPalette {
  background: string
  gutter: string
  foreground: string
  muted: string
  selection: string
  surface: {
    activeLine: string
    activeGutter: string
    tooltip: string
    tooltipBorder: string
    tooltipSelected: string
    caret: string
  }
  diagnostic: {
    error: string
    warning: string
  }
  syntax: {
    keyword: string
    string: string
    number: string
    function: string
    type: string
    property: string
    comment: string
    control: string
  }
}

export interface EditorThemeDefinition {
  id: EditorThemeId
  label: string
  description: string
  palette: EditorPalette
}

export const DEFAULT_EDITOR_THEME: EditorThemeId = 'aitest-dark'

export const editorThemeCatalog: readonly EditorThemeDefinition[] = [
  {
    id: 'aitest-dark',
    label: 'AITest 深色',
    description: '冷石墨背景和清晰的 IDE 语法色',
    palette: {
      background: '#1e1e1e',
      gutter: '#181818',
      foreground: '#d4d4d4',
      muted: '#858585',
      selection: '#356f9f',
      surface: {
        activeLine: '#292929',
        activeGutter: '#2b2b2b',
        tooltip: '#252526',
        tooltipBorder: '#464647',
        tooltipSelected: '#37373d',
        caret: '#f0f0f0',
      },
      diagnostic: { error: '#f48771', warning: '#cca700' },
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
    },
  },
  {
    id: 'vscode-dark-modern',
    label: 'VS Code Dark Modern',
    description: '熟悉的深灰表面和蓝紫语法关系',
    palette: {
      background: '#1f1f1f',
      gutter: '#181818',
      foreground: '#cccccc',
      muted: '#8c8c8c',
      selection: '#356f9f',
      surface: {
        activeLine: '#282828',
        activeGutter: '#2a2d2e',
        tooltip: '#252526',
        tooltipBorder: '#454545',
        tooltipSelected: '#04395e',
        caret: '#aeafad',
      },
      diagnostic: { error: '#f48771', warning: '#cca700' },
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
    },
  },
  {
    id: 'high-contrast-dark',
    label: '高对比深色',
    description: '更深背景和更亮的正文、行号与注释',
    palette: {
      background: '#0b0d10',
      gutter: '#050607',
      foreground: '#f1f4f8',
      muted: '#b7c0cc',
      selection: '#086faf',
      surface: {
        activeLine: '#15191f',
        activeGutter: '#1b2028',
        tooltip: '#11151a',
        tooltipBorder: '#59636f',
        tooltipSelected: '#243044',
        caret: '#ffffff',
      },
      diagnostic: { error: '#ff7b72', warning: '#f2cc60' },
      syntax: {
        keyword: '#ffa7f3',
        string: '#f7b58d',
        number: '#c7e9b0',
        function: '#ffef9f',
        type: '#77e6c3',
        property: '#a7d8ff',
        comment: '#91d18b',
        control: '#79c0ff',
      },
    },
  },
]

export function isEditorThemeId(value: unknown): value is EditorThemeId {
  return typeof value === 'string' && EDITOR_THEME_IDS.some((id) => id === value)
}

export function resolveEditorTheme(value: unknown): EditorThemeDefinition {
  const id = isEditorThemeId(value) ? value : DEFAULT_EDITOR_THEME
  return editorThemeCatalog.find((theme) => theme.id === id) ?? editorThemeCatalog[0]
}

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
