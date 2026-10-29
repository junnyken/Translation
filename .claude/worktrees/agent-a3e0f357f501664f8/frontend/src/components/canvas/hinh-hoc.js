/** Phép tính toạ độ thuần cho màn canvas — không đụng DOM nên test được trực tiếp.
 *
 * Hai hệ toạ độ, đừng nhầm:
 *   - ẢNH: pixel của ảnh GỐC. `bbox` của vùng chữ lưu và gửi lên máy chủ theo hệ này.
 *   - MÀN: pixel CSS trong khung canvas. Quan hệ: màn = ảnh × zoom + dịch.
 */
export const ZOOM_MIN = 0.05
export const ZOOM_MAX = 8
export const CAN_DUOI = 8 // khung chữ không nhỏ hơn ngần này (pixel ảnh)

export const kepZoom = (z) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z))

/** Khung nhìn vừa trọn trang trong vùng `rong`×`cao`, chừa lề; không phóng quá 100%. */
export function vuaKhung(rong, cao, W, H, le = 24) {
  if (!W || !H || rong <= 0 || cao <= 0) return { zoom: 1, panX: 0, panY: 0 }
  const zoom = kepZoom(Math.min(1, (rong - 2 * le) / W, (cao - 2 * le) / H))
  return { zoom, panX: (rong - W * zoom) / 2, panY: (cao - H * zoom) / 2 }
}

/** Đổi zoom nhưng giữ điểm ảnh đang nằm dưới (px,py) đứng yên — cuộn chuột zoom quanh con trỏ. */
export function zoomQuanhDiem(view, zoomMoi, px, py) {
  const zoom = kepZoom(zoomMoi)
  const ax = (px - view.panX) / view.zoom
  const ay = (py - view.panY) / view.zoom
  return { zoom, panX: px - ax * zoom, panY: py - ay * zoom }
}

export const manSangAnh = (view, px, py) => ({
  x: (px - view.panX) / view.zoom,
  y: (py - view.panY) / view.zoom,
})

const kep = (v, thap, cao) => Math.min(cao, Math.max(thap, v))

/** Khung chữ sau khi kéo `dx,dy` (đã đổi sang pixel ẢNH). `kieu`: 'move' hoặc góc 'nw'|'ne'|'sw'|'se'.
 *  Luôn trả số nguyên (máy chủ lưu pixel nguyên) và nằm trong trang. */
export function bboxSauKeo(kieu, bbox, dx, dy, W, H) {
  if (kieu === 'move') {
    return {
      x: Math.round(kep(bbox.x + dx, 0, Math.max(0, W - bbox.w))),
      y: Math.round(kep(bbox.y + dy, 0, Math.max(0, H - bbox.h))),
      w: Math.round(bbox.w), h: Math.round(bbox.h),
    }
  }
  let trai = bbox.x
  let phai = bbox.x + bbox.w
  let tren = bbox.y
  let duoi = bbox.y + bbox.h
  if (kieu.includes('w')) trai = kep(trai + dx, 0, phai - CAN_DUOI)
  if (kieu.includes('e')) phai = kep(phai + dx, trai + CAN_DUOI, W)
  if (kieu.includes('n')) tren = kep(tren + dy, 0, duoi - CAN_DUOI)
  if (kieu.includes('s')) duoi = kep(duoi + dy, tren + CAN_DUOI, H)
  return {
    x: Math.round(trai), y: Math.round(tren),
    w: Math.round(phai - trai), h: Math.round(duoi - tren),
  }
}

export const mauHex = (r, g, b) =>
  `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`
