import { Navigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import AppRoutes from './AppRoutes.jsx'
import { DEFAULT_BOT_PATH } from '../config/botNav'

/** Member không thấy /quan-ly. Role lấy từ cookie JWT, không tin payload FE. */
export default function ProtectedRoute({ role, children }) {
  const user = useSelector((s) => s.auth.user)

  if (!user) {
    return <Navigate to={AppRoutes.login} replace />
  }

  if (role === 'department_admin' && user.role !== 'department_admin') {
    return <Navigate to={DEFAULT_BOT_PATH} replace />
  }

  return children
}
