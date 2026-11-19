import { useEffect, useMemo, useState } from 'react'
import { API_URL, fetchApi } from '../api/client'
import { consumeChatSse } from '../utils/sse'

const EMPTY = {
  greeting: '',
  out_of_scope: '',
  clarification: '',
  handoff: '',
  role: '',
  constraints: '',
  answer_style: '',
  cosine_threshold: 0.62,
  top_k: 6,
  routing_regex: [],
}

const ROUTE_LABEL = {
  faq_exact: 'Đúng câu hỏi thường gặp',
  regex: 'Đúng cụm từ đã khai',
  cosine: 'Khớp chủ đề',
  llm: 'Bot tự chọn chủ đề',
  llm_clarify: 'Cần hỏi lại cho rõ',
}

const STATUS_LABEL = {
  answer_allowed: 'Được trả lời từ tài liệu',
  human_handoff: 'Cần cán bộ hỗ trợ',
  out_of_scope: 'Ngoài phạm vi phòng',
  clarification_required: 'Chưa rõ ý',
  faq_exact: 'Câu hỏi thường gặp',
}

function detailText(payload) {
  const d = payload?.detail
  if (!d) return ''
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((e) => e.msg || String(e)).join('\n')
  if (Array.isArray(d.errors)) return d.errors.join('\n')
  return JSON.stringify(d)
}

function glossaryToText(obj) {
  return Object.entries(obj || {})
    .map(([k, v]) => `${k} = ${v}`)
    .join('\n')
}

function textToGlossary(text) {
  const out = {}
  for (const line of String(text || '').split('\n')) {
    const t = line.trim()
    if (!t) continue
    const eq = t.indexOf('=')
    const col = t.indexOf(':')
    const sep = eq >= 0 && (col < 0 || eq < col) ? eq : col
    if (sep < 1) continue
    const k = t.slice(0, sep).trim()
    const v = t.slice(sep + 1).trim()
    if (k) out[k] = v
  }
  return out
}

function patternToPhrase(pattern) {
  let p = String(pattern || '')
  p = p.replace(/^\(\?i\)/, '')
  const simple = p.replace(/\|/g, '')
  if (!/[\\.*+?^${}()[\]]/.test(simple)) {
    return p.split('|').filter(Boolean).join(', ')
  }
  return String(pattern || '')
}

function phraseToPattern(phrase) {
  const t = String(phrase || '').trim()
  if (!t) return ''
  if (t.startsWith('(?') || t.startsWith('^')) return t
  const parts = t
    .split(/[,;]+/)
    .map((s) => s.trim())
    .filter(Boolean)
  const esc = parts.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  return `(?i)${esc.join('|')}`
}

export default function AdminPersonaPage() {
  const [form, setForm] = useState(EMPTY)
  const [glossaryText, setGlossaryText] = useState('')
  const [topics, setTopics] = useState([])
  const [modules, setModules] = useState([])
  const [stale, setStale] = useState([])
  const [moduleCode, setModuleCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [trialInput, setTrialInput] = useState('')
  const [trialBusy, setTrialBusy] = useState(false)
  const [trialLog, setTrialLog] = useState([])
  const [trialConvId, setTrialConvId] = useState(null)

  const staleIds = useMemo(() => new Set((stale || []).map((s) => s.rule_id)), [stale])
  const topicOptions = useMemo(() => {
    const filtered = moduleCode ? topics.filter((t) => t.module_code === moduleCode) : topics
    return filtered
  }, [topics, moduleCode])

  useEffect(() => {
    let alive = true
    fetchApi(`${API_URL}/admin/persona`)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}))
        if (!res.ok) throw new Error(detailText(body) || 'Không tải được cách bot trả lời')
        if (!alive) return
        const persona = { ...EMPTY, ...(body.persona || {}) }
        persona.routing_regex = (persona.routing_regex || []).map((row) => ({
          ...row,
          phrase: patternToPhrase(row.pattern),
        }))
        setForm(persona)
        setGlossaryText(glossaryToText(persona.glossary))
        setTopics(body.topics || [])
        setModules(body.modules || [])
        setStale(body.stale_regex || [])
        setModuleCode(body.modules?.[0]?.code || '')
      })
      .catch((err) => {
        if (alive) setError(err.message || 'Không tải được cách bot trả lời')
      })
    return () => {
      alive = false
    }
  }, [])

  function setField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }))
    setOk('')
  }

  function setRegex(i, patch) {
    setForm((prev) => {
      const rows = [...(prev.routing_regex || [])]
      rows[i] = { ...rows[i], ...patch }
      return { ...prev, routing_regex: rows }
    })
    setOk('')
  }

  async function onSave(e) {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    setOk('')
    const payload = {
      ...form,
      cosine_threshold: Number(form.cosine_threshold),
      top_k: Number(form.top_k),
      glossary: textToGlossary(glossaryText),
      routing_regex: (form.routing_regex || [])
        .map((r) => ({
          pattern: phraseToPattern(r.phrase || r.pattern),
          rule_id: r.rule_id,
        }))
        .filter((r) => r.pattern && r.rule_id),
    }
    delete payload.phrase
    try {
      const res = await fetchApi(`${API_URL}/admin/persona`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(detailText(body) || `Lưu không thành công (${res.status})`)
      const persona = { ...EMPTY, ...(body.persona || {}) }
      persona.routing_regex = (persona.routing_regex || []).map((row) => ({
        ...row,
        phrase: patternToPhrase(row.pattern),
      }))
      setForm(persona)
      setGlossaryText(glossaryToText(persona.glossary))
      setTopics(body.topics || topics)
      setStale(body.stale_regex || [])
      setOk('Đã lưu. Ô thử câu hỏi bên phải dùng bản vừa lưu.')
    } catch (err) {
      setError(err.message || 'Lưu không thành công')
    } finally {
      setBusy(false)
    }
  }

  async function onTrial(e) {
    e.preventDefault()
    const message = trialInput.trim()
    if (!message || trialBusy) return
    setTrialBusy(true)
    setTrialInput('')
    setTrialLog((prev) => [...prev, { role: 'user', text: message }])
    try {
      const res = await fetchApi(`${API_URL}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          module_code: moduleCode,
          trial: true,
          conversation_id: trialConvId,
        }),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}))
        throw new Error(detailText(payload) || `Thử câu không thành công (${res.status})`)
      }
      if (!res.body) throw new Error('Trình duyệt không hỗ trợ xem câu trả lời dần')
      let done = null
      await consumeChatSse(res.body.getReader(), (ev) => {
        if (ev.type === 'done') done = ev
      })
      if (done?.conversation_id) setTrialConvId(done.conversation_id)
      setTrialLog((prev) => [
        ...prev,
        {
          role: 'bot',
          text: done?.answer || done?.response || '',
          routingSource: done?.routing_source,
          status: done?.status,
        },
      ])
    } catch (err) {
      setTrialLog((prev) => [
        ...prev,
        { role: 'bot', text: err.message || 'Thử câu không thành công', routingSource: 'error' },
      ])
    } finally {
      setTrialBusy(false)
    }
  }

  const cosinePct = Math.round(Number(form.cosine_threshold || 0) * 100)

  return (
    <>
      <h1>Cách bot trả lời</h1>
      <p className="admin-lead">
        Viết lời bot dùng với người học. Ô thử câu hỏi chỉ dành cho cán bộ phòng, không trừ hạn mức
        hỏi của sinh viên.
      </p>
      {error ? (
        <p className="admin-alert admin-alert--error" role="alert">
          {error}
        </p>
      ) : null}
      {ok ? (
        <p className="admin-alert admin-alert--ok" role="status">
          {ok}
        </p>
      ) : null}
      <div className="admin-grid">
        <form className="admin-card" onSubmit={onSave}>
          <h2>Lời bot</h2>
          <label className="admin-field">
            <span>Lời chào khi bắt đầu</span>
            <textarea value={form.greeting} onChange={(e) => setField('greeting', e.target.value)} />
          </label>
          <label className="admin-field">
            <span>Khi câu hỏi không thuộc phòng</span>
            <textarea
              value={form.out_of_scope}
              onChange={(e) => setField('out_of_scope', e.target.value)}
            />
          </label>
          <label className="admin-field">
            <span>Khi chưa rõ người học muốn hỏi gì</span>
            <textarea
              value={form.clarification}
              onChange={(e) => setField('clarification', e.target.value)}
            />
          </label>
          <label className="admin-field">
            <span>Khi cần cán bộ hỗ trợ</span>
            <span className="admin-hint">Không dùng cột «Cách chatbot xử lý» trên Excel — đó là hướng dẫn nội bộ.</span>
            <textarea
              value={form.handoff}
              onChange={(e) => setField('handoff', e.target.value)}
            />
          </label>
          <label className="admin-field">
            <span>Bot giới thiệu mình là</span>
            <input value={form.role} onChange={(e) => setField('role', e.target.value)} />
          </label>
          <label className="admin-field">
            <span>Điều bot không được làm</span>
            <span className="admin-hint">Ví dụ: không bịa số ngày, không trả dữ liệu cá nhân.</span>
            <textarea
              value={form.constraints}
              onChange={(e) => setField('constraints', e.target.value)}
            />
          </label>
          <label className="admin-field">
            <span>Giọng văn</span>
            <textarea
              value={form.answer_style}
              onChange={(e) => setField('answer_style', e.target.value)}
            />
          </label>
          <label className="admin-field">
            <span>Từ viết tắt / thuật ngữ phòng</span>
            <span className="admin-hint">Mỗi dòng: viết tắt = nghĩa. Ví dụ: ĐHCQ = đại học chính quy</span>
            <textarea value={glossaryText} onChange={(e) => setGlossaryText(e.target.value)} />
          </label>
          <label className="admin-field">
            <span>Chỉ trả lời khi khá chắc đúng chủ đề ({cosinePct}%)</span>
            <span className="admin-hint">Khuyên dùng khoảng 62%. Thấp hơn thì bot dễ nhầm chủ đề.</span>
            <input
              type="range"
              min="40"
              max="90"
              step="1"
              value={cosinePct}
              onChange={(e) => setField('cosine_threshold', Number(e.target.value) / 100)}
            />
          </label>
          <label className="admin-field">
            <span>Bot đọc tối đa bao nhiêu đoạn tài liệu khi trả lời</span>
            <input
              type="number"
              min="1"
              max="20"
              step="1"
              value={form.top_k}
              onChange={(e) => setField('top_k', e.target.value)}
            />
          </label>
          <h2>Câu hỏi đi thẳng tới chủ đề</h2>
          <p className="admin-hint">
            Khi người học nói những chữ này, bot chọn đúng chủ đề bên cạnh — không cần đoán. Chủ đề
            lấy từ file phạm vi trả lời đang dùng.
          </p>
          {(form.routing_regex || []).map((row, i) => (
            <div
              key={`${row.rule_id}-${i}`}
              className={`admin-regex-row${staleIds.has(row.rule_id) ? ' stale' : ''}`}
            >
              <input
                placeholder="Ví dụ: phúc khảo, xem lại điểm"
                value={row.phrase || ''}
                onChange={(e) => setRegex(i, { phrase: e.target.value })}
              />
              <select
                value={row.rule_id || ''}
                onChange={(e) => setRegex(i, { rule_id: e.target.value })}
              >
                {staleIds.has(row.rule_id) ? (
                  <option value={row.rule_id}>Chủ đề này không còn trên file Excel</option>
                ) : null}
                <option value="">Chọn chủ đề</option>
                {topicOptions.map((t) => (
                  <option key={t.rule_id} value={t.rule_id}>
                    {t.topic}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="admin-btn admin-btn-ghost"
                onClick={() =>
                  setForm((prev) => ({
                    ...prev,
                    routing_regex: prev.routing_regex.filter((_, j) => j !== i),
                  }))
                }
              >
                Xóa
              </button>
            </div>
          ))}
          <div className="admin-actions">
            <button
              type="button"
              className="admin-btn admin-btn-ghost"
              onClick={() =>
                setForm((prev) => ({
                  ...prev,
                  routing_regex: [...(prev.routing_regex || []), { phrase: '', rule_id: '' }],
                }))
              }
            >
              Thêm cụm từ
            </button>
            <button className="admin-btn" type="submit" disabled={busy}>
              {busy ? 'Đang lưu…' : 'Lưu cách trả lời'}
            </button>
          </div>
        </form>
        <section className="admin-card">
          <h2>Thử một câu hỏi</h2>
          <p className="admin-hint">Người học không thấy ô này.</p>
          <label className="admin-field">
            <span>Thử trên mảng</span>
            <select value={moduleCode} onChange={(e) => setModuleCode(e.target.value)}>
              {modules.map((m) => (
                <option key={m.code} value={m.code}>
                  {m.name}
                </option>
              ))}
            </select>
          </label>
          <div className="admin-trial-log">
            {trialLog.length === 0 ? (
              <p className="admin-lead">{form.greeting || 'Gõ một câu như người học sẽ hỏi.'}</p>
            ) : null}
            {trialLog.map((m, i) => (
              <div key={i} className={`admin-trial-bubble ${m.role === 'user' ? 'user' : 'bot'}`}>
                {m.routingSource ? (
                  <div className="admin-counts">
                    <span className="admin-chip">
                      {ROUTE_LABEL[m.routingSource] || m.routingSource}
                    </span>
                    {m.status ? (
                      <span className="admin-chip">{STATUS_LABEL[m.status] || m.status}</span>
                    ) : null}
                  </div>
                ) : null}
                {m.text}
              </div>
            ))}
          </div>
          <form className="admin-trial-form" onSubmit={onTrial}>
            <input
              value={trialInput}
              onChange={(e) => setTrialInput(e.target.value)}
              placeholder="Gõ câu hỏi để xem bot trả lời ra sao"
              disabled={trialBusy}
            />
            <button className="admin-btn" type="submit" disabled={trialBusy || !trialInput.trim()}>
              {trialBusy ? '…' : 'Thử'}
            </button>
          </form>
        </section>
      </div>
    </>
  )
}
