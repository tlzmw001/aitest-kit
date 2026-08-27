<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ArrowUp, Check, Folder, FolderCheck, X } from '@lucide/vue'
import { api } from '../api/client'
import { messageFrom } from '../stores/workspace'
import type { DirectoryListing } from '../types'

const props = defineProps<{ initialPath?: string }>()
const emit = defineEmits<{ select: [path: string]; close: [] }>()
const listing = ref<DirectoryListing | null>(null)
const loading = ref(false)
const error = ref('')

async function load(path?: string): Promise<boolean> {
  loading.value = true
  error.value = ''
  try {
    listing.value = await api.directories(path)
    return true
  } catch (cause) {
    error.value = messageFrom(cause)
    return false
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const initialPath = props.initialPath?.trim()
  const loaded = await load(initialPath || undefined)
  if (!loaded && initialPath) await load('~')
})
</script>

<template>
  <section class="directory-picker" aria-label="浏览本地目录">
    <header>
      <div><span class="eyebrow">LOCAL DIRECTORY</span><strong>选择 workspace 目录</strong></div>
      <button type="button" aria-label="关闭目录浏览" @click="emit('close')"><X :size="16" /></button>
    </header>
    <div class="directory-location">
      <button type="button" :disabled="!listing?.parent || loading" aria-label="返回上级目录" @click="load(listing?.parent || undefined)"><ArrowUp :size="15" /></button>
      <code :title="listing?.path">{{ listing?.path || '读取目录…' }}</code>
      <span v-if="listing?.initialized" class="workspace-mark"><Check :size="12" />AITest</span>
    </div>
    <div v-if="loading" class="directory-state"><span class="spinner" />读取子目录</div>
    <div v-else-if="error" class="directory-state error">{{ error }}</div>
    <div v-else-if="!listing?.directories.length" class="directory-state">当前目录没有可浏览的子目录</div>
    <div v-else class="directory-list">
      <button
        v-for="directory in listing.directories"
        :key="directory.path"
        type="button"
        @click="load(directory.path)"
      >
        <FolderCheck v-if="directory.initialized" :size="16" />
        <Folder v-else :size="16" />
        <span>{{ directory.name }}</span>
        <small v-if="directory.initialized">AITest workspace</small>
      </button>
    </div>
    <footer>
      <small>这里只浏览目录，不读取普通文件内容。</small>
      <button type="button" class="primary-btn" :disabled="!listing" data-test="select-directory" @click="listing && emit('select', listing.path)">选择此目录</button>
    </footer>
  </section>
</template>
