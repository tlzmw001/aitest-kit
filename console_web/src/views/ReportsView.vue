<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Braces, FileText, RefreshCw, RotateCcw } from '@lucide/vue'
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from 'reka-ui'
import { api } from '../api/client'
import CodeEditor from '../components/CodeEditor.vue'
import SafeMarkdown from '../components/SafeMarkdown.vue'
import { usePreferencesStore } from '../stores/preferences'
import { messageFrom } from '../stores/workspace'
import type { ReportDetail, ReportSummary } from '../types'

const reports = ref<ReportSummary[]>([])
const preferences = usePreferencesStore()
const selected = ref<ReportSummary | null>(null)
const detail = ref<ReportDetail | null>(null)
const tab = ref<'report' | 'json'>('report')
const error = ref('')
const summary = computed(() => detail.value?.summary.summary ?? {})
const resultJson = computed(() => detail.value ? JSON.stringify(detail.value.result, null, 2) : '')
const resultPath = computed(() => detail.value?.summary.result_path ?? 'result.json')

async function loadReports(): Promise<void> {
  error.value = ''
  try {
    reports.value = (await api.reports()).reports
    if (!selected.value && reports.value.length) await selectReport(reports.value[0])
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

async function selectReport(report: ReportSummary): Promise<void> {
  selected.value = report
  error.value = ''
  try {
    detail.value = await api.reportDetail(report.result_path)
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

function formatTime(value: string): string {
  return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(value)) : ''
}

onMounted(loadReports)
</script>

<template>
  <section class="report-view">
    <div class="report-header">
      <div><span class="eyebrow">RUN HISTORY</span><h1>{{ selected?.suite || selected?.run_id || '执行报告' }}</h1><p v-if="selected"><code>{{ selected.run_id }}</code> · {{ formatTime(selected.timestamp) }} · {{ selected.duration_seconds }}s</p></div>
      <div class="report-actions"><button @click="loadReports"><RefreshCw :size="14" />刷新</button><RouterLink class="primary-btn" to="/run"><RotateCcw :size="14" />重新运行</RouterLink></div>
    </div>

    <div v-if="selected" class="summary-row">
      <div class="summary-main"><span class="result-ring">{{ summary.passed ?? 0 }}<small>passed</small></span><div><strong>{{ selected.status }}</strong><small>result.json 是本页事实来源</small></div></div>
      <div class="metric"><span>{{ summary.passed ?? 0 }}</span><small>Passed</small></div>
      <div class="metric"><span>{{ summary.failed ?? 0 }}</span><small>Failed</small></div>
      <div class="metric"><span>{{ summary.error ?? 0 }}</span><small>Error</small></div>
      <div class="metric"><span>{{ selected.duration_seconds }}s</span><small>Duration</small></div>
    </div>

    <div class="report-layout">
      <TabsRoot v-if="detail" v-model="tab" class="report-document">
        <TabsList class="document-tabs" aria-label="报告文件">
          <TabsTrigger value="report"><FileText :size="14" />report.md</TabsTrigger>
          <TabsTrigger value="json" data-test="result-json-tab"><Braces :size="14" />result.json</TabsTrigger>
        </TabsList>
        <TabsContent value="report" class="report-panel">
          <SafeMarkdown :source="detail.report_markdown" empty-text="本次执行没有 report.md。" />
        </TabsContent>
        <TabsContent value="json" class="report-panel json-editor-panel">
          <CodeEditor
            :model-value="resultJson"
            :path="resultPath"
            language="json"
            read-only
            :theme="preferences.editorTheme"
          />
        </TabsContent>
      </TabsRoot>
      <section v-else class="report-document"><div class="section-empty tall">{{ error || '选择一条历史执行查看详情。' }}</div></section>
      <aside class="history-panel">
        <div class="section-heading"><div><span class="eyebrow">FILESYSTEM HISTORY</span><h2>最近执行</h2></div><span>{{ reports.length }}</span></div>
        <div v-if="!reports.length" class="section-empty">当前 reports 目录没有历史执行。</div>
        <button v-for="report in reports" :key="report.result_path" class="history-item" :class="{ active: selected?.result_path === report.result_path }" @click="selectReport(report)">
          <span class="history-mark" :class="{ ok: !(report.summary.failed || report.summary.error), bad: report.summary.failed || report.summary.error }" />
          <div><strong>{{ report.suite || report.run_id }}</strong><small>{{ report.summary.passed ?? 0 }} passed · {{ report.summary.failed ?? 0 }} failed</small></div>
          <time>{{ report.timestamp.slice(5, 10) }}</time>
        </button>
      </aside>
    </div>
  </section>
</template>
