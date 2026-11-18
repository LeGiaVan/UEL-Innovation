import { Link } from 'react-router-dom'
import { FEATURE_DEFS } from '../config/featureIdentity'
import { useFeatureTheme } from '../context/FeatureThemeContext'
import department from '../config/department.json'
import './DepartmentHub.css'
export default function DepartmentHub({onSuggestionClick}) {
 const feature=useFeatureTheme()
 return <section className="department-hub"><h2>Trợ lý {department.name}</h2><p>{feature.tagline}</p><div className="department-cards">{FEATURE_DEFS.map(f=><Link key={f.key} to={`/bot/${f.slug}`}><f.Icon size={26}/><strong>{f.label}</strong><span>{f.tagline}</span></Link>)}</div><h3>Bạn có thể hỏi tôi</h3>{feature.welcome.bullets.map(text=><button key={text} onClick={()=>onSuggestionClick(text)}>{text}</button>)}</section>
}
