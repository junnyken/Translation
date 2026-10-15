/** Mặt nạ cọ: một canvas 2D ẨN cùng cỡ ẢNH GỐC.
 *
 * Lưu theo NÉT chứ không chỉ theo điểm ảnh: hoàn tác mặt nạ là bỏ nét cuối rồi vẽ lại các nét
 * còn lại. Hiển thị tô đỏ đặc (độ mờ do lớp "Mặt nạ cọ" quyết); khi gửi đi mới đổi sang
 * trắng/đen.
 */
const MAU_TO = '#ef4444'

export function taoMatNa(W, H) {
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')
  let nets = []

  function veNet(net, tuDiem = 0) {
    if (!ctx) return
    const d = net.diem
    ctx.save()
    ctx.globalCompositeOperation = net.tay ? 'destination-out' : 'source-over'
    ctx.strokeStyle = MAU_TO
    ctx.fillStyle = MAU_TO
    ctx.lineWidth = net.co
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    if (d.length === 1) {
      ctx.beginPath()
      ctx.arc(d[0].x, d[0].y, net.co / 2, 0, Math.PI * 2)
      ctx.fill()
    } else {
      ctx.beginPath()
      ctx.moveTo(d[Math.max(0, tuDiem - 1)].x, d[Math.max(0, tuDiem - 1)].y)
      for (let i = Math.max(1, tuDiem); i < d.length; i++) ctx.lineTo(d[i].x, d[i].y)
      ctx.stroke()
    }
    ctx.restore()
  }

  function veLai() {
    if (!ctx) return
    ctx.clearRect(0, 0, W, H)
    for (const n of nets) veNet(n)
  }

  return {
    canvas, W, H,
    veNet,
    get nets() { return nets },
    them(net) { nets.push(net) },
    boNetCuoi() { const n = nets.pop(); veLai(); return n },
    themLai(net) { nets.push(net); veNet(net) },
    xoaHet() { nets = []; veLai() },
    /** Có nét TÔ nào không (nét tẩy một mình không tạo ra vùng cần xoá). */
    coTo() { return nets.some((n) => !n.tay) },
    /** PNG đúng cỡ ảnh gốc: điểm đã tô = trắng đục, còn lại = đen. */
    async xuatPng() {
      const nguon = ctx.getImageData(0, 0, W, H)
      const ra = ctx.createImageData(W, H)
      const s = nguon.data
      const o = ra.data
      for (let i = 0; i < s.length; i += 4) {
        const v = s[i + 3] >= 128 ? 255 : 0
        o[i] = v; o[i + 1] = v; o[i + 2] = v; o[i + 3] = 255
      }
      const tam = document.createElement('canvas')
      tam.width = W
      tam.height = H
      tam.getContext('2d').putImageData(ra, 0, 0)
      return new Promise((xong, hong) => {
        tam.toBlob((b) => (b ? xong(b) : hong(new Error('Không tạo được ảnh mặt nạ'))), 'image/png')
      })
    },
  }
}
