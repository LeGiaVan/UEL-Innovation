// Access tokens stay in memory; never put credentials in VITE_* or localStorage.
let token = null
export const getAccessToken = () => token
export const setAccessToken = value => { token = value }
export function expireSession() {
 token = null
 if (typeof window !== 'undefined') window.dispatchEvent(new Event('chatbot:unauthorized'))
}
