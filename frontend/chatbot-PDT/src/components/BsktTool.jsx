/**
 * Công cụ Bổ sung kiến thức (Sau đại học) — module_7.
 * Dạng công cụ nhập liệu (giống AdmissionCalculator), nhúng file tĩnh public/bskt-tool.html
 * để giữ nguyên 100% logic tra cứu + nhật ký do Phòng TS&CTSV cung cấp.
 */
export default function BsktTool() {
  const src = `${import.meta.env.BASE_URL}bskt-tool.html`
  return (
    <div className="bskt-tool">
      <iframe
        title="Công cụ xét Bổ sung kiến thức"
        src={src}
        className="bskt-tool__frame"
        loading="eager"
      />
    </div>
  )
}
