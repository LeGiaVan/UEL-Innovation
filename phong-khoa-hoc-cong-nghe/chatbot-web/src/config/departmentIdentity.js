import baked from './department.json'

export function liveDepartment(fromApi) {
  const id = fromApi?.id || baked.id || 'starter'
  const name = fromApi?.name || baked.name || 'Trợ lý UEL'
  const short =
    fromApi?.short ||
    baked.short ||
    (id === 'starter' ? 'P.Starter' : `P.${String(id).toUpperCase()}`)
  return { id, name, short }
}
