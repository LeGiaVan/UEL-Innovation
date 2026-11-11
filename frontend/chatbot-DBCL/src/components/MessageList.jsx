import { useLayoutEffect, useEffect, useRef, useCallback } from 'react'
import { useSelector } from 'react-redux'
import { Loader2 } from 'lucide-react'
import StreamingAssistantMarkdown from './StreamingAssistantMarkdown'
import CollapsibleMessage from './CollapsibleMessage'
import Module2InlineQuiz from './Module2InlineQuiz'
import { useFeatureTheme } from '../context/FeatureThemeContext'
import { getChatWelcome, displayNameForResolvedMode } from '../config/featureIdentity'
import './MessageList.css'

/** Chỉ hiện dòng nguồn gọn khi bật VITE_SHOW_SOURCES=true và câu trả lời chưa ghi Nguồn. */
const showSources =
  (import.meta.env.VITE_SHOW_SOURCES || '').toLowerCase() === 'true'

function findScrollPane(anchorEl) {
  if (!anchorEl || typeof window === 'undefined') return null
  let el = anchorEl.parentElement
  while (el) {
    const oy = window.getComputedStyle(el).overflowY
    if (oy === 'auto' || oy === 'scroll' || oy === 'overlay') return el
    el = el.parentElement
  }
  return null
}

function isNearBottom(el, px = 96) {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= px
}

function uniqueCitationLabels(citations) {
  const seen = new Set()
  const labels = []
  for (const item of citations || []) {
    const label = String(item.document_name || item.source || '').trim()
    if (!label) continue
    const key = label.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    labels.push(label)
  }
  return labels
}

function answerAlreadyCites(text, labels) {
  const raw = text || ''
  if (/nguồn\s*:/i.test(raw)) return true
  const lower = raw.toLowerCase()
  return labels.some((label) => lower.includes(label.toLowerCase()))
}

const MessageList = ({ messages, isLoading, onSuggestionClick }) => {
  const modes = useSelector((s) => s.mode.modes)
  const feature = useFeatureTheme()
  const welcome = getChatWelcome(feature)
  const messageEndRef = useRef(null)
  const stickToBottomRef = useRef(true)
  const userGrabRef = useRef(false)

  const resolvedModeLabel = useCallback(
    (id) => displayNameForResolvedMode(id, modes),
    [modes]
  )

  const last = messages[messages.length - 1]
  const showLoaderBubble = isLoading && !(last?.role === 'assistant' && last?.streaming)

  const scrollToBottom = useCallback(() => {
    if (!stickToBottomRef.current || userGrabRef.current) return
    const pane = findScrollPane(messageEndRef.current)
    if (pane) {
      pane.scrollTop = pane.scrollHeight
      return
    }
    messageEndRef.current?.scrollIntoView({ block: 'end', behavior: 'auto' })
  }, [])

  useEffect(() => {
    const pane = findScrollPane(messageEndRef.current)
    if (!pane) return
    const onScroll = () => {
      stickToBottomRef.current = isNearBottom(pane)
    }
    const onWheel = (event) => {
      if (event.deltaY < 0) stickToBottomRef.current = false
    }
    const onPointerDown = () => {
      userGrabRef.current = true
    }
    const onPointerUp = () => {
      userGrabRef.current = false
      stickToBottomRef.current = isNearBottom(pane)
    }
    pane.addEventListener('scroll', onScroll, { passive: true })
    pane.addEventListener('wheel', onWheel, { passive: true })
    pane.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('pointerup', onPointerUp)
    return () => {
      pane.removeEventListener('scroll', onScroll)
      pane.removeEventListener('wheel', onWheel)
      pane.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('pointerup', onPointerUp)
    }
  }, [messages.length])

  useLayoutEffect(() => {
    if (messages.length === 0 && !isLoading) return
    if (messages.length === 0 && isLoading && !showLoaderBubble) return
    if (last?.role === 'user') stickToBottomRef.current = true
    scrollToBottom()
  }, [messages, isLoading, scrollToBottom, showLoaderBubble, last?.role])

  if (messages.length === 0 && !isLoading) {
    if (feature?.admission) {
      return null
    }
    if (feature?.moduleId === 'module_2' || feature?.moduleId === 'module_3') {
      return null
    }
    const circled = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧']
    return (
      <div className="empty-chat">
        <div className="empty-chat-content">
          <h2 className="empty-chat-headline">{welcome.headline}</h2>
          <p className="empty-chat-lead">{welcome.intro}</p>
          <p className="empty-chat-section-title">{welcome.bulletsTitle}</p>
          <ul className="empty-chat-journey">
            {welcome.bullets.map((text, i) => (
              <li key={i}>
                <span className="journey-icon" aria-hidden>
                  {circled[i] ?? `${i + 1}.`}
                </span>
                {text}
              </li>
            ))}
          </ul>
          <p className="empty-chat-hint">{welcome.footerHint}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="message-list">
      {messages.map((message, index) => (
        <div
          key={`${message.timestamp || index}-${index}`}
          className={`message ${message.role === 'user' ? 'message-user' : 'message-assistant'} message-animate`}
        >
          <div className="message-content">
            {/* Avatar */}
            <div className={`message-avatar ${message.role === 'user' ? 'avatar-user' : 'avatar-assistant'}`}>
              {message.role === 'user' ? (
                <div className="avatar-user-icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 12C14.7614 12 17 9.76142 17 7C17 4.23858 14.7614 2 12 2C9.23858 2 7 4.23858 7 7C7 9.76142 9.23858 12 12 12Z" fill="currentColor"/>
                    <path d="M12.0002 14.5C6.99016 14.5 2.91016 17.86 2.91016 22C2.91016 22.28 3.13016 22.5 3.41016 22.5H20.5902C20.8702 22.5 21.0902 22.28 21.0902 22C21.0902 17.86 17.0102 14.5 12.0002 14.5Z" fill="currentColor"/>
                  </svg>
                </div>
              ) : (
                <img 
                  src="/uel-logo-cap-nhat-09-4-40.jpg" 
                  alt="UEL Logo" 
                  className="avatar-image"
                />
              )}
            </div>
            <div className="message-text-wrapper">
            {message.role === 'user' ? (
              <div className="message-text user-text">
                {message.content}
              </div>
            ) : (
              <>
                {message.resolvedMode && !message.streaming && (
                  <div
                    className="resolved-mode-badge"
                    title={`Chế độ xử lý: ${resolvedModeLabel(message.resolvedMode)}`}
                  >
                    {resolvedModeLabel(message.resolvedMode)}
                  </div>
                )}
                <div className="message-text assistant-text">
                  {message.streaming && !message.content ? (
                    <p className="waiting">{message.streamLabel || 'Đang soạn câu trả lời…'}</p>
                  ) : (
                  <CollapsibleMessage
                    rawText={message.content || ''}
                    streaming={!!message.streaming}
                    onRevealTick={scrollToBottom}
                  />
                  )}
                  {message.interactive?.kind === 'module2_quiz_batch' ? (
                    <Module2InlineQuiz
                      payload={message.interactive}
                      onAfterSubmit={scrollToBottom}
                    />
                  ) : (message.interactive?.kind === 'ctdt_suggestions' ||
                       message.interactive?.kind === 'did_you_mean') ? (
                    <div className="ctdt-suggestions" aria-label="Gợi ý câu hỏi tiếp theo">
                      <p className="ctdt-suggestions__label">
                        {message.interactive.label || 'Bạn có muốn hỏi thêm về:'}
                      </p>
                      <div className="ctdt-suggestions__chips">
                        {(message.interactive.suggestions || []).map((s, i) => (
                          <button
                            key={i}
                            type="button"
                            className="ctdt-suggestions__chip"
                            onClick={() => onSuggestionClick && onSuggestionClick(s)}
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
                {showSources && !message.streaming && (() => {
                  const labels = uniqueCitationLabels(message.citations)
                  if (!labels.length || answerAlreadyCites(message.content, labels)) return null
                  return (
                    <p className="message-sources" aria-label="Nguồn tài liệu">
                      Nguồn: {labels.join(', ')}
                    </p>
                  )
                })()}
              </>
            )}
            {message.timestamp && (
              <div className="message-timestamp">
                {new Date(message.timestamp).toLocaleTimeString('vi-VN', {
                  hour: '2-digit',
                  minute: '2-digit'
                })}
              </div>
            )}
            </div>
          </div>
        </div>
      ))}
      {showLoaderBubble && (
        <div className="message message-assistant message-animate">
          <div className="message-content">
            <div className="message-avatar avatar-assistant">
              <img 
                src="/uel-logo-cap-nhat-09-4-40.jpg" 
                alt="UEL Logo" 
                className="avatar-image"
              />
            </div>
            <div className="message-text-wrapper">
              <div className="message-text assistant-text">
                <div className="loading-indicator">
                  <Loader2 className="spinner" />
                  <span>Đang trả lời...</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      <div ref={messageEndRef} />
    </div>
  )
}

export default MessageList
