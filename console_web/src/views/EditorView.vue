<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { AlertTriangle, Check, LockKeyhole, Save, X } from '@lucide/vue'
import {
  DialogContent,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogTitle,
  SplitterGroup,
  SplitterPanel,
  SplitterResizeHandle,
} from 'reka-ui'
import CodeEditor from '../components/CodeEditor.vue'
import DiffEditor from '../components/DiffEditor.vue'
import { ApiError, api } from '../api/client'
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

interface FileConflict {
  path: string
  disk: FileDocument
  localContent: string
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
const conflict = ref<FileConflict | null>(null)
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
let scheduledValidationTab: EditorTab | null = null
let validatingTab: EditorTab | null = null
let initialRouteHandled = false

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
    if (mayReplace) {
      codeEditor.value?.disposeDocument(replacePath)
      tabs.value.splice(replaceIndex, 1, nextTab)
    } else tabs.value.push(nextTab)
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
  if (!tab) return
  await saveTab(tab)
}

const savingTabs = new WeakSet<EditorTab>()

async function saveTab(tab: EditorTab): Promise<void> {
  if (!tab || tab.document.read_only || !isDirty(tab) || savingTabs.has(tab)) return
  savingTabs.add(tab)
  const sentContent = tab.content
  error.value = ''
  try {
    const saved = await api.saveFile(tab.document, sentContent)
    const current = tabs.value.find((item) => item === tab)
    if (current) {
      current.document = saved
      if (current.content === sentContent) current.content = saved.content
    }
    await store.refresh()
    savedMessage.value = '已保存并更新文件 hash'
    if (current) scheduleValidation(current)
    window.setTimeout(() => (savedMessage.value = ''), 2400)
  } catch (cause) {
    if (!tabs.value.includes(tab)) return
    if (cause instanceof ApiError && cause.code === 'FILE_CONFLICT') await openConflict(tab)
    else error.value = messageFrom(cause)
  } finally {
    savingTabs.delete(tab)
  }
}

async function openConflict(tab: EditorTab): Promise<void> {
  try {
    const disk = await api.readFile(tab.document.path)
    const current = tabs.value.find((item) => item === tab)
    if (!current) return
    conflict.value = { path: tab.document.path, disk, localContent: current.content }
    error.value = '文件已在 Console 外发生变化。请比较两个版本后再决定。'
  } catch (cause) {
    error.value = `文件冲突，且无法读取最新磁盘版本：${messageFrom(cause)}`
  }
}

function closeConflict(): void {
  conflict.value = null
}

function handleConflictOpenChange(open: boolean): void {
  if (!open) closeConflict()
}

async function keepLocalVersion(): Promise<void> {
  const state = conflict.value
  if (!state) return
  const tab = tabs.value.find((item) => item.document.path === state.path)
  if (!tab) {
    closeConflict()
    return
  }
  tab.document = state.disk
  error.value = ''
  closeConflict()
  await saveTab(tab)
}

async function loadDiskVersion(): Promise<void> {
  const state = conflict.value
  if (!state) return
  const tab = tabs.value.find((item) => item.document.path === state.path)
  if (!tab) {
    closeConflict()
    return
  }
  tab.document = state.disk
  tab.content = state.disk.content
  tab.diagnostics = []
  tab.validationError = ''
  tab.validationState = 'idle'
  error.value = ''
  closeConflict()
  if (tab.document.path === activePath.value) {
    await nextTick()
    codeEditor.value?.reloadDocument()
    scheduleValidation(tab)
  } else {
    codeEditor.value?.disposeDocument(tab.document.path)
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
  cancelPendingValidation()
  if (!tab || tab.document.read_only) return
  tab.validationState = 'waiting'
  tab.validationError = ''
  scheduledValidationTab = tab
  validationTimer = window.setTimeout(() => {
    scheduledValidationTab = null
    void validateTab(tab)
  }, 350)
}

function cancelPendingValidation(): void {
  window.clearTimeout(validationTimer)
  validationTimer = undefined
  if (scheduledValidationTab?.validationState === 'waiting') scheduledValidationTab.validationState = 'idle'
  scheduledValidationTab = null
  if (validatingTab?.validationState === 'validating') validatingTab.validationState = 'idle'
  validatingTab = null
  validationController?.abort()
  validationController = null
}

async function validateTab(tab: EditorTab): Promise<void> {
  const contentAtRequest = tab.content
  const controller = new AbortController()
  validationController = controller
  validatingTab = tab
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
    if (validationController === controller) {
      validationController = null
      validatingTab = null
    }
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
  if (isDirty(tab) && !window.confirm(`${tab.document.name} 包含未保存修改，确定放弃修改并关闭吗？`)) return
  const index = tabs.value.indexOf(tab)
  if (index < 0) return
  const wasActive = tab.document.path === activePath.value
  if (scheduledValidationTab === tab || validatingTab === tab) cancelPendingValidation()
  codeEditor.value?.disposeDocument(tab.document.path)
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
  if (nextPath) {
    initialRouteHandled = true
    void openFile(nextPath)
  } else if (!initialRouteHandled) {
    initialRouteHandled = true
    openFirstCase()
  }
}, { immediate: true })
onBeforeUnmount(() => {
  cancelPendingValidation()
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
    <SplitterGroup id="editor-inspector-split" direction="horizontal" auto-save-id="aitest-editor-inspector" class="editor-body">
      <SplitterPanel id="editor-code-panel" :default-size="76" :min-size="55" class="editor-code-panel">
        <div class="code-pane">
        <div class="breadcrumb"><span v-for="(part, index) in path.split('/')" :key="`${index}-${part}`">{{ part }}</span></div>
        <div class="code-editor-stage">
          <CodeEditor
            ref="codeEditor"
            v-model="content"
            :path="path"
            :language="language"
            :read-only="document?.read_only"
            :diagnostics="diagnostics"
            :theme="preferences.editorTheme"
            @save="save"
          />
          <div v-if="loading" class="loading-state compact editor-loading"><span class="spinner" />读取文件</div>
        </div>
        </div>
      </SplitterPanel>
      <SplitterResizeHandle id="editor-inspector-handle" class="editor-split-handle" aria-label="调整源码与 Inspector 宽度" />
      <SplitterPanel id="editor-inspector-panel" :default-size="24" :min-size="18" :max-size="40" class="editor-inspector-panel">
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
      </SplitterPanel>
    </SplitterGroup>
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

  <DialogRoot :open="Boolean(conflict)" @update:open="handleConflictOpenChange">
    <DialogPortal>
      <DialogOverlay class="asset-modal-backdrop conflict-dialog-backdrop">
        <DialogContent as="section" class="conflict-dialog">
          <DialogDescription class="sr-only">比较最新磁盘版本与当前未保存的编辑内容。</DialogDescription>
          <header>
            <div><span class="eyebrow">FILE CONFLICT</span><DialogTitle as="strong">文件已在外部修改</DialogTitle></div>
            <button aria-label="关闭版本对比" @click="closeConflict"><X :size="17" /></button>
          </header>
          <div v-if="conflict" class="conflict-copy">
            <p>左侧是最新磁盘版本，右侧是你尚未保存的编辑内容。AITest 不会自动覆盖任何一侧。</p>
            <code>{{ conflict.path }}</code>
          </div>
          <div v-if="conflict" class="conflict-diff-stage">
            <DiffEditor
              :original="conflict.disk.content"
              :modified="conflict.localContent"
              :path="conflict.path"
              :language="languageFor(conflict.path)"
              :theme="preferences.editorTheme"
            />
          </div>
          <footer>
            <button class="secondary-btn" @click="closeConflict">继续编辑</button>
            <button class="primary-btn" @click="keepLocalVersion">保留我的修改并覆盖磁盘</button>
            <button class="conflict-load-btn" @click="loadDiskVersion">丢弃当前修改并载入磁盘版本</button>
          </footer>
        </DialogContent>
      </DialogOverlay>
    </DialogPortal>
  </DialogRoot>
</template>
