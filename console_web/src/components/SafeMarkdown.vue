<script setup lang="ts">
import { computed } from 'vue'
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'

const props = withDefaults(defineProps<{
  source: string
  emptyText?: string
}>(), {
  emptyText: '没有可预览的 Markdown 内容。',
})

const markdown = new MarkdownIt({
  html: false,
  linkify: false,
  typographer: false,
})

markdown.renderer.rules.link_open = (tokens, index, options, environment, renderer) => {
  const token = tokens[index]
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer')
  return renderer.renderToken(tokens, index, options)
}

const safeHtml = computed(() => String(DOMPurify.sanitize(markdown.render(props.source), {
  ALLOWED_TAGS: [
    'a', 'blockquote', 'br', 'code', 'del', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'hr', 'li', 'ol', 'p', 'pre', 'strong', 'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul',
  ],
  ALLOWED_ATTR: ['class', 'href', 'rel', 'target', 'title'],
  ALLOW_UNKNOWN_PROTOCOLS: false,
})))
</script>

<template>
  <div v-if="source.trim()" class="markdown-preview" v-html="safeHtml" />
  <div v-else class="section-empty tall" data-test="markdown-empty">{{ emptyText }}</div>
</template>
