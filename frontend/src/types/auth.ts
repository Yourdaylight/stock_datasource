// User types
export interface User {
  id: string
  email: string
  username: string
  is_active: boolean
  created_at: string
}

// Request types
export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  username?: string
}

// Response types
export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface RegisterResponse {
  success: boolean
  message: string
  user?: User
}

export interface WhitelistEmail {
  id: string
  email: string
  added_by: string
  is_active: boolean
  created_at: string
}
