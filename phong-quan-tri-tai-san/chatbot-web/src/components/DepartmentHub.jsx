import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { BookOpen, ClipboardCheck, MessageCircle, FileText } from 'lucide-react'
import { liveDepartment } from '../config/departmentIdentity'
import './DepartmentHub.css'

const ICONS = [BookOpen, ClipboardCheck, MessageCircle, FileText]

export default function DepartmentHub({ onSuggestionClick }) {
  const department = liveDepartment(useSelector((s) => s.auth.department))
  const modes = useSelector((s) => s.mode.modes) || []
  const selectedMode = useSelector((s) => s.mode.selectedMode)
  const questions = useSelector((s) => s.qa.questions) || []
  const qaLoading = useSelector((s) => s.qa.isLoading)
  const current = modes.find((m) => m.id === selectedMode) || modes[0]
  const suggestions = questions.filter((q) => q.question).slice(0, 8)

  return (
    <section className="department-hub">
      <h2>Trợ lý {department.name}</h2>
      <p>{current?.label ? `Mảng ${current.label}` : 'Chọn mảng hỗ trợ bên trái'}</p>
      <div className="department-cards">
        {modes.map((mode, i) => {
          const n = String(mode.id || '').replace('module_', '') || String(i + 1)
          const Icon = ICONS[i % ICONS.length]
          return (
            <Link key={mode.id || i} to={`/bot/chu-de-${n}`}>
              <Icon size={26} />
              <strong>{mode.label}</strong>
              <span>Hỏi trong mảng này</span>
            </Link>
          )
        })}
      </div>
      <h3>Bạn có thể hỏi tôi</h3>
      {qaLoading ? <p>Đang tải câu hỏi của mảng này…</p> : null}
      {!qaLoading && suggestions.length === 0 ? (
        <p>
          {current?.label
            ? `Chưa có câu hỏi thường gặp. Hãy nhập câu hỏi về ${current.label}.`
            : 'Chưa có câu hỏi thường gặp cho mảng này.'}
        </p>
      ) : null}
      {suggestions.map((q) => (
        <button
          key={q.id || q.question}
          type="button"
          onClick={() => onSuggestionClick(q.question)}
        >
          {q.question}
        </button>
      ))}
    </section>
  )
}
