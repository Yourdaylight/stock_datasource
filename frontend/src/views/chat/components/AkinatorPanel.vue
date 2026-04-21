<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAkinatorStore } from '@/stores/akinator'
import ProgressIndicator from './akinator/ProgressIndicator.vue'
import QuestionCard from './akinator/QuestionCard.vue'
import QAHistory from './akinator/QAHistory.vue'
import CandidateGrid from './akinator/CandidateGrid.vue'

const router = useRouter()
const store = useAkinatorStore()

const handlePick = async (ts_code: string) => {
  await store.confirm(ts_code)
  // 跳转到股票详情页
  router.push(`/research/${ts_code}`)
}

const handleAbandon = async () => {
  await store.abandon()
}

const handleRetry = async () => {
  await store.start()
}
</script>

<template>
  <div class="akinator-panel">
    <!-- 欢迎屏 -->
    <div v-if="store.phase === 'idle'" class="aki-welcome">
      <div class="aki-logo">🔮</div>
      <h2 class="aki-title">猜你所想 · A股版</h2>
      <p class="aki-desc">
        心里想一只 A 股股票，我会通过几个问题猜出它是哪只。
      </p>
      <ul class="aki-rules">
        <li>🤖 AI 会根据全市场 5000+ 只 A 股提问</li>
        <li>💬 每个问题只需回答"是"/"不是"/"不确定"</li>
        <li>🎯 通常 10 轮内就能锁定候选</li>
        <li>⚠️ 每场游戏会消耗一定 token 配额</li>
      </ul>
      <t-button
        theme="primary"
        size="large"
        :loading="store.loading"
        @click="store.start()"
      >
        <template #icon><t-icon name="play-circle" /></template>
        开始游戏
      </t-button>
    </div>

    <!-- 提问阶段 -->
    <div v-else-if="store.phase === 'asking' && store.currentQuestion" class="aki-asking">
      <ProgressIndicator
        :current="store.candidatesRemaining"
        :initial="store.initialCandidates"
        :question-count="store.questionCount"
      />
      <QuestionCard
        :question="store.currentQuestion"
        :loading="store.loading"
        @answer="store.answer"
      />
      <!-- LLM 思考过程（流式） -->
      <div v-if="store.loading || store.thinkingText" class="aki-thinking">
        <div class="aki-thinking-header">
          <t-icon name="chat-poll" />
          <span v-if="store.thinkingActive">🧠 AI 实时生成中...</span>
          <span v-else-if="store.thinkingText">💭 AI 决策输出</span>
          <span v-else-if="store.llmHeuristic">⚡ 启发式切分（无需 LLM）</span>
          <span v-else>⏳ 正在筛选候选...</span>
          <t-loading v-if="store.loading && !store.thinkingText" size="small" />
        </div>
        <pre v-if="store.thinkingText" class="aki-thinking-text">{{ store.thinkingText }}<span v-if="store.thinkingActive" class="cursor-blink">▊</span></pre>
      </div>
      <QAHistory :history="store.history" />
      <div class="aki-quit">
        <t-button theme="default" variant="text" size="small" @click="store.abandon()">
          放弃本局
        </t-button>
      </div>
    </div>

    <!-- 结果阶段 -->
    <div v-else-if="store.phase === 'finished'" class="aki-finished">
      <ProgressIndicator
        :current="store.candidatesRemaining"
        :initial="store.initialCandidates"
        :question-count="store.questionCount"
      />
      <CandidateGrid
        :candidates="store.finalCandidates"
        @pick="handlePick"
        @abandon="handleAbandon"
        @retry="handleRetry"
      />
      <QAHistory :history="store.history" />
    </div>

    <!-- 确认/放弃 -->
    <div v-else-if="store.phase === 'confirmed'" class="aki-end">
      <div class="aki-end-emoji">🎉</div>
      <h3>猜对啦！</h3>
      <p class="aki-end-desc">感谢陪我玩这一局</p>
      <t-button theme="primary" @click="handleRetry">再玩一次</t-button>
    </div>

    <div v-else-if="store.phase === 'abandoned'" class="aki-end">
      <div class="aki-end-emoji">😅</div>
      <h3>这一局没猜到</h3>
      <p class="aki-end-desc">下次我会更努力！</p>
      <t-button theme="primary" @click="handleRetry">再试一次</t-button>
    </div>
  </div>
</template>

<style scoped>
.akinator-panel {
  height: 100%;
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}

.aki-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 24px;
  text-align: center;
  margin: auto;
}

.aki-logo {
  font-size: 64px;
  margin-bottom: 8px;
}

.aki-title {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
  background: linear-gradient(90deg, var(--td-brand-color), var(--td-success-color));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.aki-desc {
  font-size: 15px;
  color: var(--td-text-color-secondary);
  margin: 8px 0 16px;
}

.aki-rules {
  list-style: none;
  padding: 0;
  margin: 0 0 24px;
  font-size: 14px;
  color: var(--td-text-color-secondary);
  line-height: 2;
  text-align: left;
}

.aki-asking, .aki-finished {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.aki-quit {
  text-align: center;
  margin-top: 8px;
}

.aki-thinking {
  padding: 12px 14px;
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border: 1px solid #fde68a;
  border-radius: 10px;
}

.aki-thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #92400e;
  margin-bottom: 8px;
}

.aki-thinking-text {
  margin: 0;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.65;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 260px;
  overflow-y: auto;
  font-family: 'PingFang SC', 'Hiragino Sans GB', sans-serif;
}

.cursor-blink {
  color: var(--td-brand-color);
  animation: blink 1s step-end infinite;
  margin-left: 2px;
}

@keyframes blink {
  50% { opacity: 0; }
}

.aki-end {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 24px;
  text-align: center;
  margin: auto;
}

.aki-end-emoji {
  font-size: 72px;
}

.aki-end-desc {
  color: var(--td-text-color-secondary);
  margin: 0 0 16px;
}
</style>
