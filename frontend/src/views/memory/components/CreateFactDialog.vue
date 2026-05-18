<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useMemoryStore } from '@/stores/memory'
import { MessagePlugin } from 'tdesign-vue-next'

const memoryStore = useMemoryStore()

const visible = ref(false)
const submitting = ref(false)

const form = reactive({
  content: '',
  category: 'conclusion' as string,
  confidence: 0.7,
  source: 'manual'
})

const categoryOptions = [
  { value: 'risk_preference', label: '风险偏好' },
  { value: 'sector_focus', label: '板块关注' },
  { value: 'stock_opinion', label: '个股观点' },
  { value: 'trading_style', label: '交易风格' },
  { value: 'conclusion', label: '分析结论' },
  { value: 'market_signal', label: '市场信号' },
  { value: 'capital_flow', label: '资金流向' }
]

function open() {
  visible.value = true
  form.content = ''
  form.category = 'conclusion'
  form.confidence = 0.7
  form.source = 'manual'
}

async function handleSubmit() {
  if (!form.content.trim()) {
    MessagePlugin.warning('请输入记忆内容')
    return
  }
  submitting.value = true
  const result = await memoryStore.createFact({
    content: form.content.trim(),
    category: form.category,
    confidence: form.confidence,
    source: form.source
  })
  submitting.value = false
  if (result) {
    MessagePlugin.success('记忆创建成功')
    visible.value = false
  }
}

defineExpose({ open })
</script>

<template>
  <t-dialog
    v-model:visible="visible"
    header="手动添加记忆"
    :confirm-btn="{ content: '创建', loading: submitting }"
    :on-confirm="handleSubmit"
    width="520px"
  >
    <t-form label-width="80px" :colon="true">
      <t-form-item label="内容">
        <t-textarea
          v-model="form.content"
          placeholder="输入要记录的事实或观点，如：偏好科技股、风险承受能力较强..."
          :maxlength="200"
          :autosize="{ minRows: 3, maxRows: 6 }"
        />
      </t-form-item>

      <t-form-item label="类别">
        <t-select v-model="form.category" :options="categoryOptions" />
      </t-form-item>

      <t-form-item label="置信度">
        <t-slider
          v-model="form.confidence"
          :min="0.1"
          :max="1.0"
          :step="0.1"
          :marks="{ 0.3: '低', 0.5: '中', 0.7: '高', 1.0: '确定' }"
        />
      </t-form-item>

      <t-form-item label="来源">
        <t-input v-model="form.source" placeholder="手动输入 / 对话提取 / 外部导入" />
      </t-form-item>
    </t-form>
  </t-dialog>
</template>
