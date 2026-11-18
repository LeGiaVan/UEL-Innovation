import department from '../config/department.json'
export const FALLBACK_CHAT_MODES = department.topics.map((t, i) => ({ id: `module_${i+1}`, label: t[0], bot_name: t[0], description: t[1] }))
