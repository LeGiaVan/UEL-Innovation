import AuthGate from './components/AuthGate'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import BotChatPage from './pages/BotChatPage'
import { DEFAULT_BOT_PATH } from './config/botNav'
export default function App() {
 return <AuthGate><BrowserRouter><Routes><Route path="/" element={<MainLayout />}><Route index element={<Navigate to={DEFAULT_BOT_PATH} replace />} /><Route path="bot/:botSlug" element={<BotChatPage />} /><Route path="*" element={<Navigate to={DEFAULT_BOT_PATH} replace />} /></Route></Routes></BrowserRouter></AuthGate>
}
