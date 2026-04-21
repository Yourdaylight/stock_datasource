import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { akinatorApi, type QuestionDTO, type StockDTO, type AnswerType } from '@/api/akinator'

export type Phase = 'idle' | 'asking' | 'finished' | 'confirmed' | 'abandoned'

export interface QAHistoryEntry {
  question: string
  answer: AnswerType
  reasoning?: string
  candidatesBefore: number
  candidatesAfter: number
}

export const useAkinatorStore = defineStore('akinator', () => {
  const sessionId = ref<string | null>(null)
  const phase = ref<Phase>('idle')
  const currentQuestion = ref<QuestionDTO | null>(null)
  const questionCount = ref(0)
  const candidatesRemaining = ref(0)
  const initialCandidates = ref(0)  // for progress bar
  const history = ref<QAHistoryEntry[]>([])
  const finalCandidates = ref<StockDTO[]>([])
  const totalTokens = ref(0)
  const loading = ref(false)

  // Streaming thinking state
  const thinkingText = ref('')       // 当前 LLM 流式思考内容
  const thinkingActive = ref(false)  // 是否正在思考（尚未出结果）
  const llmHeuristic = ref(false)    // 本轮是否走了启发式（不是 LLM）

  const progress = computed(() => {
    if (initialCandidates.value === 0) return 0
    const eliminated = initialCandidates.value - candidatesRemaining.value
    return Math.min(100, Math.round((eliminated / initialCandidates.value) * 100))
  })

  const reset = () => {
    sessionId.value = null
    phase.value = 'idle'
    currentQuestion.value = null
    questionCount.value = 0
    candidatesRemaining.value = 0
    initialCandidates.value = 0
    history.value = []
    finalCandidates.value = []
    totalTokens.value = 0
  }

  const start = async () => {
    reset()
    loading.value = true
    try {
      const resp = await akinatorApi.start()
      sessionId.value = resp.session_id
      currentQuestion.value = resp.question
      questionCount.value = resp.question_count
      candidatesRemaining.value = resp.candidates_remaining
      initialCandidates.value = resp.candidates_remaining
      phase.value = 'asking'
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '启动失败'
      MessagePlugin.error(`游戏启动失败: ${msg}`)
      phase.value = 'idle'
    } finally {
      loading.value = false
    }
  }

  const answer = async (ans: AnswerType) => {
    if (!sessionId.value || !currentQuestion.value) return
    loading.value = true
    thinkingText.value = ''
    thinkingActive.value = false
    llmHeuristic.value = false
    const prevCount = candidatesRemaining.value
    const qText = currentQuestion.value.question
    const qReasoning = currentQuestion.value.reasoning

    try {
      await akinatorApi.answerStream(sessionId.value, ans, (ev: any) => {
        switch (ev.type) {
          case 'progress':
            candidatesRemaining.value = ev.candidates_remaining
            questionCount.value = ev.question_count
            // Record the just-answered question into history now
            history.value.push({
              question: qText,
              answer: ans,
              reasoning: qReasoning,
              candidatesBefore: prevCount,
              candidatesAfter: ev.candidates_remaining,
            })
            break
          case 'heuristic':
            llmHeuristic.value = true
            thinkingActive.value = false
            break
          case 'llm_start':
            thinkingActive.value = true
            thinkingText.value = ''
            break
          case 'think_delta':
            thinkingText.value += ev.text || ''
            break
          case 'think_end':
            thinkingActive.value = false
            break
          case 'question':
            // will be shown via 'final' event below
            break
          case 'final':
            if (ev.status === 'finished') {
              finalCandidates.value = ev.final_candidates || []
              currentQuestion.value = null
              phase.value = 'finished'
            } else {
              currentQuestion.value = ev.question
              phase.value = 'asking'
            }
            candidatesRemaining.value = ev.candidates_remaining
            questionCount.value = ev.question_count
            break
          case 'error':
            // Server already falls back; just log
            console.warn('[akinator SSE error]', ev.message)
            break
        }
      })
    } catch (e: any) {
      const msg = e?.message || '流式回答失败'
      MessagePlugin.error(`回答失败: ${msg}`)
    } finally {
      loading.value = false
    }
  }

  const confirm = async (ts_code: string) => {
    if (!sessionId.value) return
    loading.value = true
    try {
      await akinatorApi.confirm(sessionId.value, ts_code)
      phase.value = 'confirmed'
      MessagePlugin.success('猜中啦！🎉')
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '确认失败'
      MessagePlugin.error(msg)
    } finally {
      loading.value = false
    }
  }

  const abandon = async () => {
    if (!sessionId.value) {
      reset()
      return
    }
    loading.value = true
    try {
      await akinatorApi.abandon(sessionId.value)
      phase.value = 'abandoned'
    } catch {
      // ignore
    } finally {
      loading.value = false
    }
  }

  return {
    sessionId,
    phase,
    currentQuestion,
    questionCount,
    candidatesRemaining,
    initialCandidates,
    history,
    finalCandidates,
    totalTokens,
    loading,
    progress,
    thinkingText,
    thinkingActive,
    llmHeuristic,
    start,
    answer,
    confirm,
    abandon,
    reset,
  }
})
