<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { AlertCircle, ArrowRight, Check, Search } from '@lucide/vue'
import { api } from '../api/client'
import { messageFrom } from '../stores/workspace'
import { displayOwner, ownerLabel, type DisplayOwner } from '../utils/classification'
import type { ReportDetail, ReportSummary } from '../types'

interface FailureItem {
  caseId: string
  title: string
  raw: string
  message: string
  owner: DisplayOwner
}

const reports = ref<ReportSummary[]>([])
const selectedReport = ref<ReportSummary | null>(null)
const detail = ref<ReportDetail | null>(null)
const selectedFailure = ref<FailureItem | null>(null)
const error = ref('')

const failures = computed<FailureItem[]>(() => {
  const cases = Array.isArray(detail.value?.result?.cases) ? detail.value?.result?.cases as Record<string, unknown>[] : []
  return cases
    .filter((item) => !['passed', 'skipped'].includes(String(item.outcome ?? item.status ?? '').toLowerCase()))
    .map((item) => {
      const raw = String(item.failure_type ?? item.classification ?? item.error_type ?? 'UNKNOWN')
      return {
        caseId: String(item.case_id ?? item.id ?? 'unknown-case'),
        title: String(item.title ?? item.name ?? '没有 case 标题'),
        raw,
        message: String(item.message ?? item.error ?? item.longrepr ?? '本次结果没有提供失败详情'),
        owner: displayOwner(raw),
      }
    })
})

async function load(): Promise<void> {
  try {
    reports.value = (await api.reports()).reports.filter((item) => (item.summary.failed ?? 0) + (item.summary.error ?? 0) > 0)
    if (reports.value.length) await selectReport(reports.value[0])
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

async function selectReport(report: ReportSummary): Promise<void> {
  selectedReport.value = report
  try {
    detail.value = await api.reportDetail(report.result_path)
    selectedFailure.value = failures.value[0] ?? null
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

onMounted(load)
</script>

<template>
  <section class="diagnostics-view">
    <div class="failure-banner" :class="{ clear: !failures.length }">
      <div class="failure-symbol"><Check v-if="!failures.length" :size="24" /><AlertCircle v-else :size="24" /></div>
      <div><span class="eyebrow">EVIDENCE-BASED TRIAGE</span><h1>{{ failures.length ? `${failures.length} 个 case 需要分诊` : '当前历史中没有可分诊失败' }}</h1><p>断言失败先进入“待确认”，不会自动标记为待测系统问题。</p></div>
      <select v-if="reports.length" :value="selectedReport?.result_path" @change="selectReport(reports.find((item) => item.result_path === ($event.target as HTMLSelectElement).value)!)"><option v-for="report in reports" :key="report.result_path" :value="report.result_path">{{ report.run_id }}</option></select>
    </div>

    <div v-if="failures.length" class="diagnostic-layout">
      <section class="failure-list">
        <div class="failure-list-head"><strong>Failures</strong><span>{{ failures.length }} cases</span></div>
        <button v-for="failure in failures" :key="failure.caseId" class="failure-item" :class="{ active: selectedFailure?.caseId === failure.caseId }" @click="selectedFailure = failure">
          <span class="bad-dot">×</span><div><code>{{ failure.caseId }}</code><strong>{{ failure.title }}</strong><small>{{ failure.raw }}</small></div><span class="provenance" :class="failure.owner.toLowerCase()">{{ failure.owner }}</span>
        </button>
      </section>
      <section v-if="selectedFailure" class="failure-detail">
        <div class="detail-head"><div><code>{{ selectedFailure.caseId }}</code><h2>{{ selectedFailure.title }}</h2></div><RouterLink class="secondary-btn" to="/editor"><Search :size="14" />定位 source</RouterLink></div>
        <div class="evidence-chain"><div class="passed"><span>1</span><strong>Profile</strong><small>查看 run 证据</small></div><i /><div class="passed"><span>2</span><strong>生成同步</strong><small>查看 codegen_check</small></div><i /><div class="failed"><span>3</span><strong>{{ selectedFailure.raw }}</strong><small>原始分类</small></div><i /><div><span>4</span><strong>SUT judgment</strong><small>人工确认</small></div></div>
        <div class="classification-callout">
          <span class="provenance" :class="selectedFailure.owner.toLowerCase()">{{ selectedFailure.owner }}</span>
          <div><strong>当前展示归属：{{ ownerLabel(selectedFailure.owner) }}</strong><p v-if="selectedFailure.owner === 'REVIEW'">当前只有断言不一致证据，需要继续核对用例、环境、脚手架和产品契约。</p><p v-else>展示归属来自 result.json 的原始 failure classification，不覆盖原始事实。</p></div>
        </div>
        <div class="trace-panel"><div class="trace-tabs"><button class="active">Failure summary</button></div><pre>{{ selectedFailure.message }}</pre></div>
      </section>
    </div>
    <div v-else class="diagnostics-empty"><Check :size="26" /><strong>{{ error || '没有失败证据需要分诊' }}</strong><small>报告出现失败后，原始分类和展示归属会在这里保持并列。</small><RouterLink class="secondary-btn" to="/reports">查看历史<ArrowRight :size="14" /></RouterLink></div>

    <div class="ownership-guidance">
      <div><span class="provenance config">CONFIG</span><strong>配置错误</strong><small>schema、registry、profile shape</small></div>
      <div><span class="provenance case">CASE</span><strong>用例错误</strong><small>意图、步骤、已确认断言问题</small></div>
      <div><span class="provenance scaffold">SCAFFOLD</span><strong>脚手架错误</strong><small>Harness、helper、fixture、codegen</small></div>
      <div><span class="provenance env">ENV</span><strong>环境错误</strong><small>服务、变量、账号和资源前置</small></div>
      <div><span class="provenance review">REVIEW</span><strong>待确认</strong><small>普通 assertion failure</small></div>
      <div><span class="provenance sut">SUT</span><strong>待测系统</strong><small>人工确认契约后的产品行为</small></div>
    </div>
  </section>
</template>
