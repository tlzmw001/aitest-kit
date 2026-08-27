<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { autocompletion } from '@codemirror/autocomplete'
import { basicSetup } from 'codemirror'
import { lintGutter, setDiagnostics } from '@codemirror/lint'
import { Compartment, EditorState, type Extension } from '@codemirror/state'
import { EditorView, keymap } from '@codemirror/view'
import { aitestCompletionSource } from '../editor/completion'
import { positionToOffset, toCodeMirrorDiagnostics } from '../editor/diagnostics'
import { editorThemeExtension } from '../editor/theme'
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
let view: EditorView | null = null
let editorGeneration = 0
const themeCompartment = new Compartment()

async function languageExtension(): Promise<Extension> {
  if (props.language === 'markdown') return (await import('@codemirror/lang-markdown')).markdown()
  if (props.language === 'yaml') return (await import('@codemirror/lang-yaml')).yaml()
  if (props.language === 'python') return (await import('@codemirror/lang-python')).python()
  return []
}

async function createEditor(): Promise<void> {
  const generation = ++editorGeneration
  const syntax = await languageExtension()
  if (!host.value || generation !== editorGeneration) return
  view?.destroy()
  view = new EditorView({
    parent: host.value,
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        basicSetup,
        syntax,
        themeCompartment.of(editorThemeExtension(props.theme)),
        autocompletion({ override: [aitestCompletionSource(props.path)] }),
        lintGutter(),
        EditorView.editable.of(!props.readOnly),
        EditorState.readOnly.of(props.readOnly),
        keymap.of([{ key: 'Mod-s', run: () => (emit('save'), true) }]),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) emit('update:modelValue', update.state.doc.toString())
        }),
      ],
    }),
  })
  syncDiagnostics()
}

function syncDiagnostics(): void {
  if (!view) return
  view.dispatch(setDiagnostics(view.state, toCodeMirrorDiagnostics(view.state, props.diagnostics)))
}

function focusDiagnostic(diagnostic: EditorDiagnostic): void {
  if (!view) return
  const anchor = positionToOffset(view.state, diagnostic.line, diagnostic.column)
  view.dispatch({ selection: { anchor }, scrollIntoView: true })
  view.focus()
}

onMounted(() => void createEditor())
onBeforeUnmount(() => {
  editorGeneration += 1
  view?.destroy()
})

watch(() => [props.path, props.language, props.readOnly], () => void createEditor())
watch(() => props.theme, (theme) => {
  if (!view) return
  view.dispatch({ effects: themeCompartment.reconfigure(editorThemeExtension(theme)) })
})
watch(() => props.modelValue, (value) => {
  if (!view || view.state.doc.toString() === value) return
  view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } })
})
watch(() => props.diagnostics, syncDiagnostics, { deep: true })

defineExpose({ focusDiagnostic })
</script>

<template><div ref="host" class="code-editor" /></template>
