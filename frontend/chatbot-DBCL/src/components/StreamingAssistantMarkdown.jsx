import { useState, useEffect, useRef, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { formatAssistantMarkdown } from '../utils/formatAssistantMarkdown'

/**
 * Nhận cả câu rồi giả lập gõ từng ký tự — SSE có thể dump một lần,
 * phần hiện ra vẫn mượt như token stream.
 */
export default function StreamingAssistantMarkdown({
  rawText,
  streaming,
  onRevealTick,
}) {
  const [visible, setVisible] = useState('')
  const targetRef = useRef(rawText || '')
  const tickCbRef = useRef(onRevealTick)
  targetRef.current = rawText || ''
  tickCbRef.current = onRevealTick

  useEffect(() => {
    if (streaming && !(rawText || '').length) {
      setVisible('')
    }
  }, [streaming, rawText])

  useEffect(() => {
    let raf
    let frame = 0
    const tick = () => {
      frame += 1
      setVisible((prev) => {
        const target = targetRef.current
        if (prev.length >= target.length) return prev
        const lag = target.length - prev.length
        const step = lag > 160 ? 4 : 3
        return target.slice(0, prev.length + Math.min(step, lag))
      })
      if (frame % 2 === 0) {
        tickCbRef.current?.()
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [streaming, rawText])

  const catchingUp = visible.length < (rawText || '').length
  const live = streaming || catchingUp

  const md = useMemo(() => {
    if (!visible) return ''
    return formatAssistantMarkdown(visible)
  }, [visible])

  const mdComponents = useMemo(
    () => ({
      table: ({ children, ...props }) => (
        <div className="assistant-table-scroll">
          <table {...props}>{children}</table>
        </div>
      ),
    }),
    []
  )

  return (
    <div className={live ? 'assistant-md assistant-md--streaming' : 'assistant-md'}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={mdComponents}>
        {md}
      </ReactMarkdown>
      {live ? <span className="stream-cursor" aria-hidden /> : null}
    </div>
  )
}
