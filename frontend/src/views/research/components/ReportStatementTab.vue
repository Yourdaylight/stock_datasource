<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  data: any[]
  statementType: 'income' | 'balance' | 'cashflow'
  market: string
}>()

// ========== Format Helpers ==========

const parseNum = (val: any): number | null => {
  if (val === null || val === undefined || val === '' || val === 'N/A' || val === '\\N') return null
  const n = Number(val)
  return isNaN(n) ? null : n
}

const formatAmount = (val: any): string => {
  const n = parseNum(val)
  if (n === null) return '-'
  const abs = Math.abs(n)
  if (abs >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(2)
}

const formatValue = (val: any): string => {
  const n = parseNum(val)
  if (n === null) return '-'
  return n.toFixed(2)
}

const isHK = computed(() => props.market === 'HK')

// ========== Statement Titles ==========

const statementTitle = computed(() => {
  switch (props.statementType) {
    case 'income': return '利润表'
    case 'balance': return '资产负债表'
    case 'cashflow': return '现金流量表'
    default: return '报表'
  }
})

const statementIcon = computed(() => {
  switch (props.statementType) {
    case 'income': return '📊'
    case 'balance': return '🏦'
    case 'cashflow': return '💰'
    default: return '📋'
  }
})

// ========== A-Share Field Definitions ==========

interface FieldDef {
  key: string
  label: string
  format?: 'amount' | 'value' | 'pct'
  isHeader?: boolean
}

const aShareIncomeFields: FieldDef[] = [
  { key: '_header_revenue', label: '收入与成本', isHeader: true },
  { key: 'revenue', label: '营业总收入', format: 'amount' },
  { key: 'oper_cost', label: '营业总成本', format: 'amount' },
  { key: 'total_cogs', label: '营业成本合计', format: 'amount' },
  { key: '_header_expense', label: '期间费用', isHeader: true },
  { key: 'sell_exp', label: '销售费用', format: 'amount' },
  { key: 'admin_exp', label: '管理费用', format: 'amount' },
  { key: 'fin_exp', label: '财务费用', format: 'amount' },
  { key: 'rd_exp', label: '研发费用', format: 'amount' },
  { key: '_header_profit', label: '利润', isHeader: true },
  { key: 'operate_profit', label: '营业利润', format: 'amount' },
  { key: 'non_oper_income', label: '营业外收入', format: 'amount' },
  { key: 'non_oper_exp', label: '营业外支出', format: 'amount' },
  { key: 'total_profit', label: '利润总额', format: 'amount' },
  { key: 'income_tax', label: '所得税费用', format: 'amount' },
  { key: 'n_income', label: '净利润', format: 'amount' },
  { key: 'n_income_attr_p', label: '归属母公司净利润', format: 'amount' },
  { key: 'minority_gain', label: '少数股东损益', format: 'amount' },
  { key: '_header_eps', label: '每股指标', isHeader: true },
  { key: 'basic_eps', label: '基本每股收益', format: 'value' },
  { key: 'diluted_eps', label: '稀释每股收益', format: 'value' },
  { key: 'ebit', label: 'EBIT', format: 'amount' },
  { key: 'ebitda', label: 'EBITDA', format: 'amount' },
]

const aShareBalanceFields: FieldDef[] = [
  { key: '_header_ca', label: '流动资产', isHeader: true },
  { key: 'money_cap', label: '货币资金', format: 'amount' },
  { key: 'trad_asset', label: '交易性金融资产', format: 'amount' },
  { key: 'notes_receiv', label: '应收票据', format: 'amount' },
  { key: 'accounts_receiv', label: '应收账款', format: 'amount' },
  { key: 'prepayment', label: '预付款项', format: 'amount' },
  { key: 'inventories', label: '存货', format: 'amount' },
  { key: 'total_cur_assets', label: '流动资产合计', format: 'amount' },
  { key: '_header_nca', label: '非流动资产', isHeader: true },
  { key: 'fix_assets', label: '固定资产', format: 'amount' },
  { key: 'intan_assets', label: '无形资产', format: 'amount' },
  { key: 'goodwill', label: '商誉', format: 'amount' },
  { key: 'lt_eqt_invest', label: '长期股权投资', format: 'amount' },
  { key: 'total_nca', label: '非流动资产合计', format: 'amount' },
  { key: 'total_assets', label: '资产总计', format: 'amount' },
  { key: '_header_cl', label: '流动负债', isHeader: true },
  { key: 'st_borr', label: '短期借款', format: 'amount' },
  { key: 'acct_payable', label: '应付账款', format: 'amount' },
  { key: 'adv_receipts', label: '预收款项', format: 'amount' },
  { key: 'total_cur_liab', label: '流动负债合计', format: 'amount' },
  { key: '_header_ncl', label: '非流动负债', isHeader: true },
  { key: 'lt_borr', label: '长期借款', format: 'amount' },
  { key: 'bond_payable', label: '应付债券', format: 'amount' },
  { key: 'total_ncl', label: '非流动负债合计', format: 'amount' },
  { key: 'total_liab', label: '负债合计', format: 'amount' },
  { key: '_header_eq', label: '所有者权益', isHeader: true },
  { key: 'total_hldr_eqy_inc_min', label: '股东权益合计', format: 'amount' },
  { key: 'total_hldr_eqy_exc_min', label: '归属母公司股东权益', format: 'amount' },
  { key: 'minority_int', label: '少数股东权益', format: 'amount' },
]

const aShareCashflowFields: FieldDef[] = [
  { key: '_header_oper', label: '经营活动现金流', isHeader: true },
  { key: 'c_fr_sale_sg', label: '销售商品收到的现金', format: 'amount' },
  { key: 'c_fr_oth_operate_a', label: '收到其他与经营有关的现金', format: 'amount' },
  { key: 'c_paid_goods_s', label: '购买商品支付的现金', format: 'amount' },
  { key: 'c_paid_to_for_empl', label: '支付给职工的现金', format: 'amount' },
  { key: 'n_cashflow_act', label: '经营活动现金流量净额', format: 'amount' },
  { key: '_header_invest', label: '投资活动现金流', isHeader: true },
  { key: 'c_paid_invest', label: '投资支付的现金', format: 'amount' },
  { key: 'c_recp_return_invest', label: '收回投资收到的现金', format: 'amount' },
  { key: 'n_cashflow_inv_act', label: '投资活动现金流量净额', format: 'amount' },
  { key: '_header_fin', label: '筹资活动现金流', isHeader: true },
  { key: 'c_recp_borrow', label: '取得借款收到的现金', format: 'amount' },
  { key: 'c_pay_dist_dpcp_int_exp', label: '偿还债务支付的现金', format: 'amount' },
  { key: 'n_cash_flows_fnc_act', label: '筹资活动现金流量净额', format: 'amount' },
  { key: '_header_summary', label: '汇总', isHeader: true },
  { key: 'n_incr_cash_cash_equ', label: '现金净增加额', format: 'amount' },
  { key: 'c_cash_equ_end_period', label: '期末现金余额', format: 'amount' },
]

const getAShareFields = (): FieldDef[] => {
  switch (props.statementType) {
    case 'income': return aShareIncomeFields
    case 'balance': return aShareBalanceFields
    case 'cashflow': return aShareCashflowFields
    default: return []
  }
}

// ========== Data Processing ==========

// For A-share: data is array of objects with period + field values
// For HK: data is pivot-format array [{ end_date, 指标A: val, 指标B: val, ... }]

const sortedData = computed(() => {
  if (!props.data?.length) return []
  return [...props.data].sort((a, b) => {
    const pa = a.period || a.end_date || ''
    const pb = b.period || b.end_date || ''
    return pb.localeCompare(pa) // Newest first
  })
})

// ========== A-Share Row-based Table ==========

const aShareColumns = computed(() => {
  if (isHK.value || !sortedData.value.length) return []

  const cols: any[] = [
    {
      colKey: 'label',
      title: '指标项',
      fixed: 'left' as const,
      width: 180,
    },
  ]

  sortedData.value.forEach((item, idx) => {
    const period = item.period || item.end_date || `第${idx + 1}期`
    cols.push({
      colKey: `p_${idx}`,
      title: period,
      width: 140,
      align: 'right' as const,
    })
  })

  return cols
})

const aShareRows = computed(() => {
  if (isHK.value || !sortedData.value.length) return []
  const fields = getAShareFields()
  const rows: any[] = []

  for (const field of fields) {
    if (field.isHeader) {
      rows.push({
        label: field.label,
        _isHeader: true,
        _key: field.key,
      })
      continue
    }

    const row: any = {
      label: field.label,
      _key: field.key,
      _format: field.format,
      _isHeader: false,
    }

    sortedData.value.forEach((item, idx) => {
      row[`p_${idx}`] = item[field.key]
    })

    // Only include if at least one period has data
    const hasAny = sortedData.value.some((_, idx) => {
      const v = row[`p_${idx}`]
      return v !== null && v !== undefined && v !== '' && v !== '\\N'
    })

    if (hasAny || field.key.includes('total') || field.key.includes('n_income') || field.key.includes('revenue')) {
      rows.push(row)
    }
  }

  return rows
})

// ========== HK Pivot Table ==========

const excludeKeys = new Set(['end_date', 'ts_code', 'code', 'ann_date', 'report_type'])

const hkColumns = computed(() => {
  if (!isHK.value || !sortedData.value.length) return []
  const cols: any[] = [
    {
      colKey: 'indicator',
      title: '指标',
      fixed: 'left' as const,
      width: 200,
    },
  ]

  sortedData.value.forEach((item, idx) => {
    const period = item.end_date || `第${idx + 1}期`
    cols.push({
      colKey: `p_${idx}`,
      title: period,
      width: 140,
      align: 'right' as const,
    })
  })

  return cols
})

const hkRows = computed(() => {
  if (!isHK.value || !sortedData.value.length) return []

  // Collect all indicator names across all periods
  const allKeys = new Set<string>()
  sortedData.value.forEach(item => {
    Object.keys(item).forEach(k => {
      if (!excludeKeys.has(k)) allKeys.add(k)
    })
  })

  const rows: any[] = []
  for (const indicator of allKeys) {
    const row: any = { indicator }
    let hasAnyValue = false

    sortedData.value.forEach((item, idx) => {
      const val = item[indicator]
      row[`p_${idx}`] = val
      if (val !== null && val !== undefined && val !== '' && val !== '\\N') {
        hasAnyValue = true
      }
    })

    if (hasAnyValue) rows.push(row)
  }

  return rows
})

// ========== Cell Rendering ==========

const formatCell = (val: any, format?: string): string => {
  if (format === 'amount') return formatAmount(val)
  if (format === 'pct') {
    const n = parseNum(val)
    if (n === null) return '-'
    return n.toFixed(2) + '%'
  }
  return formatValue(val)
}

const getCellClass = (val: any): string => {
  const n = parseNum(val)
  if (n === null) return ''
  if (n < 0) return 'negative-cell'
  return ''
}
</script>

<template>
  <div class="report-statement-tab">
    <div class="statement-header">
      <span class="statement-icon">{{ statementIcon }}</span>
      <span class="statement-title">{{ statementTitle }}</span>
      <t-tag v-if="isHK" theme="warning" variant="light" size="small">港股</t-tag>
      <t-tag v-else theme="primary" variant="light" size="small">A股</t-tag>
      <span class="period-count" v-if="sortedData.length">
        （共 {{ sortedData.length }} 期数据）
      </span>
    </div>

    <template v-if="sortedData.length > 0">
      <!-- A-Share: Structured field-based table -->
      <div v-if="!isHK" class="statement-table-wrapper">
        <t-table
          :data="aShareRows"
          :columns="aShareColumns"
          size="small"
          bordered
          :scroll="{ x: 180 + sortedData.length * 140 }"
          row-key="_key"
          :row-class-name="(params: any) => params.row._isHeader ? 'header-row' : ''"
        >
          <template #label="{ row }">
            <span v-if="row._isHeader" class="field-header">{{ row.label }}</span>
            <span v-else class="field-label">{{ row.label }}</span>
          </template>

          <template v-for="(_, idx) in sortedData" :key="idx" #[`p_${idx}`]="{ row }">
            <template v-if="row._isHeader">
              <span></span>
            </template>
            <template v-else>
              <span :class="getCellClass(row[`p_${idx}`])">
                {{ formatCell(row[`p_${idx}`], row._format) }}
              </span>
            </template>
          </template>
        </t-table>
      </div>

      <!-- HK: Pivot-format dynamic table -->
      <div v-else class="statement-table-wrapper">
        <t-table
          :data="hkRows"
          :columns="hkColumns"
          size="small"
          bordered
          :scroll="{ x: 200 + sortedData.length * 140 }"
          row-key="indicator"
        >
          <template #indicator="{ row }">
            <span class="field-label">{{ row.indicator }}</span>
          </template>

          <template v-for="(_, idx) in sortedData" :key="idx" #[`p_${idx}`]="{ row }">
            <span :class="getCellClass(row[`p_${idx}`])">
              {{ formatAmount(row[`p_${idx}`]) }}
            </span>
          </template>
        </t-table>
      </div>
    </template>

    <t-empty v-else :description="`暂无${statementTitle}数据`" />
  </div>
</template>

<style scoped>
.report-statement-tab {
  padding: 4px 0;
}

.statement-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.statement-icon {
  font-size: 20px;
}

.statement-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.period-count {
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.statement-table-wrapper {
  border-radius: 8px;
  overflow: hidden;
}

/* Header rows for grouped sections */
:deep(.header-row) {
  background: var(--td-bg-color-secondarycontainer) !important;
}

:deep(.header-row td) {
  font-weight: 600 !important;
  color: var(--td-text-color-primary) !important;
}

.field-header {
  font-weight: 700;
  font-size: 13px;
  color: var(--td-text-color-primary);
  letter-spacing: 0.3px;
}

.field-label {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  padding-left: 8px;
}

.negative-cell {
  color: var(--td-error-color);
  font-weight: 500;
}

:deep(.t-table th) {
  background: var(--td-bg-color-secondarycontainer) !important;
  font-weight: 600;
  font-size: 13px;
}

:deep(.t-table td) {
  font-family: 'DIN Alternate', 'SF Mono', 'Monaco', monospace;
  font-size: 13px;
}
</style>
