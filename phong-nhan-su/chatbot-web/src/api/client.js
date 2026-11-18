import axios from 'axios'
import { getAccessToken, expireSession } from './session'

export const API_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')
export const MOCK_API = false

export async function fetchApi(url, options = {}) {
  const headers = new Headers(options.headers)
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await globalThis.fetch(url, { ...options, headers, credentials: 'include' })
  if (response.status === 401 && token === getAccessToken()) expireSession()
  return response
}

const client = axios.create({ timeout: 30000, withCredentials: true })
client.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) expireSession()
    return Promise.reject(error)
  },
)

export default client
