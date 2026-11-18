import { useEffect } from 'react'
import { department } from '../config/department.js'

export function useDepartmentTitle() {
  useEffect(() => {
    document.title = `Trợ lý ${department.short} | UEL`
  }, [])
}
