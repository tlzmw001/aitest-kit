<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const route = useRoute()
const steps = [
  { id: 'case', label: '用例' },
  { id: 'validate_profile', label: 'Profile 校验' },
  { id: 'codegen', label: '生成 pytest' },
  { id: 'freshness', label: '生成同步' },
  { id: 'run', label: '执行' },
  { id: 'report', label: '报告' },
]

const activeIndex = computed(() => {
  const operation = store.currentJob?.operation
  if (operation) {
    const index = steps.findIndex((step) => step.id === operation)
    if (index >= 0) return index
  }
  return { editor: 0, run: 4, reports: 5, diagnostics: 5 }[String(route.name)] ?? 0
})
</script>

<template>
  <div class="pipeline" aria-label="AITest 确定性流水线">
    <div
      v-for="(step, index) in steps"
      :key="step.id"
      class="pipe-step"
      :class="{
        done: index < activeIndex,
        active: index === activeIndex,
        failed: index === activeIndex && store.currentJob?.status === 'failed',
      }"
    >
      <span class="pipe-dot">{{ index < activeIndex ? '✓' : index + 1 }}</span>
      <span>{{ step.label }}</span>
    </div>
  </div>
</template>
