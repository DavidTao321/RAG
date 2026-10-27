import { del, get, patch, post } from './http'

export const listConversations = (page = 1, size = 50) => get(`/conversations?page=${page}&size=${size}`)
export const createConversation = (title) => post('/conversations', title ? { title } : {})
export const renameConversation = (id, title) => patch(`/conversations/${id}`, { title })
export const deleteConversation = (id) => del(`/conversations/${id}`)
export const listMessages = (id, page = 1, size = 20) =>
  get(`/conversations/${id}/messages?page=${page}&size=${size}`)
