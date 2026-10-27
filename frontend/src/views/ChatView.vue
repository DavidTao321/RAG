<template>
  <el-container class="chat-page">
    <el-aside width="270px">
      <SessionList
        :sessions="store.sessions"
        :current-id="store.currentConversationId"
        @select="selectSession"
        @new-session="newSession"
        @rename="onRename"
        @remove="onRemove"
      />
    </el-aside>
    <el-main class="chat-main">
      <MessageList
        :has-more="store.messages.length < store.messagesTotal"
        :loading-more="loadingMore"
        @load-more="loadMoreMessages"
      />
      <ChatInput :disabled="store.streaming" @send="send" />
    </el-main>
    <el-aside width="330px" class="ref-aside">
      <ReferencePanel />
    </el-aside>
  </el-container>
</template>

<script setup>
import { onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SessionList from '../components/chat/SessionList.vue'
import MessageList from '../components/chat/MessageList.vue'
import ChatInput from '../components/chat/ChatInput.vue'
import ReferencePanel from '../components/chat/ReferencePanel.vue'
import { useChatStore } from '../stores/chat'
import { streamChat } from '../api/sse'
import { deleteConversation, listConversations, listMessages, renameConversation } from '../api/conversation'

const store = useChatStore()

let loadingMore = false

const uid = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

const loadSessions = async () => {
  try {
    const data = await listConversations(1, 50)
    store.sessions = data.items
    store.sessionsTotal = data.total
  } catch (e) {
    ElMessage.error(e.message)
  }
}

const loadMessages = async (conversationId, page = 1) => {
  try {
    const data = await listMessages(conversationId, page, 20)
    store.messagesTotal = data.total
    store.messagesPage = page
    const items = [...data.items].reverse().map((m) => ({
      key: uid(),
      id: m.id,
      role: m.role,
      content: m.content,
      references: m.references || [],
      cache_hit: m.cache_hit,
      stats: { total_ms: null },
    }))
    store.messages = items
  } catch (e) {
    ElMessage.error(e.message)
  }
}

const selectSession = async (id) => {
  if (store.currentConversationId === id) return
  store.setConversation(id)
  await loadMessages(id, 1)
}

const newSession = () => {
  store.resetChat()
  store.setPanelRefs([], null)
}

const loadMoreMessages = async () => {
  if (!store.currentConversationId || loadingMore) return
  loadingMore = true
  try {
    const page = store.messagesPage + 1
    const data = await listMessages(store.currentConversationId, page, 20)
    store.messagesPage = page
    const older = [...data.items].reverse().map((m) => ({
      key: uid(),
      id: m.id,
      role: m.role,
      content: m.content,
      references: m.references || [],
      cache_hit: m.cache_hit,
      stats: { total_ms: null },
    }))
    store.messages = [...older, ...store.messages]
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loadingMore = false
  }
}

const onRename = async (session) => {
  try {
    const { value } = await ElMessageBox.prompt('输入新的会话名称', '重命名', {
      inputValue: session.title,
      inputValidator: (v) => (v && v.trim() ? true : '名称不能为空'),
    })
    await renameConversation(session.id, value.trim())
    ElMessage.success('已重命名')
    await loadSessions()
  } catch {
    /* 取消 */
  }
}

const onRemove = async (session) => {
  try {
    await ElMessageBox.confirm(`确定删除会话「${session.title}」？历史消息将一并删除。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteConversation(session.id)
    if (store.currentConversationId === session.id) newSession()
    await loadSessions()
    ElMessage.success('会话已删除')
  } catch {
    /* 取消 */
  }
}

// SSE 问答事件协议（api/sse.js 解析后端 chat 接口）：meta（会话元信息，新会话时带回 id）
// → delta（逐 token 增量）→ references（引用片段，与右侧面板联动）→ done（完整消息落定）
// / error（流中断）
const send = async (text) => {
  // 用户消息先入列表立即上屏；回答由 store.streamContent 增量累积，done 时以 assistant 消息落定
  store.messages.push({ key: uid(), role: 'user', content: text })
  store.beginStreaming()
  // streamKey 是本次流式回答的唯一 key：assistant 消息用它入列表，
  // onReferences 时 setPanelRefs(refs, streamKey) 建立"消息 ↔ 引用面板"的双向联动
  const streamKey = uid()
  try {
    await streamChat(
      { conversation_id: store.currentConversationId, question: text },
      {
        onMeta: (m) => {
          if (!store.currentConversationId) {
            store.currentConversationId = m.conversation_id
            loadSessions() // 新会话：刷新左侧列表（标题由后端生成）
          }
        },
        onDelta: (d) => {
          store.streamContent += d.content
        },
        onReferences: (refs) => {
          store.streamRefs = refs
          store.setPanelRefs(refs, streamKey)
        },
        onDone: (d) => {
          store.messages.push({
            key: streamKey,
            id: d.message_id,
            role: 'assistant',
            content: store.streamContent,
            references: store.streamRefs,
            cache_hit: d.cache_hit,
            stats: d,
          })
          store.endStreaming()
          loadSessions()
        },
        onError: (e) => {
          store.endStreaming()
          ElMessage.error(e.message)
        },
      },
    )
  } catch (e) {
    store.endStreaming()
    ElMessage.error(e.message)
  }
}

onMounted(async () => {
  await loadSessions()
  // 默认选中最近会话
  if (store.sessions.length) {
    await selectSession(store.sessions[0].id)
  }
})
</script>

<style scoped>
.chat-page {
  height: 100vh;
}

.chat-main {
  display: flex;
  flex-direction: column;
  padding: 0;
  background: #f5f7fa;
}

.chat-main > :first-child {
  flex: 1;
  overflow-y: auto;
}

.ref-aside {
  border-left: 1px solid #ebeef5;
  overflow-y: auto;
}
</style>
