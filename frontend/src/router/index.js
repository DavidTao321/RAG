import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { guest: true } },
  { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue'), meta: { guest: true } },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('../views/ProfileView.vue'),
    meta: { requiresAuth: true },
  },
  { path: '/', name: 'chat', component: () => import('../views/ChatView.vue'), meta: { requiresAuth: true } },
  {
    path: '/admin',
    component: () => import('../views/admin/AdminLayout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    children: [
      { path: '', redirect: '/admin/documents' },
      { path: 'documents', name: 'admin-documents', component: () => import('../views/admin/DocumentManage.vue') },
      { path: 'dashboard', name: 'admin-dashboard', component: () => import('../views/admin/Dashboard.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  let user = null
  try {
    user = JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    // user 数据被篡改/损坏时视为无用户信息，不阻断路由导航
    user = null
  }

  if (to.meta.requiresAuth && !token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guest && token) {
    return { name: 'chat' }
  }
  if (to.meta.requiresAdmin && !user?.is_admin) {
    return { name: 'chat' } // 普通用户访问管理页直接回首页
  }
  return true
})

export default router
