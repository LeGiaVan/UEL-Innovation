import { Send, Trash2 } from 'lucide-react'
import { useRef, useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { clearRateLimited } from '../store/slices/chatSlice'
import './MessageInput.css'

const PLACEHOLDER_DEFAULT = 'Nhập câu hỏi của bạn…'

const MessageInput = ({ value, onChange, onSend, onClear, isLoading, disabled }) => {
  const dispatch = useDispatch()
  const selectedMode = useSelector((s) => s.mode?.selectedMode ?? 'module_1')
  const rateLimit = useSelector((s) => s.chat?.rateLimit ?? null)
  const [now, setNow] = useState(Date.now())

  // Tick mỗi giây khi đang bị rate limit để cập nhật countdown.
  useEffect(() => {
    if (!rateLimit?.untilTs) return
    const id = setInterval(() => {
      setNow(Date.now())
    }, 500)
    return () => clearInterval(id)
  }, [rateLimit?.untilTs])

  // Tự clear khi hết hạn cooldown.
  useEffect(() => {
    if (rateLimit?.untilTs && now >= rateLimit.untilTs) {
      dispatch(clearRateLimited())
    }
  }, [rateLimit?.untilTs, now, dispatch])

  const remainingSec = useMemo(() => {
    if (!rateLimit?.untilTs) return 0
    return Math.max(0, Math.ceil((rateLimit.untilTs - now) / 1000))
  }, [rateLimit?.untilTs, now])
  const isRateLimited = remainingSec > 0
  const cooldownText = useMemo(() => {
    if (!isRateLimited) return ''
    const m = Math.floor(remainingSec / 60)
    const s = remainingSec % 60
    return m > 0 ? `${m} phút ${s.toString().padStart(2, '0')} giây` : `${s} giây`
  }, [isRateLimited, remainingSec])

  const placeholder = useMemo(() => {
    if (isRateLimited) {
      return `Đang chờ ${cooldownText} để hỏi tiếp…`
    }
    return PLACEHOLDER_DEFAULT
  }, [selectedMode, isRateLimited, cooldownText])
  const textareaRef = useRef(null)

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`
    }
  }, [value])

  // Chỉ focus sau khi vừa gửi xong (isLoading true → false) — tránh mobile tự cuộn tới ô nhập khi đổi module
  const prevLoadingRef = useRef(isLoading)
  useEffect(() => {
    const prev = prevLoadingRef.current
    prevLoadingRef.current = isLoading
    if (prev && !isLoading && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [isLoading])

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      onSend(e)
      // Focus lại sau khi submit
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.focus()
        }
      }, 100)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    onSend(e)
    // Focus lại sau khi submit
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus()
      }
    }, 100)
  }

  const inputDisabled = disabled || isRateLimited

  return (
    <div className="message-input-container">
      {isRateLimited && (
        <div className="message-input-cooldown" role="status" aria-live="polite">
          ⏳ Bạn đã gửi nhiều tin nhắn trong thời gian ngắn. Vui lòng chờ <strong>{cooldownText}</strong> để hỏi tiếp.
        </div>
      )}
      <div className="message-input-wrapper">
        <form onSubmit={handleSubmit} className="message-input-form">
          <textarea
            aria-label="Nhập câu hỏi"
            maxLength={4000}
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={placeholder}
            className="message-input"
            rows={1}
            disabled={inputDisabled}
          />
          <div className="message-input-actions">
            <button
              type="button"
              onClick={onClear}
              className="clear-button"
              title="Xóa cuộc trò chuyện"
              disabled={inputDisabled}
            >
              <Trash2 size={18} />
            </button>
            <button
              type="submit"
              className="send-button"
              disabled={inputDisabled || !value.trim()}
              title={isRateLimited ? `Vui lòng chờ ${cooldownText}` : 'Gửi tin nhắn (Enter)'}
            >
              <Send size={18} />
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default MessageInput
