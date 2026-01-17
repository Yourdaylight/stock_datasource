<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { MessagePlugin } from 'tdesign-vue-next'
import { LockOnIcon, MailIcon, UserIcon } from 'tdesign-icons-vue-next'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const isLogin = ref(true)
const form = ref({
  email: '',
  password: '',
  confirmPassword: '',
  username: ''
})

const formRules = computed(() => ({
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { email: true, message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ],
  confirmPassword: isLogin.value ? [] : [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { 
      validator: (val: string) => val === form.value.password, 
      message: '两次输入的密码不一致', 
      trigger: 'blur' 
    }
  ]
}))

const handleSubmit = async () => {
  if (isLogin.value) {
    const success = await authStore.login({
      email: form.value.email,
      password: form.value.password
    })
    
    if (success) {
      MessagePlugin.success('登录成功')
      const redirect = route.query.redirect as string || '/market'
      router.push(redirect)
    }
  } else {
    if (form.value.password !== form.value.confirmPassword) {
      MessagePlugin.error('两次输入的密码不一致')
      return
    }
    
    const result = await authStore.register({
      email: form.value.email,
      password: form.value.password,
      username: form.value.username || undefined
    })
    
    if (result.success) {
      MessagePlugin.success('注册成功，请登录')
      isLogin.value = true
      form.value.password = ''
      form.value.confirmPassword = ''
    } else {
      MessagePlugin.error(result.message)
    }
  }
}

const toggleMode = () => {
  isLogin.value = !isLogin.value
  form.value.password = ''
  form.value.confirmPassword = ''
}
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1>AI 智能选股平台</h1>
        <p>{{ isLogin ? '欢迎回来，请登录您的账户' : '创建新账户' }}</p>
      </div>
      
      <t-form
        :data="form"
        :rules="formRules"
        @submit="handleSubmit"
        class="login-form"
      >
        <t-form-item name="email">
          <t-input
            v-model="form.email"
            placeholder="请输入邮箱"
            size="large"
            clearable
          >
            <template #prefix-icon>
              <MailIcon />
            </template>
          </t-input>
        </t-form-item>
        
        <t-form-item v-if="!isLogin" name="username">
          <t-input
            v-model="form.username"
            placeholder="用户名（可选，默认使用邮箱前缀）"
            size="large"
            clearable
          >
            <template #prefix-icon>
              <UserIcon />
            </template>
          </t-input>
        </t-form-item>
        
        <t-form-item name="password">
          <t-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            clearable
          >
            <template #prefix-icon>
              <LockOnIcon />
            </template>
          </t-input>
        </t-form-item>
        
        <t-form-item v-if="!isLogin" name="confirmPassword">
          <t-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请确认密码"
            size="large"
            clearable
          >
            <template #prefix-icon>
              <LockOnIcon />
            </template>
          </t-input>
        </t-form-item>
        
        <t-form-item>
          <t-button
            theme="primary"
            type="submit"
            block
            size="large"
            :loading="authStore.loading"
          >
            {{ isLogin ? '登录' : '注册' }}
          </t-button>
        </t-form-item>
      </t-form>
      
      <div class="login-footer">
        <span>{{ isLogin ? '还没有账户？' : '已有账户？' }}</span>
        <t-link theme="primary" @click="toggleMode">
          {{ isLogin ? '立即注册' : '立即登录' }}
        </t-link>
      </div>
      
      <div class="login-tips" v-if="!isLogin">
        <t-alert theme="info" :close="false">
          <template #message>
            仅限白名单邮箱注册，请使用您的企业邮箱。
          </template>
        </t-alert>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 420px;
  background: white;
  border-radius: 12px;
  padding: 40px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: #1d2129;
  margin-bottom: 8px;
}

.login-header p {
  font-size: 14px;
  color: #86909c;
}

.login-form {
  margin-bottom: 24px;
}

.login-form :deep(.t-form__item) {
  margin-bottom: 20px;
}

.login-footer {
  text-align: center;
  font-size: 14px;
  color: #86909c;
}

.login-footer :deep(.t-link) {
  margin-left: 4px;
}

.login-tips {
  margin-top: 20px;
}
</style>
