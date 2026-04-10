<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
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

// K-line chart animation
const canvasRef = ref<HTMLCanvasElement | null>(null)
let animationId: number | null = null

const features = [
  { icon: '📈', title: '行情分析', desc: '实时A股/港股/ETF行情追踪' },
  { icon: '🎯', title: '智能选股', desc: 'AI多因子量化选股模型' },
  { icon: '📊', title: '量化模型', desc: 'RPS排名/动量/价值因子' },
  { icon: '🔄', title: '策略回测', desc: '历史数据驱动的策略验证' },
  { icon: '⚡', title: 'AI工作流', desc: '自动化投资研究流程' },
  { icon: '💬', title: '智能对话', desc: 'AI驱动的投研问答助手' },
  { icon: '📱', title: '微信盯盘', desc: '一键直连微信，实时推送涨跌预警', highlight: true },
]

const drawKLine = () => {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const dpr = window.devicePixelRatio || 1
  const rect = canvas.getBoundingClientRect()
  canvas.width = rect.width * dpr
  canvas.height = rect.height * dpr
  ctx.scale(dpr, dpr)

  const w = rect.width
  const h = rect.height
  const time = Date.now() * 0.001

  ctx.clearRect(0, 0, w, h)

  // Draw multiple wave lines
  const lines = [
    { color: 'rgba(0, 212, 255, 0.6)', amp: 25, freq: 0.012, speed: 0.8, phase: 0 },
    { color: 'rgba(124, 58, 237, 0.5)', amp: 18, freq: 0.018, speed: 1.2, phase: 2 },
    { color: 'rgba(16, 185, 129, 0.4)', amp: 15, freq: 0.015, speed: 0.6, phase: 4 },
  ]

  lines.forEach(line => {
    ctx.beginPath()
    ctx.strokeStyle = line.color
    ctx.lineWidth = 2
    ctx.shadowColor = line.color
    ctx.shadowBlur = 12

    for (let x = 0; x <= w; x += 2) {
      const y = h / 2 + 
        Math.sin(x * line.freq + time * line.speed + line.phase) * line.amp +
        Math.sin(x * line.freq * 2.3 + time * line.speed * 0.7) * line.amp * 0.4
      if (x === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.stroke()
    ctx.shadowBlur = 0
  })

  // Draw candlestick-like bars
  const barCount = 20
  const barWidth = Math.max(3, w / barCount * 0.4)
  const gap = w / barCount
  for (let i = 0; i < barCount; i++) {
    const x = gap * i + gap / 2
    const baseY = h / 2
    const candleH = Math.sin(i * 0.5 + time * 0.8) * 30 + Math.cos(i * 0.3 + time * 0.5) * 15
    const bodyH = Math.abs(candleH) * 0.6

    const isGreen = candleH > 0
    ctx.fillStyle = isGreen ? 'rgba(16, 185, 129, 0.35)' : 'rgba(239, 68, 68, 0.3)'

    // Wick
    ctx.fillRect(x - 0.5, baseY - candleH, 1, Math.abs(candleH))
    // Body
    ctx.fillRect(x - barWidth / 2, baseY - (isGreen ? bodyH : 0), barWidth, bodyH)
  }

  animationId = requestAnimationFrame(drawKLine)
}

onMounted(() => {
  drawKLine()
})

onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
    animationId = null
  }
})
</script>

<template>
  <div class="login-container">
    <!-- Left showcase panel -->
    <div class="login-showcase">
      <!-- Floating particles -->
      <div class="particles">
        <div v-for="i in 15" :key="i" class="particle" :style="{
          '--x': `${Math.random() * 100}%`,
          '--y': `${Math.random() * 100}%`,
          '--size': `${4 + Math.random() * 8}px`,
          '--duration': `${12 + Math.random() * 18}s`,
          '--delay': `${-Math.random() * 20}s`,
          '--opacity': `${0.15 + Math.random() * 0.35}`,
        }" />
      </div>

      <!-- Radial glow decorations -->
      <div class="glow glow-1" />
      <div class="glow glow-2" />

      <!-- Brand content -->
      <div class="showcase-content">
        <div class="brand-title">
          <span class="brand-icon">◆</span>
          <h1>AI 智能选股平台</h1>
        </div>
        <p class="brand-slogan">数据驱动决策 · AI赋能投资 · 量化引领未来</p>

        <!-- Feature cards -->
        <div class="feature-grid">
          <div 
            v-for="(feature, idx) in features" 
            :key="feature.title"
            class="feature-card"
            :class="{ 'feature-card--highlight': feature.highlight }"
            :style="{ '--delay': `${idx * 0.1}s` }"
          >
            <span class="feature-icon">{{ feature.icon }}</span>
            <div class="feature-text">
              <h3>{{ feature.title }}</h3>
              <p>{{ feature.desc }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- K-line chart decoration -->
      <div class="kline-decoration">
        <canvas ref="canvasRef" class="kline-canvas" />
      </div>
    </div>

    <!-- Right form panel -->
    <div class="login-form-panel">
      <div class="form-wrapper">
        <!-- Mobile brand bar -->
        <div class="mobile-brand-bar">
          <span class="brand-icon-sm">◆</span>
          <span>AI 智能选股平台</span>
        </div>

        <div class="form-header">
          <h2>{{ isLogin ? '欢迎回来' : '创建账户' }}</h2>
          <p>{{ isLogin ? '登录您的账户以继续' : '注册一个新的账户' }}</p>
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
  </div>
</template>

<style scoped>
/* ===== Container: Two-column layout ===== */
.login-container {
  min-height: 100vh;
  display: flex;
  width: 100%;
}

/* ===== Left showcase panel ===== */
.login-showcase {
  position: relative;
  flex: 0 0 58%;
  background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  padding: 60px 50px;
}

/* Floating particles */
.particles {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.particle {
  position: absolute;
  left: var(--x);
  top: var(--y);
  width: var(--size);
  height: var(--size);
  border-radius: 50%;
  background: radial-gradient(circle, rgba(0, 212, 255, var(--opacity)), transparent 70%);
  animation: particleFloat var(--duration) var(--delay) infinite ease-in-out;
}

@keyframes particleFloat {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: var(--opacity);
  }
  25% {
    transform: translate(30px, -40px) scale(1.2);
  }
  50% {
    transform: translate(-20px, -80px) scale(0.8);
    opacity: calc(var(--opacity) * 0.6);
  }
  75% {
    transform: translate(40px, -30px) scale(1.1);
  }
}

/* Radial glows */
.glow {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  filter: blur(80px);
}

.glow-1 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(0, 212, 255, 0.15), transparent 70%);
  top: -100px;
  left: -100px;
  animation: glowPulse 8s ease-in-out infinite;
}

.glow-2 {
  width: 350px;
  height: 350px;
  background: radial-gradient(circle, rgba(124, 58, 237, 0.12), transparent 70%);
  bottom: -80px;
  right: -80px;
  animation: glowPulse 10s 3s ease-in-out infinite;
}

@keyframes glowPulse {
  0%, 100% { transform: scale(1); opacity: 0.7; }
  50% { transform: scale(1.3); opacity: 1; }
}

/* Brand content */
.showcase-content {
  position: relative;
  z-index: 2;
  max-width: 520px;
  width: 100%;
}

.brand-title {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}

.brand-icon {
  font-size: 28px;
  color: #00d4ff;
  animation: iconPulse 3s ease-in-out infinite;
  text-shadow: 0 0 20px rgba(0, 212, 255, 0.5);
}

@keyframes iconPulse {
  0%, 100% { transform: scale(1); text-shadow: 0 0 20px rgba(0, 212, 255, 0.5); }
  50% { transform: scale(1.15); text-shadow: 0 0 35px rgba(0, 212, 255, 0.8); }
}

.brand-title h1 {
  font-size: 32px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 1px;
  animation: titleShimmer 4s ease-in-out infinite;
  background: linear-gradient(90deg, #ffffff, #00d4ff, #ffffff);
  background-size: 200% auto;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

@keyframes titleShimmer {
  0% { background-position: 0% center; }
  50% { background-position: 100% center; }
  100% { background-position: 0% center; }
}

.brand-slogan {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.55);
  letter-spacing: 2px;
  margin-bottom: 48px;
  font-weight: 400;
}

/* Feature grid */
.feature-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.feature-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(8px);
  transition: all 0.3s ease;
  animation: cardEnter 0.6s var(--delay) both ease-out;
  cursor: default;
}

.feature-card:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(0, 212, 255, 0.25);
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(0, 212, 255, 0.1);
}

/* Highlight card: spans full width with gradient border */
.feature-card--highlight {
  grid-column: 1 / -1;
  background: rgba(0, 212, 255, 0.06);
  border-color: rgba(0, 212, 255, 0.2);
  position: relative;
  overflow: hidden;
}

.feature-card--highlight::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 12px;
  padding: 1px;
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.4), rgba(124, 58, 237, 0.3), rgba(16, 185, 129, 0.3));
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

.feature-card--highlight:hover {
  background: rgba(0, 212, 255, 0.1);
  border-color: rgba(0, 212, 255, 0.35);
  box-shadow: 0 8px 32px rgba(0, 212, 255, 0.15);
}

.feature-card--highlight .feature-text h3 {
  color: #00d4ff;
}

.feature-card--highlight .feature-icon {
  animation: iconBounce 2s ease-in-out infinite;
}

@keyframes iconBounce {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.15); }
}

@keyframes cardEnter {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.feature-icon {
  font-size: 22px;
  flex-shrink: 0;
  margin-top: 2px;
}

.feature-text h3 {
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 4px;
}

.feature-text p {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1.4;
}

/* K-line decoration */
.kline-decoration {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 120px;
  z-index: 1;
  opacity: 0.7;
}

.kline-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

/* ===== Right form panel ===== */
.login-form-panel {
  flex: 0 0 42%;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  position: relative;
}

.form-wrapper {
  width: 100%;
  max-width: 400px;
}

/* Mobile brand bar (hidden on desktop) */
.mobile-brand-bar {
  display: none;
  align-items: center;
  gap: 10px;
  padding: 14px 20px;
  margin-bottom: 32px;
  background: linear-gradient(135deg, #0f0c29, #302b63);
  border-radius: 12px;
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 1px;
}

.brand-icon-sm {
  color: #00d4ff;
  font-size: 14px;
  text-shadow: 0 0 12px rgba(0, 212, 255, 0.5);
}

.form-header {
  margin-bottom: 36px;
}

.form-header h2 {
  font-size: 28px;
  font-weight: 700;
  color: #1d2129;
  margin-bottom: 8px;
  letter-spacing: -0.5px;
}

.form-header p {
  font-size: 15px;
  color: #86909c;
  font-weight: 400;
}

.login-form {
  margin-bottom: 24px;
}

.login-form :deep(.t-form__item) {
  margin-bottom: 22px;
}

.login-form :deep(.t-input) {
  border-radius: 10px;
}

.login-form :deep(.t-input--large) {
  height: 48px;
}

.login-form :deep(.t-button--large) {
  height: 48px;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
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

/* ===== Responsive ===== */
@media (max-width: 768px) {
  .login-container {
    flex-direction: column;
  }

  .login-showcase {
    display: none;
  }

  .login-form-panel {
    flex: 1;
    padding: 32px 24px;
  }

  .mobile-brand-bar {
    display: flex;
  }

  .form-header h2 {
    font-size: 24px;
  }
}

@media (max-width: 480px) {
  .login-form-panel {
    padding: 24px 16px;
  }

  .form-header h2 {
    font-size: 22px;
  }
}
</style>
