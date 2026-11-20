import { useSelector } from 'react-redux'
import { liveDepartment } from '../config/departmentIdentity'
import { assistantTitle } from '../config/assistantTitle'
import './EmptyChat.css'

export default function EmptyChat() {
  const department = liveDepartment(useSelector((s) => s.auth.department))
  const greeting = useSelector((s) => s.auth.greeting)
  const title = assistantTitle(department.short)
  const modes = useSelector((s) => s.mode.modes) || []
  const selectedMode = useSelector((s) => s.mode.selectedMode)
  const current = modes.find((m) => m.id === selectedMode)

  return (
    <section className="empty-chat empty-chat--gpt" aria-label={title}>
      <img
        src="/uel-logo-cap-nhat-09-4-40.jpg"
        alt=""
        className="empty-chat-mark"
      />
      <h2>{title}</h2>
      {current?.label ? <p className="empty-chat-module">{current.label}</p> : null}
      {greeting ? <p className="empty-chat-desc">{greeting}</p> : null}
    </section>
  )
}
