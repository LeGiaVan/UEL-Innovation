import { useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { ChevronDown } from 'lucide-react'
import { fetchQA } from '../store/slices/qaSlice'
import { applyCannedFaq } from '../store/slices/chatSlice'
import './FaqBoard.css'

export default function FaqBoard({ onAsked }) {
  const dispatch = useDispatch()
  const { questions, error, isLoading } = useSelector((s) => s.qa)
  const isChatLoading = useSelector((s) => s.chat.isLoading)
  const modes = useSelector((s) => s.mode.modes) || []
  const selectedMode = useSelector((s) => s.mode.selectedMode)
  const currentMode = modes.find((m) => m.id === selectedMode)
  const [openId, setOpenId] = useState(null)

  const items = useMemo(
    () => (questions || []).filter((q) => q.question),
    [questions],
  )

  function ask(q) {
    if (isChatLoading || !q.answer) return
    dispatch(applyCannedFaq({ question: q.question, answer: q.answer }))
    onAsked?.()
  }

  return (
    <section className="faq-board" aria-label="Câu hỏi thường gặp">
      <header className="faq-board__head">
        <h2>Câu hỏi thường gặp</h2>
        {currentMode?.label ? <p>{currentMode.label}</p> : null}
      </header>
      {error ? (
        <div className="faq-board__status" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => dispatch(fetchQA({ mode: selectedMode }))}>
            Thử lại
          </button>
        </div>
      ) : null}
      {isLoading ? <p className="faq-board__status">Đang tải…</p> : null}
      {!isLoading && !error && items.length === 0 ? (
        <p className="faq-board__status">Chưa có câu hỏi thường gặp cho mảng này.</p>
      ) : null}
      <ul className="faq-board__list">
        {items.map((q, i) => {
          const id = q.id || `${q.module_code}-${i}`
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
                  {q.answer ? (
                    <button
                      type="button"
                      className="faq-board__ask"
                      disabled={isChatLoading}
                      onClick={() => ask(q)}
                    >
                      Đưa vào hội thoại
                    </button>
                  ) : null}
                </div>
              ) : null}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
