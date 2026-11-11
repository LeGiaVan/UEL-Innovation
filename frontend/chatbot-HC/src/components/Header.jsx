import {useDispatch, useSelector} from 'react-redux'
import {logout} from '../store/slices/authSlice'
import department from '../config/department.json'
import { MOCK_API } from '../api/client'
import './Header.css'
export default function Header() {
 const dispatch=useDispatch(), user=useSelector(s=>s.auth.user)
 return <header className="header"><div className="header-content"><div className="header-logo"><img src="/docs/logo-2026-06.png" alt="UEL" className="logo-img logo-img--on-primary"/><div className="header-title"><h1 className="header-title-line">Trợ lý AI hỗ trợ {department.short}</h1><p className="header-subtitle">Trường Đại học Kinh tế - Luật (ĐHQG-HCM)</p></div></div>{MOCK_API && <span style={{color:'white',fontSize:12}}>Bản mẫu trải nghiệm</span>}{!MOCK_API && user && <button type="button" onClick={()=>dispatch(logout())} style={{padding:'8px 12px',borderRadius:8,border:0,cursor:'pointer'}}>Đăng xuất</button>}</div></header>
}
