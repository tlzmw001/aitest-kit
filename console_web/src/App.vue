<script setup lang="ts">
import { onMounted } from 'vue'
import AppShell from './components/AppShell.vue'
import { hasSessionToken } from './api/client'
import { useWorkspaceStore } from './stores/workspace'

const store = useWorkspaceStore()

onMounted(() => {
  if (hasSessionToken()) void store.refresh()
})
</script>

<template>
  <AppShell>
    <div v-if="!hasSessionToken()" class="fatal-state">
      <span class="eyebrow">LOCAL SESSION REQUIRED</span>
      <h1>Console 会话无效</h1>
      <p>请通过 <code>aitest console</code> 输出的本地会话地址重新打开页面。</p>
    </div>
    <div v-else-if="store.loading && !store.snapshot" class="loading-state" aria-live="polite">
      <span class="spinner" />
      <div><strong>正在读取 workspace</strong><small>解析 registry、suite 和报告索引</small></div>
    </div>
    <div v-else-if="store.error && !store.snapshot" class="fatal-state">
      <span class="eyebrow">WORKSPACE ERROR</span>
      <h1>无法打开 workspace</h1>
      <p>{{ store.error }}</p>
      <button class="secondary-btn" @click="store.refresh">重新检查</button>
    </div>
    <RouterView v-else />
  </AppShell>
</template>
