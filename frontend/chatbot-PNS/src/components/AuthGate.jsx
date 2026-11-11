import {useEffect} from 'react'
import {useDispatch,useSelector} from 'react-redux'
import {MOCK_API} from '../api/client'
import {sessionExpired} from '../store/slices/authSlice'
import LoginPage from '../pages/LoginPage'
export default function AuthGate({children}) {
 const dispatch=useDispatch(), user=useSelector(s=>s.auth.user)
 useEffect(()=>{const expire=()=>dispatch(sessionExpired());window.addEventListener('chatbot:unauthorized',expire);return()=>window.removeEventListener('chatbot:unauthorized',expire)},[dispatch])
 return (import.meta.env.DEV && import.meta.env.VITE_AUTH_DISABLED === 'true') || MOCK_API || user ? children : <LoginPage/>
}
