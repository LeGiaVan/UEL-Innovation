/** Tên hiển thị thống nhất: "Trợ lý AI - P.BĐCL" / "Trợ lý AI - P.Mẫu". */
export function assistantTitle(short) {
  const raw = String(short || '').trim()
  if (!raw) return 'Trợ lý AI - P.Mẫu'
  if (/^[PV]\./i.test(raw)) return `Trợ lý AI - ${raw}`
  return `Trợ lý AI - P.${raw}`
}
