import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'
import AppShell from './AppShell.vue'
import { usePreferencesStore } from '../stores/preferences'

describe('AppShell settings', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('opens settings and lets the user choose how files open', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', name: 'workbench', component: { template: '<div />' } }],
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(AppShell, {
      global: {
        plugins: [pinia, router],
        stubs: { ExplorerTree: true, PipelineRail: true },
      },
      slots: { default: '<div />' },
    })

    expect(wrapper.find('[data-test="settings-panel"]').exists()).toBe(false)
    await wrapper.get('[data-test="open-settings"]').trigger('click')
    expect(wrapper.get('[data-test="settings-panel"]').isVisible()).toBe(true)

    await wrapper.get('[data-test="open-mode-reuse"]').trigger('click')
    expect(usePreferencesStore().editorOpenMode).toBe('reuse')
  })
})
