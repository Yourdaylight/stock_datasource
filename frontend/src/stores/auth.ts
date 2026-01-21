import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { User, LoginRequest, RegisterRequest } from '@/types/auth'

const TOKEN_KEY = 'token'
const USER_KEY = 'user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<User | null>(null)
  const loading = ref(false)

  // Try to restore user from localStorage
  const storedUser = localStorage.getItem(USER_KEY)
  if (storedUser) {
    try {
      user.value = JSON.parse(storedUser)
    } catch {
      localStorage.removeItem(USER_KEY)
    }
  }

  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.is_admin === true)

  const login = async (data: LoginRequest): Promise<boolean> => {
    loading.value = true
    try {
      const response = await authApi.login(data)
      token.value = response.access_token
      localStorage.setItem(TOKEN_KEY, response.access_token)
      
      // Fetch user info after login
      await fetchUser()
      return true
    } catch (e) {
      return false
    } finally {
      loading.value = false
    }
  }

  const register = async (data: RegisterRequest): Promise<{ success: boolean; message: string }> => {
    loading.value = true
    try {
      const response = await authApi.register(data)
      return { success: response.success, message: response.message }
    } catch (e: any) {
      const message = e.response?.data?.detail || e.message || '注册失败'
      return { success: false, message }
    } finally {
      loading.value = false
    }
  }

  const fetchUser = async (): Promise<boolean> => {
    if (!token.value) return false
    
    try {
      const response = await authApi.getMe()
      user.value = response
      localStorage.setItem(USER_KEY, JSON.stringify(response))
      return true
    } catch (e) {
      // Token might be expired
      logout()
      return false
    }
  }

  const logout = () => {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  const checkAuth = async (): Promise<boolean> => {
    if (!token.value) return false
    if (user.value) return true
    return await fetchUser()
  }

  return {
    token,
    user,
    loading,
    isAuthenticated,
    isAdmin,
    login,
    register,
    fetchUser,
    logout,
    checkAuth
  }
})
