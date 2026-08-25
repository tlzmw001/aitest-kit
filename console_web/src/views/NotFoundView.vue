<script setup lang="ts">
import { ArrowLeft } from '@lucide/vue'
</script>

<template>
  <section class="fatal-state">
    <span class="eyebrow">404 · LOCAL CONSOLE</span>
    <h1>这个视图不存在</h1>
    <p>返回工作台，继续浏览当前 workspace。</p>
    <RouterLink class="primary-btn" to="/"><ArrowLeft :size="15" />返回工作台</RouterLink>
  </section>
</template>
