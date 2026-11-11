import { useState, useEffect, useCallback, useMemo } from 'react'

const HOLLAND_SCALE = [
  { n: 1, short: 'Rất không đúng' },
  { n: 2, short: 'Ít đúng' },
  { n: 3, short: 'Trung bình' },
  { n: 4, short: 'Khá đúng' },
  { n: 5, short: 'Rất đúng' },
]

function isFilled(batchAnswers, qid) {
  const v = batchAnswers[String(qid)]
  return v !== undefined && v !== '' && v !== null
}

/**
 * Một câu mỗi màn: chấm điểm / chọn A·B → tự chuyển câu sau (có thể tắt bằng autoAdvance).
 */
export default function Module2QuizBatchStep({
  batch,
  quizType,
  batchAnswers,
  setAnswer,
  loading,
  progress,
  autoAdvance = true,
  /** Holland/MBTI: ẩn gợi ý dài + dòng Câu x/n; chỉ chuyển câu bằng chấm số */
  compactBatchUi = false,
}) {
  const [step, setStep] = useState(0)

  useEffect(() => {
    setStep(0)
  }, [batch])

  const n = batch.length
  const safeStep = n ? Math.min(step, n - 1) : 0
  const item = batch[safeStep]

  const afterPick = useCallback(() => {
    if (!autoAdvance || n <= 1) return
    setStep((s) => (s < n - 1 ? s + 1 : s))
  }, [autoAdvance, n])

  const filledInBatch = useMemo(() => {
    if (!batch.length) return 0
    return batch.filter((it) => isFilled(batchAnswers, it.qid)).length
  }, [batch, batchAnswers])

  const sessionTotal = progress?.total

  if (!item || !n) return null

  return (
    <div className="module2-quiz__batch">
      {!compactBatchUi && (
        <p className="module2-quiz__batch-hint">
          {quizType === 'holland'
            ? 'Chọn điểm 1–5; sau khi chọn sẽ chuyển sang câu tiếp (hoặc bấm chấm số bên dưới).'
            : 'Chọn A hoặc B; sau khi chọn sẽ chuyển sang câu tiếp (hoặc bấm chấm số bên dưới).'}{' '}
          <strong>
            Đã chọn {filledInBatch}/{n}
            {sessionTotal ? ` · tổng câu trong phiên: ${sessionTotal}` : ''}
          </strong>
        </p>
      )}

      {!compactBatchUi && (
        <div className="module2-quiz__step-toolbar" aria-live="polite">
          <span className="module2-quiz__step-count">
            Câu {safeStep + 1}/{n} trong lượt
          </span>
          <span className="module2-quiz__step-filled">
            {filledInBatch}/{n} đã chọn
          </span>
        </div>
      )}

      <div className="module2-quiz__step-dots" role="tablist" aria-label="Chuyển nhanh giữa các mục trong lượt">
        {batch.map((it, i) => {
          const done = isFilled(batchAnswers, it.qid)
          const current = i === safeStep
          return (
            <button
              key={it.qid}
              type="button"
              className={`module2-quiz__step-dot${current ? ' module2-quiz__step-dot--current' : ''}${done ? ' module2-quiz__step-dot--done' : ''}`}
              disabled={loading}
              onClick={() => setStep(i)}
              aria-label={`Mục ${it.qid}${done ? ', đã chọn' : ', chưa chọn'}`}
              aria-current={current ? 'step' : undefined}
            >
              {i + 1}
            </button>
          )
        })}
      </div>

      <div className="module2-quiz__batch-row module2-quiz__batch-row--step">
        <div className="module2-quiz__step-body">
          <div className="module2-quiz__batch-row-head">
            <span className="module2-quiz__qid">Mục {item.qid}</span>
            {item.group ? <span className="module2-quiz__pill">Nhóm {item.group}</span> : null}
          </div>
          <div className="module2-quiz__question-focus" role="region" aria-label="Nội dung câu hỏi">
            <div className="module2-quiz__q-scroll module2-quiz__q-scroll--focus">
              <p className="module2-quiz__batch-qtext">{item.text}</p>
            </div>
          </div>
          {quizType === 'holland' && (
            <div
              className="module2-quiz__holland-scores"
              role="group"
              aria-label={`Chấm điểm mục ${item.qid}`}
            >
              <span className="module2-quiz__batch-field-label">Điểm</span>
              <div className="module2-quiz__score-btns">
                {HOLLAND_SCALE.map(({ n: nv, short }) => {
                  const picked = batchAnswers[String(item.qid)] === nv
                  return (
                    <button
                      key={nv}
                      type="button"
                      disabled={loading}
                      className={`module2-quiz__score-btn${picked ? ' module2-quiz__score-btn--picked' : ''}`}
                      title={`${nv} — ${short}`}
                      aria-pressed={picked}
                      onClick={() => {
                        setAnswer(item.qid, nv)
                        afterPick()
                      }}
                    >
                      {nv}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
          {quizType === 'mbti' && item.choices && (
            <div className="module2-quiz__batch-ab">
              <button
                type="button"
                className={`module2-quiz__mbti-choice module2-quiz__mbti-choice--a${
                  batchAnswers[String(item.qid)] === 'A' ? ' module2-quiz__mbti-choice--picked' : ''
                }`}
                disabled={loading}
                onClick={() => {
                  setAnswer(item.qid, 'A')
                  afterPick()
                }}
              >
                <span className="module2-quiz__mbti-badge">A</span>
                <span className="module2-quiz__mbti-choice-text">{item.choices.A}</span>
              </button>
              <button
                type="button"
                className={`module2-quiz__mbti-choice module2-quiz__mbti-choice--b${
                  batchAnswers[String(item.qid)] === 'B' ? ' module2-quiz__mbti-choice--picked' : ''
                }`}
                disabled={loading}
                onClick={() => {
                  setAnswer(item.qid, 'B')
                  afterPick()
                }}
              >
                <span className="module2-quiz__mbti-badge">B</span>
                <span className="module2-quiz__mbti-choice-text">{item.choices.B}</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
