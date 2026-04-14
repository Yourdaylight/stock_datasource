import request from '@/utils/request'

export interface BrokerProfile {
  id: string
  user_id: string
  name: string
  broker: string
  is_default: boolean
}

export const profileApi = {
  list(): Promise<BrokerProfile[]> {
    return request.get('/api/portfolio/profiles')
  },

  create(data: { name: string; broker?: string; is_default?: boolean }): Promise<BrokerProfile> {
    return request.post('/api/portfolio/profiles', data)
  },

  get(profileId: string): Promise<BrokerProfile> {
    return request.get(`/api/portfolio/profiles/${profileId}`)
  },

  update(profileId: string, data: { name?: string; broker?: string }): Promise<BrokerProfile> {
    return request.put(`/api/portfolio/profiles/${profileId}`, data)
  },

  delete(profileId: string): Promise<{ success: boolean; message: string }> {
    return request.delete(`/api/portfolio/profiles/${profileId}`)
  },
}
