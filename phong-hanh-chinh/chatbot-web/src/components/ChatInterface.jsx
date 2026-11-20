import { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useLocation, useNavigate } from 'react-router-dom'
import { sendMessage, clearChat } from '../store/slices/chatSlice'
import MessageList from './MessageList'
import MessageInput from './MessageInput'
import EmptyChat from './EmptyChat'
import FaqBoard from './FaqBoard'
import './ChatInterface.css'

export default function ChatInterface() {
  const dispatch = useDispatch()
  const location = useLocation()
  const navigate = useNavigate()
  const { messages, isLoading, error, conversationId, rateLimit } = useSelector((s) => s.chat)
  const mode = useSelector((s) => s.mode.selectedMode)
  const modes = useSelector((s) => s.mode.modes) || []
  const currentMode = modes.find((m) => m.id === mode)
  const greeting = useSelector((s) => s.auth.greeting)
  const [input, setInput] = useState('')
  const task = useRef(null)
  const faqOpen = new URLSearchParams(location.search).get('view') === 'faq'
  const empty = !messages.length && !isLoading && !faqOpen

  useEffect(() => {
    setInput(location.state?.question || '')
  }, [location.key, mode])

  useEffect(() => () => {
    task.current?.abort()
  }, [location.pathname])

  function closeFaq() {
    navigate({ pathname: location.pathname, search: '' }, { replace: true })
  }

  function send(text) {
    if (!text.trim() || isLoading || rateLimit?.untilTs > Date.now()) return
    if (faqOpen) closeFaq()
    task.current = dispatch(sendMessage({ message: text.trim(), conversationId }))
    setInput('')
  }

  let main
  if (faqOpen) {
    main = <FaqBoard />
  } else if (empty) {
    main = <EmptyChat />
  } else {
    main = (
      <MessageList messages={messages} isLoading={isLoading} onSuggestionClick={send} />
    )
  }

  return (
    <div
      className={`chat-interface${empty ? ' chat-interface--empty' : ''}${faqOpen ? ' chat-interface--faq' : ''}`}
    >
      {!faqOpen && !empty && currentMode?.label ? (
        <div className="chat-module-bar">
          <strong>{currentMode.label}</strong>
          {greeting ? <span>{greeting}</span> : null}
        </div>
      ) : null}
      <div className="chat-container">
        {main}
        {error ? (
          <div className="error-message" role="alert">
            {error}
          </div>
        ) : null}
      </div>
      <MessageInput
        value={input}
        onChange={setInput}
        onSend={(e) => {
          e.preventDefault()
          send(input)
        }}
        onClear={() => {
          dispatch(clearChat())
          setInput('')
          if (faqOpen) closeFaq()
        }}
        isLoading={isLoading}
        disabled={isLoading}
      />
    </div>
  )
}
