import { useState, useEffect, useRef, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { formatAssistantMarkdown } from '../utils/formatAssistantMarkdown'

/**
 * Tin mới (reveal=type): giả lập gõ dù SSE dump một lần.
 * Tin đã lưu / đổi module (reveal=instant): hiện đủ ngay, không gõ lại.
 */
export default function StreamingAssistantMarkdown({
  rawText,
  streaming,
  reveal,
  onRevealTick,
}) {
  const full = rawText || ''
  const animate = reveal === 'type' || !!streaming
  const [visible, setVisible] = useState(() => (animate ? '' : full))
  const visibleRef = useRef(animate ? '' : full)
  const targetRef = useRef(full)
  const tickCbRef = useRef(onRevealTick)
  targetRef.current = full
  tickCbRef.current = onRevealTick

  useEffect(() => {
    if (!animate) {
      visibleRef.current = full
      setVisible(full)
    } else if (streaming && !full.length) {
      visibleRef.current = ''
      setVisible('')
    }
  }, [animate, streaming, full])

  useEffect(() => {
    if (!animate || !full) return undefined
    const startLen = Math.min(visibleRef.current.length, full.length)
    if (startLen >= full.length) {
      visibleRef.current = full
      setVisible(full)
      return undefined
    }
    let raf
    const start = performance.now()
    const remain = full.length - startLen
    const duration = Math.min(1600, Math.max(480, remain * 7))
    const tick = (now) => {
      const target = targetRef.current
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - (1 - t) * (1 - t)
      const nextLen = Math.min(target.length, startLen + Math.max(1, Math.ceil(remain * eased)))
      const next = target.slice(0, nextLen)
      visibleRef.current = next
      setVisible(next)
      if (next.length < target.length) {
        tickCbRef.current?.()
        raf = requestAnimationFrame(tick)
      }
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [animate, full])

  const catchingUp = visible.length < full.length
  const live = streaming || (animate && catchingUp)

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
