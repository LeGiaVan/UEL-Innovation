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

function patternToPhrase(pattern) {
  let p = String(pattern || '')
  p = p.replace(/^\(\?i\)/, '')
  const simple = p.replace(/\|/g, '')
  if (!/[\\.*+?^${}()[\]]/.test(simple)) {
    return p.split('|').filter(Boolean).join(', ')
  }
  return String(pattern || '')
}

function topicLabel(ruleId, topics) {
  const found = (topics || []).find((t) => t.rule_id === ruleId)
  return found?.topic || ruleId || '—'
}

export default function AdminPersonaPage() {
  const [form, setForm] = useState(EMPTY)
  const [glossaryText, setGlossaryText] = useState('')
  const [topics, setTopics] = useState([])
  const [modules, setModules] = useState([])
  const [stale, setStale] = useState([])
  const [configPath, setConfigPath] = useState('chatbot-api/configs/persona.yaml')
  const [moduleCode, setModuleCode] = useState('')
  const [error, setError] = useState('')
  const [trialInput, setTrialInput] = useState('')
  const [trialBusy, setTrialBusy] = useState(false)
  const [trialLog, setTrialLog] = useState([])
  const [trialConvId, setTrialConvId] = useState(null)

  const staleIds = useMemo(() => new Set((stale || []).map((s) => s.rule_id)), [stale])

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
        setConfigPath(body.config_path || 'chatbot-api/configs/persona.yaml')
        setModuleCode(body.modules?.[0]?.code || '')
      })
      .catch((err) => {
        if (alive) setError(err.message || 'Không tải được cách bot trả lời')
      })
    return () => {
      alive = false
    }
  }, [])

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
  const personaBlocks = [
    ['Lời chào khi bắt đầu', form.greeting],
    ['Khi câu hỏi không thuộc phòng', form.out_of_scope],
    ['Khi chưa rõ người học muốn hỏi gì', form.clarification],
    ['Khi cần cán bộ hỗ trợ', form.handoff],
    ['Bot giới thiệu mình là', form.role],
    ['Điều bot không được làm', form.constraints],
    ['Giọng văn', form.answer_style],
    ['Từ viết tắt / thuật ngữ phòng', glossaryText],
  ]

  return (
    <>
      <h1>Cách bot trả lời</h1>
      <p className="admin-lead">
        Chỉ xem. Muốn sửa lời bot, giọng văn hay cụm từ định tuyến, sửa file{' '}
        <code>{configPath}</code> rồi khởi động lại dịch vụ.
      </p>
      {error ? (
        <p className="admin-alert admin-alert--error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="admin-grid">
        <section className="admin-card persona-view">
          <h2>Lời bot</h2>
          <dl className="persona-dl">
            {personaBlocks.map(([label, value]) => (
              <div key={label} className="persona-dl__item">
                <dt>{label}</dt>
                <dd>{value?.trim() ? value : '—'}</dd>
              </div>
            ))}
          </dl>
          <p className="persona-meta">
            Chỉ trả lời khi khá chắc đúng chủ đề: <strong>{cosinePct}%</strong>. Đọc tối đa{' '}
            <strong>{form.top_k}</strong> đoạn tài liệu.
          </p>
          <h2>Câu hỏi đi thẳng tới chủ đề</h2>
          {(form.routing_regex || []).length === 0 ? (
            <p className="persona-empty">Chưa khai cụm từ trong config.</p>
          ) : (
            <ul className="persona-routes">
              {(form.routing_regex || []).map((row, i) => (
                <li
                  key={`${row.rule_id}-${i}`}
                  className={`persona-routes__item${staleIds.has(row.rule_id) ? ' is-stale' : ''}`}
                >
                  <div>
                    <span className="persona-routes__kicker">Cụm từ</span>
                    <p className="persona-routes__phrase">{row.phrase || '—'}</p>
                  </div>
                  <div>
                    <span className="persona-routes__kicker">Chủ đề</span>
                    <p className="persona-routes__topic">{topicLabel(row.rule_id, topics)}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
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
              <p className="persona-empty">{form.greeting || 'Gõ một câu như người học sẽ hỏi.'}</p>
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
