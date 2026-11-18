import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'
import api, { API_URL } from '../../api/client'

export const loadMe = createAsyncThunk('auth/loadMe', async (_, { rejectWithValue }) => {
  try {
    const { data } = await api.get(`${API_URL}/auth/me`)
    if (!data?.authenticated) return rejectWithValue(null)
    return data
  } catch {
    return rejectWithValue(null)
  }
})

export const loginWithGoogle = createAsyncThunk(
  'auth/loginWithGoogle',
  async (idToken, { rejectWithValue }) => {
    try {
      const { data } = await api.post(`${API_URL}/auth/google`, { id_token: idToken })
      return data
    } catch (error) {
      const detail = error.response?.data?.detail
      return rejectWithValue(
        typeof detail === 'string' ? detail : 'Không đăng nhập được Google.',
      )
    }
  },
)

export const logout = createAsyncThunk('auth/logout', async () => {
  try {
    await api.post(`${API_URL}/auth/logout`)
  } catch {
    /* cookie may already be gone */
  }
})

const slice = createSlice({
  name: 'auth',
  initialState: { user: null, isLoading: false, loaded: false, error: null },
  reducers: {
    sessionExpired: (state) => {
      state.user = null
      state.loaded = true
      state.error = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadMe.fulfilled, (state, action) => {
        state.loaded = true
        state.user = action.payload
      })
      .addCase(loadMe.rejected, (state) => {
        state.loaded = true
        state.user = null
      })
      .addCase(loginWithGoogle.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(loginWithGoogle.fulfilled, (state, action) => {
        state.isLoading = false
        state.loaded = true
        state.user = action.payload
      })
      .addCase(loginWithGoogle.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload
      })
      .addCase(logout.fulfilled, (state) => {
        state.user = null
        state.loaded = true
        state.isLoading = false
        state.error = null
      })
      .addCase(logout.rejected, (state) => {
        state.user = null
        state.loaded = true
        state.isLoading = false
      })
  },
})

export const { sessionExpired } = slice.actions
export default slice.reducer
