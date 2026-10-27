<template>
  <div class="session-list">
    <div class="session-head">
      <div class="user-info">
        <el-avatar :size="32">{{ (auth.user?.username || '?')[0].toUpperCase() }}</el-avatar>
        <div class="user-name">
          <div>{{ auth.user?.username }}</div>
          <el-tag v-if="auth.isAdmin" size="small" type="danger">管理员</el-tag>
        </div>
      </div>
      <el-dropdown trigger="click" @command="onCommand">
        <el-button link><el-icon><MoreFilled /></el-icon></el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">修改密码</el-dropdown-item>
            <el-dropdown-item v-if="auth.isAdmin" command="admin">知识库管理</el-dropdown-item>
            <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <div class="new-btn">
      <el-button type="primary" plain style="width: 100%" @click="$emit('new-session')">
        ＋ 新建会话
      </el-button>
    </div>

    <div class="session-items">
      <div
        v-for="s in sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === currentId }"
        @click="$emit('select', s.id)"
      >
        <span class="session-title">{{ s.title }}</span>
        <span class="session-actions" @click.stop>
          <el-icon class="act" @click="$emit('rename', s)"><EditPen /></el-icon>
          <el-icon class="act danger" @click="$emit('remove', s)"><Delete /></el-icon>
        </span>
      </div>
      <el-empty v-if="!sessions.length" :image-size="50" description="暂无会话" />
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { EditPen, Delete, MoreFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '../../stores/auth'

defineProps({ sessions: { type: Array, default: () => [] }, currentId: Number })
defineEmits(['select', 'new-session', 'rename', 'remove'])

const auth = useAuthStore()
const router = useRouter()

const onCommand = (cmd) => {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  } else if (cmd === 'admin') {
    router.push('/admin/documents')
  } else if (cmd === 'profile') {
    router.push('/profile')
  }
}
</script>

<style scoped>
.session-list {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-right: 1px solid #ebeef5;
}

.session-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid #f0f2f5;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-name div {
  font-weight: 600;
  font-size: 14px;
}

.new-btn {
  padding: 12px 16px;
}

.session-items {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}

.session-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #303133;
}

.session-item:hover {
  background: #f5f7fa;
}

.session-item.active {
  background: #e8f3ff;
  color: #409eff;
}

.session-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  margin-right: 6px;
}

.session-actions {
  display: none;
  gap: 4px;
}

.session-item:hover .session-actions {
  display: inline-flex;
}

.act:hover {
  color: #409eff;
}

.act.danger:hover {
  color: #f56c6c;
}
</style>
