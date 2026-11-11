import { API_URL, fetchApi as fetch } from '../api/client'
import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Compass, Sparkles, CheckCircle2, Loader2 } from 'lucide-react'
import { sendMessage, setQuizSessionId, clearQuizSessionId, clearChat } from '../store/slices/chatSlice'
import Module2QuizBatchStep from './Module2QuizBatchStep'
/** Banner hub module 2 — nguồn: docs/image_module_2_banner.png */
const module2HubBanner = '/docs/image_module_2_banner.png'
/** Nền minh họa đáy — docs/image_banner_uel.png */
const uelBottomBannerUrl = '/docs/image_banner_uel.png'
import './Module2QuizPanel.css'



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

/** Tiêu đề ngắn trong danh sách hội thoại (sidebar). */
const QUIZ_DONE_SESSION_PREVIEW = 'Gợi ý ngành từ trắc nghiệm'

function formatDoneSummary(quizType, summary) {
  if (!summary) return 'Đã hoàn thành.'
  if (quizType === 'holland' && summary.holland?.top1) {
    const t = summary.holland.top1
    return `Tổng điểm cao nhất hiện tại: nhóm ${t[0]} (${Number(t[1]).toFixed(1)} điểm).`
  }
  if (quizType === 'mbti' && summary.mbti?.four_letter) {
    return `Khuynh hướng 4 chữ (theo đếm lựa chọn A/B): ${summary.mbti.four_letter}.`
  }
  return 'Đã hoàn thành.'
}

/** Chỉ trắc nghiệm Holland / MBTI — chat hiện khi không đang trả lời lượt câu hỏi. */
export default function Module2QuizPanel({ onChatVisibleChange }) {
  const dispatch = useDispatch()
  const conversationId = useSelector((state) => state.chat?.conversationId ?? null)
  /** Tránh gửi trùng một phiên (vd. Strict Mode / double submit) */
  const autoFollowupSentForSid = useRef(null)
  /** Đánh dấu đã thêm 1 history layer cho phiên quiz active/done. */
  const hasPushedHistoryRef = useRef(false)
  const [phase, setPhase] = useState('idle')
  const [sessionId, setSessionId] = useState(null)
  const [quizType, setQuizType] = useState(null)
  /** Theo lượt từ API (mặc định một lượt = toàn bộ câu còn lại trong phiên) */
  const [batch, setBatch] = useState([])
  /** qid (string) -> điểm 1–5 (Holland) hoặc 'A'|'B' (MBTI) */
  const [batchAnswers, setBatchAnswers] = useState({})
  const [progress, setProgress] = useState({ answered: 0, total: 0 })
  const [doneSummary, setDoneSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  /** Holland / MBTI — đang gọi API start cho ô nào (hiện spinner trên ô). */
  const [startingKind, setStartingKind] = useState(null)

  const filledInBatch = useMemo(() => {
    if (!batch.length) return 0
    return batch.filter((it) => {
      const v = batchAnswers[String(it.qid)]
      return v !== undefined && v !== '' && v !== null
    }).length
  }, [batch, batchAnswers])

  const pct = useMemo(() => {
    const { answered, total } = progress
    if (!total) return 0
    const est = Math.min(total, answered + filledInBatch)
    return Math.min(100, Math.round((est / total) * 100))
  }, [progress, filledInBatch])

  /** Đã chọn trong lượt hiện tại + đã gửi trước đó (vd. 2/54). */
  const answeredInSessionDisplay = useMemo(() => {
    const { answered, total } = progress
    const cur = (answered || 0) + filledInBatch
    if (total) return Math.min(total, cur)
    return cur
  }, [progress.answered, progress.total, filledInBatch])

  const setAnswer = useCallback((qid, val) => {
    setBatchAnswers((prev) => ({ ...prev, [String(qid)]: val }))
  }, [])

  const chatVisible = phase !== 'active'

  useEffect(() => {
    onChatVisibleChange?.(chatVisible)
    return () => {
      onChatVisibleChange?.(true)
    }
  }, [chatVisible, onChatVisibleChange])

  const resetQuizOnly = useCallback(() => {
    setPhase('idle')
    setSessionId(null)
    setQuizType(null)
    setBatch([])
    setBatchAnswers({})
    setProgress({ answered: 0, total: 0 })
    setDoneSummary(null)
    setError(null)
    setStartingKind(null)
    autoFollowupSentForSid.current = null
    dispatch(clearQuizSessionId())
  }, [dispatch])

  /**
   * Khi đang ở trong flow quiz (active/done), thêm 1 history entry cùng URL:
   * Back đầu tiên sẽ quay về hub module_2 thay vì thoát sang trang trước đó.
   */
  useEffect(() => {
    const inQuizFlow = phase === 'active' || phase === 'done'
    if (inQuizFlow && !hasPushedHistoryRef.current) {
      window.history.pushState({ ...(window.history.state || {}), m2QuizFlow: true }, '')
      hasPushedHistoryRef.current = true
    }
    if (!inQuizFlow) {
      hasPushedHistoryRef.current = false
    }
  }, [phase])

  /** Browser Back khi đang làm quiz: ưu tiên trở về hub Khám phá tính cách. */
  useEffect(() => {
    const onPopState = () => {
      if (phase === 'active' || phase === 'done') {
        resetQuizOnly()
      }
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [phase, resetQuizOnly])

  /** Click lại menu Khám phá tính cách: reset flow + dọn thread module_2. */
  useEffect(() => {
    const onSidebarReselect = (ev) => {
      if (ev?.detail?.key !== 'personality') return
      resetQuizOnly()
      dispatch(clearChat())
    }
    window.addEventListener('uel:sidebar-reselect', onSidebarReselect)
    return () => window.removeEventListener('uel:sidebar-reselect', onSidebarReselect)
  }, [dispatch, resetQuizOnly])

  const exitQuizFlow = useCallback(() => {
    resetQuizOnly()
  }, [resetQuizOnly])

  const start = async (type) => {
    setError(null)
    setStartingKind(type)
    setLoading(true)
    try {
      const data = await postQuizJson('/module_2/quiz/start', { quiz_type: type })
      setSessionId(data.session_id)
      setQuizType(data.quiz_type)
      setBatch(Array.isArray(data.batch) ? data.batch : [])
      setBatchAnswers({})
      setProgress({
        answered: 0,
        total: data.total_questions || 0,
      })
      setPhase('active')
      dispatch(clearQuizSessionId())
    } catch (e) {
      setError(e?.message || 'Không khởi tạo được phiên trắc nghiệm')
    } finally {
      setLoading(false)
      setStartingKind(null)
    }
  }

  const submitBatch = useCallback(async () => {
    if (!sessionId || !batch.length) return
    setError(null)
    for (const it of batch) {
      const v = batchAnswers[String(it.qid)]
      if (v === undefined || v === '' || v === null) {
        setError(`Vui lòng trả lời đủ ${batch.length} câu trong lượt này (đang thiếu mục ${it.qid}).`)
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
        answer: quizType === 'holland' ? Number(batchAnswers[String(it.qid)]) : String(batchAnswers[String(it.qid)]).toUpperCase(),
      }))
      const data = await postQuizJson('/module_2/quiz/answers_batch', {
        session_id: sessionId,
        answers,
      })
      setProgress({
        answered: data.progress?.answered ?? 0,
        total: data.progress?.total ?? 0,
      })
      setBatchAnswers({})
      if (data.completed) {
        setPhase('done')
        setBatch([])
        const sum = data.summary || null
        setDoneSummary(sum)
        const sid = sessionId
        dispatch(setQuizSessionId(sid))
        if (autoFollowupSentForSid.current !== sid) {
          autoFollowupSentForSid.current = sid
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
        setBatch(Array.isArray(data.batch) ? data.batch : [])
      }
    } catch (e) {
      setError(e?.message || 'Gửi lượt trả lời thất bại')
    } finally {
      setLoading(false)
    }
  }, [sessionId, batch, batchAnswers, quizType, dispatch, conversationId])

  const themeClass =
    phase === 'idle' ? 'module2-quiz--idle' : quizType ? `module2-quiz--${quizType}` : 'module2-quiz--idle'

  return (
    <section className={`module2-quiz ${themeClass}`} aria-label="Trắc nghiệm Holland & MBTI">
      <div
        className={`module2-quiz__quiz-top${phase === 'idle' ? ' module2-quiz__quiz-top--centered' : ''}${
          phase === 'active' ? ' module2-quiz__quiz-top--active' : ''
        }`}
      >
        {(phase === 'active' || phase === 'done') && (
          <nav className="module2-quiz__quiz-nav" aria-label="Điều hướng trắc nghiệm">
            <button type="button" className="module2-quiz__nav-pill" onClick={exitQuizFlow}>
              ← Chọn lại bài
            </button>
          </nav>
        )}
        {phase === 'active' && (quizType === 'holland' || quizType === 'mbti') && (
          <div className="module2-quiz__active-title-block">
            <h2 className="module2-quiz__active-title">
              {quizType === 'holland' ? 'Holland' : 'MBTI'}
            </h2>
          </div>
        )}
        {phase === 'done' && (
          <p className="module2-quiz__quiz-hint">
            Xem tóm tắt bên dưới. Dùng «Làm lại từ đầu» hoặc «Chọn lại bài» để làm bài khác.
          </p>
        )}
      </div>

      {phase === 'idle' && (
        <div className="module2-quiz__idle module2-quiz__idle--hub">
          <h1 className="module2-quiz__hub-title">Khám phá tính cách</h1>
          <p className="module2-quiz__hub-sub">Tra cứu nhóm tính cách và gợi ý nghề nghiệp</p>
          <div className="module2-quiz__hub-banner" aria-hidden="true">
            <img
              className="module2-quiz__hub-banner-img"
              src={module2HubBanner}
              alt=""
              width={707}
              height={224}
              loading="lazy"
              decoding="async"
            />
          </div>
          <div className="module2-quiz__hub-grid">
            <button
              type="button"
              className="module2-quiz__hub-card module2-quiz__hub-card--holland"
              disabled={loading}
              onClick={() => start('holland')}
              aria-busy={startingKind === 'holland'}
            >
              <span className="module2-quiz__hub-card-icon" aria-hidden>
                {startingKind === 'holland' ? (
                  <Loader2 className="module2-quiz__spin" size={48} strokeWidth={2} />
                ) : (
                  <Compass size={48} strokeWidth={1.85} />
                )}
              </span>
              <span className="module2-quiz__hub-card-label">Holland</span>
              <span className="module2-quiz__hub-card-sub">Tìm môi trường nghề nghiệp phù hợp với tính cách</span>
            </button>
            <button
              type="button"
              className="module2-quiz__hub-card module2-quiz__hub-card--mbti"
              disabled={loading}
              onClick={() => start('mbti')}
              aria-busy={startingKind === 'mbti'}
            >
              <span className="module2-quiz__hub-card-icon" aria-hidden>
                {startingKind === 'mbti' ? (
                  <Loader2 className="module2-quiz__spin" size={48} strokeWidth={2} />
                ) : (
                  <Sparkles size={48} strokeWidth={1.85} />
                )}
              </span>
              <span className="module2-quiz__hub-card-label">MBTI</span>
              <span className="module2-quiz__hub-card-sub">Hiểu bản thân để định hướng nghề nghiệp</span>
            </button>
          </div>
        </div>
      )}

      {phase === 'active' && batch.length > 0 && (
        <div className="module2-quiz__active">
          <div className="module2-quiz__progress-block">
            <div className="module2-quiz__progress-top">
              <span className="module2-quiz__progress-label">
                <span className="module2-quiz__pill">
                  {progress.total
                    ? `${answeredInSessionDisplay}/${progress.total} câu trong lượt`
                    : `${answeredInSessionDisplay}/${batch.length} câu trong lượt`}
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
              aria-label="Tiến độ phiên trắc nghiệm"
            >
              <div className="module2-quiz__progress-fill" style={{ width: `${pct}%` }} />
            </div>
          </div>

          <Module2QuizBatchStep
            batch={batch}
            quizType={quizType}
            batchAnswers={batchAnswers}
            setAnswer={setAnswer}
            loading={loading}
            progress={progress}
            compactBatchUi
          />

          <div className="module2-quiz__batch-actions module2-quiz__batch-actions--pair">
            <button
              type="button"
              className="module2-quiz__batch-secondary"
              disabled={loading}
              onClick={() => {
                resetQuizOnly()
              }}
            >
              Làm lại
            </button>
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
      )}

      {phase === 'done' && (
        <div className="module2-quiz__done" role="status">
          <div className="module2-quiz__done-icon" aria-hidden>
            <CheckCircle2 size={40} strokeWidth={1.75} />
          </div>
          <p className="module2-quiz__done-lead">Hoàn thành xuất sắc</p>
          <p className="module2-quiz__done-text">{formatDoneSummary(quizType, doneSummary)}</p>
          <p className="module2-quiz__done-meta">Phần tư vấn tiếp theo hiển thị ở hội thoại bên dưới.</p>
        </div>
      )}

      {error && (
        <p className="module2-quiz__err" role="alert">
          {error}
        </p>
      )}

      {phase === 'done' && (
        <div className="module2-quiz__footer">
          <button
            type="button"
            className="module2-quiz__link"
            disabled={loading}
            onClick={() => {
              resetQuizOnly()
            }}
          >
            Làm lại từ đầu
          </button>
        </div>
      )}

      <div className="module2-quiz__uel-banner" aria-hidden="true">
        <img
          className="module2-quiz__uel-banner-img"
          src={uelBottomBannerUrl}
          alt=""
          width={1200}
          height={280}
          decoding="async"
        />
      </div>
    </section>
  )
}
