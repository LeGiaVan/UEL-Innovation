import { fetchQA } from '../store/slices/qaSlice'
import { useCallback, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { Menu, X } from 'lucide-react'
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
  const modeLoaded = useSelector((s) => s.mode.loaded)
  const feature = useFeatureTheme()
  const vars = featureCssVars(feature)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const closeSidebar = useCallback(() => setSidebarOpen(false), [])

  useEffect(() => {
    if (!modeLoaded) {
      dispatch(fetchChatModes())
      dispatch(fetchQA())
    }
  }, [dispatch, modeLoaded])

  useEffect(() => {
    closeSidebar()
  }, [location.pathname, closeSidebar])

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
      <Header />
      <div className="app-container">
        <div className="mobile-module-bar">
          <button
            type="button"
            className="mobile-module-bar__btn"
            onClick={() => setSidebarOpen(true)}
            aria-label="Mở danh sách tư vấn"
            aria-expanded={sidebarOpen}
            aria-controls="sidebar-drawer"
          >
            <Menu size={22} strokeWidth={2} aria-hidden />
            <span>Danh sách tư vấn</span>
          </button>
        </div>

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
