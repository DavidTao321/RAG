import { get, put } from './http'

export const submitFeedback = (messageId, rating, comment) =>
  put(`/messages/${messageId}/feedback`, { rating, comment })

export const getStatsOverview = () => get('/admin/stats/overview')
export const getQaTrend = (days = 30) => get(`/admin/stats/qa-trend?days=${days}`)
export const getPerformance = () => get('/admin/stats/performance')
