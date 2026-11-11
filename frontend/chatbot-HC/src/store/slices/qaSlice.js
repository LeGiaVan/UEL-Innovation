import { API_URL, fetchApi as fetch } from '../../api/client'
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import axios from '../../api/client'

// Cấu hình API dùng chung cho phòng.


export const fetchQA = createAsyncThunk(
  'qa/fetchQA',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${API_URL}/qa`)
      return response.data
    } catch (error) {
      return rejectWithValue((typeof error.response?.data?.detail === 'string' ? error.response.data.detail : error.message))
    }
  }
)

const qaSlice = createSlice({
  name: 'qa',
  initialState: {
    questions: [],
    isLoading: false,
    error: null,
  },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchQA.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchQA.fulfilled, (state, action) => {
        state.isLoading = false
        state.questions = action.payload
      })
      .addCase(fetchQA.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload || 'Có lỗi xảy ra khi tải câu hỏi'
      })
  },
})

export default qaSlice.reducer
