<template>
  <div class="auth-page">
    <el-card class="auth-card">
      <div class="brand">
        <h2>修改密码</h2>
        <p>当前用户：{{ auth.user?.username }}</p>
      </div>
      <el-form :model="form">
        <el-form-item>
          <el-input v-model="form.oldPassword" type="password" placeholder="原密码" size="large" show-password />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.newPassword" type="password" placeholder="新密码（至少6位）" size="large" show-password />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.confirm" type="password" placeholder="确认新密码" size="large" show-password @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="submit">
          确认修改
        </el-button>
        <el-button size="large" style="width: 100%; margin-left: 0; margin-top: 10px" @click="$router.back()">
          返回
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { changePassword } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const form = reactive({ oldPassword: '', newPassword: '', confirm: '' })
const loading = ref(false)
const router = useRouter()
const auth = useAuthStore()

const submit = async () => {
  if (form.newPassword.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (form.newPassword !== form.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  loading.value = true
  try {
    const data = await changePassword(form.oldPassword, form.newPassword)
    ElMessage.success(data.detail || '密码修改成功')
    // 后端 token_version 已 +1，旧 token 全部失效 → 强制重新登录
    auth.logout()
    router.push('/login')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f3ff 0%, #f5f7fa 100%);
}

.auth-card {
  width: 400px;
}

.brand {
  text-align: center;
  margin-bottom: 20px;
}

.brand h2 {
  margin: 0 0 6px;
  color: #303133;
}

.brand p {
  margin: 0;
  color: #909399;
  font-size: 13px;
}
</style>
