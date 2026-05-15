import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  define: {
    // 让浏览器端的axios直接请求后端地址
    'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://9.135.79.139:6688')
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: false
  }
})
