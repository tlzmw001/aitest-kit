import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api, ApiError } from '../api/client'
import type { Asset, Job, Module, ReportSummary, Suite, Target, Task, TestCase, WorkspaceSnapshot } from '../types'

export const useWorkspaceStore = defineStore('workspace', () => {
  const snapshot = ref<WorkspaceSnapshot | null>(null)
  const loading = ref(false)
  const error = ref('')
  const pendingInitializationPath = ref('')
  const currentJob = ref<Job | null>(null)

  const targets = computed<Target[]>(() => snapshot.value?.targets ?? [])
  const modules = computed<Module[]>(() => targets.value.flatMap((target) => target.modules))
  const suites = computed<Suite[]>(() => modules.value.flatMap((module) => module.suites))
  const cases = computed<TestCase[]>(() => suites.value.flatMap((suite) => suite.cases))
  const tasks = computed<Task[]>(() => snapshot.value?.tasks ?? [])
  const recentReports = computed<ReportSummary[]>(() => snapshot.value?.recent_reports ?? [])
  const assets = computed<Asset[]>(() => [
    ...targets.value.flatMap((target) => target.config_path
      ? [{ path: target.config_path, name: 'target.yaml', owner: 'CONFIG' as const, exists: true }]
      : []),
    ...modules.value.flatMap((module) => module.assets),
    ...suites.value.flatMap((suite) => suite.assets),
    ...tasks.value.map((task) => ({ path: task.path, name: task.path.split('/').pop() || task.name, owner: 'CONFIG' as const, exists: true })),
  ])

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      snapshot.value = await api.workspace()
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === 'WORKSPACE_NOT_OPEN') {
        snapshot.value = null
      } else {
        error.value = messageFrom(cause)
      }
    } finally {
      loading.value = false
    }
  }

  async function open(path: string): Promise<boolean> {
    loading.value = true
    error.value = ''
    pendingInitializationPath.value = ''
    try {
      snapshot.value = await api.openWorkspace(path)
      return true
    } catch (cause) {
      error.value = messageFrom(cause)
      if (cause instanceof ApiError && cause.code === 'WORKSPACE_NOT_INITIALIZED') {
        pendingInitializationPath.value = path
      }
      return false
    } finally {
      loading.value = false
    }
  }

  async function initialize(path: string): Promise<boolean> {
    loading.value = true
    error.value = ''
    try {
      snapshot.value = await api.initializeWorkspace(path)
      pendingInitializationPath.value = ''
      return true
    } catch (cause) {
      error.value = messageFrom(cause)
      return false
    } finally {
      loading.value = false
    }
  }

  function dismissInitialization(): void {
    pendingInitializationPath.value = ''
  }

  function setCurrentJob(job: Job | null): void {
    currentJob.value = job
  }

  function setSnapshot(next: WorkspaceSnapshot): void {
    snapshot.value = next
    error.value = ''
  }

  return {
    snapshot,
    loading,
    error,
    pendingInitializationPath,
    currentJob,
    targets,
    modules,
    suites,
    cases,
    tasks,
    assets,
    recentReports,
    refresh,
    open,
    initialize,
    dismissInitialization,
    setSnapshot,
    setCurrentJob,
  }
})

export function messageFrom(cause: unknown): string {
  if (cause instanceof ApiError) return `${cause.code}: ${cause.message}`
  return cause instanceof Error ? cause.message : '无法完成操作'
}
