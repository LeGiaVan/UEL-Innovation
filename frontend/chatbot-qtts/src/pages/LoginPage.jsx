import {useState} from 'react'
import {useDispatch,useSelector} from 'react-redux'
import {login} from '../store/slices/authSlice'
import department from '../config/department.json'
import './LoginPage.css'
export default function LoginPage() {
 const dispatch=useDispatch(), {isLoading,error}=useSelector(s=>s.auth)
 const [username,setUsername]=useState(''), [password,setPassword]=useState('')
 async function submit(event){event.preventDefault();await dispatch(login({username,password}));setPassword('')}
 return <main className="login-page"><form className="login-card" onSubmit={submit}><img src="/docs/logo-2026-06.png" alt="UEL"/><h1>Trợ lý {department.name}</h1><p>Đăng nhập bằng tài khoản đã được cấp quyền sử dụng.</p><label htmlFor="username">Tên đăng nhập</label><input id="username" autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} required minLength={3} maxLength={80}/><label htmlFor="password">Mật khẩu</label><input id="password" type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required maxLength={256}/>{error && <p role="alert">{error}</p>}<button disabled={isLoading} type="submit">{isLoading?'Đang đăng nhập…':'Đăng nhập'}</button></form></main>
}
