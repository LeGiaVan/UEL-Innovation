import { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import api, { API_URL } from '../api/client'
import { loginWithGoogle } from '../store/slices/authSlice'
import department from '../config/department.json'
import './LoginPage.css'

export default function LoginPage() {
  const dispatch = useDispatch()
  const { isLoading, error } = useSelector((s) => s.auth)
  const btnRef = useRef(null)
  const [setupError, setSetupError] = useState('')

  useEffect(() => {
    let cancelled = false
    let timer
    let tries = 0

    async function boot() {
      let clientId = ''
      try {
        const { data } = await api.get(`${API_URL}/auth/config`)
        clientId = data?.google_client_id || ''
      } catch {
        if (!cancelled) {
          setSetupError('Không gọi được API /api/auth/config. Kiểm tra uvicorn (cổng 8001) và proxy Vite.')
        }
        return
      }
      if (cancelled) return
      if (!clientId) {
        setSetupError(
          'Chưa có GOOGLE_CLIENT_ID. Điền vào starter/.env hoặc starter/chatbot-api/.env rồi restart uvicorn.',
        )
        return
      }

      const start = () => {
        if (!btnRef.current || !window.google?.accounts?.id) return false
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (response) => {
            if (response?.credential) {
              dispatch(loginWithGoogle(response.credential))
            }
          },
        })
        window.google.accounts.id.renderButton(btnRef.current, {
          theme: 'outline',
          size: 'large',
          text: 'signin_with',
          locale: 'vi',
          width: 320,
        })
        return true
      }

      if (start()) return
      timer = window.setInterval(() => {
        tries += 1
        if (start()) {
          window.clearInterval(timer)
          return
        }
        if (tries > 40 && !cancelled) {
          window.clearInterval(timer)
          setSetupError('Không tải được script Google Identity. Kiểm tra mạng / chặn quảng cáo.')
        }
      }, 150)
    }

    boot()
    return () => {
      cancelled = true
      if (timer) window.clearInterval(timer)
    }
  }, [dispatch])

  return (
    <main className="login-page">
      <div className="login-card">
        <img src="/docs/logo-2026-06.png" alt="UEL" />
        <h1>Trợ lý {department.name}</h1>
        <p>Đăng nhập bằng Google. Không dùng mật khẩu.</p>
        <div ref={btnRef} className="google-btn-slot" />
        {isLoading ? <p>Đang đăng nhập…</p> : null}
        {setupError ? <p role="alert">{setupError}</p> : null}
        {error ? <p role="alert">{error}</p> : null}
      </div>
    </main>
  )
}
