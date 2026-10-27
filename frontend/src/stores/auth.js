import { defineStore } from 'pinia'

// 安全读 localStorage 的 user：数据被篡改/损坏时返回 null，避免应用初始化白屏
function readUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    // token 存 localStorage 是已知取舍：XSS 可窃取，但换来刷新不丢登录态；
    // 生产加固可改 httpOnly cookie 方案（见 security-audit 基线）
    token: localStorage.getItem('token') || '',
    user: readUser(),
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    isAdmin: (s) => !!s.user?.is_admin,
  },
  actions: {
    setAuth(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify(user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
  },
})
