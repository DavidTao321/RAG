import { defineStore } from 'pinia'

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessions: [],
    sessionsTotal: 0,
    currentConversationId: null,
    messages: [],
    messagesTotal: 0,
    messagesPage: 1,
    streaming: false,
    // 流式中的临时消息（渲染用）
    streamContent: '',
    streamRefs: [],
    // 引用联动：回答内 [n] ↔ 引用面板
    activeRefIndex: null,
    panelRefs: [],
    panelMsgKey: null,
  }),
  getters: {
    currentSession: (s) => s.sessions.find((c) => c.id === s.currentConversationId) || null,
  },
  actions: {
    resetChat() {
      this.currentConversationId = null
      this.messages = []
      this.messagesTotal = 0
      this.messagesPage = 1
      this.streaming = false
      this.streamContent = ''
      this.streamRefs = []
      this.activeRefIndex = null
    },
    setConversation(id) {
      this.currentConversationId = id
      this.messages = []
      this.messagesTotal = 0
      this.messagesPage = 1
      this.activeRefIndex = null
    },
    beginStreaming() {
      this.streaming = true
      this.streamContent = ''
      this.streamRefs = []
      this.activeRefIndex = null
    },
    endStreaming() {
      this.streaming = false
      this.streamContent = ''
      this.streamRefs = []
    },
    setActiveRef(index) {
      this.activeRefIndex = index
    },
    setPanelRefs(refs, msgKey) {
      this.panelRefs = refs || []
      this.panelMsgKey = msgKey ?? null
    },
  },
})
