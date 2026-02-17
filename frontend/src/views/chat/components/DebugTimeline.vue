<script setup lang="ts">
import { computed } from 'vue'
import type { DebugMessage } from '@/stores/chat'
import { useChatStore } from '@/stores/chat'

const props = defineProps<{
  messages: DebugMessage[]
}>()

const chatStore = useChatStore()

interface TimelineSegment {
  agent: string
  displayName: string
  startTime: number
  endTime: number
  durationMs: number
  success: boolean
  laneId?: string
  color: string
}

const segments = computed<TimelineSegment[]>(() => {
  const segs: TimelineSegment[] = []
  const agentStarts: Record<string, DebugMessage> = {}

  const colors = ['#0052d9', '#2ba471', '#e37318', '#7b61ff', '#d54941', '#029cd4']
  let colorIdx = 0
  const agentColors: Record<string, string> = {}

  for (const msg of props.messages) {
    if (msg.debugType === 'agent_start') {
      agentStarts[msg.agent] = msg
      if (!agentColors[msg.agent]) {
        agentColors[msg.agent] = colors[colorIdx % colors.length]
        colorIdx++
      }
    }
    if (msg.debugType === 'agent_end') {
      const start = agentStarts[msg.agent]
      if (start) {
        segs.push({
          agent: msg.agent,
          displayName: chatStore.getAgentDisplayName(msg.agent),
          startTime: start.timestamp,
          endTime: msg.timestamp,
          durationMs: msg.data.duration_ms || 0,
          success: msg.data.success !== false,
          laneId: start.laneId,
          color: agentColors[msg.agent] || '#888',
        })
        delete agentStarts[msg.agent]
      }
    }
  }
  return segs
})

const totalDuration = computed(() => {
  if (segments.value.length === 0) return 0
  const minStart = Math.min(...segments.value.map(s => s.startTime))
  const maxEnd = Math.max(...segments.value.map(s => s.endTime))
  return maxEnd - minStart
})

const minStart = computed(() => {
  if (segments.value.length === 0) return 0
  return Math.min(...segments.value.map(s => s.startTime))
})

const getSegmentStyle = (seg: TimelineSegment) => {
  if (totalDuration.value === 0) return { left: '0%', width: '100%' }
  const left = ((seg.startTime - minStart.value) / totalDuration.value) * 100
  const width = Math.max(((seg.endTime - seg.startTime) / totalDuration.value) * 100, 3)
  return {
    left: `${left}%`,
    width: `${width}%`,
    background: seg.success ? seg.color : '#d54941',
  }
}

const formatDuration = (ms: number) => {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
</script>

<template>
  <div class="debug-timeline" v-if="segments.length > 0">
    <div class="timeline-header">
      <span class="timeline-title">执行时间线</span>
      <span class="timeline-total" v-if="totalDuration > 0">
        总计 {{ formatDuration(totalDuration * 1000) }}
      </span>
    </div>
    <div class="timeline-tracks">
      <div
        v-for="(seg, idx) in segments"
        :key="idx"
        class="timeline-track"
      >
        <span class="track-label">{{ seg.displayName }}</span>
        <div class="track-bar-container">
          <div class="track-bar" :style="getSegmentStyle(seg)">
            <span class="bar-label" v-if="seg.durationMs > 0">{{ formatDuration(seg.durationMs) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.debug-timeline {
  padding: 12px;
  border-bottom: 1px solid var(--td-component-stroke, #e7e7e7);
  background: var(--td-bg-color-container, #fff);
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.timeline-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--td-text-color-primary, #333);
}

.timeline-total {
  font-size: 11px;
  color: var(--td-text-color-secondary, #888);
}

.timeline-tracks {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.timeline-track {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 20px;
}

.track-label {
  flex-shrink: 0;
  width: 70px;
  font-size: 11px;
  color: var(--td-text-color-secondary, #666);
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.track-bar-container {
  flex: 1;
  position: relative;
  height: 14px;
  background: var(--td-bg-color-page, #f5f5f5);
  border-radius: 3px;
  overflow: hidden;
}

.track-bar {
  position: absolute;
  top: 0;
  height: 100%;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 4px;
  opacity: 0.85;
  transition: opacity 0.2s;
}

.track-bar:hover {
  opacity: 1;
}

.bar-label {
  font-size: 10px;
  color: #fff;
  font-weight: 500;
  white-space: nowrap;
  padding: 0 4px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}
</style>
