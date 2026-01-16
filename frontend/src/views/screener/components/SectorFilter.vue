<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useScreenerStore } from '@/stores/screener'

const screenerStore = useScreenerStore()

const searchText = ref('')

const filteredSectors = computed(() => {
  if (!searchText.value) {
    return screenerStore.sectors
  }
  return screenerStore.sectors.filter(s => 
    s.name.includes(searchText.value)
  )
})

const handleSelectSector = (sector: string) => {
  screenerStore.filterBySector(sector)
}

const handleClear = () => {
  screenerStore.clearSectorFilter()
}

onMounted(() => {
  if (screenerStore.sectors.length === 0) {
    screenerStore.fetchSectors()
  }
})
</script>

<template>
  <div class="sector-filter">
    <div class="sector-header">
      <span class="sector-title">行业筛选</span>
      <t-link 
        v-if="screenerStore.selectedSector" 
        theme="primary" 
        @click="handleClear"
      >
        清除
      </t-link>
    </div>
    
    <t-input
      v-model="searchText"
      placeholder="搜索行业"
      clearable
      size="small"
      style="margin-bottom: 12px"
    >
      <template #prefix-icon>
        <t-icon name="search" />
      </template>
    </t-input>
    
    <t-loading :loading="screenerStore.sectorsLoading" size="small">
      <div class="sector-tags">
        <t-tag
          v-for="sector in filteredSectors"
          :key="sector.name"
          :theme="screenerStore.selectedSector === sector.name ? 'primary' : 'default'"
          :variant="screenerStore.selectedSector === sector.name ? 'dark' : 'light'"
          class="sector-tag"
          @click="handleSelectSector(sector.name)"
        >
          {{ sector.name }}
          <span class="sector-count">({{ sector.stock_count }})</span>
        </t-tag>
      </div>
      
      <t-empty 
        v-if="filteredSectors.length === 0 && !screenerStore.sectorsLoading"
        description="无匹配行业"
        size="small"
      />
    </t-loading>
  </div>
</template>

<style scoped>
.sector-filter {
  padding: 8px 0;
}

.sector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.sector-title {
  font-weight: 500;
  font-size: 14px;
}

.sector-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.sector-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.sector-tag:hover {
  transform: scale(1.02);
}

.sector-count {
  font-size: 10px;
  margin-left: 2px;
  opacity: 0.7;
}
</style>
