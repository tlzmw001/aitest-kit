<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArchiveRestore, Plus, Trash2, X } from '@lucide/vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { messageFrom, useWorkspaceStore } from '../stores/workspace'
import type { AssetIdentity, DeletePreview, ModuleTypeOption, TrashEntry } from '../types'

type CreateKind = 'target' | 'module' | 'suite' | 'task'

const store = useWorkspaceStore()
const router = useRouter()
const mode = ref<'create' | 'delete' | 'trash' | null>(null)
const kind = ref<CreateKind>('target')
const name = ref('')
const sourceRoot = ref('')
const target = ref('')
const moduleName = ref('')
const moduleType = ref('')
const description = ref('')
const registerSuite = ref(true)
const selectedSuites = ref<string[]>([])
const moduleTypes = ref<ModuleTypeOption[]>([])
const preview = ref<DeletePreview | null>(null)
const trashEntries = ref<TrashEntry[]>([])
const busy = ref(false)
const error = ref('')

const modules = computed(() => store.targets.find((item) => item.name === target.value)?.modules ?? [])
const suiteOptions = computed(() => store.suites.map((suite) => ({ name: suite.name, path: suite.manifest_path })))
const title = computed(() => mode.value === 'delete' ? '删除资产' : mode.value === 'trash' ? '回收站' : '新建测试资产')

async function loadOptions(): Promise<void> {
  if (moduleTypes.value.length) return
  const options = await api.assetOptions()
  moduleTypes.value = options.module_types
  moduleType.value ||= moduleTypes.value[0]?.name ?? ''
}

async function openCreate(nextKind: CreateKind = 'target', defaults: { target?: string; module?: string } = {}): Promise<void> {
  reset()
  mode.value = 'create'
  kind.value = nextKind
  target.value = defaults.target || store.targets[0]?.name || ''
  moduleName.value = defaults.module || modules.value[0]?.name || ''
  try {
    await loadOptions()
  } catch (cause) {
    error.value = messageFrom(cause)
  }
}

async function openDelete(identity: AssetIdentity): Promise<void> {
  reset()
  mode.value = 'delete'
  busy.value = true
  try {
    preview.value = await api.deletePreview(identity)
  } catch (cause) {
    error.value = messageFrom(cause)
  } finally {
    busy.value = false
  }
}

async function openTrash(): Promise<void> {
  reset()
  mode.value = 'trash'
  await refreshTrash()
}

async function refreshTrash(): Promise<void> {
  busy.value = true
  try {
    trashEntries.value = (await api.trash()).entries
  } catch (cause) {
    error.value = messageFrom(cause)
  } finally {
    busy.value = false
  }
}

function reset(): void {
  error.value = ''
  preview.value = null
  name.value = ''
  sourceRoot.value = ''
  description.value = ''
  selectedSuites.value = []
  registerSuite.value = true
}

function close(): void {
  mode.value = null
}

function syncParentChoices(): void {
  if (!store.targets.some((item) => item.name === target.value)) target.value = store.targets[0]?.name || ''
  const choices = modules.value
  if (!choices.some((item) => item.name === moduleName.value)) moduleName.value = choices[0]?.name || ''
}

async function createAsset(): Promise<void> {
  if (!name.value.trim()) return
  busy.value = true
  error.value = ''
  try {
    let snapshot
    if (kind.value === 'target') {
      snapshot = await api.createTarget({ name: name.value.trim(), source_root: sourceRoot.value.trim() })
    } else if (kind.value === 'module') {
      snapshot = await api.createModule({ target: target.value, name: name.value.trim(), module_type: moduleType.value })
    } else if (kind.value === 'suite') {
      snapshot = await api.createSuite({
        target: target.value,
        module: moduleName.value,
        name: name.value.trim(),
        register: registerSuite.value,
      })
    } else {
      snapshot = await api.createTask({
        name: name.value.trim(),
        description: description.value.trim(),
        suite_files: selectedSuites.value,
      })
    }
    store.setSnapshot(snapshot)
    const path = createdPrimaryPath(kind.value, name.value.trim())
    close()
    if (path) await router.push({ path: '/editor', query: { path } })
  } catch (cause) {
    error.value = messageFrom(cause)
  } finally {
    busy.value = false
  }
}

function createdPrimaryPath(createdKind: CreateKind, createdName: string): string {
  if (createdKind === 'target') return store.targets.find((item) => item.name === createdName)?.config_path || ''
  if (createdKind === 'module') {
    return store.targets.find((item) => item.name === target.value)?.modules
      .find((item) => item.name === createdName)?.assets.find((asset) => asset.name === 'module.yaml')?.path || ''
  }
  if (createdKind === 'suite') {
    return store.suites.find((item) => item.name === createdName && item.manifest_path.includes(`/${target.value}/`))
      ?.assets.find((asset) => asset.name === 'cases.md')?.path || ''
  }
  return store.tasks.find((item) => item.name === createdName)?.path || ''
}

async function confirmDelete(): Promise<void> {
  if (!preview.value?.can_delete) return
  busy.value = true
  try {
    const result = await api.deleteAsset(preview.value.identity)
    store.setSnapshot(result.workspace)
    close()
  } catch (cause) {
    error.value = messageFrom(cause)
  } finally {
    busy.value = false
  }
}

async function restore(entry: TrashEntry): Promise<void> {
  busy.value = true
  error.value = ''
  try {
    store.setSnapshot(await api.restoreTrash(entry.entry_id))
    await refreshTrash()
  } catch (cause) {
    error.value = messageFrom(cause)
  } finally {
    busy.value = false
  }
}

function identityLabel(identity: AssetIdentity): string {
  if (identity.kind === 'target') return `target / ${identity.target}`
  if (identity.kind === 'module') return `${identity.target} / module / ${identity.module}`
  if (identity.kind === 'suite') return `${identity.target} / ${identity.module} / suite / ${identity.suite}`
  return `task / ${identity.task}`
}

defineExpose({ openCreate, openDelete, openTrash })
</script>

<template>
  <div v-if="mode" class="asset-modal-backdrop" @click.self="close">
    <section class="asset-modal" role="dialog" aria-modal="true" :aria-label="title">
      <header>
        <div><span class="eyebrow">WORKSPACE ASSETS</span><strong>{{ title }}</strong></div>
        <button aria-label="关闭" @click="close"><X :size="17" /></button>
      </header>

      <form v-if="mode === 'create'" class="asset-form" @submit.prevent="createAsset">
        <label>资产类型
          <select v-model="kind" @change="syncParentChoices">
            <option value="target">Target</option><option value="module">Module</option>
            <option value="suite">Suite</option><option value="task">Task</option>
          </select>
        </label>
        <label v-if="kind === 'module' || kind === 'suite'">Target
          <select v-model="target" @change="syncParentChoices"><option v-for="item in store.targets" :key="item.name">{{ item.name }}</option></select>
        </label>
        <label v-if="kind === 'suite'">Module
          <select v-model="moduleName"><option v-for="item in modules" :key="item.name">{{ item.name }}</option></select>
        </label>
        <label>名称
          <input v-model="name" autocomplete="off" :placeholder="kind === 'target' ? '例如 demo_service' : kind === 'module' ? '例如 orders_api' : kind === 'task' ? '例如 nightly' : '例如 orders-smoke'" />
          <small v-if="kind === 'target' || kind === 'module'">使用 Python 标识符，只能包含字母、数字和下划线。</small>
        </label>
        <label v-if="kind === 'target'">待测系统源码路径（可选）<input v-model="sourceRoot" autocomplete="off" /></label>
        <label v-if="kind === 'module'">Module type
          <select v-model="moduleType"><option v-for="item in moduleTypes" :key="item.name" :value="item.name">{{ item.name }} · {{ item.description }}</option></select>
        </label>
        <label v-if="kind === 'task'">说明（可选）<textarea v-model="description" rows="2" /></label>
        <fieldset v-if="kind === 'task'">
          <legend>包含的 suite</legend>
          <label v-for="suite in suiteOptions" :key="suite.path" class="check-row"><input v-model="selectedSuites" type="checkbox" :value="suite.path" /><span>{{ suite.name }}</span><code>{{ suite.path }}</code></label>
          <small v-if="!suiteOptions.length">当前 workspace 没有 suite。</small>
        </fieldset>
        <label v-if="kind === 'suite'" class="check-row"><input v-model="registerSuite" type="checkbox" /><span>创建后注册到 module 聚合执行</span></label>
        <p v-if="kind === 'suite'" class="asset-note">将创建 suite.yaml、cases.md 和 suite profile。case 内容由你在 Markdown 中编辑。</p>
        <p v-if="error" class="inline-error">{{ error }}</p>
        <footer><button type="button" class="secondary-btn" @click="close">取消</button><button class="primary-btn" :disabled="busy || !name.trim() || (kind === 'task' && !selectedSuites.length)"><Plus :size="15" />创建</button></footer>
      </form>

      <div v-else-if="mode === 'delete'" class="delete-preview">
        <div v-if="busy" class="directory-state"><span class="spinner" />检查引用关系</div>
        <template v-else-if="preview">
          <strong>{{ identityLabel(preview.identity) }}</strong>
          <p>{{ preview.message }}</p>
          <dl><dt>移动</dt><dd><code v-for="path in preview.paths" :key="path">{{ path }}</code></dd><dt>同步修改</dt><dd><code v-for="path in preview.modified_files" :key="path">{{ path }}</code><span v-if="!preview.modified_files.length">无</span></dd></dl>
          <div v-if="preview.blockers.length" class="delete-blockers"><strong>当前不能删除</strong><span v-for="blocker in preview.blockers" :key="blocker">{{ blocker }}</span></div>
        </template>
        <p v-if="error" class="inline-error">{{ error }}</p>
        <footer><button class="secondary-btn" @click="close">取消</button><button class="danger-btn" :disabled="busy || !preview?.can_delete" data-test="confirm-delete" @click="confirmDelete"><Trash2 :size="15" />移到回收站</button></footer>
      </div>

      <div v-else class="trash-list">
        <div v-if="busy && !trashEntries.length" class="directory-state"><span class="spinner" />读取回收站</div>
        <div v-else-if="!trashEntries.length" class="directory-state">回收站为空</div>
        <article v-for="entry in trashEntries" :key="entry.entry_id"><div><strong>{{ identityLabel(entry.identity) }}</strong><small>{{ new Date(entry.created_at).toLocaleString('zh-CN') }}</small><code>{{ entry.paths[0] }}</code></div><button class="secondary-btn" :disabled="busy" @click="restore(entry)"><ArchiveRestore :size="14" />恢复</button></article>
        <p v-if="error" class="inline-error">{{ error }}</p>
      </div>
    </section>
  </div>
</template>
