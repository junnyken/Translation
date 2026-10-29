import { mauHex } from './hinh-hoc.js'

/** Hút màu: đọc đúng MỘT điểm ảnh của lớp ảnh trên cùng đang hiện, tại toạ độ ẢNH (x, y).
 *  Chỉ để xem mã màu — không ghi gì xuống máy chủ. Trả `null` nếu không đọc được. */
export function layMauTai(nguon, W, H, x, y) {
  try {
    const c = document.createElement('canvas')
    c.width = 1
    c.height = 1
    const ctx = c.getContext('2d', { willReadFrequently: true })
    const sw = nguon.naturalWidth || nguon.width
    const sh = nguon.naturalHeight || nguon.height
    const sx = Math.min(sw - 1, Math.max(0, Math.floor((x / W) * sw)))
    const sy = Math.min(sh - 1, Math.max(0, Math.floor((y / H) * sh)))
    ctx.drawImage(nguon, sx, sy, 1, 1, 0, 0, 1, 1)
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data
    return a === 0 ? null : mauHex(r, g, b)
  } catch {
    return null
  }
}
