import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { usePreferencesStore } from './preferences'

describe('preferences store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('uses stable defaults when no preferences were stored', () => {
    const preferences = usePreferencesStore()

    expect(preferences.editorOpenMode).toBe('tabs')
    expect(preferences.editorTheme).toBe('aitest-dark')
  })

  it('preserves an old editor open mode while adding the default theme', () => {
    localStorage.setItem('aitest-console-preferences', JSON.stringify({ editorOpenMode: 'reuse' }))

    const preferences = usePreferencesStore()

    expect(preferences.editorOpenMode).toBe('reuse')
    expect(preferences.editorTheme).toBe('aitest-dark')
  })

  it('falls back only the invalid field', () => {
    localStorage.setItem('aitest-console-preferences', JSON.stringify({
      editorOpenMode: 'reuse',
      editorTheme: 'unknown-theme',
    }))

    const preferences = usePreferencesStore()

    expect(preferences.editorOpenMode).toBe('reuse')
    expect(preferences.editorTheme).toBe('aitest-dark')
  })

  it('writes the complete preferences object after either field changes', async () => {
    const preferences = usePreferencesStore()

    preferences.editorTheme = 'high-contrast-dark'
    await nextTick()
    expect(JSON.parse(localStorage.getItem('aitest-console-preferences') || '{}')).toEqual({
      editorOpenMode: 'tabs',
      editorTheme: 'high-contrast-dark',
    })

    preferences.editorOpenMode = 'reuse'
    await nextTick()
    expect(JSON.parse(localStorage.getItem('aitest-console-preferences') || '{}')).toEqual({
      editorOpenMode: 'reuse',
      editorTheme: 'high-contrast-dark',
    })
  })
})
