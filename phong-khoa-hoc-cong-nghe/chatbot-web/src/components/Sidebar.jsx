import { Link, useLocation } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { Database, HelpCircle, MessageCircle, Settings } from 'lucide-react'
import AppRoutes from '../routes/AppRoutes.jsx'
import './Sidebar.css'

const MODULE_ICONS = [
  <svg key="i0" viewBox="0 0 24 24" fill="none" aria-hidden>
    <path d="M7 4.5h7.2L19 9.2V19a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 6 19V6A1.5 1.5 0 0 1 7.5 4.5H7Z" stroke="currentColor" strokeWidth="1.6" />
    <path d="M14 4.8V9h4.3" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
  </svg>,
  <svg key="i1" viewBox="0 0 24 24" fill="none" aria-hidden>
    <circle cx="12" cy="12" r="7.25" stroke="currentColor" strokeWidth="1.6" />
    <path d="M12 8.2v4.1l2.6 1.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
  </svg>,
  <svg key="i2" viewBox="0 0 24 24" fill="none" aria-hidden>
    <path d="M8 17.5 5.5 20v-4.2A7.5 7.5 0 1 1 18.4 16" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    <path d="M9 11h6M9 14h3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
  </svg>,
  <svg key="i3" viewBox="0 0 24 24" fill="none" aria-hidden>
    <path d="M8 5.5h8A2.5 2.5 0 0 1 18.5 8v10.2L12 15.2l-6.5 3V8A2.5 2.5 0 0 1 8 5.5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
  </svg>,
]

export default function Sidebar({ onNavigate }) {
  const { pathname, search } = useLocation()
  const { isLoading } = useSelector((s) => s.chat)
  const modes = useSelector((s) => s.mode.modes) || []
  const modeError = useSelector((s) => s.mode.error)
  const isAdmin = useSelector((s) => s.auth.user?.role === 'department_admin')
  const faqOpen = new URLSearchParams(search).get('view') === 'faq'
  const activeModulePath = modes.reduce((found, mode, i) => {
    const n = String(mode.id || '').replace('module_', '') || String(i + 1)
    const to = `/bot/chu-de-${n}`
    return pathname === to ? to : found
  }, pathname.startsWith('/bot/') ? pathname : `/bot/chu-de-1`)

  return (
    <aside className="sidebar">
      <nav className="sidebar-modes" aria-label="Chủ đề hỗ trợ">
        {modeError ? <p role="alert">{modeError}</p> : null}
        <ul className="sidebar-modes-list">
          {modes.map((mode, i) => {
            const n = String(mode.id || '').replace('module_', '') || String(i + 1)
            const to = `/bot/chu-de-${n}`
            const active = pathname === to && !faqOpen
            return (
              <li key={mode.id || i}>
                <Link
                  to={to}
                  aria-disabled={isLoading}
                  aria-current={active ? 'page' : undefined}
                  className={`sidebar-mode-btn${active ? ' active' : ''}`}
                  onClick={(e) => {
                    if (isLoading) e.preventDefault()
                    else onNavigate?.()
                  }}
                >
                  <span className="sidebar-mode-btn-icon">{MODULE_ICONS[i % MODULE_ICONS.length]}</span>
                  <span className="sidebar-mode-btn-label">{mode.label}</span>
                </Link>
              </li>
            )
          })}
          <li>
            <Link
              to={`${activeModulePath}?view=faq`}
              className={`sidebar-mode-btn${faqOpen ? ' active' : ''}`}
              aria-current={faqOpen ? 'page' : undefined}
              onClick={() => onNavigate?.()}
            >
              <span className="sidebar-mode-btn-icon">
                <HelpCircle size={18} strokeWidth={1.7} />
              </span>
              <span className="sidebar-mode-btn-label">FAQ</span>
            </Link>
          </li>
        </ul>
        {modes.length === 0 ? (
          <p className="sidebar-mode-btn-sub">Chưa có mảng hỗ trợ. Cán bộ phòng cần cập nhật dữ liệu.</p>
        ) : null}
      </nav>
      {isAdmin ? (
        <nav className="sidebar-modes" aria-label="Quản lý phòng">
          <h2 className="sidebar-modes-title">Quản lý</h2>
          <ul className="sidebar-modes-list">
            <li>
              <Link
                to={AppRoutes.adminIngest}
                className={`sidebar-mode-btn${pathname.startsWith(AppRoutes.adminIngest) ? ' active' : ''}`}
                aria-current={pathname.startsWith(AppRoutes.adminIngest) ? 'page' : undefined}
                onClick={() => onNavigate?.()}
              >
                <span className="sidebar-mode-btn-icon">
                  <Database size={18} strokeWidth={1.7} />
                </span>
                <span className="sidebar-mode-btn-label">Cập nhật dữ liệu</span>
              </Link>
            </li>
            <li>
              <Link
                to={AppRoutes.adminPersona}
                className={`sidebar-mode-btn${pathname.startsWith(AppRoutes.adminPersona) ? ' active' : ''}`}
                aria-current={pathname.startsWith(AppRoutes.adminPersona) ? 'page' : undefined}
                onClick={() => onNavigate?.()}
              >
                <span className="sidebar-mode-btn-icon">
                  <Settings size={18} strokeWidth={1.7} />
                </span>
                <span className="sidebar-mode-btn-label">Cách bot trả lời</span>
              </Link>
            </li>
          </ul>
        </nav>
      ) : null}
      <p className="sidebar-footer">
        <MessageCircle size={14} strokeWidth={1.7} aria-hidden />
        Hỏi theo tài liệu phòng đã nạp
      </p>
    </aside>
  )
}
