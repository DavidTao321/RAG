<template>
  <div class="chat-input">
    <el-input
      v-model="text"
      type="textarea"
      :rows="3"
      resize="none"
      placeholder="输入您关于商品的问题，例如：星耀 X90 Pro 的电池容量和价格是多少？（Enter 发送，Shift+Enter 换行）"
      :disabled="disabled"
      @keydown.enter.exact.prevent="send"
    />
    <div class="input-bar">
      <span class="hint">{{ disabled ? '回答生成中…' : '回答将引用知识库内容并标注来源' }}</span>
      <el-button type="primary" :disabled="disabled || !text.trim()" @click="send">发送</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({ disabled: Boolean })
const emit = defineEmits(['send'])

const text = ref('')

const send = () => {
  const content = text.value.trim()
  if (!content) return
  emit('send', content)
  text.value = ''
}
</script>

<style scoped>
.chat-input {
  border-top: 1px solid #ebeef5;
  padding: 12px 16px;
  background: #fff;
}

.input-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.hint {
  font-size: 12px;
  color: #c0c4cc;
}
</style>
