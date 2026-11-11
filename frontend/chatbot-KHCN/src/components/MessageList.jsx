import { useLayoutEffect, useRef, useCallback } from 'react'
import { useSelector } from 'react-redux'
import { Loader2 } from 'lucide-react'
import StreamingAssistantMarkdown from './StreamingAssistantMarkdown'
import CollapsibleMessage from './CollapsibleMessage'
import Module2InlineQuiz from './Module2InlineQuiz'
import { useFeatureTheme } from '../context/FeatureThemeContext'
import { getChatWelcome, displayNameForResolvedMode } from '../config/featureIdentity'
import './MessageList.css'

/** Chỉ hiện khối "Nguồn trích dẫn" khi bật rõ: VITE_SHOW_SOURCES=true */
const showSources =
  (import.meta.env.VITE_SHOW_SOURCES || '').toLowerCase() === 'true'

/** Cuộn vùng overflow gần anchor nhất (tránh scrollIntoView kéo nhầm khi có 2 lớp cuộn: .chat-container vs .chat-container__thread-body). */
function scrollConversationPaneToBottom(anchorEl) {
  if (!anchorEl || typeof window === 'undefined') return
  let el = anchorEl.parentElement
  while (el) {
    const st = window.getComputedStyle(el)
    const oy = st.overflowY
    const canScroll =
      (oy === 'auto' || oy === 'scroll' || oy === 'overlay') &&
      el.scrollHeight > el.clientHeight + 1
    if (canScroll) {
      el.scrollTop = el.scrollHeight
      return
    }
    el = el.parentElement
  }
  anchorEl.scrollIntoView({ block: 'end', behavior: 'auto' })
}

const MessageList = ({ messages, isLoading, onSuggestionClick }) => {
  const modes = useSelector((s) => s.mode.modes)
  const feature = useFeatureTheme()
  const welcome = getChatWelcome(feature)
  const messageEndRef = useRef(null)

  const formatRelevance = (s) => {
    if (s === undefined || s === null) return null
    const n = Number(s)
    if (Number.isNaN(n)) return null
    if (n >= 0 && n <= 1.5) return `${(n * 100).toFixed(1)}%`
    return n.toFixed(2)
  }

  const resolvedModeLabel = useCallback(
    (id) => displayNameForResolvedMode(id, modes),
    [modes]
  )

  const last = messages[messages.length - 1]
  const showLoaderBubble = isLoading && !(last?.role === 'assistant' && last?.streaming)

  const scrollToBottom = useCallback(() => {
    scrollConversationPaneToBottom(messageEndRef.current)
  }, [])

  useLayoutEffect(() => {
    // Không kéo scroll khi chưa có hội thoại (welcome / đổi module) — tránh mobile nhảy xuống cuối trang
    if (messages.length === 0 && !isLoading) return
    if (messages.length === 0 && isLoading && !showLoaderBubble) return
    scrollToBottom()
  }, [messages, isLoading, scrollToBottom, showLoaderBubble])

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
                  <CollapsibleMessage
                    rawText={message.content || ''}
                    streaming={!!message.streaming}
                    onRevealTick={scrollToBottom}
                  />
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
                {showSources &&
                  message.citations &&
                  Array.isArray(message.citations) &&
                  message.citations.length > 0 && (
                  <div className="message-citations" aria-label="Nguồn tài liệu">
                    <div className="citations-header">Nguồn trích dẫn</div>
                    <p className="citations-lead">
                      Các đoạn dưới đây là nội dung tham khảo (FAQ hoặc tài liệu chính thức) được dùng để soạn câu trả lời.
                    </p>
                    {message.citations.map((citation, idx) => {
                      const rel = formatRelevance(citation.score)
                      const excerpt = citation.excerpt || citation.text_preview
                      return (
                      <div key={idx} className="citation-item">
                        <div className="citation-index">{citation.index || idx + 1}</div>
                        <div className="citation-content">
                          <div className="citation-source-row">
                            <span className={`citation-badge citation-badge--${citation.source_kind || 'other'}`}>
                              {citation.source_kind === 'faq'
                                ? 'FAQ'
                                : citation.source_kind === 'document'
                                  ? 'Tài liệu'
                                  : 'Nguồn'}
                            </span>
                            {citation.document_name && (
                              <span className="citation-doc-name" title={citation.source}>
                                {citation.document_name}
                              </span>
                            )}
                          </div>
                          <div className="citation-source">
                            <strong>Tóm tắt nguồn:</strong>{' '}
                            {citation.source || citation.document_name || 'Tài liệu tham khảo'}
                            {citation.question && (
                              <span className="citation-question"> — {citation.question}</span>
                            )}
                          </div>
                          {citation.topic && (
                            <div className="citation-meta-line">
                              <span className="citation-meta-label">Chủ đề / mục:</span>{' '}
                              {citation.topic}
                              {citation.section_title && citation.section_title !== citation.topic
                                ? ` — ${citation.section_title}`
                                : ''}
                            </div>
                          )}
                          {citation.data_module && (
                            <div className="citation-meta-line">
                              <span className="citation-meta-label">Module dữ liệu:</span>{' '}
                              {citation.data_module}
                            </div>
                          )}
                          {excerpt && (
                            <div className="citation-excerpt-block">
                              <div className="citation-excerpt-label">Đoạn trích tham khảo</div>
                              <div className="citation-preview">{excerpt}</div>
                            </div>
                          )}
                          {citation.answer_preview && (
                            <div className="citation-answer-preview">
                              <span className="citation-meta-label">Trích từ câu trả lời FAQ:</span>{' '}
                              {citation.answer_preview}
                            </div>
                          )}
                          {rel !== null && (
                            <div className="citation-score">Độ liên quan (retrieval): {rel}</div>
                          )}
                        </div>
                      </div>
                      )
                    })}
                  </div>
                )}
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
