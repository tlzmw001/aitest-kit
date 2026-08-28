import { createRouter, createWebHashHistory } from 'vue-router'

export function createConsoleRouter() {
  return createRouter({
    history: createWebHashHistory(),
    routes: [
      { path: '/', name: 'workbench', component: () => import('./views/WorkbenchView.vue') },
      { path: '/editor', name: 'editor', component: () => import('./views/EditorView.vue') },
      { path: '/run', name: 'run', component: () => import('./views/RunView.vue') },
      { path: '/reports', name: 'reports', component: () => import('./views/ReportsView.vue') },
      { path: '/diagnostics', name: 'diagnostics', component: () => import('./views/DiagnosticsView.vue') },
      { path: '/environment', name: 'environment', component: () => import('./views/EnvironmentView.vue') },
      { path: '/settings/agent', name: 'agent-connection', component: () => import('./views/AgentConnectionView.vue') },
      { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('./views/NotFoundView.vue') },
    ],
  })
}
