import { useEffect, useMemo, useRef, useState } from 'react'
import { API_URL, fetchApi } from '../api/client'
import { consumeChatSse } from '../utils/sse'

const SLOTS = [
  { key: 'file_01', label: 'Phạm vi bot được trả lời', hint: 'File Excel 01 — ô Tên Mô-đun phải trùng mảng đã chọn' },
  { key: 'file_02', label: 'Câu hỏi thường gặp', hint: 'File Excel 02' },
  { key: 'file_03', label: 'Tài liệu nghiệp vụ', hint: 'File Excel 03' },
  { key: 'file_04', label: 'Mốc thời gian', hint: 'File Excel 04 — thiếu ngày vẫn nạp được, bot nói theo cột Nội dung' },
  { key: 'file_05', label: 'Bài giới thiệu', hint: 'File Excel 05 — để trống cũng được' },
]

const FILE_LABEL = {
  '01': 'Phạm vi bot được trả lời',
  '02': 'Câu hỏi thường gặp',
  '03': 'Tài liệu nghiệp vụ',
  '04': 'Mốc thời gian',
  '05': 'Bài giới thiệu',
}

function detailText(payload) {
  const d = payload?.detail ?? payload
  if (!d) return ''
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((e) => e.msg || String(e)).join('\n')
  if (Array.isArray(d.errors)) return d.errors.join('\n')
  return JSON.stringify(d)
}

function unpackDetail(payload) {
  if (!payload) return null
  if (payload.issues || payload.errors || payload.warnings) return payload
  if (payload.detail && typeof payload.detail === 'object') return payload.detail
  return null
}

function IssuePanel({ report, title }) {
  if (!report) return null
  const issues = Array.isArray(report.issues) ? report.issues : []
  const errors = issues.filter((i) => i.level === 'ERROR')
  const warnings = issues.filter((i) => i.level === 'WARNING')
  const fallbackErrors = errors.length ? [] : report.errors || []
  const fallbackWarnings = warnings.length ? [] : report.warnings || []
  if (!errors.length && !warnings.length && !fallbackErrors.length && !fallbackWarnings.length) return null

  const groups = new Map()
  ;[...errors, ...warnings].forEach((item) => {
    const key = item.file || '00'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(item)
  })

  return (
    <section className="admin-card">
      <h2>{title}</h2>
      {errors.length || fallbackErrors.length ? (
        <p className="admin-alert admin-alert--error" role="alert">
          {errors.length || fallbackErrors.length} mục chặn nạp — sửa trên Excel rồi chọn lại file.
        </p>
      ) : (
        <p className="admin-alert admin-alert--ok" role="status">
          Có thể nạp. Hệ thống đã chuẩn hóa các ô gần đúng; các mục bên dưới chỉ là lưu ý.
        </p>
      )}
      {fallbackErrors.map((msg) => (
        <div key={msg} className="admin-issue admin-issue--error">
          {msg}
        </div>
      ))}
      {[...groups.entries()].map(([file, rows]) => (
        <div key={file}>
          <p className="admin-issue-file">{FILE_LABEL[file] || `File ${file}`}</p>
          {rows.map((item, idx) => (
            <div
              key={`${file}-${idx}-${item.ref || item.message}`}
              className={`admin-issue ${item.level === 'ERROR' ? 'admin-issue--error' : ''}`}
            >
              {item.ref ? <strong>{item.ref}. </strong> : null}
              {item.message}
              {item.raw && item.mapped ? (
                <p className="admin-map">
                  File ghi «{item.raw}» → dùng «{item.mapped}»
                </p>
              ) : null}
            </div>
          ))}
        </div>
      ))}
      {fallbackWarnings.map((msg) => (
        <p key={msg} className="admin-warn">
          {msg}
        </p>
      ))}
      {report.choices?.audience?.length ? (
        <>
          <p className="admin-issue-file">Danh sách đối tượng chuẩn (sheet _DS)</p>
          <div className="admin-choices">
            {report.choices.audience.map((item) => (
              <span key={item} className="admin-chip">
                {item}
              </span>
            ))}
          </div>
        </>
      ) : null}
    </section>
  )
}

const PROGRESS_STEPS = [
  { id: 'parse', label: 'Đọc và đối chiếu Excel', from: 0 },
  { id: 'store', label: 'Lưu vào kho dữ liệu', from: 16 },
  { id: 'embed_rules', label: 'Gắn chủ đề vào bot', from: 28 },
  { id: 'embed_docs', label: 'Gắn FAQ, tài liệu, mốc thời gian', from: 52 },
  { id: 'activate', label: 'Đưa bản mới cho người học', from: 94 },
]

function ProgressOverlay({ name, progress }) {
  const pct = Math.max(2, Math.min(100, Number(progress?.pct) || 2))
  return (
    <div className="admin-progress" role="status" aria-live="polite">
      <div className="admin-progress-card">
        <h2>Đang đưa dữ liệu vào bot</h2>
        <p>
          Mảng «{name || 'đang chọn'}». Việc này có thể mất vài phút — không đóng trang.
        </p>
        <div className="admin-progress-bar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
          <span style={{ width: `${pct}%` }} />
        </div>
        <p className="admin-progress-msg">{progress?.message || 'Đang bắt đầu…'}</p>
        <ol className="admin-progress-steps">
          {PROGRESS_STEPS.map((step, index) => {
            const currentIndex = PROGRESS_STEPS.findIndex((s) => s.id === progress?.step)
            const current = step.id === progress?.step
            const done = currentIndex >= 0 && index < currentIndex
            return (
              <li key={step.id} className={current ? 'is-current' : done ? 'is-done' : ''}>
                {step.label}
              </li>
            )
          })}
        </ol>
      </div>
    </div>
  )
}

export default function AdminIngestPage() {
  const [modules, setModules] = useState([])
  const [moduleCode, setModuleCode] = useState('')
  const [files, setFiles] = useState({})
  const [newName, setNewName] = useState('')
  const [busy, setBusy] = useState(false)
  const [checking, setChecking] = useState(false)
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [result, setResult] = useState(null)
  const [preview, setPreview] = useState(null)
  const [progress, setProgress] = useState(null)
  const checkSeq = useRef(0)

  function applyModules(list, prefer) {
    setModules(list)
    setModuleCode((prev) => prefer || prev || list[0]?.code || '')
  }

  useEffect(() => {
    let alive = true
    fetchApi(`${API_URL}/admin/status`)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}))
        if (!res.ok) throw new Error(detailText(body) || 'Không tải được danh sách mảng hỗ trợ')
        if (!alive) return
        applyModules(body.modules || [])
      })
      .catch((err) => {
        if (alive) setError(err.message || 'Không tải được danh sách mảng hỗ trợ')
      })
    return () => {
      alive = false
    }
  }, [])

  const selected = useMemo(
    () => modules.find((m) => m.code === moduleCode) || null,
    [modules, moduleCode]
  )
  const ready = Boolean(moduleCode) && SLOTS.every((s) => files[s.key] instanceof File)
  const fileStamp = SLOTS.map((s) => files[s.key]?.name || '').join('|')

  function packForm() {
    const body = new FormData()
    body.set('module_code', moduleCode)
    SLOTS.forEach((s) => body.set(s.key, files[s.key]))
    return body
  }

  async function runCheck() {
    if (!ready) return
    const seq = ++checkSeq.current
    setChecking(true)
    try {
      const res = await fetchApi(`${API_URL}/admin/ingest/check`, { method: 'POST', body: packForm() })
      const payload = await res.json().catch(() => ({}))
      if (seq !== checkSeq.current) return
      const report = unpackDetail(payload)
      if (!res.ok) throw new Error(detailText(payload) || 'Không kiểm tra được file')
      setPreview(report)
      setError('')
    } catch (err) {
      if (seq !== checkSeq.current) return
      setError(err.message || 'Không kiểm tra được file')
    } finally {
      if (seq === checkSeq.current) setChecking(false)
    }
  }

  useEffect(() => {
    if (!ready) {
      setPreview(null)
      return undefined
    }
    const timer = setTimeout(() => {
      runCheck()
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- recheck when the five files or module change
  }, [ready, moduleCode, fileStamp])

  function selectModule(code) {
    if (code === moduleCode) return
    setModuleCode(code)
    setFiles({})
    setPreview(null)
    setResult(null)
    setError('')
    setOk('')
  }

  function onPick(key, file) {
    setResult(null)
    setError('')
    setOk('')
    setFiles((prev) => ({ ...prev, [key]: file || undefined }))
  }

  async function onAddModule(e) {
    e.preventDefault()
    const name = newName.trim()
    if (!name || adding) return
    setAdding(true)
    setError('')
    setOk('')
    try {
      const res = await fetchApi(`${API_URL}/admin/modules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(detailText(body) || 'Không thêm được mảng hỗ trợ')
      applyModules(body.modules || [], body.module?.code)
      setNewName('')
      const folder = body.module?.folder
      const yamlFile = body.module?.yaml
      const bits = [`Đã tạo mảng «${body.module.name}».`]
      if (folder) bits.push(`Kho dữ liệu: chatbot-data/${folder}.`)
      if (yamlFile) bits.push(`Đã ghi ${yamlFile} và modules.yaml.`)
      bits.push("Chọn đủ 5 file rồi bấm Cập nhật dữ liệu.")
      setOk(bits.join(" "))
    } catch (err) {
      setError(err.message || 'Không thêm được mảng hỗ trợ')
    } finally {
      setAdding(false)
    }
  }

  async function onSubmit(e) {
    e.preventDefault()
    if (!ready || busy) return
    setBusy(true)
    setError('')
    setResult(null)
    setProgress({ step: 'parse', pct: 2, message: 'Bắt đầu cập nhật dữ liệu…' })
    try {
      const res = await fetchApi(`${API_URL}/admin/ingest/stream`, { method: 'POST', body: packForm() })
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}))
        setPreview(unpackDetail(payload))
        const n = unpackDetail(payload)?.errors?.length
        throw new Error(
          n ? `${n} mục chặn nạp — xem danh sách bên dưới.` : detailText(payload) || `Cập nhật không thành công (${res.status})`
        )
      }
      if (!res.body) throw new Error('Trình duyệt không hỗ trợ theo dõi tiến trình')
      let donePayload = null
      let errorPayload = null
      await consumeChatSse(res.body.getReader(), (ev) => {
        if (ev.type === 'progress') setProgress(ev)
        if (ev.type === 'done') donePayload = ev
        if (ev.type === 'error') errorPayload = ev
      })
      if (errorPayload) {
        const detail = unpackDetail(errorPayload.detail) || errorPayload
        setPreview(detail)
        const n = detail?.errors?.length
        throw new Error(n ? `${n} mục chặn nạp — xem danh sách bên dưới.` : detailText(errorPayload) || 'Cập nhật không thành công')
      }
      if (!donePayload) throw new Error('Mất kết nối khi đang cập nhật. Kiểm tra lại trạng thái mảng.')
      setResult(donePayload)
      setPreview(donePayload)
      setModules((prev) =>
        prev.map((m) =>
          m.code === donePayload.module_code
            ? {
                ...m,
                release_id: donePayload.release_id,
                warnings: donePayload.warnings || [],
                counts: donePayload.counts || m.counts,
              }
            : m
        )
      )
    } catch (err) {
      setError(err.message || 'Cập nhật không thành công')
    } finally {
      setBusy(false)
      setProgress(null)
    }
  }

  return (
    <>
      {busy ? <ProgressOverlay name={selected?.name} progress={progress} /> : null}
      <h1>Cập nhật dữ liệu phòng</h1>
      <p className="admin-lead">
        Mỗi phòng một trang quản lý này. Thêm từng mảng hỗ trợ (Khảo thí, Học phí, …), mỗi mảng một bộ 5 Excel.
        Hệ thống tự chuẩn hóa đối tượng gần đúng; mốc thiếu ngày vẫn nạp. Chỉ chặn khi thiếu sheet, trùng mã, hoặc phạm vi trả lời sai.
      </p>
      {error ? (
        <p className="admin-alert admin-alert--error" role="alert">
          {error}
        </p>
      ) : null}
      {ok ? (
        <p className="admin-alert admin-alert--ok" role="status">
          {ok}
        </p>
      ) : null}

      <form className="admin-card" onSubmit={onAddModule}>
        <h2>Thêm mảng hỗ trợ</h2>
        <p className="admin-hint">
          Tên gõ ở đây phải trùng ô <strong>Tên Mô-đun</strong> trên file Excel phạm vi trả lời.
          Sau khi thêm, chọn 5 file của mảng đó rồi cập nhật.
        </p>
        <div className="admin-inline">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Ví dụ: Học phí, Công tác sinh viên"
          />
          <button className="admin-btn" type="submit" disabled={adding || !newName.trim()}>
            {adding ? 'Đang thêm…' : 'Thêm mảng'}
          </button>
        </div>
      </form>

      <section className="admin-card">
        <h2>Mảng hỗ trợ của phòng ({modules.length})</h2>
        <p className="admin-hint">
          Chọn một mảng bên dưới rồi đưa 5 file của đúng mảng đó. Người hỏi sẽ thấy từng mảng trên thanh bên trái.
        </p>
        {modules.length === 0 ? (
          <p className="admin-hint">Chưa có mảng. Thêm mảng ở form trên.</p>
        ) : (
          <div className="admin-mod-grid">
            {modules.map((m) => {
              const counts = m.counts || {}
              const hasData = Boolean(m.release_id)
              return (
                <button
                  key={m.code}
                  type="button"
                  className={`admin-mod-card${m.code === moduleCode ? ' is-selected' : ''}${hasData ? '' : ' is-empty'}`}
                  onClick={() => selectModule(m.code)}
                >
                  <strong>{m.name}</strong>
                  <span className="admin-mod-meta">{hasData ? 'Đã có dữ liệu trên bot' : 'Chưa nạp Excel'}</span>
                  <span className="admin-mod-meta">
                    {counts.rules || 0} chủ đề · {counts.faqs || 0} câu hỏi · {counts.milestones || 0} mốc
                  </span>
                </button>
              )
            })}
          </div>
        )}
      </section>

      <form className="admin-card" onSubmit={onSubmit}>
        <h2>Đưa file Excel vào «{selected?.name || 'mảng đã chọn'}»</h2>
        {selected?.release_id ? (
          <p className="admin-hint">Đang dùng bản cập nhật gần nhất: {selected.release_id}</p>
        ) : (
          <p className="admin-hint">Mảng này chưa có dữ liệu. Hãy chọn đủ 5 file rồi cập nhật.</p>
        )}
        {SLOTS.map((slot) => (
          <label key={slot.key} className="admin-file-row">
            <span>
              {slot.label}
              <small className="admin-hint">{slot.hint}</small>
            </span>
            <input
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(e) => onPick(slot.key, e.target.files?.[0])}
            />
            <span className="admin-file-name">
              {files[slot.key] ? files[slot.key].name : 'Chưa chọn file'}
            </span>
          </label>
        ))}
        <div className="admin-actions">
          <button className="admin-btn admin-btn-ghost" type="button" disabled={!ready || checking} onClick={runCheck}>
            {checking ? 'Đang đối chiếu…' : 'Kiểm tra file'}
          </button>
          <button className="admin-btn" type="submit" disabled={!ready || busy || (preview && preview.ok === false)}>
            {busy ? 'Đang xử lý, vui lòng đợi vài phút…' : 'Cập nhật dữ liệu'}
          </button>
        </div>
      </form>
      {checking && !preview ? <p className="admin-hint">Đang đối chiếu 5 file với danh sách chuẩn…</p> : null}
      <IssuePanel
        report={preview}
        title={result ? 'Đã chuẩn hóa khi nạp' : preview?.ok === false ? 'Cần sửa trước khi nạp' : 'Kết quả đối chiếu'}
      />
      {result ? (
        <section className="admin-card">
          <h2>Đã cập nhật xong</h2>
          <p>Người học sẽ nhận câu trả lời theo bản vừa đưa lên.</p>
          <div className="admin-counts">
            <span className="admin-chip">{result.counts?.rules ?? 0} chủ đề</span>
            <span className="admin-chip">{result.counts?.faqs ?? 0} câu hỏi thường gặp</span>
            <span className="admin-chip">{result.counts?.milestones ?? 0} mốc thời gian</span>
            <span className="admin-chip">{result.counts?.file03_sheets ?? 0} tài liệu nghiệp vụ</span>
            <span className="admin-chip">{result.counts?.file05_articles ?? 0} bài giới thiệu</span>
          </div>
          <ul className="admin-file-list">
            {(result.files || []).map((f) => (
              <li key={f.index}>
                Đã nhận file {f.index}: {f.filename}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  )
}
