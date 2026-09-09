import { useEffect, useRef, useState } from 'react'
import * as api from '../api.js'

/** Phóng to đúng vùng chữ trên ẢNH GỐC (chưa xoá chữ) để đối chiếu `raw_text` (E21).
 *
 * `typeset-preview` (dùng để vẽ khung ở màn chính) đã xoá chữ gốc — không đối chiếu được. Vì
 * vậy modal này tự tải riêng `/pages/{id}/original-image`, chỉ khi bấm mở — không tải sẵn cho
 * mọi vùng, phần lớn thời gian người dùng không cần nhìn ảnh gốc.
 *
 * Vẽ bằng canvas thay vì CSS crop: `drawImage` với vùng nguồn = bbox (pixel ẢNH GỐC, đúng đơn vị
 * `region.bbox` đã trả về) phóng lên kích thước lớn hơn hẳn — không phụ thuộc trình duyệt co
 * ảnh thế nào, và tự nới thêm lề quanh bbox để còn thấy được bối cảnh (bong bóng, nét vẽ xung
 * quanh), không chỉ đúng khung chữ nhật sát mép.
 */
export default function ZoomCropModal({ pageId, bbox, onClose }) {
  const canvasRef = useRef(null)
  const hopRef = useRef(null)
  const [loi, setLoi] = useState(null)
  const [dangTai, setDangTai] = useState(true)

  useEffect(() => {
    const nghe = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', nghe)
    hopRef.current?.focus()
    return () => window.removeEventListener('keydown', nghe)
  }, [onClose])

  useEffect(() => {
    let huyBo = false
    let urlBlob = null
    ;(async () => {
      try {
        urlBlob = await api.taiVeBlobUrl(api.duongDanAnhGoc(pageId))
        const img = new Image()
        img.src = urlBlob
        await img.decode()
        if (huyBo) return

        // Nới lề quanh bbox 40% mỗi chiều (tối thiểu 24px) — đủ thấy bối cảnh quanh chữ, và kẹp
        // trong biên ảnh để không vẽ ra ngoài.
        const leX = Math.max(24, bbox.w * 0.4)
        const leY = Math.max(24, bbox.h * 0.4)
        const sx = Math.max(0, bbox.x - leX)
        const sy = Math.max(0, bbox.y - leY)
        const sw = Math.min(img.naturalWidth - sx, bbox.w + leX * 2)
        const sh = Math.min(img.naturalHeight - sy, bbox.h + leY * 2)

        // Phóng tới khi cạnh dài nhất chạm ~900px màn hình, không phóng thêm vô ích với vùng đã
        // to sẵn (ảnh vỡ hạt không giúp đọc rõ hơn).
        const tiLe = Math.min(6, Math.max(1, 900 / Math.max(sw, sh)))
        const canvas = canvasRef.current
        canvas.width = Math.round(sw * tiLe)
        canvas.height = Math.round(sh * tiLe)
        const ctx = canvas.getContext('2d')
        ctx.imageSmoothingEnabled = false // giữ nét răng cưa thật, không làm mờ chữ nhỏ thêm
        ctx.drawImage(img, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height)

        // Khung đỏ đánh dấu ĐÚNG bbox (phân biệt với phần lề vừa nới thêm quanh nó).
        ctx.strokeStyle = 'rgba(220,38,38,.85)'
        ctx.lineWidth = 2
        ctx.strokeRect(
          Math.round((bbox.x - sx) * tiLe), Math.round((bbox.y - sy) * tiLe),
          Math.round(bbox.w * tiLe), Math.round(bbox.h * tiLe),
        )
        setDangTai(false)
      } catch (e) {
        if (!huyBo) { setLoi(String(e?.message || e)); setDangTai(false) }
      }
    })()
    return () => { huyBo = true; if (urlBlob) URL.revokeObjectURL(urlBlob) }
  }, [pageId, bbox])

  return (
    <div className="lop-phu" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="hop-thoai hop-thoai-rong" role="dialog" aria-modal="true"
           aria-labelledby="tieu-de-phong-to" tabIndex={-1} ref={hopRef}>
        <h2 id="tieu-de-phong-to">Ảnh gốc — chưa xoá chữ</h2>
        <p className="ghi-chu">
          Khung đỏ là đúng vùng máy đang đọc. So chữ trong khung với ô "chữ gốc" bên dưới trước
          khi quyết định có cần gõ lại không.
        </p>
        {dangTai && <p className="ghi-chu">Đang tải ảnh gốc…</p>}
        {loi && <p className="canh-bao">Không tải được ảnh gốc: {loi}</p>}
        <div className="khung-anh-phong-to">
          <canvas ref={canvasRef} hidden={dangTai || !!loi} />
        </div>
        <div className="hang nut">
          <button onClick={onClose}>Đóng</button>
        </div>
      </div>
    </div>
  )
}
