<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useChatStore } from '@/stores/chat'
import DebugMessage from './DebugMessage.vue'
import DebugTimeline from './DebugTimeline.vue'

const chatStore = useChatStore()
const messagesContainer = ref<HTMLElement | null>(null)

// Auto-scroll to bottom when new debug messages arrive
watch(
  () => chatStore.debugMessages.length,
  () => {
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      }
    })
  }
)

const hasMessages = computed(() => chatStore.debugMessages.length > 0)

const close = () => {
  chatStore.debugSidebarOpen = false
}
</script>

<template>
  <div class="debug-sidebar" v-if="chatStore.debugSidebarOpen">
    <div class="debug-sidebar__header">
      <div class="header-title">
        <t-icon name="bug-report" size="16px" />
        <span>Agent 调试</span>
        <t-tag size="small" variant="light" theme="primary" v-if="hasMessages">
          {{ chatStore.debugMessages.length }}
        </t-tag>
      </div>
      <t-button theme="default" variant="text" size="small" @click="close">
        <t-icon name="close" />
      </t-button>
    </div>

    <!-- Timeline overview -->
    <DebugTimeline :messages="chatStore.debugMessages" />

    <!-- Message list -->
    <div ref="messagesContainer" class="debug-sidebar__messages">
      <template v-if="hasMessages">
        <DebugMessage
          v-for="msg in chatStore.debugMessages"
          :key="msg.id"
          :message="msg"
        />
      </template>
      <div v-else class="debug-sidebar__empty">
        <t-icon name="info-circle" size="24px" />
        <p>发送消息后，Agent 的思考过程将在这里展示</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.debug-sidebar {
  width: 360px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--td-bg-color-container, #fff);
  border-left: 1px solid var(--td-component-stroke, #e7e7e7);
  height: 100%;
  overflow: hidden;
}

.debug-sidebar__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--td-component-stroke, #e7e7e7);
  background: var(--td-bg-color-container, #fff);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--td-text-color-primary, #333);
}

.debug-sidebar__messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px 4px;
}

.debug-sidebar__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 40px 20px;
  color: var(--td-text-color-placeholder, #aaa);
  text-align: center;
}

.debug-sidebar__empty p {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.5;
}

/* Responsive: overlay mode for medium screens */
@media (max-width: 1400px) {
  .debug-sidebar {
    position: absolute;
    right: 0;
    top: 0;
    bottom: 0;
    z-index: 100;
    box-shadow: -4px 0 16px rgba(0, 0, 0, 0.1);
  }
}

/* Responsive: drawer mode for small screens */
@media (max-width: 1024px) {
  .debug-sidebar {
    width: 100%;
    max-width: 360px;
  }
}
</style>
