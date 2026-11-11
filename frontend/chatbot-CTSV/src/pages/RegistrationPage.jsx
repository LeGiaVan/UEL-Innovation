import { API_URL, fetchApi as fetch } from '../api/client'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import axios from '../api/client'
import {
  User,
  Mail,
  Phone,
  MessageSquare,
  Send,
  CheckCircle2,
} from 'lucide-react'
import { DEFAULT_BOT_PATH } from '../config/botNav'
import { useFeatureTheme } from '../context/FeatureThemeContext'
import '../components/RegistrationLeadModal.css'
import './RegistrationPage.css'



export default function RegistrationPage() {
  const feature = useFeatureTheme()
  const heroBg =
    feature.accentDeep != null
      ? {
          background: `linear-gradient(145deg, ${feature.accentDeep} 0%, ${feature.accent} 52%, ${feature.accent} 100%)`,
        }
      : { background: feature.accent }

  const conversationId = useSelector((s) => s.chat.conversationId)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [programLevel, setProgramLevel] = useState('')
  const [note, setNote] = useState('')
  const [status, setStatus] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  /** Danh sách bậc đào tạo — để bộ phận tuyển sinh điều hướng phản hồi đúng người. */
  const PROGRAM_LEVELS = [
    'Tiến sĩ',
    'Thạc sĩ',
    'Đại học chính quy',
    'Vừa làm vừa học',
    'Văn bằng 2',
    'Liên kết quốc tế',
  ]

  const handleSubmit = async (e) => {
    e.preventDefault()
    setStatus(null)
    if (!programLevel) {
      setStatus({ ok: false, text: 'Vui lòng chọn bậc đào tạo bạn quan tâm.' })
      return
    }
    setSubmitting(true)
    try {
      const { data } = await axios.post(`${API_URL}/admission-lead`, {
        name: name.trim(),
        email: email.trim(),
        phone: phone.trim(),
        program_level: programLevel || undefined,
        note: note.trim() || undefined,
        conversation_id: conversationId || undefined,
      })
      const serverMsg =
        data?.message ||
        'Đã ghi nhận đăng ký. Phòng Tuyển sinh và Công tác sinh viên sẽ liên hệ khi cần.'
      const partial =
        data?.stored_firestore && data?.email_sent === false
      let text = serverMsg
      if (partial) {
        text +=
          ' Lưu ý: chưa gửi được email thông báo tới phụ trách (kiểm tra cấu hình SMTP trên API).'
      }
      setStatus({ ok: true, text, warnPartial: !!partial })
      setName('')
      setEmail('')
      setPhone('')
      setProgramLevel('')
      setNote('')
    } catch (err) {
      const raw = err.response?.data?.detail
      const detail = Array.isArray(raw)
        ? raw.map((x) => x.msg || String(x)).join(' ')
        : raw
      setStatus({
        ok: false,
        text: detail || err.message || 'Gửi không thành công. Vui lòng thử lại.',
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="reg-page">
      <div className="reg-page-inner">

        <div className="reg-modal-panel reg-page-panel">
          <div className="reg-modal-hero reg-page-hero-branded" style={heroBg}>
            <div className="reg-modal-hero-pattern" aria-hidden />
            <h1 className="reg-modal-title">Đăng ký nhận tư vấn tuyển sinh chuyên sâu</h1>
            <p className="reg-modal-sub">
              Phòng Tuyển sinh và Công tác sinh viên tiếp nhận và phản hồi theo thông tin bạn cung cấp
            </p>
          </div>

          <div className="reg-modal-body">
            <p className="reg-modal-lead">
              Điền form bên dưới để được tư vấn, nhận cập nhật hoặc hỗ trợ liên quan tuyển sinh.
            </p>

            <form onSubmit={handleSubmit} className="reg-modal-form">
              <div className="reg-field">
                <label className="reg-field-label" htmlFor="reg-page-name">
                  Họ và tên <span className="req">*</span>
                </label>
                <div className="reg-field-input-wrap">
                  <User className="reg-field-icon" size={18} strokeWidth={2} aria-hidden />
                  <input
                    id="reg-page-name"
                    className="reg-field-input"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    autoComplete="name"
                    placeholder="Nguyễn Văn A"
                  />
                </div>
              </div>

              <div className="reg-field">
                <label className="reg-field-label" htmlFor="reg-page-email">
                  Email <span className="req">*</span>
                </label>
                <div className="reg-field-input-wrap">
                  <Mail className="reg-field-icon" size={18} strokeWidth={2} aria-hidden />
                  <input
                    id="reg-page-email"
                    className="reg-field-input"
                    required
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                    placeholder="email@example.com"
                  />
                </div>
              </div>

              <div className="reg-field">
                <label className="reg-field-label" htmlFor="reg-page-phone">
                  Điện thoại <span className="req">*</span>
                </label>
                <div className="reg-field-input-wrap">
                  <Phone className="reg-field-icon" size={18} strokeWidth={2} aria-hidden />
                  <input
                    id="reg-page-phone"
                    className="reg-field-input"
                    required
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    autoComplete="tel"
                    placeholder="09xx xxx xxx"
                  />
                </div>
              </div>

              <div className="reg-field reg-field--full">
                <label className="reg-field-label">
                  Bậc đào tạo quan tâm <span className="req">*</span>
                </label>
                <div
                  className="reg-program-grid"
                  role="radiogroup"
                  aria-label="Chọn bậc đào tạo"
                  aria-required="true"
                >
                  {PROGRAM_LEVELS.map((lv) => {
                    const active = programLevel === lv
                    return (
                      <button
                        key={lv}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        className={`reg-program-pill${active ? ' is-active' : ''}`}
                        onClick={() => setProgramLevel(lv)}
                      >
                        <span className="reg-program-pill-dot" aria-hidden />
                        <span className="reg-program-pill-label">{lv}</span>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="reg-field reg-field--full">
                <label className="reg-field-label" htmlFor="reg-page-note">
                  Ghi chú <span className="reg-optional">(tuỳ chọn)</span>
                </label>
                <div className="reg-field-input-wrap reg-field-textarea-wrap">
                  <MessageSquare
                    className="reg-field-icon reg-field-icon-ta"
                    size={18}
                    strokeWidth={2}
                    aria-hidden
                  />
                  <textarea
                    id="reg-page-note"
                    className="reg-field-textarea"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    rows={3}
                    placeholder="Ngành quan tâm, câu hỏi ngắn…"
                  />
                </div>
              </div>

              {status && (
                <div
                  className={`reg-field--full ${
                    status.ok
                      ? status.warnPartial
                        ? 'reg-modal-msg reg-modal-msg--warn'
                        : 'reg-modal-msg reg-modal-msg--ok'
                      : 'reg-modal-msg reg-modal-msg--err'
                  }`}
                  role="status"
                >
                  {status.ok && (
                    <CheckCircle2 className="reg-modal-msg-icon" size={20} strokeWidth={2} aria-hidden />
                  )}
                  <span>{status.text}</span>
                </div>
              )}

              <div className="reg-modal-actions reg-field--full">
                <Link to={DEFAULT_BOT_PATH} className="reg-btn reg-btn--ghost reg-page-link-btn">
                  Hủy
                </Link>
                <button type="submit" className="reg-btn reg-btn--primary" disabled={submitting}>
                  {submitting ? (
                    'Đang gửi…'
                  ) : (
                    <>
                      <Send size={18} strokeWidth={2} aria-hidden />
                      Gửi đăng ký
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
