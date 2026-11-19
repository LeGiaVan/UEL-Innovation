import { configureStore, combineReducers } from '@reduxjs/toolkit'
import chat from './slices/chatSlice'
import qa from './slices/qaSlice'
import mode from './slices/modeSlice'
import auth from './slices/authSlice'

const combined = combineReducers({ chat, qa, mode, auth })

const CLEAR_SESSION = [
  'auth/logout/fulfilled',
  'auth/logout/rejected',
  'auth/sessionExpired',
]

export const store = configureStore({
  devTools: import.meta.env.DEV
    ? {
        actionSanitizer: (action) =>
          action.type.startsWith('auth/login/')
            ? {
                ...action,
                meta: {
                  ...action.meta,
                  arg: { username: action.meta?.arg?.username, password: '[REDACTED]' },
                },
              }
            : action,
      }
    : false,
  reducer: (state, action) => {
    if (CLEAR_SESSION.includes(action.type)) {
      // Xóa chat/qa/mode; giữ loaded=true để AuthGate hiện login, không kẹt spinner.
      return combined(
        {
          auth: {
            user: null,
            isLoading: false,
            loaded: true,
            department: state?.auth?.department || null,
            googleClientId: state?.auth?.googleClientId || '',
            error:
              action.type === 'auth/sessionExpired'
                ? 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
                : null,
          },
        },
        action,
      )
    }
    return combined(state, action)
  },
})
