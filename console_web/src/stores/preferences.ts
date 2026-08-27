import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import {
  DEFAULT_EDITOR_THEME,
  isEditorThemeId,
  type EditorThemeId,
} from '../editor/themeCatalog'

export type EditorOpenMode = 'tabs' | 'reuse'

const STORAGE_KEY = 'aitest-console-preferences'

interface ConsolePreferences {
  editorOpenMode: EditorOpenMode
  editorTheme: EditorThemeId
}

function loadPreferences(): ConsolePreferences {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') as unknown
    const stored = parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : {}
    return {
      editorOpenMode: stored.editorOpenMode === 'reuse' ? 'reuse' : 'tabs',
      editorTheme: isEditorThemeId(stored.editorTheme) ? stored.editorTheme : DEFAULT_EDITOR_THEME,
    }
  } catch {
    return { editorOpenMode: 'tabs', editorTheme: DEFAULT_EDITOR_THEME }
  }
}

export const usePreferencesStore = defineStore('preferences', () => {
  const stored = loadPreferences()
  const editorOpenMode = ref<EditorOpenMode>(stored.editorOpenMode)
  const editorTheme = ref<EditorThemeId>(stored.editorTheme)

  watch([editorOpenMode, editorTheme], ([openMode, theme]) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      editorOpenMode: openMode,
      editorTheme: theme,
    }))
  })

  return { editorOpenMode, editorTheme }
})
