import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { ChevronDown, Search } from 'lucide-react'
import { fetchQA } from '../store/slices/qaSlice'
import './FaqBoard.css'

function fold(text) {
  return String(text || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
}

export default function FaqBoard() {
  const dispatch = useDispatch()
  const { questions, error, isLoading } = useSelector((s) => s.qa)
  const modes = useSelector((s) => s.mode.modes) || []
  const selectedMode = useSelector((s) => s.mode.selectedMode)
  const currentMode = modes.find((m) => m.id === selectedMode)
  const [moduleCode, setModuleCode] = useState(currentMode?.code || '')
  const [section, setSection] = useState('')
  const [query, setQuery] = useState('')
  const [openId, setOpenId] = useState(null)

  useEffect(() => {
    if (currentMode?.code && !moduleCode) setModuleCode(currentMode.code)
  }, [currentMode?.code, moduleCode])

  const byModule = useMemo(() => {
    const rows = (questions || []).filter((q) => q.question)
    if (!moduleCode) return rows
    return rows.filter((q) => q.module_code === moduleCode)
  }, [questions, moduleCode])

  const sections = useMemo(() => {
    const seen = []
    for (const q of byModule) {
      const name = String(q.section || '').trim()
      if (name && !seen.includes(name)) seen.push(name)
    }
    return seen
  }, [byModule])

  useEffect(() => {
    if (section && !sections.includes(section)) setSection('')
  }, [section, sections])

  const items = useMemo(() => {
    const scoped = section
      ? byModule.filter((q) => String(q.section || '').trim() === section)
      : byModule
    const needle = fold(query).trim()
    if (!needle) return scoped
    return scoped.filter((q) => {
      const hay = `${fold(q.question)} ${fold(q.answer)} ${fold(q.section)}`
      return hay.includes(needle)
    })
  }, [byModule, section, query])

  const grouped = useMemo(() => {
    const map = new Map()
    for (const q of items) {
      const key = String(q.section || '').trim() || 'Khác'
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(q)
    }
    return [...map.entries()]
  }, [items])

  return (
    <section className="faq-board" aria-label="Câu hỏi thường gặp">
      <header className="faq-board__head">
        <h2>Câu hỏi thường gặp</h2>
        <label className="faq-board__search">
          <Search size={18} strokeWidth={1.75} aria-hidden />
          <input
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setOpenId(null)
            }}
            placeholder="Tìm nhanh câu hỏi…"
            aria-label="Tìm câu hỏi thường gặp"
            autoComplete="off"
          />
        </label>
        <div className="faq-board__filters">
          <label>
            <span>Mô-đun</span>
            <select
              value={moduleCode}
              onChange={(e) => {
                setModuleCode(e.target.value)
                setSection('')
                setOpenId(null)
              }}
            >
              {modes.map((m) => (
                <option key={m.id} value={m.code || m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Phân mục</span>
            <select
              value={section}
              onChange={(e) => {
                setSection(e.target.value)
                setOpenId(null)
              }}
            >
              <option value="">Tất cả phân mục</option>
              {sections.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>
      {error ? (
        <div className="faq-board__status" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => dispatch(fetchQA({ all: true }))}>
            Thử lại
          </button>
        </div>
      ) : null}
      {isLoading ? <p className="faq-board__status">Đang tải…</p> : null}
      {!isLoading && !error && items.length === 0 ? (
        <p className="faq-board__status">
          {query.trim()
            ? 'Không tìm thấy câu hỏi khớp với từ khóa này.'
            : 'Chưa có câu hỏi thường gặp cho lựa chọn này.'}
        </p>
      ) : null}
      {grouped.map(([group, rows]) => (
        <div key={group} className="faq-board__group">
          {!section && grouped.length > 1 ? <h3>{group}</h3> : null}
          <ul className="faq-board__list">
            {rows.map((q, i) => {
              const id = q.id || `${q.module_code}-${group}-${i}`
              const open = openId === id
              return (
                <li key={id} className={`faq-board__item${open ? ' is-open' : ''}`}>
                  <button
                    type="button"
                    className="faq-board__q"
                    aria-expanded={open}
                    onClick={() => setOpenId(open ? null : id)}
                  >
                    <span>{q.question}</span>
                    <ChevronDown size={18} strokeWidth={1.75} aria-hidden />
                  </button>
                  {open ? (
                    <div className="faq-board__a">
                      <p>{q.answer || 'Chưa có câu trả lời.'}</p>
                    </div>
                  ) : null}
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </section>
  )
}
