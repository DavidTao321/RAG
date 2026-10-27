<template>
  <el-container class="admin-page">
    <el-header class="admin-header">
      <div class="title">🛒 慧购优选 · 知识库管理后台</div>
      <div class="actions">
        <el-button link @click="$router.push('/')">← 返回问答</el-button>
        <el-dropdown @command="onCommand">
          <span class="user-trigger">{{ auth.user?.username }}（管理员）</span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>
    <el-container>
      <el-aside width="200px" class="admin-aside">
        <el-menu :default-active="$route.path" router>
          <el-menu-item index="/admin/documents">
            <el-icon><Document /></el-icon><span>文档管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/dashboard">
            <el-icon><DataAnalysis /></el-icon><span>数据看板</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="admin-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { Document, DataAnalysis } from '@element-plus/icons-vue'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const onCommand = (cmd) => {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.admin-page {
  height: 100vh;
}

.admin-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
}

.title {
  font-size: 17px;
  font-weight: 700;
  color: #303133;
}

.actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.user-trigger {
  cursor: pointer;
  color: #606266;
  font-size: 14px;
}

.admin-aside {
  background: #fff;
  border-right: 1px solid #ebeef5;
}

.admin-main {
  background: #f5f7fa;
}
</style>
