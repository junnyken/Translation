import { describe, expect, it, vi } from 'vitest'
import { taoMatNa } from './mat-na.js'
import { taoRendererWebGPU } from './renderer-webgpu.js'

describe('mặt nạ cọ', () => {
  it('xuất PNG đúng cỡ: điểm đã tô = trắng đục, còn lại = đen đục', async () => {
    const W = 3
    const H = 1
    // điểm 0 đã tô đặc, điểm 1 tô mờ (<50%), điểm 2 chưa tô
    const nguon = new Uint8ClampedArray([255, 0, 0, 255, 255, 0, 0, 90, 0, 0, 0, 0])
    let ghiRa = null
    const ctxs = []
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(function () {
      const c = {
        getImageData: () => ({ data: nguon }),
        createImageData: (w, h) => ({ data: new Uint8ClampedArray(w * h * 4) }),
        putImageData: (d) => { ghiRa = d },
        save() {}, restore() {}, beginPath() {}, arc() {}, fill() {}, stroke() {},
        moveTo() {}, lineTo() {}, clearRect() {},
      }
      ctxs.push(c)
      return c
    })
    let kichThuoc = null
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (cb, kieu) {
      kichThuoc = [this.width, this.height, kieu]
      cb(new Blob(['x'], { type: kieu }))
    })
    const mn = taoMatNa(W, H)
    const blob = await mn.xuatPng()
    expect(blob.type).toBe('image/png')
    expect(kichThuoc).toEqual([3, 1, 'image/png'])
    expect(Array.from(ghiRa.data)).toEqual([255, 255, 255, 255, 0, 0, 0, 255, 0, 0, 0, 255])
    vi.restoreAllMocks()
  })

  it('nét tẩy một mình không tính là có vùng tô', () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
    const mn = taoMatNa(10, 10)
    mn.them({ diem: [{ x: 1, y: 1 }], co: 4, tay: true })
    expect(mn.coTo()).toBe(false)
    mn.them({ diem: [{ x: 1, y: 1 }], co: 4, tay: false })
    expect(mn.coTo()).toBe(true)
    mn.boNetCuoi()
    expect(mn.coTo()).toBe(false)
    vi.restoreAllMocks()
  })
})

describe('renderer WebGPU (thiết bị giả)', () => {
  function gpuGia() {
    const lenh = { draw: 0, copy: [], writeBuffer: 0, submit: 0, texture: [] }
    const pass = {
      setPipeline() {}, setBindGroup() {}, draw: () => { lenh.draw += 1 }, end() {},
    }
    const device = {
      limits: { maxTextureDimension2D: 4096 },
      createShaderModule: () => ({}),
      createRenderPipeline: () => ({ getBindGroupLayout: () => ({}) }),
      createSampler: () => ({}),
      createBuffer: () => ({ destroy() {} }),
      createTexture: (o) => { lenh.texture.push(o.size); return { createView: () => ({}), destroy() {} } },
      createBindGroup: () => ({}),
      createCommandEncoder: () => ({ beginRenderPass: () => pass, finish: () => ({}) }),
      queue: {
        writeBuffer: () => { lenh.writeBuffer += 1 },
        submit: () => { lenh.submit += 1 },
        copyExternalImageToTexture: (...a) => lenh.copy.push(a),
      },
      destroy() {},
    }
    const gpu = {
      requestAdapter: async () => ({ requestDevice: async () => device }),
      getPreferredCanvasFormat: () => 'bgra8unorm',
    }
    const canvas = {
      getContext: (k) => (k === 'webgpu'
        ? { configure() {}, getCurrentTexture: () => ({ createView: () => ({}) }), unconfigure() {} }
        : null),
    }
    return { gpu, canvas, lenh }
  }

  it('mỗi lớp đang hiện là một lượt vẽ; lớp ẩn không vẽ; ảnh nạp vào texture riêng', async () => {
    const { gpu, canvas, lenh } = gpuGia()
    const r = await taoRendererWebGPU(canvas, gpu)
    expect(r.loai).toBe('webgpu')
    r.datKichThuoc(800, 600, 1)
    r.datTheGioi(1000, 1000)
    r.datKhungNhin({ zoom: 0.5, panX: 0, panY: 0 })
    r.datLop('goc', { width: 1000, height: 1000 })
    r.datLop('dich', { width: 2000, height: 2000 })
    r.ve()
    expect(lenh.copy).toHaveLength(2)
    expect(lenh.texture).toEqual([[1000, 1000], [2000, 2000]])
    expect(lenh.draw).toBe(1) // Ảnh gốc mặc định ẩn ⇒ chỉ vẽ "dich"
    r.datTrangThaiLop('goc', { hien: true })
    r.ve()
    expect(lenh.draw).toBe(3)
    r.datTrangThaiLop('dich', { doMo: 0 })
    r.ve()
    expect(lenh.draw).toBe(4)
  })

  it('không có adapter ⇒ ném lỗi để nơi gọi lùi về 2D', async () => {
    const { canvas } = gpuGia()
    await expect(taoRendererWebGPU(canvas, { requestAdapter: async () => null }))
      .rejects.toThrow('khong-co-adapter')
  })
})
