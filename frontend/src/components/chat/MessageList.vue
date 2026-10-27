<template>
  <div ref="listEl" class="message-list">
    <div v-if="hasMore" class="load-more">
      <el-button link type="primary" size="small" :loading="loadingMore" @click="$emit('load-more')">
        加载更早的消息
      </el-button>
    </div>
    <el-empty v-if="!store.messages.length && !store.streaming" description="开始提问吧，我会基于商品知识库为您解答" />
    <MessageItem v-for="m in store.messages" :key="m.key" :msg="m" />
    <!-- 流式中的临时助手消息 -->
    <div v-if="store.streaming" class="streaming-wrap">
      <MessageItem
        :msg="{ key: '__streaming__', role: 'assistant', content: store.streamContent, references: store.streamRefs, streaming: true }"
      />
      <span class="cursor">▍</span>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import MessageItem from './MessageItem.vue'
import { useChatStore } from '../../stores/chat'

defineEmits(['load-more'])
const props = defineProps({ hasMore: Boolean, loadingMore: Boolean })

const store = useChatStore()
const listEl = ref(null)

const scrollToBottom = () => {
  nextTick(() => {
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
  })
}

// 新消息 / 流式内容更新时自动滚到底部
watch(
  () => [store.messages.length, store.streamContent.length],
  () => scrollToBottom(),
)
</script>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.load-more {
  text-align: center;
  margin-bottom: 12px;
}

.cursor {
  display: inline-block;
  animation: blink 1s infinite;
  color: #409eff;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
