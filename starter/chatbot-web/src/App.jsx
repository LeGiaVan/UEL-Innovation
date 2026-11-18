import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import AuthGate from './components/AuthGate'
import MainLayout from './layouts/MainLayout'
import BotChatPage from './pages/BotChatPage'
import AdminLayout from './pages/AdminLayout'
import AdminIngestPage from './pages/AdminIngestPage'
import AdminPersonaPage from './pages/AdminPersonaPage'
import ProtectedRoute from './routes/ProtectedRoute'
import { DEFAULT_BOT_PATH } from './config/botNav'

function AdminGate() {
  return (
    <ProtectedRoute role="department_admin">
      <AdminLayout />
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <AuthGate>
      <BrowserRouter>
        <Routes>
          <Route path="/quan-ly" element={<AdminGate />}>
            <Route index element={<Navigate to="/quan-ly/nap-tri-thuc" replace />} />
            <Route path="nap-tri-thuc" element={<AdminIngestPage />} />
            <Route path="persona" element={<AdminPersonaPage />} />
          </Route>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<Navigate to={DEFAULT_BOT_PATH} replace />} />
            <Route path="bot/:botSlug" element={<BotChatPage />} />
            <Route path="*" element={<Navigate to={DEFAULT_BOT_PATH} replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthGate>
  )
}
