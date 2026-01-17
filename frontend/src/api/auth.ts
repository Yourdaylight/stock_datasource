import request from '@/utils/request'
import type { 
  LoginRequest, 
  RegisterRequest, 
  TokenResponse, 
  RegisterResponse, 
  User,
  WhitelistEmail
} from '@/types/auth'

export const authApi = {
  // User registration
  register(data: RegisterRequest) {
    return request.post<RegisterResponse>('/api/auth/register', data)
  },

  // User login
  login(data: LoginRequest) {
    return request.post<TokenResponse>('/api/auth/login', data)
  },

  // Get current user info
  getMe() {
    return request.get<User>('/api/auth/me')
  },

  // Logout
  logout() {
    return request.post<{ success: boolean; message: string }>('/api/auth/logout')
  },

  // Get whitelist (requires auth)
  getWhitelist(params?: { limit?: number; offset?: number }) {
    return request.get<WhitelistEmail[]>('/api/auth/whitelist', { params })
  },

  // Add email to whitelist (requires auth)
  addToWhitelist(email: string) {
    return request.post<WhitelistEmail>('/api/auth/whitelist', { email })
  }
}
