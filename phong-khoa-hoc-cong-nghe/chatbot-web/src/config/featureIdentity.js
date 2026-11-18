import { BookOpen, ClipboardCheck, MessageCircle, FileText } from 'lucide-react'
import department from './department.json'
const icons = [BookOpen, ClipboardCheck, MessageCircle, FileText]
export const FEATURE_DEFS = department.topics.map((topic, i) => ({
 key: `department-${i + 1}`, slug: `chu-de-${i + 1}`, moduleId: `module_${i + 1}`,
 label: topic[0], title: topic[0], bot_name: topic[0], tagline: topic[1],
 accent: '#144E8C', accentSoft: 'rgba(20,78,140,.14)', Icon: icons[i],
 welcome: { headline: `Trợ lý ${department.name}`, intro: topic[1], bulletsTitle: 'Bạn có thể hỏi tôi', bullets: [topic[2]], footerHint: 'Nhập câu hỏi để được hỗ trợ.' }
}))
export const DEFAULT_BOT_PATH = `/bot/${FEATURE_DEFS[0].slug}`
export const BOT_CHAT_NAV = FEATURE_DEFS
export const REGISTRATION = { path: '/dang-ky-nhan-tin', label: 'Đăng ký hỗ trợ', bot_name: department.name }
export const REGISTRATION_FEATURE = { ...FEATURE_DEFS[0], ...REGISTRATION }
export const SIDEBAR_NAV_ITEMS = FEATURE_DEFS.map(f => ({ ...f, to: `/bot/${f.slug}`, sub: f.tagline, isActive: path => path === `/bot/${f.slug}` }))
export const getModuleIdBySlug = slug => FEATURE_DEFS.find(f => f.slug === slug)?.moduleId
export const resolveFeatureFromPathname = path => FEATURE_DEFS.find(f => path === `/bot/${f.slug}`) || FEATURE_DEFS[0]
export const getChatWelcome = feature => (feature || FEATURE_DEFS[0]).welcome
export const displayNameForResolvedMode = (id, modes = []) => modes.find(m => m.id === id)?.label || FEATURE_DEFS.find(f => f.moduleId === id)?.label || id
export const featureCssVars = feature => ({ '--feature-accent': feature.accent, '--feature-accent-soft': feature.accentSoft })
export const isAdmissionHubPathname = () => false
