import { Navigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import AppRoutes from './AppRoutes.jsx'

/** P1 sẽ khóa cookie JWT. P0: cho vào chat; màn admin luôn chặn (chưa có role). */
export default function ProtectedRoute({ role, children }) {
  const user = useSelector((s) => s.auth.user)

  if (role === 'department_admin') {
    if (user?.role !== 'department_admin') {
      return (
        <main className="page-card">
          <h1>Quản lý phòng</h1>
          <p>Chỉ tài khoản trong <code>admins</code> của phòng. Google login và phân quyền làm ở P1; nạp Excel / persona làm ở P5.</p>
        </main>
      )
    }
  }

  if (!user) {
    return <Navigate to={AppRoutes.login} replace />
  }

  return children
}
