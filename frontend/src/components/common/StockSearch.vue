<script setup lang="ts">
import { ref } from 'vue'
import { marketApi } from '@/api/market'

const emit = defineEmits<{
  select: [code: string]
}>()

const searchValue = ref('')
const options = ref<{ value: string; label: string }[]>([])
const loading = ref(false)

let searchTimer: ReturnType<typeof setTimeout> | null = null

const handleSearch = async (keyword: string) => {
  if (!keyword) {
    options.value = []
    return
  }

  if (searchTimer) {
    clearTimeout(searchTimer)
  }

  searchTimer = setTimeout(async () => {
    loading.value = true
    try {
      const results = await marketApi.searchStock(keyword)
      options.value = results.map(item => ({
        value: item.code,
        label: `${item.code} - ${item.name}`
      }))
    } catch (e) {
      options.value = []
    } finally {
      loading.value = false
    }
  }, 300)
}

const handleChange = (value: string) => {
  emit('select', value)
}
</script>

<template>
  <t-select
    v-model="searchValue"
    filterable
    :loading="loading"
    :options="options"
    placeholder="搜索股票代码或名称"
    style="width: 200px"
    @search="handleSearch"
    @change="handleChange"
  />
</template>
