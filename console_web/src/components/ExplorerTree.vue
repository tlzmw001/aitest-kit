<script setup lang="ts">
import { FileCode2, FileText, RefreshCw } from '@lucide/vue'
import { useRoute } from 'vue-router'
import { useWorkspaceStore } from '../stores/workspace'
import type { Asset } from '../types'

defineEmits<{ navigate: [] }>()
const store = useWorkspaceStore()
const route = useRoute()

function editorLink(asset: Asset): { path: string; query: { path: string } } {
  return { path: '/editor', query: { path: asset.path } }
}

function isActive(asset: Asset): boolean {
  return route.path === '/editor' && route.query.path === asset.path
}
</script>

<template>
  <div class="panel-title">
    <span>EXPLORER</span>
    <button aria-label="刷新 workspace" @click="store.refresh"><RefreshCw :size="14" /></button>
  </div>
  <div class="workspace-name">
    <strong>{{ store.snapshot?.name ?? 'No workspace' }}</strong>
    <span class="branch">{{ store.snapshot?.branch }}</span>
  </div>
  <div v-if="!store.snapshot?.targets.length" class="explorer-empty">当前 workspace 没有 target。</div>
  <div v-else class="tree" role="tree">
    <details v-for="target in store.targets" :key="target.name" open>
      <summary class="tree-row"><span class="folder">TARGET</span><strong>{{ target.name }}</strong></summary>
      <details v-for="module in target.modules" :key="module.name" open>
        <summary class="tree-row depth-1"><span class="folder">MODULE</span><strong>{{ module.name }}</strong></summary>
        <details v-for="suite in module.suites" :key="suite.name" open>
          <summary class="tree-row depth-2">
            <span class="folder">SUITE</span><strong>{{ suite.name }}</strong><span class="count">{{ suite.cases.length }}</span>
          </summary>
          <RouterLink
            v-for="asset in suite.assets"
            :key="asset.path"
            :to="editorLink(asset)"
            class="tree-row depth-3 tree-link"
            :class="{ active: isActive(asset) }"
            @click="$emit('navigate')"
          >
            <FileText v-if="asset.name.endsWith('.md')" :size="14" />
            <FileCode2 v-else :size="14" />
            <span :title="asset.path">{{ asset.name }}</span>
            <span class="provenance" :class="asset.owner.toLowerCase()">{{ asset.owner }}</span>
          </RouterLink>
        </details>
        <div v-for="asset in module.assets" :key="asset.path">
          <RouterLink
            :to="editorLink(asset)"
            class="tree-row depth-2 tree-link"
            :class="{ active: isActive(asset) }"
            @click="$emit('navigate')"
          >
            <FileCode2 :size="14" />
            <span :title="asset.path">{{ asset.name }}</span>
            <span class="provenance" :class="asset.owner.toLowerCase()">{{ asset.owner }}</span>
          </RouterLink>
        </div>
      </details>
    </details>
  </div>
  <div class="explorer-footer">
    <span>{{ store.snapshot?.counts.modules ?? 0 }} modules</span>
    <span>{{ store.snapshot?.counts.suites ?? 0 }} suites</span>
  </div>
</template>
