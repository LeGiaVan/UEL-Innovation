import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { sessionExpired } from '../store/slices/authSlice'
import LoginPage from '../pages/LoginPage'

/** P1 khóa cookie. P0: vào chat để giữ giao diện cũ (header / sidebar / hub). */
const SKIP_AUTH_P0 = true

export default function AuthGate({ children }) {
  const dispatch = useDispatch()
  const user = useSelector((s) => s.auth.user)
  useEffect(() => {
    const expire = () => dispatch(sessionExpired())
    window.addEventListener('chatbot:unauthorized', expire)
    return () => window.removeEventListener('chatbot:unauthorized', expire)
  }, [dispatch])
  if (SKIP_AUTH_P0 || user) return children
  return <LoginPage />
}
