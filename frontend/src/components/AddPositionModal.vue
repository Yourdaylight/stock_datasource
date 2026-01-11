<template>
  <el-dialog
    v-model="visible"
    title="添加持仓"
    width="500px"
    :before-close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
      @submit.prevent="handleSubmit"
    >
      <el-form-item label="股票代码" prop="ts_code">
        <el-autocomplete
          v-model="form.ts_code"
          :fetch-suggestions="searchStocks"
          placeholder="请输入股票代码或名称"
          style="width: 100%"
          clearable
          @select="handleStockSelect"
        >
          <template #default="{ item }">
            <div class="stock-suggestion">
              <span class="stock-code">{{ item.ts_code }}</span>
              <span class="stock-name">{{ item.name }}</span>
            </div>
          </template>
        </el-autocomplete>
      </el-form-item>

      <el-form-item label="股票名称" prop="stock_name">
        <el-input
          v-model="form.stock_name"
          placeholder="股票名称"
          readonly
        />
      </el-form-item>

      <el-form-item label="持仓数量" prop="quantity">
        <el-input-number
          v-model="form.quantity"
          :min="1"
          :max="999999999"
          :step="100"
          placeholder="请输入持仓数量"
          style="width: 100%"
        />
        <div class="form-tip">单位：股</div>
      </el-form-item>

      <el-form-item label="成本价" prop="cost_price">
        <el-input-number
          v-model="form.cost_price"
          :min="0.01"
          :precision="3"
          :step="0.01"
          placeholder="请输入成本价"
          style="width: 100%"
        />
        <div class="form-tip">单位：元</div>
      </el-form-item>

      <el-form-item label="买入日期" prop="buy_date">
        <el-date-picker
          v-model="form.buy_date"
          type="date"
          placeholder="选择买入日期"
          style="width: 100%"
          :disabled-date="disabledDate"
        />
      </el-form-item>

      <el-form-item label="备注" prop="notes">
        <el-input
          v-model="form.notes"
          type="textarea"
          :rows="3"
          placeholder="可选，添加备注信息"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>

      <!-- Cost calculation -->
      <el-form-item v-if="form.quantity && form.cost_price" label="总成本">
        <div class="cost-calculation">
          <span class="cost-amount">¥{{ formatNumber(totalCost) }}</span>
          <span class="cost-detail">
            ({{ form.quantity }}股 × ¥{{ form.cost_price }})
          </span>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          确定添加
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { portfolioApi } from '@/api/portfolio'

interface Props {
  modelValue: boolean
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Reactive data
const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  ts_code: '',
  stock_name: '',
  quantity: null as number | null,
  cost_price: null as number | null,
  buy_date: new Date(),
  notes: ''
})

// Mock stock data for autocomplete
const stockDatabase = [
  { ts_code: '600519.SH', name: '贵州茅台' },
  { ts_code: '000001.SZ', name: '平安银行' },
  { ts_code: '000002.SZ', name: '万科A' },
  { ts_code: '600036.SH', name: '招商银行' },
  { ts_code: '000858.SZ', name: '五粮液' },
  { ts_code: '600276.SH', name: '恒瑞医药' },
  { ts_code: '000568.SZ', name: '泸州老窖' },
  { ts_code: '002415.SZ', name: '海康威视' },
  { ts_code: '600887.SH', name: '伊利股份' },
  { ts_code: '000858.SZ', name: '五粮液' }
]

// Computed
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const totalCost = computed(() => {
  if (!form.quantity || !form.cost_price) return 0
  return form.quantity * form.cost_price
})

// Form validation rules
const rules: FormRules = {
  ts_code: [
    { required: true, message: '请输入股票代码', trigger: 'blur' },
    { 
      pattern: /^\d{6}\.(SH|SZ)$/, 
      message: '股票代码格式不正确', 
      trigger: 'blur' 
    }
  ],
  stock_name: [
    { required: true, message: '请选择股票', trigger: 'blur' }
  ],
  quantity: [
    { required: true, message: '请输入持仓数量', trigger: 'blur' },
    { type: 'number', min: 1, message: '持仓数量必须大于0', trigger: 'blur' }
  ],
  cost_price: [
    { required: true, message: '请输入成本价', trigger: 'blur' },
    { type: 'number', min: 0.01, message: '成本价必须大于0', trigger: 'blur' }
  ],
  buy_date: [
    { required: true, message: '请选择买入日期', trigger: 'change' }
  ]
}

// Methods
const searchStocks = (queryString: string, callback: (suggestions: any[]) => void) => {
  if (!queryString) {
    callback([])
    return
  }

  const suggestions = stockDatabase.filter(stock => 
    stock.ts_code.toLowerCase().includes(queryString.toLowerCase()) ||
    stock.name.includes(queryString)
  )
  
  callback(suggestions)
}

const handleStockSelect = (item: any) => {
  form.ts_code = item.ts_code
  form.stock_name = item.name
}

const disabledDate = (time: Date) => {
  // Disable future dates
  return time.getTime() > Date.now()
}

const resetForm = () => {
  form.ts_code = ''
  form.stock_name = ''
  form.quantity = null
  form.cost_price = null
  form.buy_date = new Date()
  form.notes = ''
  
  if (formRef.value) {
    formRef.value.clearValidate()
  }
}

const handleClose = () => {
  resetForm()
  visible.value = false
}

const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    const valid = await formRef.value.validate()
    if (!valid) return

    submitting.value = true

    const requestData = {
      ts_code: form.ts_code,
      quantity: form.quantity!,
      cost_price: form.cost_price!,
      buy_date: formatDate(form.buy_date),
      notes: form.notes || undefined
    }

    await portfolioApi.createPosition(requestData)
    
    ElMessage.success('添加持仓成功')
    emit('success')
    handleClose()

  } catch (error) {
    console.error('Add position error:', error)
    ElMessage.error('添加持仓失败，请重试')
  } finally {
    submitting.value = false
  }
}

const formatDate = (date: Date): string => {
  return date.toISOString().split('T')[0]
}

const formatNumber = (value: number): string => {
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}

// Watch for ts_code changes to auto-complete stock name
watch(() => form.ts_code, (newCode) => {
  if (newCode && !form.stock_name) {
    const stock = stockDatabase.find(s => s.ts_code === newCode)
    if (stock) {
      form.stock_name = stock.name
    }
  }
})
</script>

<style scoped>
.stock-suggestion {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.stock-code {
  font-weight: bold;
  color: #409eff;
}

.stock-name {
  color: #606266;
  font-size: 13px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.cost-calculation {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cost-amount {
  font-size: 18px;
  font-weight: bold;
  color: #409eff;
}

.cost-detail {
  font-size: 13px;
  color: #909399;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
}

:deep(.el-input-number) {
  width: 100%;
}

:deep(.el-input-number .el-input__inner) {
  text-align: left;
}
</style>