import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import api, { API_URL } from '../../api/client'
import { setAccessToken } from '../../api/session'
import department from '../../config/department.json'

export const login = createAsyncThunk('auth/login', async (credentials, {rejectWithValue}) => {
 try {
  const {data} = await api.post(`${API_URL}/auth/login`, credentials)
  setAccessToken(data.access_token)
  if (!data.user.memberships.some(m => m.department === department.id)) {
   try { await api.post(`${API_URL}/auth/logout`) } finally { setAccessToken(null) }
   return rejectWithValue('Tài khoản chưa được cấp quyền truy cập phòng này.')
  }
  return data.user
 } catch (error) {
  setAccessToken(null)
  const detail = error.response?.data?.detail
  return rejectWithValue(typeof detail === 'string' ? detail : 'Không thể đăng nhập. Vui lòng kiểm tra thông tin và kết nối.')
 }
})
export const logout = createAsyncThunk('auth/logout', async () => {
 try { await api.post(`${API_URL}/auth/logout`) } finally { setAccessToken(null) }
})
const slice = createSlice({
 name:'auth', initialState:{user:null,isLoading:false,error:null},
 reducers:{sessionExpired:state=>{state.user=null;state.error='Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'}},
 extraReducers:builder=>builder
  .addCase(login.pending,state=>{state.isLoading=true;state.error=null})
  .addCase(login.fulfilled,(state,action)=>{state.isLoading=false;state.user=action.payload})
  .addCase(login.rejected,(state,action)=>{state.isLoading=false;state.error=action.payload})
})
export const {sessionExpired} = slice.actions
export default slice.reducer
