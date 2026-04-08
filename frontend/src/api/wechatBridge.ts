import { request } from '@/utils/request'

export interface PicoclawStatus {
  installed: boolean
  version: string | null
  running: boolean
  pid: number | null
  port: number | null
  gateway_url: string | null
  rt_running: boolean
  rt_pid: number | null
  config_exists: boolean
  config_path: string
}

export interface PicoclawConfig {
  llm_model: string
  llm_base_url: string
  mcp_server_url: string
  mcp_connected: boolean
  ws_realtime_url: string
  channel_weixin_enabled: boolean
  config_path: string
  raw_config?: string
}

export interface ActionResponse {
  success: boolean
  message: string
  pid?: number
  rt_pid?: number | null
}

export interface WechatQrResponse {
  success: boolean
  message: string
  qr_url?: string | null
  output?: string | null
  error?: string | null
  pid?: number
}

export const wechatBridgeApi = {
  getStatus(): Promise<PicoclawStatus> {
    return request.get('/api/wechat-bridge/status')
  },

  getConfig(): Promise<PicoclawConfig> {
    return request.get('/api/wechat-bridge/config')
  },

  generateConfig(mcpToken?: string): Promise<ActionResponse> {
    return request.post('/api/wechat-bridge/generate-config', null, {
      params: { mcp_token: mcpToken }
    })
  },

  start(options?: { mcpToken?: string; symbols?: string; noRt?: boolean }): Promise<ActionResponse> {
    // Downloading picoclaw (~22MB) can take time; allow up to 5 minutes
    return request.post('/api/wechat-bridge/start', null, {
      params: {
        mcp_token: options?.mcpToken,
        symbols: options?.symbols,
        no_rt: options?.noRt
      },
      timeout: 300_000,  // 5 min for download + extract + start
    })
  },

  stop(): Promise<ActionResponse> {
    return request.post('/api/wechat-bridge/stop')
  },

  triggerWechatLogin(): Promise<WechatQrResponse> {
    return request.get('/api/wechat-bridge/weixin-qr', { timeout: 30_000 })
  },
}
