<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { editor, IDisposable } from 'monaco-editor/editor/editor.api.js'
import {
  completionKeysForPath,
  insideSupportedYaml,
  isYamlKeyPosition,
} from '../editor/completion'
import { clampPosition, toMonacoMarkers } from '../editor/diagnostics'
import { monaco, nextEditorAuthority } from '../editor/monacoEnvironment'
import { applyEditorTheme } from '../editor/theme'
import { DEFAULT_EDITOR_THEME, type EditorThemeId } from '../editor/themeCatalog'
import type { EditorDiagnostic } from '../types'

const props = withDefaults(defineProps<{
  modelValue: string
  path?: string
  language?: string
  readOnly?: boolean
  diagnostics?: EditorDiagnostic[]
  theme?: EditorThemeId
}>(), {
  path: '',
  language: 'text',
  readOnly: false,
  diagnostics: () => [],
  theme: DEFAULT_EDITOR_THEME,
})
const emit = defineEmits<{ 'update:modelValue': [value: string]; save: [] }>()
const host = ref<HTMLElement | null>(null)
const instanceAuthority = nextEditorAuthority()
const models = new Map<string, editor.ITextModel>()
const viewStates = new Map<string, editor.ICodeEditorViewState>()
const disposables: IDisposable[] = []
let codeEditor: editor.IStandaloneCodeEditor | null = null
let contentListener: IDisposable | null = null
let activeKey = ''
let applyingExternalValue = false

function createEditor(): void {
  if (!host.value) return
  applyEditorTheme(monaco, props.theme)
  codeEditor = monaco.editor.create(host.value, {
    model: null,
    automaticLayout: true,
    readOnly: props.readOnly,
    minimap: { enabled: false },
    glyphMargin: true,
    lineNumbers: 'on',
    folding: true,
    scrollBeyondLastLine: false,
    renderWhitespace: 'selection',
    fontFamily: 'SFMono-Regular, Cascadia Code, Menlo, Monaco, monospace',
    fontSize: 13,
    lineHeight: 21,
    padding: { top: 11, bottom: 44 },
    roundedSelection: false,
    overviewRulerBorder: false,
    fixedOverflowWidgets: true,
  })
  codeEditor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => emit('save'))
  registerCompletionProviders()
  switchDocument()
}

function switchDocument(): void {
  if (!codeEditor) return
  const key = documentKey(props.path)
  const language = languageId(props.language)
  if (activeKey === key) {
    const activeModel = codeEditor.getModel()
    if (activeModel) {
      monaco.editor.setModelLanguage(activeModel, language)
      setModelValue(activeModel, props.modelValue)
      syncDiagnostics()
    }
    return
  }
  if (activeKey) {
    const viewState = codeEditor.saveViewState()
    if (viewState) viewStates.set(activeKey, viewState)
  }
  contentListener?.dispose()

  let model = models.get(key)
  if (!model) {
    model = monaco.editor.createModel(props.modelValue, language, documentUri(props.path))
    models.set(key, model)
  } else {
    monaco.editor.setModelLanguage(model, language)
    setModelValue(model, props.modelValue)
  }

  activeKey = key
  codeEditor.setModel(model)
  const viewState = viewStates.get(key)
  if (viewState) codeEditor.restoreViewState(viewState)
  contentListener = model.onDidChangeContent(() => {
    if (!applyingExternalValue) emit('update:modelValue', model?.getValue() ?? '')
  })
  syncDiagnostics()
}

function registerCompletionProviders(): void {
  for (const language of ['yaml', 'markdown']) {
    disposables.push(monaco.languages.registerCompletionItemProvider(language, {
      provideCompletionItems(model, position, context) {
        if (model.uri.authority !== instanceAuthority) return undefined
        const path = model.uri.path.replace(/^\//, '')
        const options = completionKeysForPath(path)
        if (!options.length) return undefined
        const lineBeforeCursor = model.getLineContent(position.lineNumber).slice(0, position.column - 1)
        const documentBeforeCursor = model.getValueInRange({
          startLineNumber: 1,
          startColumn: 1,
          endLineNumber: position.lineNumber,
          endColumn: position.column,
        })
        if (!isYamlKeyPosition(lineBeforeCursor) || !insideSupportedYaml(path, documentBeforeCursor)) return undefined
        const word = lineBeforeCursor.match(/[A-Za-z_][A-Za-z0-9_-]*$/)?.[0] ?? ''
        if (!word && context.triggerKind !== monaco.languages.CompletionTriggerKind.Invoke) return undefined
        const range = {
          startLineNumber: position.lineNumber,
          startColumn: position.column - word.length,
          endLineNumber: position.lineNumber,
          endColumn: position.column,
        }
        return {
          suggestions: options.map((option) => ({
            label: option.label,
            detail: option.detail,
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: option.apply,
            range,
          })),
        }
      },
    }))
  }
}

function syncDiagnostics(): void {
  const model = codeEditor?.getModel()
  if (!model) return
  monaco.editor.setModelMarkers(model, 'aitest', toMonacoMarkers(model, props.diagnostics))
}

function focusDiagnostic(diagnostic: EditorDiagnostic): void {
  const model = codeEditor?.getModel()
  if (!codeEditor || !model) return
  const position = clampPosition(model, diagnostic.line, diagnostic.column)
  codeEditor.setPosition(position)
  codeEditor.revealPositionInCenter(position)
  codeEditor.focus()
}

function setModelValue(model: editor.ITextModel, value: string): void {
  if (model.getValue() === value) return
  applyingExternalValue = true
  try {
    model.setValue(value)
  } finally {
    applyingExternalValue = false
  }
}

function languageId(language: string): string {
  if (language === 'markdown' || language === 'yaml' || language === 'python') return language
  return 'plaintext'
}

function documentKey(path: string): string {
  return path.replaceAll('\\', '/') || '__untitled__'
}

function documentUri(path: string) {
  const normalized = path.replaceAll('\\', '/') || 'untitled.env'
  return monaco.Uri.from({
    scheme: 'aitest',
    authority: instanceAuthority,
    path: normalized.startsWith('/') ? normalized : `/${normalized}`,
  })
}

onMounted(createEditor)
onBeforeUnmount(() => {
  contentListener?.dispose()
  for (const disposable of disposables) disposable.dispose()
  codeEditor?.dispose()
  for (const model of models.values()) {
    monaco.editor.setModelMarkers(model, 'aitest', [])
    model.dispose()
  }
  models.clear()
  viewStates.clear()
})

watch(() => [props.path, props.language], switchDocument)
watch(() => props.readOnly, (readOnly) => codeEditor?.updateOptions({ readOnly }))
watch(() => props.theme, (theme) => applyEditorTheme(monaco, theme))
watch(() => props.modelValue, (value) => {
  if (activeKey !== documentKey(props.path)) return
  const model = codeEditor?.getModel()
  if (model) setModelValue(model, value)
})
watch(() => props.diagnostics, syncDiagnostics, { deep: true })

defineExpose({ focusDiagnostic })
</script>

<template><div ref="host" class="code-editor monaco-host" /></template>
