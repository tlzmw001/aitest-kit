<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  Activity,
  Bug,
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

const route = useRoute()
const store = useWorkspaceStore()
const explorerOpen = ref(false)
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
      <button class="rail-action" aria-label="设置"><Settings :size="17" /></button>
    </nav>

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
        <div class="runtime"><span class="state-dot success" />Local <kbd>⌘K</kbd></div>
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
