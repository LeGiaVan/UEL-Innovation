import { useEffect, useState, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useLocation } from 'react-router-dom'
import { sendMessage, clearChat } from '../store/slices/chatSlice'
import MessageList from './MessageList'
import MessageInput from './MessageInput'
import DepartmentHub from './DepartmentHub'
import { MOCK_API } from '../api/client'
import './ChatInterface.css'
export default function ChatInterface() {
 const dispatch=useDispatch(), location=useLocation()
 const {messages,isLoading,error,conversationId,rateLimit}=useSelector(s=>s.chat)
 const mode=useSelector(s=>s.mode.selectedMode)
 const [input,setInput]=useState(''), task=useRef(null)
 useEffect(()=>{setInput(location.state?.question || '')},[location.key,mode])
 useEffect(()=>()=>{task.current?.abort()},[location.pathname])
 function send(text) {
  if(!text.trim() || isLoading || (rateLimit?.untilTs > Date.now()))return
  task.current=dispatch(sendMessage({message:text.trim(),conversationId}));setInput('')
 }
 return <div className="chat-interface"><div className="chat-container">{!messages.length&&!isLoading ? <DepartmentHub onSuggestionClick={send}/> : <MessageList messages={messages} isLoading={isLoading} onSuggestionClick={send}/>} {error && <div className="error-message" role="alert">{error}</div>}</div><MessageInput value={input} onChange={setInput} onSend={e=>{e.preventDefault();send(input)}} onClear={()=>{dispatch(clearChat());setInput('')}} isLoading={isLoading} disabled={isLoading}/>{MOCK_API && <p className="department-disclaimer">Bản mẫu • Phản hồi mô phỏng, chưa gửi yêu cầu đến phòng.</p>}</div>
}
