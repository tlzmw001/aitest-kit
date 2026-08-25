<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { AlertTriangle, Check, LockKeyhole, Save } from '@lucide/vue'
import CodeEditor from '../components/CodeEditor.vue'
import { api } from '../api/client'
import { messageFrom, useWorkspaceStore } from '../stores/workspace'
import type { FileDocument } from '../types'

const route = useRoute()
const router = useRouter()
const store = useWorkspaceStore()
const document = ref<FileDocument | null>(null)
const content = ref('')
const loading = ref(false)
const error = ref('')
const savedMessage = ref('')
const path = computed(() => String(route.query.path || store.assets.find((asset) => asset.owner === 'CASE')?.path || store.assets[0]?.path || ''))
const dirty = computed(() => Boolean(document.value && content.value !== document.value.content))
const language = computed(() => {
  const value = path.value.toLowerCase()
  if (value.endsWith('.md')) return 'markdown'
  if (value.endsWith('.yaml') || value.endsWith('.yml')) return 'yaml'
  if (value.endsWith('.py')) return 'python'
  return 'text'
})

async function load(): Promise<void> {
  if (!path.value) return
  loading.value = true
  error.value = ''
  savedMessage.value = ''
  try {
    document.value = await api.readFile(path.value)
    content.value = document.value.content
  } catch (cause) {
    document.value = null
    content.value = ''
    error.value = messageFrom(cause)
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  if (!document.value || document.value.read_only || !dirty.value) return
  error.value = ''
  try {
    document.value = await api.saveFile(document.value, content.value)
    content.value = document.value.content
    savedMessage.value = '已保存并更新文件 hash'
    window.setTimeout(() => (savedMessage.value = ''), 2400)
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

function openFirstCase(): void {
  const first = store.assets.find((asset) => asset.owner === 'CASE')
  if (first) void router.replace({ path: '/editor', query: { path: first.path } })
}

watch(path, load)
onMounted(() => (path.value ? load() : openFirstCase()))
onBeforeRouteLeave(() => !dirty.value || window.confirm('当前文件有未保存修改，确定离开吗？'))
</script>

<template>
  <section class="editor-view">
    <div class="editor-tabs">
      <div v-if="document" class="tab active"><span class="file-icon">{{ language[0]?.toUpperCase() }}</span>{{ document.name }}<i v-if="dirty">●</i></div>
      <div v-else class="tab active">没有打开文件</div>
      <span class="tab-spacer" />
      <button v-if="document && !document.read_only" class="tab-action" :disabled="!dirty" @click="save"><Save :size="14" />保存 <kbd>⌘S</kbd></button>
    </div>
    <div class="editor-body">
      <div class="code-pane">
        <div class="breadcrumb"><span v-for="part in path.split('/')" :key="part">{{ part }}</span></div>
        <div v-if="loading" class="loading-state compact"><span class="spinner" />读取文件</div>
        <CodeEditor v-else v-model="content" :language="language" :read-only="document?.read_only" @save="save" />
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
        <RouterLink class="wide-btn" to="/run">进入确定性执行</RouterLink>
      </aside>
    </div>
    <div class="bottom-panel">
      <div class="panel-tabs"><button class="active">Problems <span>{{ error ? 1 : 0 }}</span></button><button>Validation</button><button>Output</button></div>
      <div class="empty-problems"><span :class="{ danger: error }">{{ error ? '!' : '✓' }}</span><div><strong>{{ error || '当前编辑器没有阻塞诊断' }}</strong><small>{{ dirty ? '保存后再执行校验和生成同步检查' : '文件内容与磁盘版本一致' }}</small></div></div>
    </div>
  </section>
</template>
