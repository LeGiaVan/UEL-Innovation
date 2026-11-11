import { API_URL, fetchApi as fetch } from '../api/client'
import { useEffect, useMemo, useRef, useState } from 'react'
import './AdmissionSurveyModal.css'

export default function AdmissionSurveyModal({ onSubmit, onDismissOutside, submitting = false, submitError = '' }) {
  
  /** role: 'candidate' | 'parent' | null. Form chỉ hiện sau khi user chủ động chọn. */
  const [role, setRole] = useState(null)
  /** level: 'undergrad' | 'postgrad' | null — chỉ áp dụng khi role='candidate'. */
  const [level, setLevel] = useState(null)
  const [schoolName, setSchoolName] = useState('')
  const [provinceName, setProvinceName] = useState('')
  const [schoolLoading, setSchoolLoading] = useState(false)
  const [schoolSuggestions, setSchoolSuggestions] = useState([])
  const [openSuggestions, setOpenSuggestions] = useState(false)
  const [suppressSuggestions, setSuppressSuggestions] = useState(false)
  const [touched, setTouched] = useState(false)
  const schoolAbortRef = useRef(null)
  /**
   * Cloudflare Turnstile — invisible CAPTCHA chống mass-create profile.
   * Site key đọc từ env VITE_TURNSTILE_SITE_KEY. Nếu thiếu → tắt feature (dev fallback).
   */
  const turnstileSiteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY || ''
  const [turnstileToken, setTurnstileToken] = useState('')
  const turnstileWidgetRef = useRef(null)
  const turnstileWidgetIdRef = useRef(null)

  const _school = schoolName.trim()
  const _province = provinceName.trim()

  const isParent = role === 'parent'
  const isCandidate = role === 'candidate'
  const isUndergrad = isCandidate && level === 'undergrad'
  const isPostgrad = isCandidate && level === 'postgrad'
  const showLevelSelector = isCandidate
  const showForm = isParent || isUndergrad || isPostgrad
  /** Chỉ THPT (parent / candidate-undergrad) gọi API gợi ý 149 trường ưu tiên. */
  const wantsThpt = isParent || isUndergrad
  const schoolFieldLabel = isPostgrad ? 'Trường Đại học' : 'Trường THPT'
  const schoolPlaceholder = isPostgrad
    ? 'Ví dụ: Trường Đại học Kinh tế - Luật'
    : 'Ví dụ: THPT Lê Quý Đôn'

  const turnstileRequired = Boolean(turnstileSiteKey)
  const turnstileOk = !turnstileRequired || Boolean(turnstileToken)
  const isValid = showForm && _school.length >= 2 && _province.length >= 2 && turnstileOk

  const question2 = useMemo(() => {
    if (isParent) return 'Con bạn học trường THPT nào, tỉnh/thành phố nào?'
    if (isUndergrad) return 'Bạn học trường THPT nào, tỉnh/thành phố nào?'
    if (isPostgrad) return 'Bạn đã học trường Đại học nào, tỉnh/thành phố nào?'
    return null
  }, [isParent, isUndergrad, isPostgrad])

  /** Đổi role/level → reset form để tránh lệch context (THPT ↔ Đại học). */
  useEffect(() => {
    setSchoolName('')
    setProvinceName('')
    setSchoolSuggestions([])
    setOpenSuggestions(false)
    setSuppressSuggestions(false)
    setTouched(false)
  }, [role, level])

  /** Khi đổi role, level cũ (nếu role mới là parent) phải clear. */
  useEffect(() => {
    if (!isCandidate && level !== null) setLevel(null)
  }, [isCandidate, level])

  useEffect(() => {
    if (suppressSuggestions || !wantsThpt) {
      setOpenSuggestions(false)
      return
    }
    const q = schoolName.trim()
    if (!q) {
      setSchoolSuggestions([])
      setOpenSuggestions(false)
      return
    }
    const timer = setTimeout(async () => {
      if (schoolAbortRef.current) schoolAbortRef.current.abort()
      const controller = new AbortController()
      schoolAbortRef.current = controller
      setSchoolLoading(true)
      try {
        // Gợi ý từ danh sách THPT 2026 toàn quốc (single source of truth, Bộ GD&ĐT).
        // Each entry kèm cờ `uu_tien` cho biết trường thuộc 149 ưu tiên hay không.
        const res = await fetch(
          `${API_URL}/module-d/thpt-2026?q=${encodeURIComponent(q)}&limit=0`,
          { signal: controller.signal }
        )
        const data = await res.json().catch(() => ({}))
        if (!res.ok) {
          setSchoolSuggestions([])
          setOpenSuggestions(false)
          return
        }
        const rows = Array.isArray(data?.truong) ? data.truong : []
        setSchoolSuggestions(rows)
        setOpenSuggestions(rows.length > 0)
      } catch (err) {
        if (err?.name !== 'AbortError') {
          setSchoolSuggestions([])
          setOpenSuggestions(false)
        }
      } finally {
        setSchoolLoading(false)
      }
    }, 260)
    return () => clearTimeout(timer)
  }, [API_URL, schoolName, suppressSuggestions, wantsThpt])

  useEffect(() => () => schoolAbortRef.current?.abort(), [])

  // Render Turnstile widget khi script đã load + container ready.
  // Re-run khi `showForm` flip (container chỉ tồn tại khi user đã chọn role/level).
  useEffect(() => {
    if (!turnstileSiteKey) return
    if (!showForm) return
    let cancelled = false
    const tryRender = () => {
      if (cancelled) return
      const container = turnstileWidgetRef.current
      if (!container) {
        // DOM chưa mount xong → chờ frame tiếp.
        setTimeout(tryRender, 100)
        return
      }
      const ts = window.turnstile
      if (!ts || typeof ts.render !== 'function') {
        // Script chưa load (hoặc bị adblock) → retry.
        setTimeout(tryRender, 250)
        return
      }
      if (turnstileWidgetIdRef.current) return  // tránh render trùng
      try {
        const id = ts.render(container, {
          sitekey: turnstileSiteKey,
          theme: 'light',
          // 'interaction-only' = widget tự ẩn khi xác thực silent thành công;
          // chỉ hiện UI nếu Cloudflare đánh giá cần user tương tác.
          appearance: 'interaction-only',
          size: 'flexible',
          callback: (token) => setTurnstileToken(token || ''),
          'error-callback': () => setTurnstileToken(''),
          'expired-callback': () => setTurnstileToken(''),
        })
        turnstileWidgetIdRef.current = id
      } catch (e) {
        // adblock / domain mismatch / config sai → không render được. Token rỗng.
        // Có thể log để debug; user sẽ không bấm được Tiếp tục — đó là behavior đúng.
        console.warn('Turnstile render failed:', e)
      }
    }
    tryRender()
    return () => {
      cancelled = true
      try {
        if (window.turnstile && turnstileWidgetIdRef.current) {
          window.turnstile.remove(turnstileWidgetIdRef.current)
        }
      } catch {
        // ignore
      }
      turnstileWidgetIdRef.current = null
    }
  }, [turnstileSiteKey, showForm])

  return (
    <div
      className="admission-survey-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Tư vấn nhanh tuyển sinh"
    >
      <div className="admission-survey-modal">
        <h2 className="admission-survey-title">Tư vấn nhanh</h2>
        <p className="admission-survey-q">
          Để tối ưu hóa trong việc tra cứu và tư vấn, vui lòng cho biết bạn là:
          <span className="admission-survey-required" aria-hidden="true"> *</span>
        </p>
        <div className="admission-survey-role-row">
          <label className="admission-survey-role">
            <input
              type="radio"
              name="admission-survey-role"
              value="candidate"
              checked={role === 'candidate'}
              onChange={() => setRole('candidate')}
            />
            <span>Người dự tuyển</span>
          </label>
          <label className="admission-survey-role">
            <input
              type="radio"
              name="admission-survey-role"
              value="parent"
              checked={role === 'parent'}
              onChange={() => setRole('parent')}
            />
            <span>Phụ huynh</span>
          </label>
        </div>

        {showLevelSelector && (
          <>
            <p className="admission-survey-q">
              Bạn dự tuyển bậc nào?
              <span className="admission-survey-required" aria-hidden="true"> *</span>
            </p>
            <div className="admission-survey-role-row">
              <label className="admission-survey-role">
                <input
                  type="radio"
                  name="admission-survey-level"
                  value="undergrad"
                  checked={level === 'undergrad'}
                  onChange={() => setLevel('undergrad')}
                />
                <span>Bậc Đại học</span>
              </label>
              <label className="admission-survey-role">
                <input
                  type="radio"
                  name="admission-survey-level"
                  value="postgrad"
                  checked={level === 'postgrad'}
                  onChange={() => setLevel('postgrad')}
                />
                <span>Bậc Sau Đại học</span>
              </label>
            </div>
          </>
        )}

        {showForm && (
          <>
            <p className="admission-survey-q">
              {question2}
              <span className="admission-survey-required" aria-hidden="true"> *</span>
            </p>
            <div className="admission-survey-grid">
              <label className="admission-survey-field">
                <span>{schoolFieldLabel} <span className="admission-survey-required">*</span></span>
                <input
                  type="text"
                  value={schoolName}
                  onChange={(e) => {
                    setSuppressSuggestions(false)
                    setSchoolName(e.target.value)
                    setOpenSuggestions(true)
                  }}
                  onFocus={() => {
                    if (!suppressSuggestions && schoolSuggestions.length > 0) setOpenSuggestions(true)
                  }}
                  placeholder={schoolPlaceholder}
                />
                {schoolLoading ? (
                  <span className="admission-survey-hint">Đang gợi ý trường…</span>
                ) : null}
                {openSuggestions && schoolSuggestions.length > 0 && (
                  <div className="admission-survey-suggest-list">
                    {schoolSuggestions.map((s) => (
                      <button
                        key={`${s.ma_tinh}-${s.ma_truong}-${s.ten_truong}`}
                        type="button"
                        className="admission-survey-suggest-item"
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => {
                          setSuppressSuggestions(true)
                          setSchoolName(String(s.ten_truong || ''))
                          setProvinceName(String(s.ten_tinh || ''))
                          setOpenSuggestions(false)
                        }}
                      >
                        <span className="admission-survey-suggest-name">{s.ten_truong}</span>
                        <small className="admission-survey-suggest-sub">
                          {[s.dia_chi, s.ten_tinh].filter(Boolean).join(' — ')}
                        </small>
                      </button>
                    ))}
                  </div>
                )}
              </label>
              <label className="admission-survey-field">
                <span>Tỉnh/Thành phố <span className="admission-survey-required">*</span></span>
                <input
                  type="text"
                  value={provinceName}
                  onChange={(e) => setProvinceName(e.target.value)}
                  placeholder="Ví dụ: TP. Hồ Chí Minh"
                />
              </label>
            </div>
          </>
        )}

        {turnstileRequired && showForm && (
          <div className="admission-survey-turnstile" ref={turnstileWidgetRef} aria-label="Xác thực bảo mật" />
        )}

        {touched && !isValid && (
          <p className="admission-survey-error" role="alert">
            {turnstileRequired && !turnstileOk
              ? 'Vui lòng hoàn tất xác thực bảo mật để tiếp tục.'
              : 'Vui lòng chọn đầy đủ các tùy chọn và nhập tên trường, tỉnh/thành phố để tiếp tục.'}
          </p>
        )}

        {submitError && (
          <p className="admission-survey-error" role="alert">
            {submitError}
          </p>
        )}

        <div className="admission-survey-actions">
          <button
            type="button"
            className="admission-survey-btn"
            disabled={!isValid || submitting}
            onClick={() => {
              setTouched(true)
              if (!isValid) return
              onSubmit?.({
                role,
                education_level: isCandidate ? level : null,
                school_name: _school,
                province_name: _province,
                completed: true,
                skipped: false,
                turnstile_token: turnstileToken || null,
              })
            }}
          >
            {submitting ? 'Đang xử lý…' : 'Tiếp tục'}
          </button>
        </div>
      </div>
    </div>
  )
}
