<template>
  <div class="auth-page">
    <el-card class="auth-card">
      <div class="brand">
        <h2>注册新账号</h2>
      </div>
      <el-form :model="form">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名（2-64位字母/数字/中文）" size="large" :prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码（至少6位）" size="large" show-password :prefix-icon="Lock" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.confirm" type="password" placeholder="确认密码" size="large" show-password :prefix-icon="Lock" @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="submit">
          注 册
        </el-button>
      </el-form>
      <div class="foot">
        已有账号？<router-link to="/login">去登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { register } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const form = reactive({ username: '', password: '', confirm: '' })
const loading = ref(false)
const router = useRouter()
const auth = useAuthStore()

const submit = async () => {
  if (!form.username || form.password.length < 6) {
    ElMessage.warning('用户名不能为空，密码至少 6 位')
    return
  }
  if (form.password !== form.confirm) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  loading.value = true
  try {
    const data = await register(form.username, form.password)
    auth.setAuth(data.access_token, data.user)
    ElMessage.success('注册成功，已自动登录')
    router.push('/')
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
  margin: 0;
  color: #303133;
}

.foot {
  margin-top: 14px;
  text-align: center;
  font-size: 13px;
  color: #909399;
}
</style>
