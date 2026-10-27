<template>
  <div class="msg-row" :class="msg.role">
    <div class="msg-bubble">
      <!-- 用户消息：纯文本 -->
      <div v-if="msg.role === 'user'" class="user-text">{{ msg.content }}</div>
      <!-- 助手消息：Markdown + 可点击引用编号 -->
      <template v-else>
        <template v-for="(seg, i) in segments" :key="i">
          <MarkdownView v-if="seg.type === 'text'" :content="seg.text" />
          <span
            v-else
            class="cite-mark"
            :class="{ active: isActiveCite(seg) }"
            @click="onCiteClick(seg)"
          >
            [{{ seg.indices.join(',') }}]
          </span>
        </template>
      </template>
    </div>
    <div v-if="msg.role === 'assistant' && msg.id" class="msg-meta">
      <el-tag v-if="msg.cache_hit" size="small" type="warning" effect="plain">缓存命中</el-tag>
      <span v-if="msg.stats?.total_ms" class="time-cost">{{ msg.stats.total_ms }}ms</span>
      <el-button
        v-if="msg.references?.length"
        link
        type="primary"
        size="small"
        @click="showRefs"
      >
        查看引用 ({{ msg.references.length }})
      </el-button>
      <template v-if="!msg.streaming">
        <el-button link size="small" :type="feedback === 1 ? 'success' : 'info'" @click="vote(1)">
          👍
        </el-button>
        <el-button link size="small" :type="feedback === -1 ? 'danger' : 'info'" @click="vote(-1)">
          👎
        </el-button>
      </template>
    </div>
  </div>
</template>

<script setup>
// 回答内 [n] 引用编号 ↔ 引用面板 双向联动
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import MarkdownView from '../common/MarkdownView.vue'
import { useChatStore } from '../../stores/chat'
import { submitFeedback } from '../../api/stats'

const props = defineProps({
  msg: { type: Object, required: true },
})

const store = useChatStore()
const feedback = ref(0)

const CITATION_RE = /\[(\d+(?:[,\s]\d+)*)\]/g

// 将内容按引用编号切分为 文本段 / 引用标记段；越界编号渲染为普通文本
const segments = computed(() => {
  const maxRef = props.msg.references?.length || 0
  const parts = []
  let last = 0
  let m
  const re = new RegExp(CITATION_RE.source, 'g')
  while ((m = re.exec(props.msg.content))) {
    if (m.index > last) parts.push({ type: 'text', text: props.msg.content.slice(last, m.index) })
    const indices = m[1].replace(/,/g, ' ').split(/\s+/).map(Number).filter((n) => n >= 1 && n <= maxRef)
    if (indices.length) parts.push({ type: 'cite', indices })
    else parts.push({ type: 'text', text: m[0] })
    last = m.index + m[0].length
  }
  if (last < props.msg.content.length) parts.push({ type: 'text', text: props.msg.content.slice(last) })
  return parts
})

const isActiveCite = (seg) => store.activeRefIndex !== null && seg.indices.includes(store.activeRefIndex)

const onCiteClick = (seg) => {
  store.setActiveRef(seg.indices[0])
  // 打开/切换引用面板到本条消息
  store.panelMsgKey = props.msg.key
  store.panelRefs = props.msg.references
}

const showRefs = () => {
  store.panelMsgKey = props.msg.key
  store.panelRefs = props.msg.references
  store.setActiveRef(null)
}

const vote = async (rating) => {
  try {
    await submitFeedback(props.msg.id, rating, null)
    feedback.value = rating
    ElMessage.success(rating === 1 ? '感谢反馈！' : '已记录，我们会持续改进')
  } catch (e) {
    ElMessage.error(e.message)
  }
}
</script>

<style scoped>
.msg-row {
  flex-direction: column;
  align-items: flex-start;
}

.msg-row.user {
  align-items: flex-end;
}

.user-text {
  white-space: pre-wrap;
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.time-cost {
  color: #c0c4cc;
}
</style>
