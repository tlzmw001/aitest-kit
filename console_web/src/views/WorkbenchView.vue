<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowRight, Check, FolderOpen, History } from '@lucide/vue'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const showOpen = ref(!store.snapshot)
const workspacePath = ref(store.snapshot?.path ?? '')
const latest = computed(() => store.recentReports[0] ?? null)

async function openWorkspace(): Promise<void> {
  if (!workspacePath.value.trim()) return
  if (await store.open(workspacePath.value.trim())) showOpen.value = false
}

async function initializeWorkspace(): Promise<void> {
  const path = store.pendingInitializationPath
  if (!path) return
  if (await store.initialize(path)) {
    workspacePath.value = path
    showOpen.value = false
  }
}

function date(value: string): string {
  return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '没有时间记录'
}
</script>

<template>
  <section class="workbench-view">
    <div class="view-heading">
      <div>
        <span class="eyebrow">LOCAL TEST WORKSPACE</span>
        <h1>从用例到报告，保持一条可追溯链路</h1>
        <p v-if="store.snapshot">
          当前 workspace 已识别 {{ store.snapshot.counts.targets }} 个 target、{{ store.snapshot.counts.modules }} 个 module、
          {{ store.snapshot.counts.suites }} 个 suite 和 {{ store.snapshot.counts.cases }} 个 case。
        </p>
      </div>
      <button class="primary-btn" @click="showOpen = !showOpen"><FolderOpen :size="16" />打开 workspace</button>
    </div>

    <form v-if="showOpen" class="open-workspace" @submit.prevent="openWorkspace">
      <label for="workspace-path">本地 workspace 路径</label>
      <div><input id="workspace-path" v-model="workspacePath" autocomplete="off" /><button class="primary-btn">打开</button></div>
      <small>打开只读取 workspace 结构，不执行 fixture、Harness 或 pytest。</small>
      <div v-if="store.pendingInitializationPath" class="initialization-confirmation" role="alert">
        <div>
          <strong>该目录尚未初始化</strong>
          <p><code>{{ store.pendingInitializationPath }}</code></p>
          <small>初始化会写入 AITest 配置、测试空间模板和协作文件；不会使用 force 覆盖已有模板文件。</small>
        </div>
        <div class="initialization-actions">
          <button type="button" class="secondary-btn" @click="store.dismissInitialization">取消</button>
          <button
            type="button"
            class="primary-btn"
            data-test="initialize-workspace"
            :disabled="store.loading"
            @click="initializeWorkspace"
          >初始化并打开</button>
        </div>
      </div>
      <p v-else-if="store.error" class="inline-error">{{ store.error }}</p>
    </form>

    <div class="workbench-grid">
      <section class="map-panel">
        <div class="section-heading">
          <div><span class="eyebrow">WORKSPACE MAP</span><h2>{{ store.targets[0]?.name ?? '没有 target' }}</h2></div>
          <span v-if="store.snapshot" class="status-chip ok"><i />ready</span>
        </div>
        <div v-if="!store.modules.length" class="section-empty">没有可展示的 module。</div>
        <div v-for="(module, index) in store.modules" :key="`${module.name}-${index}`" class="module-line">
          <div><span class="module-index">{{ String(index + 1).padStart(2, '0') }}</span><strong>{{ module.name }}</strong><small>{{ module.module_type || '未声明类型' }}</small></div>
          <div class="module-meta"><span>{{ module.suites.length }} suite</span><span>{{ module.suites.reduce((total, suite) => total + suite.cases.length, 0) }} cases</span></div>
        </div>
      </section>

      <section class="activity-panel">
        <div class="section-heading">
          <div><span class="eyebrow">RECENT EXECUTION</span><h2>{{ latest?.suite || latest?.run_id || '尚无执行' }}</h2></div>
          <span v-if="latest" class="run-id">…{{ latest.run_id.slice(-12) }}</span>
        </div>
        <div v-if="latest" class="run-result">
          <span class="big-number">{{ latest.summary.passed ?? 0 }}</span>
          <div><strong>{{ latest.status === 'COMPLETED' ? '执行完成' : latest.status }}</strong><small>{{ date(latest.timestamp) }} · {{ latest.duration_seconds }}s</small></div>
          <span class="status-chip" :class="{ ok: !latest.summary.failed && !latest.summary.error }"><i />{{ latest.status.toLowerCase() }}</span>
        </div>
        <div v-else class="section-empty tall"><History :size="24" /><strong>尚无执行记录</strong><small>运行 case、suite、module 或 task 后，结果会出现在这里。</small></div>
        <div class="compact-pipeline"><span>校验</span><b /><span>生成</span><b /><span>同步</span><b /><span>执行</span><b /><span>报告</span></div>
        <div class="next-actions">
          <RouterLink class="secondary-btn" to="/reports">打开报告<ArrowRight :size="14" /></RouterLink>
          <RouterLink class="secondary-btn" to="/editor">编辑用例</RouterLink>
          <RouterLink class="secondary-btn" to="/run">配置运行</RouterLink>
        </div>
      </section>
    </div>

    <section class="ownership-strip">
      <div><span class="provenance config">CONFIG</span><strong>配置</strong><small>manifest · registry · profile shape</small></div>
      <div><span class="provenance case">CASE</span><strong>用例</strong><small>Markdown source</small></div>
      <div><span class="provenance scaffold">SCAFFOLD</span><strong>脚手架</strong><small>Harness · fixture · helper</small></div>
      <div><span class="provenance env">ENV</span><strong>环境</strong><small>service · variable · resource</small></div>
      <div><span class="provenance review">REVIEW</span><strong>待确认</strong><small>assertion failure 不自动归责</small></div>
      <div><span class="provenance sut">SUT</span><strong>待测系统</strong><small>人工确认的产品行为</small></div>
    </section>
  </section>
</template>
