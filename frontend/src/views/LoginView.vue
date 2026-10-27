<template>
  <div class="auth-page">
    <el-card class="auth-card">
      <div class="brand">
        <h2>🛒 慧购优选 · 知识库问答系统</h2>
        <p>基于 LangChain 的企业级 RAG 智能客服</p>
      </div>
      <el-form :model="form" @submit.prevent="submit">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" size="large" :prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
            :prefix-icon="Lock"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="submit">
          登 录
        </el-button>
      </el-form>
      <div class="foot">
        还没有账号？<router-link to="/register">立即注册</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { login } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const submit = async () => {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const data = await login(form.username, form.password)
    auth.setAuth(data.access_token, data.user)
    ElMessage.success(`欢迎回来，${data.user.username}`)
    router.push(route.query.redirect || '/')
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

.foot {
  margin-top: 14px;
  text-align: center;
  font-size: 13px;
  color: #909399;
}
</style>
