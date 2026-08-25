import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { configureTokenFromUrl } from './api/client'
import './styles/base.css'
import './styles/views.css'

configureTokenFromUrl()

createApp(App).use(createPinia()).use(router).mount('#app')
