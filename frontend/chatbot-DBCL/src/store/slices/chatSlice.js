import { consumeChatSse } from '../../utils/sse'
import { API_URL, fetchApi as fetch } from '../../api/client'
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import axios from '../../api/client'
import { upsertSession, mergeSessionsWithServer } from '../../utils/sessionLog'
import { setSelectedMode } from './modeSlice'

/** @typedef {{ message: string, conversationId?: string | null, quizSessionId?: string | null, quizSummarySilent?: boolean, omitUserBubble?: boolean, sessionPreview?: string | null }} SendMessageArg */

function cloneMessagesForModule(msgs) {
  if (!Array.isArray(msgs)) return []
  return msgs.map((m) => ({ ...m }))
}



export const sendMessage = createAsyncThunk(
  'chat/sendMessage',
  async (
    {
      message,
      conversationId = null,
      quizSessionId: quizFromArg = null,
      quizSummarySilent = false,
      omitUserBubble = false,
      sessionPreview = null,
    },
    { dispatch, rejectWithValue, getState, signal, requestId }
  ) => {
    try {
      const mode = getState().mode?.selectedMode ?? 'module_1'
      const quizSessionId =
        quizFromArg ?? getState().chat?.quizSessionId ?? null
      const body = {
        message,
        conversation_id: conversationId,
        mode,
      }
      if (quizSessionId) {
        body.quiz_session_id = quizSessionId
      }
      if (quizSummarySilent) {
        body.quiz_summary_silent = true
      }
      const res = await fetch(`${API_URL}/chat/stream`, {
        method: 'POST',
        signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}))
        if (res.status === 429) dispatch(setRateLimited({requestId, retryAfterSec: Number(res.headers.get('Retry-After') || 60)}))
        const detail = payload.detail
        return rejectWithValue(typeof detail === 'string' ? detail : (Array.isArray(detail) ? detail.map(e=>e.msg).join(' ') : 'Không thể gửi tin nhắn.'))
      }
      if (!res.body) {
        return rejectWithValue('Trình duyệt không hỗ trợ stream')
      }
      let donePayload = null
      let rateLimitedPayload = null
      await consumeChatSse(res.body.getReader(), (ev) => {
        if (ev.type === 'status' && ev.label) {
          dispatch(setStreamStatus({label: ev.label, requestId}))
        }
        if (ev.type === 'token' && ev.text) {
          dispatch(appendStreamChunk({text: ev.text, requestId}))
        }
        if (ev.type === 'done') {
          donePayload = ev
        }
        if (ev.type === 'rate_limited') {
          rateLimitedPayload = ev
          dispatch(setRateLimited({
            requestId,
            retryAfterSec: Number(ev.retry_after_sec || 60),
            reason: String(ev.reason || ''),
          }))
        }
        if (ev.type === 'error') {
          throw new Error(ev.message || 'Lỗi stream')
        }
      })
      if (!donePayload) {
        throw new Error('Kết thúc stream không hợp lệ')
      }
      if (quizSummarySilent) {
        dispatch(clearQuizSessionId())
      }
      return donePayload
    } catch (error) {
      const msg =
        typeof error === 'string'
          ? error
          : error?.message || 'Có lỗi xảy ra khi gửi tin nhắn'
      return rejectWithValue(msg)
    }
  }
)

export const fetchConversation = createAsyncThunk(
  'chat/fetchConversation',
  async (conversationId, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${API_URL}/conversations/${conversationId}`)
      return response.data
    } catch (error) {
      const raw = error.response?.data?.detail
      const detail = Array.isArray(raw)
        ? raw.map((x) => x.msg || String(x)).join(' ')
        : raw
      return rejectWithValue(
        detail || error.response?.data || error.message || 'Lỗi tải hội thoại'
      )
    }
  }
)

/** Tải toàn bộ danh sách hội thoại từ Firestore (GET /api/conversations), gộp vào localStorage. */
export const fetchConversationList = createAsyncThunk(
  'chat/fetchConversationList',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${API_URL}/conversations`, {
        params: { limit: 200 },
      })
      const conversations = response.data?.conversations || []
      mergeSessionsWithServer(conversations)
      return { count: conversations.length }
    } catch (error) {
      const raw = error.response?.data?.detail
      const detail = Array.isArray(raw)
        ? raw.map((x) => x.msg || String(x)).join(' ')
        : raw
      return rejectWithValue(
        detail ||
          error.response?.data ||
          error.message ||
          'Không tải được danh sách hội thoại'
      )
    }
  }
)

const chatSlice = createSlice({
  name: 'chat',
  initialState: {
    messages: [],
    isLoading: false,
    isHistoryLoading: false,
    isStreaming: false,
    error: null,
    conversationId: null,
    /** Phiên trắc nghiệm module_2 (UUID) — gửi kèm chat stream. */
    quizSessionId: null,
    /** Module đang hiển thị trong khung chat (đồng bộ với selectedMode khi ở trang bot). */
    activeChatModuleId: null,
    /** Hội thoại lưu theo từng module — khi chuyển bot chỉ đổi view, không trộn nội dung. */
    chatByModule: {},
    /** Tăng khi đã đồng bộ danh sách từ server (Sidebar đọc lại localStorage). */
    conversationListVersion: 0,
    isConversationListLoading: false,
    /** module_2: đang stream phản hồi sau khi nộp xong bài trắc nghiệm. */
    silentFollowupStreaming: false,
    /**
     * Rate limit: khi BE trả `type=rate_limited`, FE lưu `untilTs` (epoch ms) + `reason`.
     * Input bị disable đến khi Date.now() > untilTs. null = không bị limit.
     */
    rateLimit: null,
  },
  reducers: {
    setQuizSessionId: (state, action) => {
      state.quizSessionId = action.payload || null
    },
    clearQuizSessionId: (state) => {
      state.quizSessionId = null
    },
    clearChat: (state) => {
      state.activeRequestId = null
      state.activeHistoryRequestId = null
      state.isHistoryLoading = false
      state.isLoading = false
      state.isStreaming = false
      state.messages = []
      state.conversationId = null
      state.error = null
      state.quizSessionId = null
      state.silentFollowupStreaming = false
      const mid = state.activeChatModuleId
      if (mid) {
        state.chatByModule[mid] = {
          messages: [],
          conversationId: null,
          quizSessionId: null,
        }
      }
    },
    clearChatError: (state) => {
      state.error = null
    },
    addMessage: (state, action) => {
      state.messages.push(action.payload)
    },
    setRateLimited: (state, action) => {
      const sec = Math.max(1, Number(action.payload?.retryAfterSec || 60))
      if (action.payload.requestId && action.payload.requestId !== state.activeRequestId) return
      state.rateLimit = {
        untilTs: Date.now() + sec * 1000,
        reason: String(action.payload?.reason || ''),
      }
    },
    clearRateLimited: (state) => {
      state.rateLimit = null
    },
    setStreamStatus: (state, action) => {
      if (action.payload.requestId !== state.activeRequestId) return
      const last = state.messages[state.messages.length - 1]
      if (last && last.role === 'assistant' && last.streaming) {
        last.streamLabel = action.payload.label
      }
    },
    appendStreamChunk: (state, action) => {
      if (action.payload.requestId !== state.activeRequestId) return
      const last = state.messages[state.messages.length - 1]
      if (last && last.role === 'assistant' && last.streaming) {
        last.streamLabel = ''
        last.content += action.payload.text
      }
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(setSelectedMode, (state, action) => {
        const next = action.payload
        if (state.activeChatModuleId === next) return

        state.activeRequestId = null
        state.activeHistoryRequestId = null
        state.isHistoryLoading = false
        const prev = state.activeChatModuleId
        if (prev != null) {
          state.chatByModule[prev] = {
            messages: cloneMessagesForModule(state.messages.filter(m => !m.streaming)),
            conversationId: state.conversationId,
            quizSessionId: state.quizSessionId,
          }
        }

        const snap = state.chatByModule[next]
        state.messages = cloneMessagesForModule(snap?.messages)
        state.conversationId = snap?.conversationId ?? null
        state.quizSessionId = snap?.quizSessionId ?? null
        state.error = null
        state.isLoading = false
        state.isStreaming = false
        state.silentFollowupStreaming = false
        state.activeChatModuleId = next
      })
      .addCase(sendMessage.pending, (state, action) => {
        state.activeRequestId = action.meta.requestId
        state.isLoading = true
        state.isStreaming = true
        state.error = null
        const { message, omitUserBubble } = action.meta.arg
        state.silentFollowupStreaming = Boolean(omitUserBubble)
        const ts = new Date().toISOString()
        if (!omitUserBubble) {
          state.messages.push({
            role: 'user',
            content: message,
            timestamp: ts,
          })
        }
        state.messages.push({
          role: 'assistant',
          content: '',
          streaming: true,
          streamLabel: 'Đang xử lý câu hỏi…',
          contactInfo: undefined,
          citations: [],
          resolvedMode: undefined,
          interactive: null,
          timestamp: ts,
        })
      })
      .addCase(sendMessage.fulfilled, (state, action) => {
        if (state.activeRequestId !== action.meta.requestId) return
        state.activeRequestId = null
        state.isLoading = false
        state.isStreaming = false
        state.silentFollowupStreaming = false
        const p = action.payload
        const last = state.messages[state.messages.length - 1]
        if (last && last.role === 'assistant') {
          last.content = p.response
          last.streaming = false
          last.contactInfo = p.contact_info
          last.citations = p.citations || []
          last.resolvedMode = p.resolved_mode || undefined
          last.interactive = p.interactive ?? null
        }
        if (p.conversation_id) {
          state.conversationId = p.conversation_id
          const preview =
            (action.meta.arg.sessionPreview && String(action.meta.arg.sessionPreview).trim()) ||
            (p.user_message && String(p.user_message).trim()) ||
            (action.meta.arg.message && String(action.meta.arg.message).trim()) ||
            'Tin nhắn mới'
          upsertSession(p.conversation_id, preview)
        }
      })
      .addCase(sendMessage.rejected, (state, action) => {
        if (state.activeRequestId !== action.meta.requestId) return
        state.activeRequestId = null
        state.isLoading = false
        state.isStreaming = false
        state.silentFollowupStreaming = false
        state.error = action.meta.aborted ? null : (action.payload || 'Có lỗi xảy ra khi gửi tin nhắn')
        const last = state.messages[state.messages.length - 1]
        if (last?.streaming) {
          state.messages.pop()
        }
      })
      .addCase(fetchConversation.pending, (state, action) => {
        state.activeHistoryRequestId = action.meta.requestId
        state.isHistoryLoading = true
        state.error = null
        state.isLoading = false
      })
      .addCase(fetchConversation.fulfilled, (state, action) => {
        if (state.activeHistoryRequestId !== action.meta.requestId) return
        state.activeHistoryRequestId = null
        state.isHistoryLoading = false
        state.quizSessionId = null
        const rows = action.payload.messages || []
        const mapped = []
        rows.forEach((m) => {
          const ts = m.timestamp || new Date().toISOString()
          const um = (m.user_message || '').trim()
          if (um) {
            mapped.push({
              role: 'user',
              content: um,
              timestamp: ts,
            })
          }
          mapped.push({
            role: 'assistant',
            content: m.assistant_response || '',
            contactInfo: m.contact_info,
            citations: [],
            timestamp: ts,
          })
        })
        state.messages = mapped
        state.conversationId = action.payload.conversation_id
        const mid = state.activeChatModuleId
        if (mid) {
          state.chatByModule[mid] = {
            messages: cloneMessagesForModule(state.messages.filter(m => !m.streaming)),
            conversationId: state.conversationId,
            quizSessionId: null,
          }
        }
      })
      .addCase(fetchConversation.rejected, (state, action) => {
        if (state.activeHistoryRequestId !== action.meta.requestId) return
        state.activeHistoryRequestId = null
        state.isHistoryLoading = false
        state.error =
          typeof action.payload === 'string'
            ? action.payload
            : action.payload?.detail || 'Không tải được lịch sử hội thoại'
      })
      .addCase(fetchConversationList.pending, (state) => {
        state.isConversationListLoading = true
      })
      .addCase(fetchConversationList.fulfilled, (state) => {
        state.isConversationListLoading = false
        state.conversationListVersion += 1
      })
      .addCase(fetchConversationList.rejected, (state) => {
        state.isConversationListLoading = false
      })
  },
})

export const {
  clearChat,
  clearChatError,
  addMessage,
  appendStreamChunk,
  setStreamStatus,
  setQuizSessionId,
  clearQuizSessionId,
  setRateLimited,
  clearRateLimited,
} = chatSlice.actions
export default chatSlice.reducer
