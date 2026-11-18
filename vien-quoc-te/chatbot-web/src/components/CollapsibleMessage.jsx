import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import StreamingAssistantMarkdown from './StreamingAssistantMarkdown'

/**
 * Wrap assistant markdown với "Xem tiếp / Thu gọn" trên mobile khi nội dung quá dài.
 * Desktop (> 768px) hiển thị full luôn, không collapse.
 *
 * Logic:
 * - Đo chiều cao thực sau khi render. Nếu > maxCollapsedPx → cho phép collapse.
 * - Khi đang stream → KHÔNG collapse (user đọc realtime).
 * - Bottom có gradient mờ dần khi collapsed.
 */
const CollapsibleMessage = ({
  rawText,
  streaming,
  onRevealTick,
  maxCollapsedPx = 360,
}) => {
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' && window.matchMedia('(max-width: 768px)').matches,
  )
  const [collapsed, setCollapsed] = useState(true)
  const [needCollapse, setNeedCollapse] = useState(false)
  const innerRef = useRef(null)

  // Theo dõi viewport mobile
  useEffect(() => {
    if (typeof window === 'undefined') return
    const mq = window.matchMedia('(max-width: 768px)')
    const onChange = () => setIsMobile(mq.matches)
    mq.addEventListener?.('change', onChange)
    return () => mq.removeEventListener?.('change', onChange)
  }, [])

  // Đo chiều cao sau mỗi render để biết có cần collapse không
  useLayoutEffect(() => {
    if (!innerRef.current) return
    const h = innerRef.current.scrollHeight
    setNeedCollapse(h > maxCollapsedPx)
  }, [rawText, streaming, maxCollapsedPx])

  const showCollapse = isMobile && needCollapse && !streaming
  const isCollapsed = showCollapse && collapsed

  return (
    <div className={`collapsible-msg${isCollapsed ? ' is-collapsed' : ''}`}>
      <div
        ref={innerRef}
        className="collapsible-msg__inner"
        style={isCollapsed ? { maxHeight: `${maxCollapsedPx}px`, overflow: 'hidden' } : undefined}
      >
        <StreamingAssistantMarkdown
          rawText={rawText}
          streaming={streaming}
          onRevealTick={onRevealTick}
        />
      </div>
      {isCollapsed && <div className="collapsible-msg__fade" aria-hidden="true" />}
      {showCollapse && (
        <button
          type="button"
          className="collapsible-msg__toggle"
          onClick={() => setCollapsed((c) => !c)}
          aria-expanded={!collapsed}
        >
          {collapsed ? 'Xem tiếp ▾' : 'Thu gọn ▴'}
        </button>
      )}
    </div>
  )
}

export default CollapsibleMessage
