import { Link, Outlet, useLocation } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { logout } from '../store/slices/authSlice'
import { liveDepartment } from '../config/departmentIdentity'
import AppRoutes from '../routes/AppRoutes.jsx'
import { DEFAULT_BOT_PATH } from '../config/botNav'
import '../components/Header.css'
import './admin.css'

export default function AdminLayout() {
  const { pathname } = useLocation()
  const dispatch = useDispatch()
  const user = useSelector((s) => s.auth.user)
  const department = liveDepartment(useSelector((s) => s.auth.department))
  const ingest = pathname.includes('/persona') === false
  return (
    <div className="admin-shell">
      <header className="header">
        <div className="header-content">
          <div className="header-logo">
            <img
              src="/docs/logo-2026-06.png"
              alt="UEL"
              className="logo-img logo-img--on-primary"
            />
            <div className="header-title">
              <h1 className="header-title-line">Quản lý dữ liệu — {department.short}</h1>
              <p className="header-subtitle">Cập nhật Excel. Cách bot trả lời chỉ sửa trong config.</p>
            </div>
          </div>
          <div className="header-user">
            <Link className="header-admin-link" to={DEFAULT_BOT_PATH}>
              Về trang hỏi đáp
            </Link>
            <span className="header-user-email">{user?.email}</span>
            <button type="button" className="header-logout" onClick={() => dispatch(logout())}>
              Đăng xuất
            </button>
          </div>
        </div>
      </header>
      <div className="admin-page">
        <nav className="admin-nav" aria-label="Việc cần làm">
          <Link to={AppRoutes.adminIngest} aria-current={ingest ? 'page' : undefined}>
            Cập nhật dữ liệu
          </Link>
          <Link to={AppRoutes.adminPersona} aria-current={!ingest ? 'page' : undefined}>
            Cách bot trả lời
          </Link>
        </nav>
        <Outlet />
      </div>
    </div>
  )
}
