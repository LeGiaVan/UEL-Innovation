import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { loadMe, sessionExpired } from '../store/slices/authSlice'
import LoginPage from '../pages/LoginPage'

export default function AuthGate({ children }) {
  const dispatch = useDispatch()
  const { user, loaded } = useSelector((s) => s.auth)

  useEffect(() => {
    dispatch(loadMe())
  }, [dispatch])

  useEffect(() => {
    const expire = () => dispatch(sessionExpired())
    window.addEventListener('chatbot:unauthorized', expire)
    return () => window.removeEventListener('chatbot:unauthorized', expire)
  }, [dispatch])

  if (!loaded) {
    return <main className="login-page">Đang kiểm tra phiên đăng nhập…</main>
  }
  if (!user) return <LoginPage />
  return children
}
