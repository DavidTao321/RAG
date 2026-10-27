// fetch 封装：自动携带 JWT、统一错误处理、401 跳登录
const BASE = '/api'

function getToken() {
  return localStorage.getItem('token') || ''
}

export async function request(method, path, body, options = {}) {
  const headers = { ...(options.headers || {}) }
  let payload
  if (body instanceof FormData) {
    payload = body // 上传文件：不手动设置 Content-Type
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(BASE + path, { method, headers, body: payload })
  const data = await res.json().catch(() => ({}))
  if (res.status === 401 && path !== '/auth/login') {
    // 会话过期：清凭据并跳登录。
    // 登录接口自身的 401 是"用户名或密码错误"，交给下方统一抛后端 detail，不清凭据不跳转
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    if (!location.pathname.startsWith('/login')) {
      location.href = '/login'
    }
    throw new Error('登录已过期，请重新登录')
  }
  if (!res.ok) {
    throw new Error(data.detail || `请求失败 (${res.status})`)
  }
  return data
}

export const get = (path) => request('GET', path)
export const post = (path, body) => request('POST', path, body)
export const put = (path, body) => request('PUT', path, body)
export const patch = (path, body) => request('PATCH', path, body)
export const del = (path) => request('DELETE', path)
