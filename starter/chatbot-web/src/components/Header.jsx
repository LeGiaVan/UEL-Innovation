import { Link } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { logout } from '../store/slices/authSlice'
import department from '../config/department.json'
import AppRoutes from '../routes/AppRoutes.jsx'
import './Header.css'

export default function Header() {
  const dispatch = useDispatch()
  const user = useSelector((s) => s.auth.user)
  const isAdmin = user?.role === 'department_admin'

  return (
    <header className="header">
      <div className="header-content">
        <div className="header-logo">
          <img
            src="/docs/logo-2026-06.png"
            alt="UEL"
            className="logo-img logo-img--on-primary"
          />
          <div className="header-title">
            <h1 className="header-title-line">Trợ lý AI hỗ trợ {department.short}</h1>
            <p className="header-subtitle">Trường Đại học Kinh tế - Luật (ĐHQG-HCM)</p>
          </div>
        </div>
        {user ? (
          <div className="header-user">
            {isAdmin ? (
              <nav className="header-admin" aria-label="Quản lý phòng">
                <Link to={AppRoutes.adminIngest}>Cập nhật dữ liệu</Link>
                <Link to={AppRoutes.adminPersona}>Cách bot trả lời</Link>
              </nav>
            ) : null}
            <span className="header-user-email">{user.email}</span>
            {isAdmin ? <span className="header-user-role">Admin</span> : null}
            <button type="button" className="header-logout" onClick={() => dispatch(logout())}>
              Đăng xuất
            </button>
          </div>
        ) : null}
      </div>
    </header>
  )
}
