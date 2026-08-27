<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { editor } from 'monaco-editor/editor/editor.api.js'
import { monaco, nextEditorAuthority } from '../editor/monacoEnvironment'
import { applyEditorTheme } from '../editor/theme'
import { DEFAULT_EDITOR_THEME, type EditorThemeId } from '../editor/themeCatalog'

const props = withDefaults(defineProps<{
  original: string
  modified: string
  path?: string
  language?: string
  theme?: EditorThemeId
}>(), {
  path: 'conflict.txt',
  language: 'text',
  theme: DEFAULT_EDITOR_THEME,
})

const host = ref<HTMLElement | null>(null)
const authority = nextEditorAuthority()
let diffEditor: editor.IStandaloneDiffEditor | null = null
let originalModel: editor.ITextModel | null = null
let modifiedModel: editor.ITextModel | null = null

function createEditor(): void {
  if (!host.value) return
  applyEditorTheme(monaco, props.theme)
  diffEditor = monaco.editor.createDiffEditor(host.value, {
    automaticLayout: true,
    readOnly: true,
    originalEditable: false,
    minimap: { enabled: false },
    renderSideBySide: true,
    useInlineViewWhenSpaceIsLimited: true,
    renderOverviewRuler: false,
    overviewRulerLanes: 0,
    scrollBeyondLastLine: false,
    fontFamily: 'SFMono-Regular, Cascadia Code, Menlo, Monaco, monospace',
    fontSize: 12,
    lineHeight: 20,
    fixedOverflowWidgets: true,
  })
  replaceModels()
}

function replaceModels(): void {
  if (!diffEditor) return
  disposeModels()
  const language = languageId(props.language)
  originalModel = monaco.editor.createModel(
    props.original,
    language,
    documentUri('disk'),
  )
  modifiedModel = monaco.editor.createModel(
    props.modified,
    language,
    documentUri('local'),
  )
  diffEditor.setModel({ original: originalModel, modified: modifiedModel })
}

function syncContent(): void {
  setModelValue(originalModel, props.original)
  setModelValue(modifiedModel, props.modified)
}

function setModelValue(model: editor.ITextModel | null, value: string): void {
  if (model && model.getValue() !== value) model.setValue(value)
}

function disposeModels(): void {
  diffEditor?.setModel(null)
  originalModel?.dispose()
  modifiedModel?.dispose()
  originalModel = null
  modifiedModel = null
}

function languageId(language: string): string {
  if (['json', 'markdown', 'yaml', 'python'].includes(language)) return language
  return 'plaintext'
}

function documentUri(side: 'disk' | 'local') {
  const normalized = props.path.replaceAll('\\', '/') || 'conflict.txt'
  return monaco.Uri.from({
    scheme: 'aitest-diff',
    authority,
    path: `/${side}/${normalized.replace(/^\/+/, '')}`,
  })
}

onMounted(createEditor)
onBeforeUnmount(() => {
  diffEditor?.dispose()
  diffEditor = null
  disposeModels()
})

watch(() => [props.path, props.language], replaceModels)
watch(() => [props.original, props.modified], syncContent)
watch(() => props.theme, (theme) => applyEditorTheme(monaco, theme))
</script>

<template><div ref="host" class="diff-editor monaco-host" /></template>
