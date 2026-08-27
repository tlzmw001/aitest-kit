import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

export type EditorOpenMode = 'tabs' | 'reuse'

const STORAGE_KEY = 'aitest-console-preferences'

function loadEditorOpenMode(): EditorOpenMode {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') as { editorOpenMode?: unknown }
    return stored.editorOpenMode === 'reuse' ? 'reuse' : 'tabs'
  } catch {
    return 'tabs'
  }
}

export const usePreferencesStore = defineStore('preferences', () => {
  const editorOpenMode = ref<EditorOpenMode>(loadEditorOpenMode())

  watch(editorOpenMode, (value) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ editorOpenMode: value }))
  })

  return { editorOpenMode }
})
