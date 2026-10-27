import { del, get, post } from './http'

export const listDocuments = (page = 1, size = 20, status = '') =>
  get(`/documents?page=${page}&size=${size}${status ? `&status=${status}` : ''}`)

export const uploadDocument = (file) => {
  const form = new FormData()
  form.append('file', file)
  return post('/documents/upload', form)
}

export const deleteDocument = (id) => del(`/documents/${id}`)
export const reindexDocument = (id) => post(`/documents/${id}/reindex`)
export const previewChunks = (id, page = 1, size = 20) =>
  get(`/documents/${id}/chunks?page=${page}&size=${size}`)
