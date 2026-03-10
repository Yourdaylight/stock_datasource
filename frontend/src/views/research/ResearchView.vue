<script setup lang="ts">
// ResearchView is now a layout container for nested routes:
// /research          -> CompanyListView
// /research/:code    -> ReportListView
// /research/:code/:period -> ReportDetailView
</script>

<template>
  <div class="research-layout">
    <router-view />
  </div>
</template>

<style scoped>
.research-layout {
  height: 100%;
  background: var(--td-bg-color-page);
}
</style>
