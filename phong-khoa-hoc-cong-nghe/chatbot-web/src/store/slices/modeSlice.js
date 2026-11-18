import { FALLBACK_CHAT_MODES } from '../../constants/chatModes'
import { API_URL, fetchApi as fetch } from '../../api/client'
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import axios from '../../api/client'



export const fetchChatModes = createAsyncThunk(
  'mode/fetchChatModes',
  async (_, { rejectWithValue }) => {
    try {
      const { data } = await axios.get(`${API_URL}/chat/modes`)
      return Array.isArray(data.modes) ? data.modes : []
    } catch (error) {
      const raw = error.response?.data?.detail
      const detail = Array.isArray(raw)
        ? raw.map((x) => x.msg || String(x)).join(' ')
        : raw
      return rejectWithValue(
        detail || error.response?.data || error.message || 'Không tải được danh sách chế độ'
      )
    }
  }
)

const modeSlice = createSlice({
  name: 'mode',
  initialState: {
    /** Mặc định module_1 (hub Thông tin tuyển sinh — gồm CTĐT + FAQ + lịch). */
    selectedMode: 'module_1',
    modes: FALLBACK_CHAT_MODES,
    loaded: false,
    error: null,
  },
  reducers: {
    setSelectedMode: (state, action) => {
      state.selectedMode = action.payload
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchChatModes.pending, (state) => {
        state.error = null
      })
      .addCase(fetchChatModes.fulfilled, (state, action) => {
        const all = Array.isArray(action.payload) ? action.payload : []
        state.modes = all.filter(
          (m) =>
            m &&
            typeof m.id === 'string' &&
            (m.id === 'auto' || m.id.startsWith('module_'))
        )
        state.loaded = true
        const valid = new Set(state.modes.map((m) => m.id))
        if (!valid.has(state.selectedMode)) {
          state.selectedMode = valid.has('module_1') ? 'module_1' : (valid.has('auto') ? 'auto' : 'module_1_1')
        }
      })
      .addCase(fetchChatModes.rejected, (state, action) => {
        state.loaded = true
        state.error =
          typeof action.payload === 'string'
            ? action.payload
            : 'Không tải được danh sách chế độ'
      })
  },
})

export const { setSelectedMode } = modeSlice.actions
export default modeSlice.reducer
