<script setup lang="ts">
import { useRouter } from 'vue-router'

interface Props {
  /** 空状态描述文案 */
  description?: string
  /** 可选：跳转数据管理时预选的插件名 */
  pluginName?: string
  /** 是否显示"前往数据管理"按钮，默认 true */
  showGuide?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  description: '暂无数据',
  pluginName: '',
  showGuide: true,
})

const router = useRouter()

const handleGoToDataManage = () => {
  const query: Record<string, string> = {}
  if (props.pluginName) {
    query.plugin = props.pluginName
  }
  router.push({ path: '/datamanage', query })
}
</script>

<template>
  <div class="data-empty-guide">
    <t-empty :description="description">
      <template v-if="showGuide" #extra>
        <div class="guide-tip">
          <span class="guide-text">可在「数据管理」中执行插件更新数据</span>
          <t-button size="small" theme="primary" variant="outline" @click="handleGoToDataManage">
            前往数据管理
          </t-button>
        </div>
      </template>
    </t-empty>
  </div>
</template>

<style scoped>
.data-empty-guide {
  padding: 16px 0;
}

.guide-tip {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.guide-text {
  font-size: 13px;
  color: var(--td-text-color-placeholder);
}
</style>
