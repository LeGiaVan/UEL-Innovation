import department from '../config/department.json'
import './LoginPage.css'

export default function LoginPage() {
  return (
    <main className="login-page">
      <div className="login-card">
        <img src="/docs/logo-2026-06.png" alt="UEL" />
        <h1>Trợ lý {department.name}</h1>
        <p>Đăng nhập Google sẽ gắn ở P1. Không dùng mật khẩu.</p>
        <button type="button" disabled>
          Đăng nhập với Google — P1
        </button>
      </div>
    </main>
  )
}
