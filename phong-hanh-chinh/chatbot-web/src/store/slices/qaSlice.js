import { API_URL } from '../../api/client'
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import axios from '../../api/client'

export const fetchQA = createAsyncThunk(
  'qa/fetchQA',
  async (arg, { getState, rejectWithValue }) => {
    try {
      const all = Boolean(arg?.all)
      const mode = all ? null : arg?.mode || getState().mode?.selectedMode || 'module_1'
      const response = await axios.get(`${API_URL}/qa`, all ? {} : { params: { mode } })
      return { mode: all ? 'all' : mode, questions: Array.isArray(response.data) ? response.data : [] }
    } catch (error) {
      return rejectWithValue(
        typeof error.response?.data?.detail === 'string' ? error.response.data.detail : error.message
      )
    }
  }
)

const qaSlice = createSlice({
  name: 'qa',
  initialState: {
    questions: [],
    mode: null,
    isLoading: false,
    error: null,
  },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchQA.pending, (state, action) => {
        state.isLoading = true
        state.error = null
        const nextMode = action.meta.arg?.mode
        if (nextMode && nextMode !== state.mode) {
          state.questions = []
        }
      })
      .addCase(fetchQA.fulfilled, (state, action) => {
        state.isLoading = false
        state.mode = action.payload.mode
        state.questions = action.payload.questions
      })
      .addCase(fetchQA.rejected, (state, action) => {
        state.isLoading = false
        state.questions = []
        state.error = action.payload || 'Có lỗi xảy ra khi tải câu hỏi'
      })
  },
})

export default qaSlice.reducer
