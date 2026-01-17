<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  (e: 'click'): void
}>()

const isHovered = ref(false)

const handleClick = () => {
  emit('click')
}
</script>

<template>
  <div 
    class="float-button"
    :class="{ hovered: isHovered }"
    @mouseenter="isHovered = true"
    @mouseleave="isHovered = false"
    @click="handleClick"
  >
    <t-icon name="chat" size="24px" />
    <span class="button-text" v-if="isHovered">AI助手</span>
  </div>
</template>

<style scoped>
.float-button {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 56px;
  height: 56px;
  border-radius: 28px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
  transition: all 0.3s ease;
  z-index: 1000;
  overflow: hidden;
}

.float-button:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.5);
}

.float-button.hovered {
  width: 120px;
  padding: 0 16px;
}

.button-text {
  margin-left: 8px;
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
}
</style>
