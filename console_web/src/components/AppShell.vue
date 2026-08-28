<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  Activity,
  Bug,
  Cable,
  FileText,
  FlaskConical,
  FolderTree,
  Menu,
  Play,
  Settings,
  ShieldCheck,
  X,
} from '@lucide/vue'
import ExplorerTree from './ExplorerTree.vue'
import PipelineRail from './PipelineRail.vue'
import { useWorkspaceStore } from '../stores/workspace'
import { usePreferencesStore } from '../stores/preferences'
import { editorThemeCatalog } from '../editor/themeCatalog'

const route = useRoute()
const store = useWorkspaceStore()
const preferences = usePreferencesStore()
const explorerOpen = ref(false)
const settingsOpen = ref(false)
const nav = [
  { name: 'workbench', label: '工作台', icon: FolderTree, to: '/' },
  { name: 'editor', label: '用例', icon: FileText, to: '/editor' },
  { name: 'run', label: '运行', icon: Play, to: '/run' },
  { name: 'reports', label: '报告', icon: Activity, to: '/reports' },
  { name: 'diagnostics', label: '诊断', icon: Bug, to: '/diagnostics' },
  { name: 'environment', label: '环境', icon: ShieldCheck, to: '/environment' },
]

const subtitle = computed(() => {
  if (route.name === 'editor' && route.query.path) return String(route.query.path)
  return store.snapshot?.path ?? 'No workspace'
})

function handleEscape(event: KeyboardEvent): void {
  if (event.key === 'Escape') settingsOpen.value = false
}

onMounted(() => window.addEventListener('keydown', handleEscape))
onBeforeUnmount(() => window.removeEventListener('keydown', handleEscape))
</script>

<template>
  <div class="app-shell">
    <nav class="rail" aria-label="主导航">
      <RouterLink class="brand" to="/" aria-label="AITest 工作台">AI/<b>TS</b></RouterLink>
      <div class="nav-stack">
        <RouterLink
          v-for="item in nav"
          :key="item.name"
          :to="item.to"
          class="nav-item"
          :class="{ active: route.name === item.name }"
        >
          <component :is="item.icon" :size="17" :stroke-width="1.65" />
          <small>{{ item.label }}</small>
        </RouterLink>
      </div>
      <button
        class="rail-action"
        :class="{ active: settingsOpen }"
        aria-label="设置"
        aria-controls="console-settings"
        :aria-expanded="settingsOpen"
        data-test="open-settings"
        @click="settingsOpen = !settingsOpen"
      ><Settings :size="18" /></button>
    </nav>

    <aside
      v-if="settingsOpen"
      id="console-settings"
      class="settings-panel"
      aria-label="Console 设置"
      data-test="settings-panel"
    >
      <header class="settings-head">
        <div><span class="eyebrow">PREFERENCES</span><strong>Console 设置</strong></div>
        <button aria-label="关闭设置" @click="settingsOpen = false"><X :size="17" /></button>
      </header>
      <section class="settings-section">
        <div class="settings-subsection settings-destination">
          <span class="section-label">Agent</span>
          <strong>模型连接</strong>
          <p>配置模型地址和凭证，由 Console 识别底层接口，无需查找 Pi Provider。</p>
          <RouterLink
            class="settings-route"
            to="/settings/agent"
            data-test="agent-connection-settings"
            @click="settingsOpen = false"
          >
            <Cable :size="17" />
            <span><b>打开模型连接</b><small>测试 Base URL、模型和 API Key</small></span>
          </RouterLink>
        </div>
        <div class="settings-subsection">
          <span class="section-label">编辑器</span>
          <strong>打开文件的方式</strong>
          <p>控制从左侧资源树打开另一个文件时，是否保留当前标签。</p>
          <div class="setting-options" role="radiogroup" aria-label="打开文件的方式">
            <button
              role="radio"
              :aria-checked="preferences.editorOpenMode === 'tabs'"
              :class="{ active: preferences.editorOpenMode === 'tabs' }"
              data-test="open-mode-tabs"
              @click="preferences.editorOpenMode = 'tabs'"
            >
              <span>多标签打开</span><small>保留已打开文件，像 VS Code 一样切换</small>
            </button>
            <button
              role="radio"
              :aria-checked="preferences.editorOpenMode === 'reuse'"
              :class="{ active: preferences.editorOpenMode === 'reuse' }"
              data-test="open-mode-reuse"
              @click="preferences.editorOpenMode = 'reuse'"
            >
              <span>复用当前标签</span><small>打开新文件时替换当前的已保存标签</small>
            </button>
          </div>
          <p class="settings-footnote">存在未保存修改时会始终保留原标签，避免内容丢失。</p>
        </div>
        <div class="settings-subsection theme-settings">
          <span class="section-label">外观</span>
          <strong>编辑器配色</strong>
          <p>只改变代码区域，Console 外壳保持当前冷石墨主题。</p>
          <div class="setting-options theme-options" role="radiogroup" aria-label="编辑器配色">
            <button
              v-for="theme in editorThemeCatalog"
              :key="theme.id"
              role="radio"
              :aria-checked="preferences.editorTheme === theme.id"
              :class="{ active: preferences.editorTheme === theme.id }"
              :data-test="`editor-theme-${theme.id}`"
              @click="preferences.editorTheme = theme.id"
            >
              <span class="setting-copy"><span>{{ theme.label }}</span><small>{{ theme.description }}</small></span>
              <span class="theme-preview" :style="{ backgroundColor: theme.palette.background }" aria-hidden="true">
                <b :style="{ color: theme.palette.syntax.keyword }">def</b>
                <b :style="{ color: theme.palette.syntax.property }">target</b>
                <b :style="{ color: theme.palette.syntax.string }">"suite"</b>
                <b :style="{ color: theme.palette.syntax.function }">run()</b>
              </span>
            </button>
          </div>
        </div>
      </section>
    </aside>

    <section class="workspace-shell">
      <header class="topbar">
        <button class="explorer-toggle" aria-label="打开资源树" @click="explorerOpen = !explorerOpen">
          <X v-if="explorerOpen" :size="17" />
          <Menu v-else :size="17" />
        </button>
        <div class="context">
          <span class="context-label">WORKSPACE</span>
          <strong>{{ store.snapshot?.name ?? 'AITest' }}</strong>
          <span class="separator">/</span>
          <span :title="subtitle">{{ subtitle }}</span>
        </div>
        <PipelineRail />
        <div class="runtime"><span class="state-dot success" />Local</div>
      </header>

      <div class="workspace-body">
        <aside class="explorer" :class="{ open: explorerOpen }">
          <ExplorerTree @navigate="explorerOpen = false" />
        </aside>
        <main id="main-content" class="main-content" tabindex="-1">
          <slot />
        </main>
      </div>

      <footer class="statusbar">
        <span><b>✓</b> {{ store.snapshot ? 'workspace ready' : 'workspace unavailable' }}</span>
        <span>{{ store.snapshot?.branch || 'no git branch' }}</span>
        <span v-if="store.currentJob">{{ store.currentJob.operation }} · {{ store.currentJob.status }}</span>
        <span class="status-right">UTF-8 LF · AITest Console MVP</span>
      </footer>
    </section>
  </div>
</template>
