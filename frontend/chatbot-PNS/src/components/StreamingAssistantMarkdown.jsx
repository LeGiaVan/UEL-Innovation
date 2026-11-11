import { useState, useEffect, useRef, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { formatAssistantMarkdown } from '../utils/formatAssistantMarkdown'

/**
 * Khi streaming: văn bản đích (rawText) cập nhật theo chunk từ API;
 * phần hiển thị tăng dần từng (vài) ký tự mỗi khung hình để mượt như gõ tay.
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
    if (!streaming) {
      setVisible(rawText || '')
    }
  }, [streaming, rawText])

  useEffect(() => {
    if (streaming && !(rawText || '').length) {
      setVisible('')
    }
  }, [streaming, rawText])

  useEffect(() => {
    if (!streaming) return

    let raf
    let frame = 0
    const tick = () => {
      frame += 1
      setVisible((prev) => {
        const target = targetRef.current
        if (prev.length >= target.length) return prev
        const lag = target.length - prev.length
        let step = 1
        if (lag > 400) step = 3
        else if (lag > 150) step = 2
        else step = 1
        return target.slice(0, prev.length + Math.min(step, lag))
      })
      if (frame % 2 === 0) {
        tickCbRef.current?.()
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [streaming])

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

  // Stream và hoàn thành đều qua Markdown + GFM (bảng, danh sách) để hiển thị dạng ô/bảng, không chỉ khối text.
  return (
    <div className={streaming ? 'assistant-md assistant-md--streaming' : 'assistant-md'}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={mdComponents}>
        {md}
      </ReactMarkdown>
      {streaming ? <span className="stream-cursor" aria-hidden /> : null}
    </div>
  )
}
