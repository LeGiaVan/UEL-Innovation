import { createSlice } from '@reduxjs/toolkit'

const slice = createSlice({
  name: 'module',
  initialState: { selected: null, items: [] },
  reducers: {
    setModules(state, action) {
      state.items = action.payload
      if (!state.selected && action.payload[0]) {
        state.selected = action.payload[0].code
      }
    },
    setSelectedModule(state, action) {
      state.selected = action.payload
    },
  },
})

export const { setModules, setSelectedModule } = slice.actions
export default slice.reducer
