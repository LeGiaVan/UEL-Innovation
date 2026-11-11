import { API_URL, fetchApi as fetch } from '../api/client'
import { useState, useCallback, useMemo, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Loader2 } from 'lucide-react'
import { addMessage, sendMessage, setQuizSessionId } from '../store/slices/chatSlice'
import Module2QuizBatchStep from './Module2QuizBatchStep'
import './Module2QuizPanel.css'



/** Tiêu đề ngắn trong danh sách hội thoại (sidebar). */
const QUIZ_DONE_SESSION_PREVIEW = 'Gợi ý ngành từ trắc nghiệm'

async function postQuizJson(path, body) {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const text = await res.text()
  let data = {}
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = { detail: text }
    }
  }
  if (!res.ok) {
    const msg =
      typeof data.detail === 'string'
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail.map((x) => x.msg || String(x)).join(' ')
          : data.message || text || res.statusText
    throw new Error(msg || `Lỗi ${res.status}`)
  }
  return data
}

function cheerMessage(answered, total) {
  if (!total) return ''
  const r = answered / total
  if (r < 0.12) return 'Khởi đầu tốt — chọn mức độ phù hợp nhất với bạn.'
  if (r < 0.45) return 'Tiến độ ổn — cứ theo cảm nhận đầu tiên.'
  if (r < 0.78) return 'Đã qua nửa chặng — kiên nhẫn thêm một đoạn.'
  return 'Sắp xong — hoàn thành để xem phần tóm tắt và tư vấn tiếp theo.'
}

/**
 * Form trắc nghiệm nhúng trong bubble assistant (chế độ chat module_2).
 * Payload từ API: done.interactive (kind module2_quiz_batch).
 */
export default function Module2InlineQuiz({ payload, onAfterSubmit }) {
  const dispatch = useDispatch()
  const conversationId = useSelector((s) => s.chat?.conversationId ?? null)
  const autoFollowupSent = useRef(null)

  const quizType = payload?.quiz_type
  const sessionId = payload?.session_id
  const batch = Array.isArray(payload?.batch) ? payload.batch : []
  const progress = payload?.progress || { answered: 0, total: 0 }

  const [batchAnswers, setBatchAnswers] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const setAnswer = useCallback((qid, val) => {
    setBatchAnswers((prev) => ({ ...prev, [String(qid)]: val }))
  }, [])

  const filledInBatch = useMemo(() => {
    if (!batch.length) return 0
    return batch.filter((it) => {
      const v = batchAnswers[String(it.qid)]
      return v !== undefined && v !== '' && v !== null
    }).length
  }, [batch, batchAnswers])

  const pct = useMemo(() => {
    const total = progress.total || 0
    if (!total) return 0
    const est = Math.min(total, (progress.answered || 0) + filledInBatch)
    return Math.min(100, Math.round((est / total) * 100))
  }, [progress.answered, progress.total, filledInBatch])

  const cheer = useMemo(
    () =>
      cheerMessage(
        Math.min((progress.answered || 0) + filledInBatch, progress.total || 0),
        progress.total || 0
      ),
    [progress.answered, progress.total, filledInBatch]
  )

  const submitBatch = useCallback(async () => {
    if (!sessionId || !batch.length) return
    setError(null)
    for (const it of batch) {
      const v = batchAnswers[String(it.qid)]
      if (v === undefined || v === '' || v === null) {
        setError(`Vui lòng trả lời đủ ${batch.length} mục (thiếu mục ${it.qid}).`)
        return
      }
      if (quizType === 'holland') {
        const n = Number(v)
        if (!Number.isInteger(n) || n < 1 || n > 5) {
          setError(`Mục ${it.qid}: chọn điểm từ 1 đến 5.`)
          return
        }
      } else {
        const c = String(v).toUpperCase()
        if (c !== 'A' && c !== 'B') {
          setError(`Mục ${it.qid}: chọn A hoặc B.`)
          return
        }
      }
    }
    setLoading(true)
    try {
      const answers = batch.map((it) => ({
        qid: it.qid,
        answer:
          quizType === 'holland'
            ? Number(batchAnswers[String(it.qid)])
            : String(batchAnswers[String(it.qid)]).toUpperCase(),
      }))
      const data = await postQuizJson('/module_2/quiz/answers_batch', {
        session_id: sessionId,
        answers,
      })
      onAfterSubmit?.()
      if (data.completed) {
        const sid = sessionId
        dispatch(setQuizSessionId(sid))
        if (autoFollowupSent.current !== sid) {
          autoFollowupSent.current = sid
          dispatch(
            sendMessage({
              message: '',
              conversationId,
              quizSessionId: sid,
              quizSummarySilent: true,
              omitUserBubble: true,
              sessionPreview: QUIZ_DONE_SESSION_PREVIEW,
            })
          )
        }
      } else {
        const nextBatch = Array.isArray(data.batch) ? data.batch : []
        const intro =
          quizType === 'holland'
            ? `**Lượt tiếp theo** (${data.progress?.answered ?? 0}/${data.progress?.total ?? '—'}) — chọn đủ điểm rồi bấm **Gửi**.`
            : `**Lượt tiếp theo** (${data.progress?.answered ?? 0}/${data.progress?.total ?? '—'}) — chọn A hoặc B rồi bấm **Gửi**.`
        dispatch(
          addMessage({
            role: 'assistant',
            content: intro,
            streaming: false,
            citations: [],
            timestamp: new Date().toISOString(),
            interactive: {
              kind: 'module2_quiz_batch',
              quiz_type: quizType,
              session_id: sessionId,
              batch: nextBatch,
              progress: data.progress || { answered: 0, total: 0 },
            },
          })
        )
      }
    } catch (e) {
      setError(e?.message || 'Gửi lượt trả lời thất bại')
    } finally {
      setLoading(false)
    }
  }, [
    sessionId,
    batch,
    batchAnswers,
    quizType,
    dispatch,
    conversationId,
    onAfterSubmit,
  ])

  if (!payload || payload.kind !== 'module2_quiz_batch' || !batch.length) {
    return null
  }

  const theme = quizType === 'mbti' ? 'mbti' : 'holland'
  const totalQ = progress.total || 0
  const answeredSoFar = totalQ
    ? Math.min(totalQ, (progress.answered || 0) + filledInBatch)
    : (progress.answered || 0) + filledInBatch
  const countLabel = totalQ
    ? `${answeredSoFar}/${totalQ} câu trong lượt`
    : `${answeredSoFar}/${batch.length} câu trong lượt`

  return (
    <div
      className={`module2-quiz module2-inline-quiz module2-quiz--${theme}`}
      aria-label="Trắc nghiệm nhúng trong chat"
    >
      <div className="module2-quiz__active">
        <div className="module2-quiz__progress-block">
          <div className="module2-quiz__progress-top">
            <span className="module2-quiz__progress-label">
              <span className="module2-quiz__pill">
                {quizType === 'holland' ? 'Holland' : 'MBTI'} · {countLabel}
              </span>
            </span>
            <span className="module2-quiz__progress-pct">{pct}%</span>
          </div>
          <div
            className="module2-quiz__progress-track"
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div className="module2-quiz__progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <p className="module2-quiz__cheer">{cheer}</p>
        </div>

        <Module2QuizBatchStep
          batch={batch}
          quizType={quizType}
          batchAnswers={batchAnswers}
          setAnswer={setAnswer}
          loading={loading}
          progress={progress}
        />

        <div className="module2-quiz__batch-actions">
          <button
            type="button"
            className="module2-quiz__batch-submit"
            disabled={loading || filledInBatch < batch.length}
            onClick={() => submitBatch()}
          >
            {loading ? (
              <>
                <Loader2 className="module2-quiz__spin" size={18} aria-hidden />
                Đang gửi…
              </>
            ) : (
              'Gửi'
            )}
          </button>
        </div>
      </div>

      {error ? (
        <p className="module2-quiz__err" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}
