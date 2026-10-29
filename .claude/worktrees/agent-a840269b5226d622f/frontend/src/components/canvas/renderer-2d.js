/** Bộ vẽ Canvas 2D — đường lùi khi máy không có WebGPU, CÙNG giao diện với `renderer-webgpu.js`.
 *
 * Giao diện chung (cả hai bộ vẽ đều phải đủ các hàm này):
 *   loai                       'webgpu' | '2d'
 *   datKichThuoc(rong, cao, dpr)   cỡ khung vẽ theo pixel CSS + tỷ lệ màn
 *   datLop(ten, nguon)         nạp/nạp lại ảnh cho một lớp (nguon = ảnh/canvas, hoặc null = trống)
 *   datTrangThaiLop(ten, {hien, doMo})
 *   datKhungNhin({zoom, panX, panY}) + datTheGioi(W, H)   trang cỡ W×H pixel ảnh gốc
 *   ve()                       vẽ lại ngay
 *   huy()                      giải phóng
 */

/** Thứ tự vẽ từ DƯỚI lên TRÊN. */
export const TEN_LOP = ['goc', 'sach', 'dich', 'matna']

export function taoRenderer2D(canvas) {
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Không mở được canvas 2D')
  let rong = 0
  let cao = 0
  let dpr = 1
  let W = 0
  let H = 0
  let khung = { zoom: 1, panX: 0, panY: 0 }
  const nguon = {}
  const trangThai = {
    goc: { hien: false, doMo: 1 }, sach: { hien: true, doMo: 1 },
    dich: { hien: true, doMo: 1 }, matna: { hien: true, doMo: 0.6 },
  }

  function ve() {
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    if (!W || !H) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.imageSmoothingEnabled = true
    for (const ten of TEN_LOP) {
      const s = nguon[ten]
      const tt = trangThai[ten]
      if (!s || !tt.hien || tt.doMo <= 0) continue
      ctx.globalAlpha = tt.doMo
      ctx.drawImage(s, khung.panX, khung.panY, W * khung.zoom, H * khung.zoom)
    }
    ctx.globalAlpha = 1
  }

  return {
    loai: '2d',
    datKichThuoc(r, c, tyLe = 1) {
      rong = r; cao = c; dpr = tyLe || 1
      canvas.width = Math.max(1, Math.round(r * dpr))
      canvas.height = Math.max(1, Math.round(c * dpr))
      ve()
    },
    datTheGioi(w, h) { W = w; H = h },
    datLop(ten, s) { nguon[ten] = s || null },
    datTrangThaiLop(ten, tt) { trangThai[ten] = { ...trangThai[ten], ...tt } },
    datKhungNhin(k) { khung = k },
    ve,
    huy() { for (const k of Object.keys(nguon)) nguon[k] = null },
  }
}
