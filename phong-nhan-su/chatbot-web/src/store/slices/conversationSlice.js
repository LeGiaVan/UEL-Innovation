import { createSlice } from '@reduxjs/toolkit'

const slice = createSlice({
  name: 'conversation',
  initialState: { items: [] },
  reducers: {
    setConversations(state, action) {
      state.items = action.payload
    },
  },
})

export const { setConversations } = slice.actions
export default slice.reducer
