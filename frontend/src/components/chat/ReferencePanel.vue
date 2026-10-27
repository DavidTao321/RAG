<template>
  <div class="ref-panel">
    <div class="panel-head">
      <span>📚 引用来源</span>
      <el-button v-if="store.panelRefs.length" link size="small" @click="store.setActiveRef(null)">
        取消高亮
      </el-button>
    </div>
    <el-empty
      v-if="!store.panelRefs.length"
      :image-size="60"
      description="暂无引用，提问后将在此显示回答引用的知识库片段"
    />
    <template v-else>
      <div
        v-for="ref in store.panelRefs"
        :key="ref.index"
        class="ref-item"
        :class="{ active: store.activeRefIndex === ref.index }"
        @click="selectRef(ref)"
      >
        <div class="ref-title">
          <b>[{{ ref.index }}]</b> {{ ref.doc_name }}
          <span v-if="ref.score != null" class="ref-score">相关度 {{ ref.score }}</span>
        </div>
        <div class="ref-content">{{ ref.content }}</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { useChatStore } from '../../stores/chat'

const store = useChatStore()

const selectRef = (ref) => {
  store.setActiveRef(ref.index)
}
</script>

<style scoped>
.ref-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fafafa;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  font-weight: 600;
  border-bottom: 1px solid #ebeef5;
  background: #fff;
}

.ref-content {
  font-size: 13px;
  color: #606266;
  white-space: pre-wrap;
  max-height: 160px;
  overflow-y: auto;
  margin-top: 4px;
}

.ref-title {
  font-size: 13px;
  color: #303133;
  margin-bottom: 2px;
}

.ref-panel > .el-empty,
.ref-panel > .ref-item {
  margin: 10px 12px;
}
</style>
