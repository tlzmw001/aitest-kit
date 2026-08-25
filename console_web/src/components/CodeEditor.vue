<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { basicSetup } from 'codemirror'
import { EditorState, type Extension } from '@codemirror/state'
import { EditorView, keymap } from '@codemirror/view'

const props = withDefaults(defineProps<{ modelValue: string; language?: string; readOnly?: boolean }>(), {
  language: 'text',
  readOnly: false,
})
const emit = defineEmits<{ 'update:modelValue': [value: string]; save: [] }>()
const host = ref<HTMLElement | null>(null)
let view: EditorView | null = null

async function languageExtension(): Promise<Extension> {
  if (props.language === 'markdown') return (await import('@codemirror/lang-markdown')).markdown()
  if (props.language === 'yaml') return (await import('@codemirror/lang-yaml')).yaml()
  if (props.language === 'python') return (await import('@codemirror/lang-python')).python()
  return []
}

async function createEditor(): Promise<void> {
  const syntax = await languageExtension()
  if (!host.value) return
  view?.destroy()
  view = new EditorView({
    parent: host.value,
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        basicSetup,
        syntax,
        EditorView.editable.of(!props.readOnly),
        EditorState.readOnly.of(props.readOnly),
        keymap.of([{ key: 'Mod-s', run: () => (emit('save'), true) }]),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) emit('update:modelValue', update.state.doc.toString())
        }),
        EditorView.theme({
          '&': { height: '100%', backgroundColor: 'transparent', color: 'var(--text)' },
          '.cm-scroller': { fontFamily: 'var(--mono)', fontSize: '12px', lineHeight: '1.72' },
          '.cm-content': { padding: '12px 0 40px', caretColor: 'var(--signal)' },
          '.cm-gutters': { backgroundColor: 'transparent', color: 'var(--muted-2)', border: '0' },
          '.cm-activeLine, .cm-activeLineGutter': { backgroundColor: 'color-mix(in oklch, var(--signal) 7%, transparent)' },
          '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': { backgroundColor: 'var(--selection)' },
          '&.cm-focused': { outline: 'none' },
        }, { dark: true }),
      ],
    }),
  })
}

onMounted(() => void createEditor())
onBeforeUnmount(() => view?.destroy())

watch(() => [props.language, props.readOnly], () => void createEditor())
watch(() => props.modelValue, (value) => {
  if (!view || view.state.doc.toString() === value) return
  view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } })
})
</script>

<template><div ref="host" class="code-editor" /></template>
