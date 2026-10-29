import { describe, expect, it, vi } from 'vitest'
import { bboxSauKeo, manSangAnh, vuaKhung, zoomQuanhDiem } from './hinh-hoc.js'
import { taoRenderer2D } from './renderer-2d.js'
import { taoRenderer } from './renderer.js'

describe('hình học canvas', () => {
  it('zoom quanh con trỏ giữ điểm ảnh dưới con trỏ đứng yên', () => {
    const v = { zoom: 0.5, panX: 40, panY: 10 }
    const truoc = manSangAnh(v, 300, 200)
    const moi = zoomQuanhDiem(v, 2, 300, 200)
    const sau = manSangAnh(moi, 300, 200)
    expect(sau.x).toBeCloseTo(truoc.x)
    expect(sau.y).toBeCloseTo(truoc.y)
  })

  it('vừa khung: không phóng quá 100% và căn giữa', () => {
    const v = vuaKhung(800, 600, 100, 100)
    expect(v.zoom).toBe(1)
    expect(v.panX).toBe(350)
    expect(v.panY).toBe(250)
  })

  it('kéo khung bị chặn trong trang và luôn ra số nguyên', () => {
    const b = { x: 10, y: 10, w: 100, h: 50 }
    expect(bboxSauKeo('move', b, -500, 0.4, 1000, 1000)).toEqual({ x: 0, y: 10, w: 100, h: 50 })
    expect(bboxSauKeo('move', b, 5000, 5000, 1000, 1000)).toEqual({ x: 900, y: 950, w: 100, h: 50 })
  })

  it('đổi cỡ không cho nhỏ hơn mức tối thiểu và lật góc đúng phía', () => {
    const b = { x: 100, y: 100, w: 100, h: 100 }
    expect(bboxSauKeo('se', b, -500, -500, 1000, 1000)).toEqual({ x: 100, y: 100, w: 8, h: 8 })
    expect(bboxSauKeo('nw', b, 20, 30, 1000, 1000)).toEqual({ x: 120, y: 130, w: 80, h: 70 })
  })
})

describe('renderer 2D', () => {
  function ctxGia() {
    return {
      setTransform: vi.fn(), clearRect: vi.fn(), drawImage: vi.fn(), globalAlpha: 1,
      imageSmoothingEnabled: true,
    }
  }
  it('chỉ vẽ lớp đang hiện, theo độ mờ, đúng thứ tự dưới → trên', () => {
    const ctx = ctxGia()
    const alphas = []
    ctx.drawImage.mockImplementation(() => alphas.push(ctx.globalAlpha))
    const canvas = { getContext: () => ctx, width: 0, height: 0 }
    const r = taoRenderer2D(canvas)
    r.datKichThuoc(800, 600, 1)
    r.datTheGioi(1000, 1000)
    r.datKhungNhin({ zoom: 0.5, panX: 10, panY: 20 })
    r.datLop('goc', { id: 'goc' })
    r.datLop('sach', { id: 'sach' })
    r.datLop('dich', { id: 'dich' })
    r.datTrangThaiLop('sach', { doMo: 0.5 })
    r.ve()
    expect(ctx.drawImage.mock.calls.map((c) => c[0].id)).toEqual(['sach', 'dich']) // gốc mặc định ẩn
    expect(ctx.drawImage).toHaveBeenLastCalledWith({ id: 'dich' }, 10, 20, 500, 500)
    expect(alphas.slice(-2)).toEqual([0.5, 1])
  })

  it('taoRenderer: không có gpu ⇒ 2D kèm lý do; có gpu nhưng adapter null ⇒ 2D', async () => {
    const canvas = { getContext: () => ctxGia() }
    const a = await taoRenderer(canvas, { gpu: undefined })
    expect([a.renderer.loai, a.lyDoLui]).toEqual(['2d', 'khong-co-webgpu'])
    const b = await taoRenderer(canvas, { gpu: { requestAdapter: async () => null } })
    expect([b.renderer.loai, b.lyDoLui]).toEqual(['2d', 'khong-co-adapter'])
  })
})
