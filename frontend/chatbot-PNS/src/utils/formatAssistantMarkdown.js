/**
 * Chuẩn hóa văn bản từ LLM trước khi đưa vào ReactMarkdown:
 * chèn xuống dòng khi model dính "mã xét tuyển ... 2." hoặc danh sách số trên một dòng.
 */
export function formatAssistantMarkdown(text) {
  if (!text || typeof text !== 'string') return text
  let s = text.replace(/\r\n/g, '\n')

  // "Mã xét tuyển: ... 419 2. Công nghệ..." → xuống dòng trước "2."
  s = s.replace(
    /(Mã xét tuyển:\s*[\d\sEeHh()+/,]+)\s+(\d{1,2})\.\s+(?=[A-ZÀÁÂÃẠẢĂÂÊÔƠƯĐ])/gu,
    '$1\n\n$2. '
  )

  // Mã 3–4 số (có thể có E/H, ngoặc) dính với mục danh sách tiếp theo: "419 2. Ngành"
  s = s.replace(
    /(\d{3,4}[EH]?(?:\s*\([^)]*\))?)\s+(\d{1,2})\.\s+(?=[A-ZÀÁÂÃẠẢĂÂÊÔƠƯĐ])/gu,
    '$1\n\n$2. '
  )

  // Sau dấu đóng ngoặc hoặc "sinh viên" dính "N. " (tiêu đề mới)
  s = s.replace(
    /(\)|sinh viên|học viên)\s+(\d{1,2})\.\s+(?=[A-ZÀÁÂÃẠẢĂÂÊÔƠƯĐ])/giu,
    '$1\n\n$2. '
  )

  // Mã tổ hợp (A01, X26, …) dính đoạn mới bắt đầu bằng "Năm"
  s = s.replace(/([A-Z]\d{2}:\s*[^\n]+)(\s+)(Năm\s+\d{4})/gu, '$1\n\n$3')

  // Gom quá nhiều dòng trống
  s = s.replace(/\n{4,}/g, '\n\n\n')

  // Không dùng trim() toàn chuỗi — dễ mất xuống dòng đầu/cuối mà LLM cố tình để
  return s.replace(/^\uFEFF/, '')
}
