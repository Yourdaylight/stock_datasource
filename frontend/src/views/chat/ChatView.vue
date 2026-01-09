<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { useChatStore } from '@/stores/chat'
import MessageList from './components/MessageList.vue'
import InputBox from './components/InputBox.vue'

const chatStore = useChatStore()
const messageListRef = ref<HTMLElement | null>(null)

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

const handleSend = async (content: string) => {
  await chatStore.sendMessage(content)
}

// Auto scroll when messages change or streaming content updates
watch(
  () => [chatStore.messages.length, chatStore.streamingContent],
  () => scrollToBottom(),
  { deep: true }
)

onMounted(() => {
  chatStore.initSession()
})
</script>

<template>
  <div class="chat-view">
    <div class="chat-container">
      <div ref="messageListRef" class="message-area">
        <MessageList :messages="chatStore.messages" :loading="chatStore.loading" />
      </div>
      
      <div class="input-area">
        <div class="suggestions">
          <t-tag
            v-for="suggestion in ['分析贵州茅台', '推荐低估值股票', '今日大盘走势']"
            :key="suggestion"
            theme="primary"
            variant="light"
            class="suggestion-tag"
            @click="handleSend(suggestion)"
          >
            {{ suggestion }}
          </t-tag>
        </div>
        <InputBox @send="handleSend" :disabled="chatStore.loading" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.message-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.input-area {
  border-top: 1px solid #e7e7e7;
  padding: 16px 20px;
}

.suggestions {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.suggestion-tag {
  cursor: pointer;
}

.suggestion-tag:hover {
  opacity: 0.8;
}
</style>
