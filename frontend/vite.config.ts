import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { readFileSync } from 'fs'

// Read version from project root VERSION file
const version = (() => {
  try {
    return readFileSync(resolve(__dirname, '../VERSION'), 'utf-8').trim()
  } catch {
    return '0.0.0'
  }
})()

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  define: {
    // 让浏览器端的axios直接请求后端地址
    'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://9.135.79.139:6688'),
    __APP_VERSION__: JSON.stringify(version),
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: false
  }
})
