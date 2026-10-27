import { get, post } from './http'

export const login = (username, password) => post('/auth/login', { username, password })
export const register = (username, password) => post('/auth/register', { username, password })
export const changePassword = (old_password, new_password) =>
  post('/auth/change-password', { old_password, new_password })
export const getMe = () => get('/auth/me')
