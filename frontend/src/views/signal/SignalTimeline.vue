<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useSignalAggregatorStore } from '@/stores/signalAggregator'
import type { SignalSnapshot } from '@/api/signalAggregator'

const props = defineProps<{
  tsCode: string
}>()

const signalStore = useSignalAggregatorStore()
const days = ref(30)

const fetchTimeline = async () => {
  if (!props.tsCode) return
  await signalStore.fetchTimeline(props.tsCode, days.value)
}

// 评分颜色
const scoreColor = (score: number) => {
  if (score >= 70) return '#00a870'
  if (score >= 55) return '#0052d9'
  if (score >= 40) return '#e37318'
  return '#d54941'
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  if (dateStr.length === 8) {
    return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`
  }
  return dateStr
}

watch(() => props.tsCode, fetchTimeline)
onMounted(fetchTimeline)
</script>

<template>
  <div class="signal-timeline">
    <!-- 控制栏 -->
    <div class="timeline-controls">
      <span>回溯天数：</span>
      <t-radio-group v-model="days" variant="default-filled" size="small" @change="fetchTimeline">
        <t-radio-button :value="7">7天</t-radio-button>
        <t-radio-button :value="14">14天</t-radio-button>
        <t-radio-button :value="30">30天</t-radio-button>
        <t-radio-button :value="90">90天</t-radio-button>
      </t-radio-group>
    </div>

    <!-- 数据表格 -->
    <t-table
      :data="signalStore.timeline?.snapshots || []"
      :loading="signalStore.loading"
      row-key="signal_date"
      size="small"
      stripe
      max-height="500"
    >
      <t-table-col title="日期" field="signal_date" width="110">
        <template #cell="{ row }">
          {{ formatDate(row.signal_date) }}
        </template>
      </t-table-col>
      <t-table-col title="综合评分" field="composite_score" width="100" align="center">
        <template #cell="{ row }">
          <span :style="{ color: scoreColor(row.composite_score), fontWeight: 'bold' }">
            {{ row.composite_score?.toFixed(1) }}
          </span>
        </template>
      </t-table-col>
      <t-table-col title="消息面" field="news_score" width="80" align="center">
        <template #cell="{ row }">
          <span :style="{ color: scoreColor(row.news_score) }">
            {{ row.news_score?.toFixed(0) }}
          </span>
        </template>
      </t-table-col>
      <t-table-col title="资金面" field="capital_score" width="80" align="center">
        <template #cell="{ row }">
          <span :style="{ color: scoreColor(row.capital_score) }">
            {{ row.capital_score?.toFixed(0) }}
          </span>
        </template>
      </t-table-col>
      <t-table-col title="技术面" field="tech_score" width="80" align="center">
        <template #cell="{ row }">
          <span :style="{ color: scoreColor(row.tech_score) }">
            {{ row.tech_score?.toFixed(0) }}
          </span>
        </template>
      </t-table-col>
      <t-table-col title="消息面详情" field="news_detail" min-width="200">
        <template #cell="{ row }">
          <div class="detail-cell">
            <template v-if="row.news_detail?.top_headlines?.length">
              <div v-for="(h, i) in row.news_detail.top_headlines.slice(0, 2)" :key="i" class="headline-item">
                {{ h }}
              </div>
            </template>
            <template v-else-if="row.news_detail?.reason">
              {{ row.news_detail.reason }}
            </template>
            <span v-else class="text-secondary">-</span>
          </div>
        </template>
      </t-table-col>
      <t-table-col title="资金面详情" field="capital_detail" min-width="200">
        <template #cell="{ row }">
          <div class="detail-cell">
            <template v-if="row.capital_detail">
              <div v-if="row.capital_detail.net_institutional_flow">
                机构净流入: {{ (row.capital_detail.net_institutional_flow / 1e8).toFixed(2) }}亿
              </div>
              <div v-if="row.capital_detail.hot_money_count">
                游资席位: {{ row.capital_detail.hot_money_count }}
              </div>
              <div v-if="row.capital_detail.seat_hhi">
                HHI: {{ row.capital_detail.seat_hhi.toFixed(2) }}
              </div>
            </template>
            <span v-else class="text-secondary">-</span>
          </div>
        </template>
      </t-table-col>
    </t-table>

    <!-- 趋势简图（文字版） -->
    <t-card title="评分趋势" style="margin-top: 12px" v-if="signalStore.timeline?.snapshots?.length">
      <div class="trend-chart">
        <div
          v-for="snapshot in [...(signalStore.timeline?.snapshots || [])].reverse()"
          :key="snapshot.signal_date"
          class="trend-bar"
        >
          <div class="trend-date">{{ formatDate(snapshot.signal_date).slice(5) }}</div>
          <div class="trend-bars">
            <div
              class="bar news"
              :style="{ width: snapshot.news_score + '%', backgroundColor: scoreColor(snapshot.news_score) }"
              :title="`消息面: ${snapshot.news_score?.toFixed(1)}`"
            />
            <div
              class="bar capital"
              :style="{ width: snapshot.capital_score + '%', backgroundColor: scoreColor(snapshot.capital_score) }"
              :title="`资金面: ${snapshot.capital_score?.toFixed(1)}`"
            />
            <div
              class="bar tech"
              :style="{ width: snapshot.tech_score + '%', backgroundColor: scoreColor(snapshot.tech_score) }"
              :title="`技术面: ${snapshot.tech_score?.toFixed(1)}`"
            />
          </div>
          <div class="trend-score" :style="{ color: scoreColor(snapshot.composite_score) }">
            {{ snapshot.composite_score?.toFixed(0) }}
          </div>
        </div>
      </div>
    </t-card>

    <t-empty v-if="!signalStore.loading && !signalStore.timeline?.snapshots?.length" description="暂无时序数据" />
  </div>
</template>

<style scoped>
.signal-timeline {
  padding: 8px;
}
.timeline-controls {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.detail-cell {
  font-size: 12px;
  line-height: 1.4;
}
.headline-item {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.text-secondary {
  color: #999;
}
.trend-chart {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.trend-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.trend-date {
  width: 40px;
  font-size: 11px;
  color: #666;
  flex-shrink: 0;
}
.trend-bars {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.bar {
  height: 6px;
  border-radius: 2px;
  transition: width 0.3s;
}
.trend-score {
  width: 30px;
  font-size: 12px;
  font-weight: bold;
  text-align: right;
  flex-shrink: 0;
}
</style>
