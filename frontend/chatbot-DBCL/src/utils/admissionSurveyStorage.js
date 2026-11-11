const SURVEY_STORAGE_KEY = 'uel_admission_survey_v1'

export function loadAdmissionSurveyProfile() {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.sessionStorage.getItem(SURVEY_STORAGE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    if (!data || typeof data !== 'object') return null
    return data
  } catch {
    return null
  }
}

export function saveAdmissionSurveyProfile(profile) {
  if (typeof window === 'undefined') return
  try {
    window.sessionStorage.setItem(SURVEY_STORAGE_KEY, JSON.stringify(profile))
  } catch {
    // ignore write errors in private mode/quota exceeded
  }
}

export function buildDefaultAdmissionSurveyProfile() {
  return {
    role: 'candidate',
    salutation: 'Chào bạn',
    school_name: '',
    province_name: '',
    completed: false,
    skipped: true,
    created_at: new Date().toISOString(),
  }
}

