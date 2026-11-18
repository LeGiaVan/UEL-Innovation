import { Link, useLocation } from 'react-router-dom'
import { useSelector, useDispatch } from 'react-redux'
import { BookOpen, ClipboardCheck, MessageCircle, FileText } from 'lucide-react'
import department from '../config/department.json'
import { fetchQA } from '../store/slices/qaSlice'
import { applyCannedFaq } from '../store/slices/chatSlice'
import AppRoutes from '../routes/AppRoutes.jsx'
import './Sidebar.css'

const MODE_ICONS = [BookOpen, ClipboardCheck, MessageCircle, FileText]

export default function Sidebar({ onNavigate }) {
  const { pathname } = useLocation()
  const dispatch = useDispatch()
  const { isLoading } = useSelector((s) => s.chat)
  const { questions, error, isLoading: qaLoading } = useSelector((s) => s.qa)
  const modes = useSelector((s) => s.mode.modes) || []
  const selectedMode = useSelector((s) => s.mode.selectedMode)
  const modeError = useSelector((s) => s.mode.error)
  const isAdmin = useSelector((s) => s.auth.user?.role === 'department_admin')
  const currentMode = modes.find((m) => m.id === selectedMode)

  return (
    <aside className="sidebar">
      <nav className="sidebar-modes" aria-label="Chủ đề hỗ trợ">
        <h2 className="sidebar-modes-title">{department.name}</h2>
        {modeError ? <p role="alert">{modeError}</p> : null}
        <ul className="sidebar-modes-list">
          {modes.map((mode, i) => {
            const n = String(mode.id || '').replace('module_', '') || String(i + 1)
            const to = `/bot/chu-de-${n}`
            const Icon = MODE_ICONS[i % MODE_ICONS.length]
            const active = pathname === to
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
                  <span className="sidebar-mode-btn-icon">
                    <Icon size={22} />
                  </span>
                  <span className="sidebar-mode-btn-text">
                    <span className="sidebar-mode-btn-label">{mode.label}</span>
                    <span className="sidebar-mode-btn-sub">Hỏi trong mảng này</span>
                  </span>
                </Link>
              </li>
            )
          })}
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
                <span className="sidebar-mode-btn-text">
                  <span className="sidebar-mode-btn-label">Cập nhật dữ liệu</span>
                  <span className="sidebar-mode-btn-sub">Đưa file Excel vào bot</span>
                </span>
              </Link>
            </li>
            <li>
              <Link
                to={AppRoutes.adminPersona}
                className={`sidebar-mode-btn${pathname.startsWith(AppRoutes.adminPersona) ? ' active' : ''}`}
                aria-current={pathname.startsWith(AppRoutes.adminPersona) ? 'page' : undefined}
                onClick={() => onNavigate?.()}
              >
                <span className="sidebar-mode-btn-text">
                  <span className="sidebar-mode-btn-label">Cách bot trả lời</span>
                  <span className="sidebar-mode-btn-sub">Lời chào, phạm vi, thử câu</span>
                </span>
              </Link>
            </li>
          </ul>
        </nav>
      ) : null}
      <section className="sidebar-notices">
        <h3 className="sidebar-notices-title">Câu hỏi thường gặp</h3>
        {currentMode?.label ? (
          <p className="sidebar-mode-btn-sub">Mảng {currentMode.label}</p>
        ) : null}
        {error ? (
          <div role="alert">
            {error}
            <button type="button" onClick={() => dispatch(fetchQA({ mode: selectedMode }))}>
              Thử lại
            </button>
          </div>
        ) : null}
        {qaLoading ? <p className="sidebar-mode-btn-sub">Đang tải câu hỏi của mảng này…</p> : null}
        {!qaLoading && !error && questions.length === 0 ? (
          <p className="sidebar-mode-btn-sub">Chưa có câu hỏi thường gặp cho mảng này.</p>
        ) : null}
        <ul className="sidebar-notices-list">
          {questions.map((q, i) => (
            <li key={q.id || `${q.module_code}-${i}`}>
              <button
                type="button"
                className="sidebar-notice-link"
                disabled={isLoading || !q.answer}
                onClick={() => {
                  if (isLoading || !q.answer) return
                  dispatch(applyCannedFaq({ question: q.question, answer: q.answer }))
                  onNavigate?.()
                }}
              >
                {q.question}
              </button>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  )
}
