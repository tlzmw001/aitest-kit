<script setup lang="ts">
import { FileCode2, FileText, Plus, RefreshCw, RotateCcw, Trash2 } from '@lucide/vue'
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { useWorkspaceStore } from '../stores/workspace'
import type { Asset } from '../types'
import AssetManager from './AssetManager.vue'

defineEmits<{ navigate: [] }>()
const store = useWorkspaceStore()
const route = useRoute()
const manager = ref<InstanceType<typeof AssetManager> | null>(null)

function editorLink(asset: Asset): { path: string; query: { path: string } } {
  return { path: '/editor', query: { path: asset.path } }
}

function isActive(asset: Asset): boolean {
  return route.path === '/editor' && route.query.path === asset.path
}

function targetAsset(path: string | null): Asset | null {
  return path ? { path, name: 'target.yaml', owner: 'CONFIG', exists: true } : null
}
</script>

<template>
  <div class="panel-title">
    <span>EXPLORER</span>
    <span class="panel-actions">
      <button aria-label="新建资产" data-test="create-asset" :disabled="!store.snapshot" @click="manager?.openCreate()"><Plus :size="15" /></button>
      <button aria-label="打开回收站" :disabled="!store.snapshot" @click="manager?.openTrash()"><RotateCcw :size="14" /></button>
      <button aria-label="刷新 workspace" @click="store.refresh"><RefreshCw :size="14" /></button>
    </span>
  </div>
  <div class="workspace-name">
    <strong>{{ store.snapshot?.name ?? 'No workspace' }}</strong>
    <span class="branch">{{ store.snapshot?.branch }}</span>
  </div>
  <div v-if="!store.snapshot?.targets.length" class="explorer-empty">当前 workspace 没有 target。</div>
  <div v-else class="tree" role="tree">
    <details v-for="target in store.targets" :key="target.name" open>
      <summary class="tree-row"><span class="folder">TARGET</span><strong>{{ target.name }}</strong><button class="tree-delete" :aria-label="`删除 target ${target.name}`" @click.stop.prevent="manager?.openDelete({ kind: 'target', target: target.name })"><Trash2 :size="12" /></button></summary>
      <RouterLink
        v-if="targetAsset(target.config_path)"
        :to="editorLink(targetAsset(target.config_path)!)"
        class="tree-row depth-1 tree-link"
        :class="{ active: isActive(targetAsset(target.config_path)!) }"
        @click="$emit('navigate')"
      ><FileCode2 :size="14" /><span>target.yaml</span><span class="provenance config">CONFIG</span></RouterLink>
      <details v-for="module in target.modules" :key="module.name" open>
        <summary class="tree-row depth-1"><span class="folder">MODULE</span><strong>{{ module.name }}</strong><button class="tree-delete" :aria-label="`删除 module ${module.name}`" @click.stop.prevent="manager?.openDelete({ kind: 'module', target: target.name, module: module.name })"><Trash2 :size="12" /></button></summary>
        <details v-for="suite in module.suites" :key="suite.name" open>
          <summary class="tree-row depth-2">
            <span class="folder">SUITE</span><strong>{{ suite.name }}</strong><span class="count">{{ suite.cases.length }}</span><button class="tree-delete" :aria-label="`删除 suite ${suite.name}`" @click.stop.prevent="manager?.openDelete({ kind: 'suite', target: target.name, module: module.name, suite: suite.name })"><Trash2 :size="12" /></button>
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
    <details v-if="store.tasks.length" open>
      <summary class="tree-row"><span class="folder">TASKS</span><strong>执行任务</strong><span class="count">{{ store.tasks.length }}</span></summary>
      <div v-for="task in store.tasks" :key="task.path" class="tree-task-row">
        <RouterLink
          :to="editorLink({ path: task.path, name: task.path.split('/').pop() || task.name, owner: 'CONFIG', exists: true })"
          class="tree-row depth-1 tree-link"
          :class="{ active: route.path === '/editor' && route.query.path === task.path }"
          @click="$emit('navigate')"
        ><FileCode2 :size="14" /><span>{{ task.name }}</span><span class="provenance config">CONFIG</span></RouterLink>
        <button class="tree-delete task-delete" :aria-label="`删除 task ${task.name}`" @click="manager?.openDelete({ kind: 'task', task: task.name })"><Trash2 :size="12" /></button>
      </div>
    </details>
  </div>
  <div class="explorer-footer">
    <span>{{ store.snapshot?.counts.modules ?? 0 }} modules</span>
    <span>{{ store.snapshot?.counts.suites ?? 0 }} suites</span>
  </div>
  <AssetManager ref="manager" />
</template>
