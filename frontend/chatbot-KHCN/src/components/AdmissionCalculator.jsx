import { API_URL, fetchApi as fetch } from '../api/client'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { addMessage } from '../store/slices/chatSlice'
import { loadAdmissionSurveyProfile } from '../utils/admissionSurveyStorage'



const DT_LABELS = {
  DT1: 'Đối tượng 1: Có ĐGNL + THPT + học bạ',
  DT2: 'Đối tượng 2: Có THPT + học bạ (không dùng ĐGNL)',
  DT3: 'Đối tượng 3: Có ĐGNL + học bạ (không dùng THPT)',
  DT4: 'Đối tượng 4: Có chứng chỉ quốc tế quy đổi (CCQT)',
}

const ENG_LOAI_LABEL = {
  ielts_academic: 'IELTS Academic',
  linguaskill: 'Linguaskill',
  toeic: 'TOEIC (Nghe–Đọc & Nói–Viết)',
  toefl_ibt: 'TOEFL iBT',
}

/** Chuẩn hóa số thập phân: chấm hoặc phẩy; hỗ trợ dấu thập phân Unicode hay nhầm lẫn dấu. */
function asNum(v) {
  if (v === '' || v == null) return null
  let s = String(v).trim()
  if (!s) return null
  s = s.replace(/\u00A0/g, '').replace(/[\u00B7\u2022\u2219\u22C5\uFF0E]/g, '.')
  const hasComma = s.includes(',')
  const hasDot = s.includes('.')
  if (hasComma && hasDot) {
    if (s.lastIndexOf(',') > s.lastIndexOf('.')) {
      s = s.replace(/\./g, '').replace(',', '.')
    } else {
      s = s.replace(/,/g, '')
    }
  } else if (hasComma) {
    s = s.replace(',', '.')
  }
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}

export default function AdmissionCalculator() {
  const dispatch = useDispatch()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [missingRequired, setMissingRequired] = useState(new Set())
  const [schoolQuery, setSchoolQuery] = useState('')
  const [schoolLoading, setSchoolLoading] = useState(false)
  const [schoolResults, setSchoolResults] = useState([])
  const [ccqtLoading, setCcqtLoading] = useState(false)
  const [ccqtNote, setCcqtNote] = useState('')
  const [engBonusLoading, setEngBonusLoading] = useState(false)
  const [engBonusPreview, setEngBonusPreview] = useState(null)
  const schoolAbortRef = useRef(null)
  const englishAbortRef = useRef(null)
  const suppressNextAutoSuggestRef = useRef(false)
  const [form, setForm] = useState({
    hoc_luc_dt: 'DT1',
    khu_vuc: 'KV2',
    doi_tuong_uu_tien: 'NONE',
    nam_xet_tuyen: '2026',
    diem_dgnl_thang_1200: '',
    thpt_mon1: '',
    thpt_mon2: '',
    thpt_mon3: '',
    hb_mon1: '',
    hb_mon2: '',
    hb_mon3: '',
    dt4_diem_quy_doi_100: '',
    ielts_overall: '',
    linguaskill: '',
    toeic_nghe_doc: '',
    toeic_noi_viet: '',
    toefl_ibt: '',
    sat: '',
    act: '',
    ib: '',
    a_level: '',
    ma_tinh_tp: '',
    ma_truong_thpt: '',
    ten_truong_thpt: '',
    ten_tinh_tp: '',
    thuoc_149: false,
  })

  const need = useMemo(() => {
    const dt = form.hoc_luc_dt
    return {
      dgnl: dt === 'DT1' || dt === 'DT3',
      thpt: dt === 'DT1' || dt === 'DT2',
      hb: dt === 'DT1' || dt === 'DT2' || dt === 'DT3',
      dt4: dt === 'DT4',
    }
  }, [form.hoc_luc_dt])

  const onChange = (key, value) => {
    setForm((p) => {
      const next = { ...p, [key]: value }
      // Auto-switch ĐT khi user nhập/xoá điểm ĐGNL (chỉ giữa DT1 ↔ DT2 — không động vào DT3/DT4 thủ công)
      if (key === 'diem_dgnl_thang_1200' && (p.hoc_luc_dt === 'DT1' || p.hoc_luc_dt === 'DT2')) {
        const hasDgnl = String(value || '').trim() !== ''
        next.hoc_luc_dt = hasDgnl ? 'DT1' : 'DT2'
        // Clear stale missing flags do đổi DT
        setMissingRequired((prev) => {
          const s = new Set(prev)
          s.delete('diem_dgnl_thang_1200')
          return s
        })
      }
      return next
    })
    setMissingRequired((prev) => {
      if (!prev.has(key) && !(key === 'dt4_diem_quy_doi_100' && prev.has('__dt4_bundle'))) {
        return prev
      }
      const next = new Set(prev)
      next.delete(key)
      if (key === 'dt4_diem_quy_doi_100' || key === 'sat' || key === 'act' || key === 'ib' || key === 'a_level') {
        next.delete('__dt4_bundle')
      }
      return next
    })
  }

  /** Không giới hạn input: để trống thì mặc định mức thấp nhất (0). */
  const numOrMin = (v, min = 0) => {
    const n = asNum(v)
    return n == null ? min : n
  }

  const buildPayload = () => {
    const body = {
      hoc_luc_dt: form.hoc_luc_dt,
      khu_vuc: form.khu_vuc,
      doi_tuong_uu_tien: form.doi_tuong_uu_tien,
      nam_xet_tuyen: Number(form.nam_xet_tuyen) || 2026,
      include_markdown: true,
    }
    if (form.ma_tinh_tp && form.ma_truong_thpt) {
      body.ma_tinh_tp = form.ma_tinh_tp
      body.ma_truong_thpt = form.ma_truong_thpt
      // BE sẽ tự xác định ưu tiên qua lookup_truong; flag dưới đây giữ làm hint backward-compat.
      body.thuoc_149 = Boolean(form.thuoc_149)
    }
    if (need.dgnl) body.diem_dgnl_thang_1200 = numOrMin(form.diem_dgnl_thang_1200, 0)
    if (need.thpt) {
      body.thpt_mon1 = numOrMin(form.thpt_mon1, 0)
      body.thpt_mon2 = numOrMin(form.thpt_mon2, 0)
      body.thpt_mon3 = numOrMin(form.thpt_mon3, 0)
    }
    if (need.hb) {
      body.hb_mon1 = numOrMin(form.hb_mon1, 0)
      body.hb_mon2 = numOrMin(form.hb_mon2, 0)
      body.hb_mon3 = numOrMin(form.hb_mon3, 0)
    }
    if (need.dt4) {
      body.dt4_diem_quy_doi_100 = numOrMin(form.dt4_diem_quy_doi_100, 0)
      body.sat = numOrMin(form.sat, 0)
      body.act = numOrMin(form.act, 0)
      body.ib = numOrMin(form.ib, 0)
      const al = (form.a_level || '').trim()
      body.a_level = al || ''
    }
    body.ielts_overall = numOrMin(form.ielts_overall, 0)
    body.linguaskill = numOrMin(form.linguaskill, 0)
    body.toeic_nghe_doc = numOrMin(form.toeic_nghe_doc, 0)
    body.toeic_noi_viet = numOrMin(form.toeic_noi_viet, 0)
    body.toefl_ibt = numOrMin(form.toefl_ibt, 0)
    return body
  }

  /** Trường bắt buộc: cảnh báo theo từng ô, nhưng không chặn tính điểm. */
  const collectMissingRequiredKeys = () => {
    const missing = []
    if (need.dgnl && asNum(form.diem_dgnl_thang_1200) == null) {
      missing.push('diem_dgnl_thang_1200')
    }
    if (need.thpt) {
      if (asNum(form.thpt_mon1) == null) missing.push('thpt_mon1')
      if (asNum(form.thpt_mon2) == null) missing.push('thpt_mon2')
      if (asNum(form.thpt_mon3) == null) missing.push('thpt_mon3')
    }
    if (need.hb) {
      if (asNum(form.hb_mon1) == null) missing.push('hb_mon1')
      if (asNum(form.hb_mon2) == null) missing.push('hb_mon2')
      if (asNum(form.hb_mon3) == null) missing.push('hb_mon3')
    }
    if (need.dt4) {
      const hasCcqt =
        asNum(form.sat) != null ||
        asNum(form.act) != null ||
        asNum(form.ib) != null ||
        String(form.a_level || '').trim() !== ''
      if (asNum(form.dt4_diem_quy_doi_100) == null && !hasCcqt) {
        missing.push('__dt4_bundle')
      }
    }
    return missing
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    const missing = collectMissingRequiredKeys()
    setMissingRequired(new Set(missing))
    const body = buildPayload()
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/module_3/compute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const text = await res.text()
      const data = text ? JSON.parse(text) : {}
      if (!res.ok) throw new Error(data?.detail || data?.message || text || 'Tính điểm thất bại')

      const ts = new Date().toISOString()
      const utLabel =
        body.doi_tuong_uu_tien === 'NONE' ? 'Không ưu tiên' : body.doi_tuong_uu_tien
      const summary = `Tính điểm ${DT_LABELS[body.hoc_luc_dt] || body.hoc_luc_dt} • ${body.khu_vuc} • ${utLabel}`
      dispatch(addMessage({ role: 'user', content: summary, timestamp: ts }))
      dispatch(
        addMessage({
          role: 'assistant',
          content: data.markdown || 'Đã tính điểm thành công.',
          streaming: false,
          citations: [],
          timestamp: ts,
        })
      )
    } catch (err) {
      setError(err?.message || 'Tính điểm thất bại')
    } finally {
      setLoading(false)
    }
  }

  /**
   * Chuẩn hoá KV chuỗi (vd 'KV2_NT' → 'KV2NT', vì admission engine dùng dạng không gạch dưới).
   */
  const normalizeKv = (kv) => {
    if (!kv) return ''
    const s = String(kv).trim().toUpperCase().replace(/_/g, '')
    return ['KV1', 'KV2NT', 'KV2', 'KV3'].includes(s) ? s : ''
  }

  /**
   * Heuristic fallback theo tỉnh (chỉ dùng khi BE không trả `khu_vuc` cho trường).
   * KV chính xác phải lấy từ list Bộ GD&ĐT (field `khu_vuc` trong API response).
   */
  const suggestKvFromProvince = (provinceName) => {
    const p = (provinceName || '').toLowerCase()
    if (
      p.includes('hà nội') ||
      p.includes('tp. hcm') ||
      p.includes('hồ chí minh') ||
      p.includes('đà nẵng') ||
      p.includes('cần thơ') ||
      p.includes('hải phòng')
    ) {
      return 'KV3'
    }
    return 'KV2'
  }

  useEffect(() => {
    const survey = loadAdmissionSurveyProfile()
    if (!survey) return
    const school = String(survey.school_name || '').trim()
    const province = String(survey.province_name || '').trim()
    if (!school && !province) return
    setForm((p) => {
      const next = { ...p }
      if (!p.ten_truong_thpt && school) next.ten_truong_thpt = school
      if (!p.ten_tinh_tp && province) next.ten_tinh_tp = province
      if (!p.ten_tinh_tp && province) next.khu_vuc = suggestKvFromProvince(province)
      return next
    })
    if (!schoolQuery && school) {
      // Set query để hiện trong input nhưng SUPPRESS auto-suggest dropdown
      suppressNextAutoSuggestRef.current = true
      setSchoolQuery(school)
    }
    // Auto-resolve trường từ survey: search list THPT 2026 (single source of truth).
    // Mỗi entry có cờ `uu_tien: bool` → flag thuoc_149 set trực tiếp, codes dùng post-merger.
    if (school) {
      ;(async () => {
        try {
          const res = await fetch(
            `${API_URL}/module-d/thpt-2026?q=${encodeURIComponent(school)}&limit=0`,
          )
          if (!res.ok) return
          const data = await res.json()
          const rows = Array.isArray(data?.truong) ? data.truong : []
          if (!rows.length) return
          const norm = (s) => String(s || '').trim().toLowerCase()
          const provinceMatches = (r) => {
            if (!province) return true
            return norm(r?.ten_tinh) === norm(province)
          }
          const exactNameRows = rows.filter((r) => norm(r?.ten_truong) === norm(school))
          const match =
            exactNameRows.find(provinceMatches) ||
            (exactNameRows.length === 1 ? exactNameRows[0] : null) ||
            rows.find(provinceMatches) ||
            (rows.length === 1 ? rows[0] : null)
          if (!match) return
          setForm((p) => {
            if (p.ma_truong_thpt) return p
            const kvFromBe = normalizeKv(match.khu_vuc)
            return {
              ...p,
              ma_tinh_tp: String(match.ma_tinh || ''),
              ma_truong_thpt: String(match.ma_truong || ''),
              ten_truong_thpt: String(match.ten_truong || school),
              ten_tinh_tp: String(match.ten_tinh || province),
              khu_vuc: kvFromBe || suggestKvFromProvince(match.ten_tinh || province),
              thuoc_149: Boolean(match.uu_tien),
            }
          })
        } catch {
          // Im lặng — user vẫn có thể chọn thủ công
        }
      })()
    }
  }, []) // chỉ nạp 1 lần khi mở tab Tính điểm

  const searchSchools = async (queryText = schoolQuery) => {
    const q = String(queryText || '').trim()
    if (!q) {
      setSchoolResults([])
      return
    }
    if (schoolAbortRef.current) {
      schoolAbortRef.current.abort()
    }
    const controller = new AbortController()
    schoolAbortRef.current = controller
    setSchoolLoading(true)
    try {
      // Search trong list THPT 2026 (single source of truth, Bộ GD&ĐT).
      // Mỗi entry có cờ `uu_tien: bool` cho biết trường thuộc 149 ưu tiên ĐHQG-HCM.
      const res = await fetch(
        `${API_URL}/module-d/thpt-2026?q=${encodeURIComponent(q)}&limit=0`,
        { signal: controller.signal }
      )
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'Không tra được danh sách trường')
      const rows = Array.isArray(data?.truong) ? data.truong : []
      const seen = new Set()
      const dedup = rows.filter((r) => {
        const key = `${r?.ma_tinh || ''}-${r?.ma_truong || ''}`
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
      setSchoolResults(dedup)
    } catch (err) {
      if (err?.name === 'AbortError') return
      setError(err?.message || 'Không tra được danh sách trường')
    } finally {
      setSchoolLoading(false)
    }
  }

  useEffect(() => {
    if (suppressNextAutoSuggestRef.current) {
      suppressNextAutoSuggestRef.current = false
      return
    }
    const q = schoolQuery.trim()
    if (!q) {
      setSchoolResults([])
      return
    }
    const timer = setTimeout(() => {
      searchSchools(q)
    }, 260)
    return () => clearTimeout(timer)
  }, [schoolQuery])

  useEffect(() => {
    const ielts = asNum(form.ielts_overall)
    const ling = asNum(form.linguaskill)
    const toeL = asNum(form.toeic_nghe_doc)
    const toeS = asNum(form.toeic_noi_viet)
    const toefl = asNum(form.toefl_ibt)
    const hasEnglish =
      ielts != null || ling != null || toefl != null || toeL != null || toeS != null
    if (!hasEnglish) {
      englishAbortRef.current?.abort()
      setEngBonusLoading(false)
      setEngBonusPreview(null)
      return
    }
    const timer = setTimeout(async () => {
      if (englishAbortRef.current) {
        englishAbortRef.current.abort()
      }
      const controller = new AbortController()
      englishAbortRef.current = controller
      setEngBonusLoading(true)
      try {
        const res = await fetch(`${API_URL}/module-d/uel-english-bonus-lookup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            ielts_overall: ielts,
            linguaskill: ling,
            toeic_nghe_doc: toeL,
            toeic_noi_viet: toeS,
            toefl_ibt: toefl,
            toefl_la_home_edition: false,
          }),
        })
        const data = await res.json().catch(() => ({}))
        if (!res.ok) {
          setEngBonusPreview(null)
          return
        }
        setEngBonusPreview({
          diemCong: data.diem_cong,
          chon: data.chi_tiet?.chon,
          canhBao: data.chi_tiet?.canh_bao || [],
        })
      } catch (err) {
        if (err?.name === 'AbortError') return
        setEngBonusPreview(null)
      } finally {
        setEngBonusLoading(false)
      }
    }, 380)
    return () => {
      clearTimeout(timer)
      englishAbortRef.current?.abort()
    }
  }, [
    form.ielts_overall,
    form.linguaskill,
    form.toeic_nghe_doc,
    form.toeic_noi_viet,
    form.toefl_ibt,
  ])

  const pickSchool = (s) => {
    // Ưu tiên KV chuẩn từ Bộ (field `khu_vuc` trong response); fallback heuristic theo tỉnh.
    const kvFromBe = normalizeKv(s?.khu_vuc)
    const kv = kvFromBe || suggestKvFromProvince(s?.ten_tinh)
    suppressNextAutoSuggestRef.current = true
    // Codes post-merger (single namespace). `uu_tien` boolean → bonus +5 nếu true.
    setForm((p) => ({
      ...p,
      ma_tinh_tp: String(s?.ma_tinh || ''),
      ma_truong_thpt: String(s?.ma_truong || ''),
      ten_truong_thpt: String(s?.ten_truong || ''),
      ten_tinh_tp: String(s?.ten_tinh || ''),
      khu_vuc: kv,
      thuoc_149: Boolean(s?.uu_tien),
    }))
    setSchoolResults([])
    setSchoolQuery(String(s?.ten_truong || ''))
  }

  const lookupCcqt = async () => {
    setCcqtNote('')
    const payload = {
      sat: asNum(form.sat),
      act: asNum(form.act),
      ib: asNum(form.ib),
      a_level: form.a_level?.trim() || null,
    }
    const hasAny =
      payload.sat != null ||
      payload.act != null ||
      payload.ib != null ||
      (payload.a_level != null && payload.a_level !== '')
    if (!hasAny) {
      setError('Vui lòng nhập ít nhất một chứng chỉ quốc tế (SAT/ACT/IB/A-Level) để quy đổi.')
      return
    }
    setError('')
    setCcqtLoading(true)
    try {
      const res = await fetch(`${API_URL}/module-d/uel-ccqt-lookup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'Không quy đổi được chứng chỉ quốc tế')
      const converted = data?.diem_quy_doi_100
      const curManual = asNum(form.dt4_diem_quy_doi_100)
      const nextVal =
        converted == null
          ? form.dt4_diem_quy_doi_100
          : curManual != null
            ? String(Math.max(curManual, Number(converted)))
            : String(converted)
      setForm((p) => ({
        ...p,
        dt4_diem_quy_doi_100: nextVal,
      }))
      const warns = data?.chi_tiet?.canh_bao
      if (Array.isArray(warns) && warns.length) {
        setCcqtNote(warns.join(' '))
      } else if (converted != null && Number(converted) < 1e-9) {
        setCcqtNote(
          'Chứng chỉ quốc tế (CCQT) không được cộng điểm quy đổi — điểm quy đổi thang 100 = 0 theo bảng.'
        )
      }
    } catch (err) {
      setError(err?.message || 'Không quy đổi được chứng chỉ quốc tế')
    } finally {
      setCcqtLoading(false)
    }
  }

  const scoreInput = (key, label, placeholder) => (
    <label className={`admission-calc__field${missingRequired.has(key) ? ' admission-calc__field--warn' : ''}`}>
      <span className="admission-calc__label">{label}</span>
      <input
        className="admission-calc__input"
        type="text"
        inputMode="decimal"
        value={form[key]}
        onChange={(e) => onChange(key, e.target.value)}
        placeholder={placeholder}
      />
      {missingRequired.has(key) ? (
        <span className="admission-calc__field-warn">Ô bắt buộc. Đang tạm dùng giá trị 0.</span>
      ) : null}
    </label>
  )

  const engShowZeroFallback =
    engBonusPreview &&
    !engBonusLoading &&
    (engBonusPreview.diemCong == null || Number(engBonusPreview.diemCong) < 1e-9) &&
    !(engBonusPreview.canhBao || []).length

  return (
    <form className="admission-calc" onSubmit={submit}>
      <header className="admission-calc__page-head">
        <h2 className="admission-calc__page-title">Tính điểm xét tuyển</h2>
        <p className="admission-calc__page-lead">
          Hệ thống quy đổi điểm tham khảo cho thí sinh
        </p>
      </header>

      <div className="admission-calc__panel">
        <div className="admission-calc__school-search">
          <input
            className="admission-calc__input admission-calc__input--solo"
            type="text"
            autoComplete="off"
            aria-label="Tìm tên trường THPT"
            value={schoolQuery}
            onChange={(e) => setSchoolQuery(e.target.value)}
            placeholder="Tìm tên trường THPT (ví dụ: Lê Quý Đôn)"
          />
          {schoolLoading ? (
            <span className="admission-calc__inline-hint">Đang tìm…</span>
          ) : null}
        </div>
        {schoolResults.length > 0 && (
          <div className="admission-calc__school-list">
            {schoolResults.map((s) => (
              <button
                key={`${s.ma_tinh}-${s.ma_truong}-${s.ten_truong}`}
                type="button"
                className="admission-calc__school-item"
                onClick={() => pickSchool(s)}
              >
                <span className="admission-calc__school-item-name">{s.ten_truong}</span>
                <small className="admission-calc__school-item-sub">
                  {[s.dia_chi, s.ten_tinh].filter(Boolean).join(' — ')}
                </small>
              </button>
            ))}
          </div>
        )}
        {form.ten_truong_thpt ? (
          <p className="admission-calc__card-foot">
            Đã chọn: <strong>{form.ten_truong_thpt}</strong> ({form.ten_tinh_tp}) — gợi ý KV:{' '}
            <strong>{form.khu_vuc}</strong>.
          </p>
        ) : null}

        <div className="admission-calc__row admission-calc__row--3">
          <label className="admission-calc__field">
            <span className="admission-calc__label">Đối tượng xét tuyển</span>
            <select value={form.hoc_luc_dt} onChange={(e) => onChange('hoc_luc_dt', e.target.value)}>
              <option value="DT1">{DT_LABELS.DT1}</option>
              <option value="DT2">{DT_LABELS.DT2}</option>
              <option value="DT3">{DT_LABELS.DT3}</option>
              <option value="DT4">{DT_LABELS.DT4}</option>
            </select>
          </label>
          <label className="admission-calc__field">
            <span className="admission-calc__label">Khu vực ưu tiên</span>
            <select value={form.khu_vuc} onChange={(e) => onChange('khu_vuc', e.target.value)}>
              <option value="KV1">KV1</option>
              <option value="KV2NT">KV2NT</option>
              <option value="KV2">KV2</option>
              <option value="KV3">KV3</option>
            </select>
          </label>
          <label className="admission-calc__field">
            <span className="admission-calc__label">Nhóm ưu tiên (UT)</span>
            <select
              value={form.doi_tuong_uu_tien}
              onChange={(e) => onChange('doi_tuong_uu_tien', e.target.value)}
            >
              <option value="NONE">Không ưu tiên</option>
              <option value="UT123">UT123</option>
              <option value="UT456">UT456</option>
            </select>
          </label>
        </div>

        <div className="admission-calc__row admission-calc__row--eng5">
          {scoreInput('ielts_overall', 'IELTS', '6.5 hoặc 6,5')}
          {scoreInput('toefl_ibt', 'TOEFL iBT', 'Ví dụ: 78')}
          {scoreInput('toeic_nghe_doc', 'TOEIC – L&R', 'Ví dụ: 720')}
          {scoreInput('toeic_noi_viet', 'TOEIC – S&W', 'Ví dụ: 260')}
          {scoreInput('linguaskill', 'Linguaskill', 'Ví dụ: 160')}
        </div>
        {(engBonusLoading || engBonusPreview) && (
          <div className="admission-calc__eng-preview" aria-live="polite">
            {engBonusLoading ? (
              <span>Đang tính điểm cộng tiếng Anh…</span>
            ) : engBonusPreview ? (
              <>
                <strong>Điểm cộng tiếng Anh (ước tính):</strong>{' '}
                <span className="admission-calc__eng-preview-score">+{engBonusPreview.diemCong ?? 0}</span>
                {engBonusPreview.chon?.loai ? (
                  <span className="admission-calc__eng-preview-meta">
                    {' '}
                    — áp dụng theo:{' '}
                    <strong>{ENG_LOAI_LABEL[engBonusPreview.chon.loai] || engBonusPreview.chon.loai}</strong>
                  </span>
                ) : null}
                {engShowZeroFallback ? (
                  <p className="admission-calc__eng-zero">
                    Chứng chỉ tiếng Anh (CCTA) không được cộng điểm — kiểm tra ngưỡng trong bảng UEL hoặc nhập đủ cặp
                    TOEIC (L&R và S&W).
                  </p>
                ) : null}
                {(engBonusPreview.canhBao || []).length > 0 && (
                  <ul className="admission-calc__eng-preview-warn">
                    {engBonusPreview.canhBao.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                )}
              </>
            ) : null}
          </div>
        )}

        {need.dt4 && (
          <div className="admission-calc__dt4-block">
            <div className="admission-calc__row admission-calc__row--4">
              {scoreInput('sat', 'SAT', 'Ví dụ: 1250')}
              {scoreInput('act', 'ACT', 'Ví dụ: 28')}
              {scoreInput('ib', 'IB', 'Ví dụ: 32')}
              {scoreInput('a_level', 'A-Level', 'Ví dụ: A*')}
            </div>
            <div className="admission-calc__row admission-calc__row--2">
              <label className={`admission-calc__field${missingRequired.has('__dt4_bundle') ? ' admission-calc__field--warn' : ''}`}>
                <span className="admission-calc__label">Điểm quy đổi CCQT (thang 100)</span>
                <div className="admission-calc__inline">
                  <input
                    className="admission-calc__input"
                    type="text"
                    inputMode="decimal"
                    value={form.dt4_diem_quy_doi_100}
                    onChange={(e) => onChange('dt4_diem_quy_doi_100', e.target.value)}
                    placeholder="Ví dụ: 72 hoặc 72,5"
                  />
                  <button
                    type="button"
                    className="admission-calc__lookup-btn"
                    onClick={lookupCcqt}
                    disabled={ccqtLoading}
                  >
                    {ccqtLoading ? 'Đang quy đổi…' : 'Quy đổi tự động'}
                  </button>
                </div>
                {missingRequired.has('__dt4_bundle') ? (
                  <span className="admission-calc__field-warn">
                    Cần nhập điểm quy đổi hoặc ít nhất 1 chứng chỉ (SAT/ACT/IB/A-Level). Đang tạm dùng 0.
                  </span>
                ) : null}
              </label>
            </div>
            {ccqtNote ? <p className="admission-calc__ccqt-note">{ccqtNote}</p> : null}
          </div>
        )}

        {need.dgnl && (
          <div className="admission-calc__group">
            {scoreInput('diem_dgnl_thang_1200', 'Điểm ĐGNL (thang 1200)', 'Ví dụ: 950')}
          </div>
        )}
        {need.thpt && (
          <div className="admission-calc__row">
            {scoreInput('thpt_mon1', 'Điểm THPT môn 1', 'Ví dụ: 8.5 hoặc 8,5')}
            {scoreInput('thpt_mon2', 'Điểm THPT môn 2', 'Ví dụ: 7.75')}
            {scoreInput('thpt_mon3', 'Điểm THPT môn 3', 'Ví dụ: 8.0')}
          </div>
        )}
        {need.hb && (
          <div className="admission-calc__row">
            {scoreInput('hb_mon1', 'Điểm học bạ môn 1', 'Ví dụ: 8.2')}
            {scoreInput('hb_mon2', 'Điểm học bạ môn 2', 'Ví dụ: 8.0')}
            {scoreInput('hb_mon3', 'Điểm học bạ môn 3', 'Ví dụ: 7.9')}
          </div>
        )}
      </div>

      {error ? <p className="admission-calc__error">{error}</p> : null}
      <div className="admission-calc__actions">
        <button type="submit" className="admission-calc__submit" disabled={loading}>
          {loading ? 'Đang tính…' : 'Tính điểm xét tuyển'}
        </button>
      </div>
    </form>
  )
}
