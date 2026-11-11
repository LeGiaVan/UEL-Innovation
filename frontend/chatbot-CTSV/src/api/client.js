import axios from 'axios'
import { mockRequest } from './mockApi'
import department from '../config/department.json'
import { getAccessToken, expireSession } from './session'
export const API_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')
export const MOCK_API = import.meta.env.VITE_MOCK_API === 'true' || (import.meta.env.DEV && import.meta.env.VITE_MOCK_API !== 'false')
export async function fetchApi(url, options = {}) {
 if (MOCK_API) return mockRequest(url, options)
 const headers = new Headers(options.headers)
 headers.set('X-Department-ID', department.id)
 const token = getAccessToken()
 if (token) headers.set('Authorization', `Bearer ${token}`)
 const response = await globalThis.fetch(url, {...options, headers})
 if (response.status === 401 && token === getAccessToken()) expireSession()
 return response
}
const client = axios.create({ timeout: 30000 })
client.interceptors.request.use(config => {
 if (!MOCK_API) {
  config.headers['X-Department-ID'] = department.id
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
 }
 return config
})
client.interceptors.response.use(response => response, error => {
 if (!MOCK_API && error.response?.status === 401 && error.config?.headers?.Authorization === `Bearer ${getAccessToken()}`) expireSession()
 return Promise.reject(error)
})
if (MOCK_API) {
 client.defaults.adapter = async config => {
  const response = await mockRequest(config.url, { method: config.method, body: config.data, signal: config.signal })
  const data = await response.json()
  if (!response.ok) throw new axios.AxiosError(data.detail || 'Lỗi API', 'ERR_BAD_RESPONSE', config, null, {status:response.status,data})
  return {data,status:response.status,statusText:response.statusText,headers:{},config}
 }
}
export default client
