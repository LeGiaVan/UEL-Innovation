import { fetchQA } from '../store/slices/qaSlice'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { X } from 'lucide-react'
import Header from '../components/Header'
import Sidebar from '../components/Sidebar'
import { fetchChatModes } from '../store/slices/modeSlice'
import { FeatureThemeProvider, useFeatureTheme } from '../context/FeatureThemeContext'
import { featureCssVars } from '../config/featureIdentity'
import '../App.css'
import '../styles/feature-scope.css'

function MainLayoutShell() {
  const dispatch = useDispatch()
  const location = useLocation()
  const feature = useFeatureTheme()
  const vars = featureCssVars(feature)
  const selectedMode = useSelector((s) => s.mode.selectedMode)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const closeSidebar = useCallback(() => setSidebarOpen(false), [])

  const modeFromPath = useMemo(() => {
    const match = /\/bot\/chu-de-(\d+)/.exec(location.pathname)
    return match ? `module_${match[1]}` : selectedMode
  }, [location.pathname, selectedMode])

  useEffect(() => {
    dispatch(fetchChatModes())
  }, [dispatch])

  const faqOpen = new URLSearchParams(location.search).get('view') === 'faq'

  useEffect(() => {
    if (faqOpen) dispatch(fetchQA({ all: true }))
    else dispatch(fetchQA({ mode: modeFromPath }))
  }, [dispatch, modeFromPath, faqOpen])

  useEffect(() => {
    closeSidebar()
  }, [location.pathname, location.search, closeSidebar])

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)')
    const apply = () => {
      if (mq.matches && sidebarOpen) {
        document.body.classList.add('layout-drawer-open')
      } else {
        document.body.classList.remove('layout-drawer-open')
      }
    }
    apply()
    mq.addEventListener('change', apply)
    return () => {
      mq.removeEventListener('change', apply)
      document.body.classList.remove('layout-drawer-open')
    }
  }, [sidebarOpen])

  useEffect(() => {
    if (!sidebarOpen) return
    const onKey = (e) => {
      if (e.key === 'Escape') closeSidebar()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [sidebarOpen, closeSidebar])

  return (
    <div className="app" style={vars}>
      <Header onOpenMenu={() => setSidebarOpen(true)} />
      <div className="app-container">

        <div
          className={`sidebar-overlay${sidebarOpen ? ' is-visible' : ''}`}
          onClick={closeSidebar}
          aria-hidden="true"
        />

        <div
          id="sidebar-drawer"
          className={`sidebar-drawer${sidebarOpen ? ' sidebar-drawer--open' : ''}`}
          role="dialog"
          aria-modal="true"
          aria-label="Danh sách module"
        >
          <div className="sidebar-drawer__head">
            <span className="sidebar-drawer__title">Chọn chức năng</span>
            <button
              type="button"
              className="sidebar-drawer__close"
              onClick={closeSidebar}
              aria-label="Đóng menu"
            >
              <X size={22} strokeWidth={2} aria-hidden />
            </button>
          </div>
          <Sidebar onNavigate={closeSidebar} />
        </div>

        <main
          className={`main-outlet feature-scope feature-scope--${feature.key}`}
          style={vars}
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default function MainLayout() {
  return (
    <FeatureThemeProvider>
      <MainLayoutShell />
    </FeatureThemeProvider>
  )
}
