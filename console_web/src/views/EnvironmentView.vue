<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { AlertTriangle, Check, Eye, EyeOff, FileKey2, KeyRound, Plus, Save, ShieldCheck } from '@lucide/vue'
import CodeEditor from '../components/CodeEditor.vue'
import { api } from '../api/client'
import { messageFrom } from '../stores/workspace'
import type { EnvironmentMetadata, EnvSource, FileDocument } from '../types'

const metadata = ref<EnvironmentMetadata | null>(null)
const selectedPath = ref('')
const document = ref<FileDocument | null>(null)
const content = ref('')
const revealPending = ref(false)
const externalPath = ref('')
const error = ref('')
const message = ref('')

const selected = computed<EnvSource | null>(() => metadata.value?.sources.find((item) => item.path === selectedPath.value) ?? null)
const dirty = computed(() => Boolean(document.value && document.value.content !== content.value))

async function loadMetadata(): Promise<void> {
  error.value = ''
  try {
    metadata.value = await api.environment()
    if (!metadata.value.sources.some((item) => item.path === selectedPath.value)) {
      selectedPath.value = metadata.value.sources.find((item) => item.active)?.path ?? metadata.value.sources[0]?.path ?? ''
    }
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

function requestReveal(path: string): void {
  if (path === selectedPath.value && (document.value || revealPending.value)) return
  if (!confirmDiscardSensitiveChanges()) return
  selectedPath.value = path
  clearSensitive()
  revealPending.value = true
}

function confirmDiscardSensitiveChanges(): boolean {
  return !dirty.value || window.confirm('Env 文件包含未保存修改，确定放弃这些修改吗？')
}

function hideSensitive(): void {
  if (confirmDiscardSensitiveChanges()) clearSensitive()
}

async function reveal(): Promise<void> {
  error.value = ''
  try {
    document.value = await api.revealEnv(selectedPath.value)
    content.value = document.value.content
    revealPending.value = false
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

function clearSensitive(): void {
  document.value = null
  content.value = ''
  revealPending.value = false
}

async function save(): Promise<void> {
  if (!document.value || !dirty.value) return
  error.value = ''
  try {
    document.value = await api.saveEnv(document.value, content.value)
    content.value = document.value.content
    message.value = 'Env 已保存，内容未写入历史记录'
    await loadMetadata()
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

async function grantExternal(): Promise<void> {
  if (!externalPath.value.trim()) return
  error.value = ''
  try {
    await api.grantEnv(externalPath.value.trim())
    externalPath.value = ''
    await loadMetadata()
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

async function setActive(): Promise<void> {
  if (!selectedPath.value) return
  try {
    await api.setActiveEnv(selectedPath.value)
    message.value = '已设为 Console 运行 env 文件'
    await loadMetadata()
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

onMounted(loadMetadata)
onBeforeUnmount(clearSensitive)
onBeforeRouteLeave(() => !dirty.value || window.confirm('Env 文件包含未保存修改，确定离开并放弃这些修改吗？'))
</script>

<template>
  <section class="environment-view">
    <div class="environment-header">
      <div><span class="eyebrow">LOCAL SENSITIVE CONFIGURATION</span><h1>环境与凭证引用</h1><p>用户可以显式编辑 env，Agent、日志、报告和普通文件接口只能看到变量名与存在状态。</p></div>
      <span class="status-chip ok"><ShieldCheck :size="13" />local only</span>
    </div>

    <div class="env-precedence"><div><span>1</span><strong>Shell</strong><small>同名变量优先，只读</small></div><i /><div><span>2</span><strong>显式 env files</strong><small>AITEST_ENV_FILE / task</small></div><i /><div><span>3</span><strong>workspace .env</strong><small>默认文件</small></div></div>

    <div class="environment-layout">
      <aside class="env-sources">
        <div class="env-source-head"><strong>Env sources</strong><span>{{ metadata?.sources.length ?? 0 }}</span></div>
        <button v-for="source in metadata?.sources" :key="source.path" class="env-source" :class="{ active: selectedPath === source.path }" @click="requestReveal(source.path)">
          <FileKey2 :size="16" /><div><strong>{{ source.path }}</strong><small>{{ source.keys.length }} keys · {{ source.git_status }}{{ source.external ? ' · external' : '' }}</small></div><span class="state-dot" :class="{ success: source.exists }" />
        </button>
        <form class="external-env" @submit.prevent="grantExternal"><label for="external-env">授权外部 env 文件</label><div><input id="external-env" v-model="externalPath" placeholder="/absolute/path/test.env" /><button aria-label="授权文件"><Plus :size="15" /></button></div></form>
        <div class="shell-keys"><span class="section-label">SHELL PRESENCE</span><div v-if="!metadata?.shell_keys.length" class="muted-copy">没有匹配的 Shell env 名称。</div><span v-for="key in metadata?.shell_keys" :key="key"><KeyRound :size="11" />{{ key }}<b>present</b></span></div>
      </aside>

      <section class="env-editor-panel">
        <div class="env-toolbar">
          <div><span class="eyebrow">SENSITIVE FILE</span><strong>{{ selectedPath || '选择 env source' }}</strong></div>
          <span class="toolbar-spacer" />
          <button v-if="selected && !selected.active" class="secondary-btn" @click="setActive"><Check :size="14" />设为运行 env</button>
          <button v-if="document" class="secondary-btn" @click="hideSensitive"><EyeOff :size="14" />隐藏值</button>
          <button v-if="document" class="primary-btn" :disabled="!dirty" @click="save"><Save :size="14" />保存</button>
        </div>

        <div v-if="selected && (selected.git_status === 'tracked' || selected.git_status === 'untracked')" class="env-warning"><AlertTriangle :size="17" /><div><strong>{{ selected.git_status === 'tracked' ? '该 env 文件已被 Git 跟踪' : '该 env 文件未被 Git 忽略' }}</strong><small>Console 不会自动修改 .gitignore，请在保存凭证前确认版本控制边界。</small></div></div>

        <div v-if="revealPending" class="sensitive-gate"><Eye :size="24" /><span class="eyebrow">EXPLICIT REVEAL</span><h2>显示敏感 env 内容</h2><p>内容会进入当前浏览器页面内存，但不会写入日志、报告、Agent 上下文或浏览器持久化存储。</p><div><button class="secondary-btn" @click="clearSensitive">取消</button><button class="primary-btn" @click="reveal">确认并显示</button></div></div>
        <CodeEditor v-else-if="document" v-model="content" :path="selectedPath" language="text" @save="save" />
        <div v-else class="env-placeholder"><EyeOff :size="28" /><strong>敏感值默认隐藏</strong><small>选择一个 env source，再显式确认显示和编辑。</small></div>

        <div v-if="error || message" class="env-message" :class="{ error }"><AlertTriangle v-if="error" :size="15" /><Check v-else :size="15" />{{ error || message }}</div>
      </section>
    </div>
  </section>
</template>
