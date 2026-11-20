import { useEffect } from 'react'
import { useSelector } from 'react-redux'
import { liveDepartment } from '../config/departmentIdentity'
import { assistantTitle } from '../config/assistantTitle'

export function useDepartmentTitle() {
  const department = liveDepartment(useSelector((s) => s.auth.department))
  const title = assistantTitle(department.short)

  useEffect(() => {
    document.title = `${title} | UEL`
  }, [title])
}
