import {MOCK_API} from '../api/client'
/**
 * Lưu danh sách phiên chat trên trình duyệt (không đăng nhập).
 * ID hội thoại do server trả về; chỉ thiết bị này thấy danh sách.
 */
const STORAGE_KEY = 'chatbot-CTSV_chat_sessions_v1'
const MAX_SESSIONS = 30

export function readSessions() {
  if (!MOCK_API) return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw)
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

function writeSessions(sessions) {
  if (!MOCK_API) return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.slice(0, MAX_SESSIONS)))
  } catch {
    /* ignore quota */
  }
}

/** Ghi nhận / cập nhật một phiên (đưa lên đầu). */
export function upsertSession(conversationId, previewText) {
  if (!conversationId) return
  const preview = (previewText || '').trim().slice(0, 100)
  const list = readSessions().filter((s) => s.id !== conversationId)
  list.unshift({
    id: conversationId,
    preview: preview || '(Không có tiêu đề)',
    updatedAt: new Date().toISOString(),
  })
  writeSessions(list)
}

export function removeSession(conversationId) {
  writeSessions(readSessions().filter((s) => s.id !== conversationId))
}

/**
 * Gộp danh sách từ server (GET /api/conversations) với bản local:
 * cùng id thì ưu tiên bản server; giữ thêm phiên chỉ có trên máy (chưa kịp đồng bộ).
 */
export function mergeSessionsWithServer(serverList) {
  const fromServer = (Array.isArray(serverList) ? serverList : []).map((s) => ({
    id: s.id,
    preview: (s.preview || '').trim().slice(0, 100) || '(Không có tiêu đề)',
    updatedAt: s.updated_at || s.updatedAt || new Date().toISOString(),
  }))
  const byId = new Map()
  readSessions().forEach((s) => byId.set(s.id, s))
  fromServer.forEach((s) => byId.set(s.id, s))
  const merged = Array.from(byId.values()).sort(
    (a, b) => new Date(b.updatedAt) - new Date(a.updatedAt)
  )
  writeSessions(merged.slice(0, MAX_SESSIONS))
}
