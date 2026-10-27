<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <div>
          <h3 style="margin: 0 0 4px">知识库文档管理</h3>
          <span class="sub">支持 PDF / Word / Excel / TXT / Markdown，上传后自动解析分块并向量化入库</span>
        </div>
        <el-upload
          :auto-upload="false"
          :show-file-list="false"
          accept=".pdf,.docx,.xlsx,.txt,.md"
          :on-change="onFileChange"
        >
          <el-button type="primary" :icon="Upload" :loading="uploading">上传文档</el-button>
        </el-upload>
      </div>

      <el-table :data="docs" v-loading="loading" style="width: 100%; margin-top: 12px">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="filename" label="文件名" min-width="220" show-overflow-tooltip />
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.file_type.toUpperCase() }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="90">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <DocStatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="分块数" width="80" />
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" :disabled="row.status !== 'done'" @click="showChunks(row)">
              分块预览
            </el-button>
            <el-button link type="warning" size="small" :disabled="row.status === 'processing'" @click="onReindex(row)">
              重建索引
            </el-button>
            <el-button link type="danger" size="small" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        :page-size="size"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 14px; justify-content: flex-end"
        @current-change="load"
      />
    </el-card>

    <!-- 失败原因展示 -->
    <el-alert
      v-if="failedDoc"
      style="margin-top: 12px"
      :title="`「${failedDoc.filename}」解析失败：${failedDoc.error_msg}`"
      type="error"
      show-icon
      :closable="true"
    />

    <!-- 分块预览弹窗 -->
    <el-dialog v-model="chunkDialog" title="分块预览" width="720px" top="6vh">
      <div class="chunk-list">
        <div v-for="c in chunks" :key="c.id" class="chunk-item">
          <b>#{{ c.chunk_index }}</b>（{{ c.char_count }} 字）
          <p>{{ c.content }}</p>
        </div>
      </div>
      <template #footer>
        <el-pagination
          v-model:current-page="chunkPage"
          :page-size="chunkSize"
          :total="chunkTotal"
          layout="total, prev, pager, next"
          @current-change="loadChunks"
        />
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import DocStatusTag from '../../components/admin/DocStatusTag.vue'
import { deleteDocument, listDocuments, previewChunks, reindexDocument, uploadDocument } from '../../api/document'

const docs = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(10)
const loading = ref(false)
const uploading = ref(false)
const failedDoc = ref(null)

// 分块预览
const chunkDialog = ref(false)
const chunks = ref([])
const chunkPage = ref(1)
const chunkSize = ref(10)
const chunkTotal = ref(0)
const currentDoc = ref(null)

let pollTimer = null

const load = async () => {
  loading.value = true
  try {
    const data = await listDocuments(page.value, size.value)
    docs.value = data.items
    total.value = data.total
    failedDoc.value = data.items.find((d) => d.status === 'failed') || null
    // 有待处理/处理中文档时 2s 轮询刷新
    const hasActive = data.items.some((d) => d.status === 'pending' || d.status === 'processing')
    if (hasActive && !pollTimer) {
      pollTimer = setInterval(load, 2000)
    } else if (!hasActive && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

const onFileChange = async (uploadFile) => {
  uploading.value = true
  try {
    await uploadDocument(uploadFile.raw)
    ElMessage.success(`「${uploadFile.name}」已上传，后台解析中…`)
    page.value = 1
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    uploading.value = false
  }
}

const onDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定删除「${row.filename}」？其向量与分块将一并清除，删除后问答将不再引用该文档。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteDocument(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    /* 取消 */
  }
}

const onReindex = async (row) => {
  try {
    await ElMessageBox.confirm(`对「${row.filename}」重新解析并重建向量索引？`, '重建索引', {
      type: 'info',
      confirmButtonText: '重建',
    })
    await reindexDocument(row.id)
    ElMessage.success('已开始重建，稍后自动刷新状态')
    await load()
  } catch {
    /* 取消 */
  }
}

const showChunks = (row) => {
  currentDoc.value = row
  chunkPage.value = 1
  chunkDialog.value = true
  loadChunks()
}

const loadChunks = async () => {
  if (!currentDoc.value) return
  try {
    const data = await previewChunks(currentDoc.value.id, chunkPage.value, chunkSize.value)
    chunks.value = data.items
    chunkTotal.value = data.total
  } catch (e) {
    // 预览接口失败不能产生未处理的 Promise 拒绝，弹窗内给出明确提示
    ElMessage.error(e.message || '分块加载失败')
  }
}

const formatSize = (bytes) => {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

const formatTime = (iso) => (iso ? iso.replace('T', ' ').slice(0, 19) : '-')

onMounted(load)
onBeforeUnmount(() => pollTimer && clearInterval(pollTimer))
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sub {
  font-size: 12px;
  color: #909399;
}

.chunk-list {
  max-height: 50vh;
  overflow-y: auto;
}

.chunk-item {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 8px;
  font-size: 13px;
}

.chunk-item p {
  margin: 4px 0 0;
  color: #606266;
  white-space: pre-wrap;
}
</style>
