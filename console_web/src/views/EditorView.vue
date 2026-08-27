<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { AlertTriangle, Check, LockKeyhole, Save, X } from '@lucide/vue'
import CodeEditor from '../components/CodeEditor.vue'
import { api } from '../api/client'
import { messageFrom, useWorkspaceStore } from '../stores/workspace'
import { usePreferencesStore } from '../stores/preferences'
import type { EditorDiagnostic, FileDocument } from '../types'

interface EditorTab {
  document: FileDocument
  content: string
  diagnostics: EditorDiagnostic[]
  validationError: string
  validationState: 'idle' | 'waiting' | 'validating' | 'ready'
}

const route = useRoute()
const router = useRouter()
const store = useWorkspaceStore()
const preferences = usePreferencesStore()
const codeEditor = ref<InstanceType<typeof CodeEditor> | null>(null)
const tabs = ref<EditorTab[]>([])
const activePath = ref('')
const loadingPath = ref('')
const error = ref('')
const savedMessage = ref('')
const requestedPath = computed(() => String(route.query.path || ''))
const activeTab = computed(() => tabs.value.find((tab) => tab.document.path === activePath.value) ?? null)
const document = computed(() => activeTab.value?.document ?? null)
const content = computed({
  get: () => activeTab.value?.content ?? '',
  set: (value: string) => {
    if (activeTab.value) {
      activeTab.value.content = value
      scheduleValidation(activeTab.value)
    }
  },
})
const path = computed(() => activeTab.value?.document.path ?? requestedPath.value)
const loading = computed(() => Boolean(loadingPath.value))
const dirty = computed(() => Boolean(activeTab.value && activeTab.value.content !== activeTab.value.document.content))
const diagnostics = computed(() => activeTab.value?.diagnostics ?? [])
const validationError = computed(() => activeTab.value?.validationError ?? '')
const hasDirtyTabs = computed(() => tabs.value.some((tab) => isDirty(tab)))
const language = computed(() => languageFor(path.value))
let validationTimer: number | undefined
let validationController: AbortController | null = null

function languageFor(value: string): string {
  value = value.toLowerCase()
  if (value.endsWith('.md')) return 'markdown'
  if (value.endsWith('.yaml') || value.endsWith('.yml')) return 'yaml'
  if (value.endsWith('.py')) return 'python'
  return 'text'
}

function isDirty(tab: EditorTab): boolean {
  return tab.content !== tab.document.content
}

async function openFile(nextPath: string): Promise<void> {
  if (!nextPath) return
  const existing = tabs.value.find((tab) => tab.document.path === nextPath)
  if (existing) {
    activePath.value = nextPath
    error.value = ''
    scheduleValidation(existing)
    return
  }

  const replacePath = activePath.value
  loadingPath.value = nextPath
  error.value = ''
  savedMessage.value = ''
  try {
    const loaded = await api.readFile(nextPath)
    const duplicate = tabs.value.find((tab) => tab.document.path === loaded.path)
    if (duplicate) {
      activePath.value = duplicate.document.path
      return
    }
    const nextTab: EditorTab = {
      document: loaded,
      content: loaded.content,
      diagnostics: [],
      validationError: '',
      validationState: 'idle',
    }
    const replaceIndex = tabs.value.findIndex((tab) => tab.document.path === replacePath)
    const mayReplace = preferences.editorOpenMode === 'reuse'
      && replaceIndex >= 0
      && !isDirty(tabs.value[replaceIndex])
    if (mayReplace) tabs.value.splice(replaceIndex, 1, nextTab)
    else tabs.value.push(nextTab)
    activePath.value = loaded.path
    scheduleValidation(tabs.value.find((tab) => tab.document.path === loaded.path) ?? null)
  } catch (cause) {
    error.value = messageFrom(cause)
  } finally {
    if (loadingPath.value === nextPath) loadingPath.value = ''
  }
}

async function save(): Promise<void> {
  const tab = activeTab.value
  if (!tab || tab.document.read_only || !isDirty(tab)) return
  error.value = ''
  try {
    const saved = await api.saveFile(tab.document, tab.content)
    const current = tabs.value.find((item) => item.document.path === tab.document.path)
    if (current) {
      current.document = saved
      current.content = saved.content
    }
    await store.refresh()
    savedMessage.value = '已保存并更新文件 hash'
    scheduleValidation(current ?? tab)
    window.setTimeout(() => (savedMessage.value = ''), 2400)
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

function activateTab(nextPath: string): void {
  activePath.value = nextPath
  error.value = ''
  savedMessage.value = ''
  const tab = tabs.value.find((item) => item.document.path === nextPath)
  if (tab) scheduleValidation(tab)
  if (requestedPath.value !== nextPath) void router.replace({ path: '/editor', query: { path: nextPath } })
}

function scheduleValidation(tab: EditorTab | null): void {
  window.clearTimeout(validationTimer)
  validationController?.abort()
  validationController = null
  if (!tab || tab.document.read_only) return
  tab.validationState = 'waiting'
  tab.validationError = ''
  validationTimer = window.setTimeout(() => void validateTab(tab), 350)
}

async function validateTab(tab: EditorTab): Promise<void> {
  const contentAtRequest = tab.content
  const controller = new AbortController()
  validationController = controller
  tab.validationState = 'validating'
  tab.validationError = ''
  try {
    const result = await api.validateEditor(tab.document.path, contentAtRequest, controller.signal)
    if (controller.signal.aborted || tab.content !== contentAtRequest) return
    tab.diagnostics = result.diagnostics
    tab.validationState = 'ready'
  } catch (cause) {
    if (controller.signal.aborted) return
    tab.validationError = messageFrom(cause)
    tab.validationState = 'ready'
  } finally {
    if (validationController === controller) validationController = null
  }
}

function focusDiagnostic(diagnostic: EditorDiagnostic): void {
  codeEditor.value?.focusDiagnostic(diagnostic)
}

function validationLabel(): string {
  if (validationError.value) return '校验服务不可用'
  if (activeTab.value?.validationState === 'validating') return '正在校验'
  if (activeTab.value?.validationState === 'waiting') return '等待校验'
  if (!document.value) return '没有打开文件'
  return '快速校验'
}

function closeTab(tab: EditorTab): void {
  if (isDirty(tab)) {
    error.value = `请先保存 ${tab.document.name}，再关闭标签。`
    return
  }
  const index = tabs.value.indexOf(tab)
  if (index < 0) return
  const wasActive = tab.document.path === activePath.value
  tabs.value.splice(index, 1)
  if (!wasActive) return
  const replacement = tabs.value[Math.min(index, tabs.value.length - 1)]
  activePath.value = replacement?.document.path ?? ''
  void router.replace(replacement
    ? { path: '/editor', query: { path: replacement.document.path } }
    : { path: '/editor' })
}

function openFirstCase(): void {
  const first = store.assets.find((asset) => asset.owner === 'CASE')
  if (first) void router.replace({ path: '/editor', query: { path: first.path } })
}

watch(requestedPath, (nextPath) => {
  if (nextPath) void openFile(nextPath)
  else openFirstCase()
}, { immediate: true })
onBeforeUnmount(() => {
  window.clearTimeout(validationTimer)
  validationController?.abort()
})
onBeforeRouteLeave(() => !hasDirtyTabs.value || window.confirm('有文件包含未保存修改，确定离开吗？'))
</script>

<template>
  <section class="editor-view">
    <div class="editor-tabs">
      <div
        v-for="tab in tabs"
        :key="tab.document.path"
        class="tab"
        :class="{ active: tab.document.path === activePath }"
        data-test="editor-tab"
      >
        <button class="tab-select" :title="tab.document.path" @click="activateTab(tab.document.path)">
          <span class="file-icon">{{ languageFor(tab.document.path)[0]?.toUpperCase() }}</span>
          <span>{{ tab.document.name }}</span>
          <i v-if="isDirty(tab)">●</i>
        </button>
        <button class="tab-close" :aria-label="`关闭 ${tab.document.name}`" @click="closeTab(tab)"><X :size="13" /></button>
      </div>
      <div v-if="!tabs.length" class="tab empty active">没有打开文件</div>
      <span class="tab-spacer" />
      <button v-if="document && !document.read_only" class="tab-action" :disabled="!dirty" @click="save"><Save :size="14" />保存 <kbd>⌘S</kbd></button>
    </div>
    <div class="editor-body">
      <div class="code-pane">
        <div class="breadcrumb"><span v-for="part in path.split('/')" :key="part">{{ part }}</span></div>
        <div v-if="loading" class="loading-state compact"><span class="spinner" />读取文件</div>
        <CodeEditor
          v-else
          ref="codeEditor"
          v-model="content"
          :path="path"
          :language="language"
          :read-only="document?.read_only"
          :diagnostics="diagnostics"
          @save="save"
        />
      </div>
      <aside class="inspector">
        <div class="inspector-head">
          <span class="eyebrow">SOURCE OWNERSHIP</span>
          <strong>{{ document?.owner ?? 'NO FILE' }}</strong>
          <span v-if="document" class="provenance" :class="document.owner.toLowerCase()">{{ document.owner }}</span>
        </div>
        <dl v-if="document"><dt>Path</dt><dd>{{ document.path }}</dd><dt>Mode</dt><dd>{{ document.read_only ? '只读产物' : '可编辑源文件' }}</dd><dt>SHA-256</dt><dd>{{ document.sha256.slice(0, 16) }}…</dd><dt>Language</dt><dd>{{ language }}</dd></dl>
        <div v-if="document?.read_only" class="inspector-note"><LockKeyhole :size="17" /><div><strong>只读文件</strong><small>Generated 与 report 是产物，请修改源用例或 Profile。</small></div></div>
        <div v-if="dirty" class="inspector-note warning"><AlertTriangle :size="17" /><div><strong>尚未保存</strong><small>校验、生成和运行只读取磁盘已保存版本。</small></div></div>
        <div v-if="savedMessage" class="inspector-note success"><Check :size="17" /><div><strong>{{ savedMessage }}</strong></div></div>
        <div v-if="error" class="inspector-error">{{ error }}</div>
        <RouterLink class="wide-btn secondary-btn" to="/run">进入确定性执行</RouterLink>
      </aside>
    </div>
    <div class="bottom-panel">
      <div class="panel-tabs">
        <button class="active">Problems <span>{{ diagnostics.length }}</span></button>
        <span class="validation-status"><i :class="{ busy: activeTab?.validationState === 'validating' }" />{{ validationLabel() }}</span>
      </div>
      <div v-if="validationError" class="problem-service-error"><AlertTriangle :size="15" /><span>{{ validationError }}</span></div>
      <div v-else-if="diagnostics.length" class="problem-list" role="list" aria-label="编辑器诊断">
        <button
          v-for="diagnostic in diagnostics"
          :key="`${diagnostic.code}-${diagnostic.line}-${diagnostic.column}-${diagnostic.message}`"
          class="problem-row"
          :class="diagnostic.severity"
          role="listitem"
          @click="focusDiagnostic(diagnostic)"
        >
          <AlertTriangle :size="14" />
          <code>{{ diagnostic.code }}</code>
          <span>{{ diagnostic.message }}</span>
          <small>{{ diagnostic.source }} · {{ diagnostic.line }}:{{ diagnostic.column }}</small>
        </button>
      </div>
      <div v-else class="empty-problems">
        <span :class="{ danger: error }">{{ error ? '!' : '✓' }}</span>
        <div>
          <strong>{{ error || '快速校验未发现问题' }}</strong>
          <small v-if="dirty">当前诊断基于编辑器内容；完整门禁仍需保存后运行</small>
          <small v-else>内容与磁盘版本一致；完整门禁仍需运行 Profile 校验</small>
        </div>
      </div>
    </div>
  </section>
</template>
