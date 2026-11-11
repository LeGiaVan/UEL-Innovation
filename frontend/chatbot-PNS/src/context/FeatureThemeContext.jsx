import { createContext, useContext, useMemo } from 'react'
import { useLocation } from 'react-router-dom'
import { resolveFeatureFromPathname } from '../config/featureIdentity'

const FeatureThemeContext = createContext(null)

export function FeatureThemeProvider({ children }) {
  const { pathname } = useLocation()
  const feature = useMemo(() => resolveFeatureFromPathname(pathname), [pathname])
  return (
    <FeatureThemeContext.Provider value={feature}>{children}</FeatureThemeContext.Provider>
  )
}

export function useFeatureTheme() {
  const ctx = useContext(FeatureThemeContext)
  return ctx ?? resolveFeatureFromPathname('/')
}
