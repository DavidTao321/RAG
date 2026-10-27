<template>
  <el-tag :type="tagType" size="small">{{ label }}</el-tag>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ status: { type: String, required: true } })

const MAP = {
  pending: { type: 'info', label: '待处理' },
  processing: { type: 'warning', label: '解析中' },
  done: { type: 'success', label: '已入库' },
  failed: { type: 'danger', label: '失败' },
}

const tagType = computed(() => MAP[props.status]?.type || 'info')
const label = computed(() => MAP[props.status]?.label || props.status)
</script>
