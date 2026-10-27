<template>
  <div class="md-content" v-html="rendered"></div>
</template>

<script setup>
// Markdown 渲染管线：marked → DOMPurify 消毒（防 XSS）→ highlight.js 代码高亮
// 流式渲染保护：代码块未闭合时降级为纯文本，闭合后再渲染
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

marked.use({
  renderer: {
    code({ text, lang }) {
      let highlighted
      try {
        highlighted = lang && hljs.getLanguage(lang)
          ? hljs.highlight(text, { language: lang }).value
          : hljs.highlightAuto(text).value
      } catch {
        highlighted = text
      }
      return `<pre><code class="hljs">${highlighted}</code></pre>`
    },
  },
})

const props = defineProps({
  content: { type: String, default: '' },
})

const hasUnclosedFence = (text) => (text.match(/```/g) || []).length % 2 === 1

const escapeHtml = (s) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

const rendered = computed(() => {
  if (!props.content) return ''
  if (hasUnclosedFence(props.content)) {
    return `<pre>${escapeHtml(props.content)}</pre>`
  }
  const html = marked.parse(props.content, { async: false })
  return DOMPurify.sanitize(html)
})
</script>
