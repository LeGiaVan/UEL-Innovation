import { useEffect } from 'react'
import { useParams, Navigate } from 'react-router-dom'
import { useDispatch } from 'react-redux'
import { setSelectedMode } from '../store/slices/modeSlice'
import { getModuleIdBySlug, DEFAULT_BOT_PATH } from '../config/botNav'
import ChatInterface from '../components/ChatInterface'

export default function BotChatPage() {
  const { botSlug } = useParams()
  const dispatch = useDispatch()
  const moduleId = getModuleIdBySlug(botSlug)

  useEffect(() => {
    if (moduleId) {
      dispatch(setSelectedMode(moduleId))
    }
  }, [moduleId, dispatch])

  if (!moduleId) {
    return <Navigate to={DEFAULT_BOT_PATH} replace />
  }

  return <ChatInterface />
}
