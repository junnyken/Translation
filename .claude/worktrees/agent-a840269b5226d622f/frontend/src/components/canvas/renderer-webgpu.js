/** Bộ vẽ WebGPU: mỗi lớp là một texture, ghép theo độ mờ, pan/zoom bằng cách đổi hình chữ nhật
 *  của lớp trong không gian màn. Giao diện y hệt `renderer-2d.js` (xem chú thích ở đó).
 *
 * `taoRenderer` (renderer.js) chỉ gọi hàm này khi `navigator.gpu` có thật và `requestAdapter`
 * trả về adapter; mọi lỗi khởi tạo ném ra để nơi gọi lùi về 2D.
 */
import { TEN_LOP } from './renderer-2d.js'

const SHADER = `
struct U { rect: vec4f, mo: vec4f };
@group(0) @binding(0) var<uniform> u: U;
@group(0) @binding(1) var smp: sampler;
@group(0) @binding(2) var tex: texture_2d<f32>;
struct VO { @builtin(position) pos: vec4f, @location(0) uv: vec2f };
@vertex fn vs(@builtin(vertex_index) i: u32) -> VO {
  var c = array<vec2f, 6>(vec2f(0,0), vec2f(1,0), vec2f(0,1), vec2f(0,1), vec2f(1,0), vec2f(1,1));
  let p = c[i];
  var o: VO;
  o.pos = vec4f(mix(u.rect.x, u.rect.z, p.x), mix(u.rect.y, u.rect.w, p.y), 0.0, 1.0);
  o.uv = vec2f(p.x, 1.0 - p.y);
  return o;
}
@fragment fn fs(in: VO) -> @location(0) vec4f {
  // Texture nạp ở dạng đã nhân sẵn alpha ⇒ nhân độ mờ vào cả bốn kênh.
  return textureSample(tex, smp, in.uv) * u.mo.x;
}`

// Hằng số cờ dùng của WebGPU (có sẵn ở `GPUTextureUsage`, ghi số phòng khi môi trường thiếu).
const TEX_COPY_DST = 0x02
const TEX_BINDING = 0x04
const TEX_RENDER = 0x10
const BUF_COPY_DST = 0x08
const BUF_UNIFORM = 0x40

export async function taoRendererWebGPU(canvas, gpu = globalThis.navigator?.gpu) {
  if (!gpu) throw new Error('khong-co-webgpu')
  const adapter = await gpu.requestAdapter()
  if (!adapter) throw new Error('khong-co-adapter')
  const device = await adapter.requestDevice()
  const ctx = canvas.getContext('webgpu')
  if (!ctx) throw new Error('khong-mo-duoc-ngu-canh')
  const dinhDang = gpu.getPreferredCanvasFormat()
  ctx.configure({ device, format: dinhDang, alphaMode: 'premultiplied' })

  const gioiHan = device.limits?.maxTextureDimension2D ?? 8192
  const module = device.createShaderModule({ code: SHADER })
  const pipeline = device.createRenderPipeline({
    layout: 'auto',
    vertex: { module, entryPoint: 'vs' },
    fragment: {
      module, entryPoint: 'fs',
      targets: [{
        format: dinhDang,
        blend: {
          color: { srcFactor: 'one', dstFactor: 'one-minus-src-alpha', operation: 'add' },
          alpha: { srcFactor: 'one', dstFactor: 'one-minus-src-alpha', operation: 'add' },
        },
      }],
    },
    primitive: { topology: 'triangle-list' },
  })
  const sampler = device.createSampler({ magFilter: 'linear', minFilter: 'linear' })

  let rong = 0
  let cao = 0
  let dpr = 1
  let W = 0
  let H = 0
  let khung = { zoom: 1, panX: 0, panY: 0 }
  const lop = {}
  for (const ten of TEN_LOP) {
    lop[ten] = {
      tex: null, bind: null, w: 0, h: 0, hien: ten !== 'goc', doMo: ten === 'matna' ? 0.6 : 1,
      ubo: device.createBuffer({ size: 32, usage: BUF_UNIFORM | BUF_COPY_DST }),
    }
  }

  /** Ảnh vượt giới hạn texture của GPU thì thu nhỏ trước, thay vì để lệnh nạp ném lỗi. */
  function chuanBiNguon(s) {
    const w = s.naturalWidth || s.width
    const h = s.naturalHeight || s.height
    if (w <= gioiHan && h <= gioiHan) return { s, w, h }
    const k = Math.min(gioiHan / w, gioiHan / h)
    const c = document.createElement('canvas')
    c.width = Math.floor(w * k); c.height = Math.floor(h * k)
    c.getContext('2d').drawImage(s, 0, 0, c.width, c.height)
    return { s: c, w: c.width, h: c.height }
  }

  function ve() {
    if (!W || !H) return
    const enc = device.createCommandEncoder()
    const pass = enc.beginRenderPass({
      colorAttachments: [{
        view: ctx.getCurrentTexture().createView(),
        clearValue: { r: 0, g: 0, b: 0, a: 0 }, loadOp: 'clear', storeOp: 'store',
      }],
    })
    pass.setPipeline(pipeline)
    const x0 = (khung.panX / rong) * 2 - 1
    const x1 = ((khung.panX + W * khung.zoom) / rong) * 2 - 1
    const yTren = 1 - (khung.panY / cao) * 2
    const yDuoi = 1 - ((khung.panY + H * khung.zoom) / cao) * 2
    for (const ten of TEN_LOP) {
      const l = lop[ten]
      if (!l.bind || !l.hien || l.doMo <= 0) continue
      device.queue.writeBuffer(l.ubo, 0, new Float32Array([x0, yDuoi, x1, yTren, l.doMo, 0, 0, 0]))
      pass.setBindGroup(0, l.bind)
      pass.draw(6)
    }
    pass.end()
    device.queue.submit([enc.finish()])
  }

  return {
    loai: 'webgpu',
    datKichThuoc(r, c, tyLe = 1) {
      rong = r; cao = c; dpr = tyLe || 1
      canvas.width = Math.max(1, Math.round(r * dpr))
      canvas.height = Math.max(1, Math.round(c * dpr))
      ve()
    },
    datTheGioi(w, h) { W = w; H = h },
    datLop(ten, nguon) {
      const l = lop[ten]
      if (!nguon) {
        l.tex?.destroy(); l.tex = null; l.bind = null
        return
      }
      const { s, w, h } = chuanBiNguon(nguon)
      if (!l.tex || l.w !== w || l.h !== h) {
        l.tex?.destroy()
        l.tex = device.createTexture({
          size: [w, h], format: 'rgba8unorm',
          usage: TEX_BINDING | TEX_COPY_DST | TEX_RENDER,
        })
        l.w = w; l.h = h
        l.bind = device.createBindGroup({
          layout: pipeline.getBindGroupLayout(0),
          entries: [
            { binding: 0, resource: { buffer: l.ubo } },
            { binding: 1, resource: sampler },
            { binding: 2, resource: l.tex.createView() },
          ],
        })
      }
      device.queue.copyExternalImageToTexture(
        { source: s }, { texture: l.tex, premultipliedAlpha: true }, [w, h],
      )
    },
    datTrangThaiLop(ten, tt) { Object.assign(lop[ten], tt) },
    datKhungNhin(k) { khung = k },
    ve,
    huy() {
      for (const ten of TEN_LOP) { lop[ten].tex?.destroy(); lop[ten].ubo.destroy() }
      ctx.unconfigure?.()
      device.destroy?.()
    },
  }
}
