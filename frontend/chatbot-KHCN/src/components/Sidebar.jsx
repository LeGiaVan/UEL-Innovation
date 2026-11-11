import { Link, useLocation } from 'react-router-dom'
import { useSelector, useDispatch } from 'react-redux'
import { SIDEBAR_NAV_ITEMS } from '../config/featureIdentity'
import department from '../config/department.json'
import { fetchQA } from '../store/slices/qaSlice'
import './Sidebar.css'
export default function Sidebar({onNavigate}) {
 const {pathname}=useLocation(), dispatch=useDispatch()
 const {isLoading}=useSelector(s=>s.chat)
 const {questions,error}=useSelector(s=>s.qa)
 const modeError=useSelector(s=>s.mode.error)
 return <aside className="sidebar"><nav className="sidebar-modes" aria-label="Chủ đề hỗ trợ"><h2 className="sidebar-modes-title">{department.name}</h2>{modeError && <p role="alert">{modeError}</p>}<ul className="sidebar-modes-list">{SIDEBAR_NAV_ITEMS.map(item=><li key={item.key}><Link to={item.to} aria-disabled={isLoading} aria-current={item.isActive(pathname)?'page':undefined} className={`sidebar-mode-btn${item.isActive(pathname)?' active':''}`} onClick={e=>{if(isLoading)e.preventDefault();else onNavigate?.()}}><span className="sidebar-mode-btn-icon"><item.Icon size={22}/></span><span className="sidebar-mode-btn-text"><span className="sidebar-mode-btn-label">{item.label}</span><span className="sidebar-mode-btn-sub">{item.sub}</span></span></Link></li>)}</ul></nav><section className="sidebar-notices"><h3 className="sidebar-notices-title">Câu hỏi thường gặp</h3>{error && <div role="alert">{error}<button onClick={()=>dispatch(fetchQA())}>Thử lại</button></div>}<ul className="sidebar-notices-list">{questions.map((q,i)=><li key={q.id || i}><Link className="sidebar-notice-link" to={SIDEBAR_NAV_ITEMS.find(f=>f.moduleId===q.mode)?.to || SIDEBAR_NAV_ITEMS[0].to} state={{question:q.question}} onClick={e=>{if(isLoading)e.preventDefault();else onNavigate?.()}}>{q.question}</Link></li>)}</ul></section></aside>
}
