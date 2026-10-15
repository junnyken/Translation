import { taoRenderer2D } from './renderer-2d.js'
import { taoRendererWebGPU } from './renderer-webgpu.js'

/** Chọn bộ vẽ: WebGPU nếu máy có (có `navigator.gpu` VÀ adapter thật), không thì Canvas 2D.
 *
 * Trả `{ renderer, lyDoLui }`. `lyDoLui` là `null` khi dùng được WebGPU, còn lại là mã lý do để
 * giao diện hiện banner: 'khong-co-webgpu' | 'khong-co-adapter' | 'loi-khoi-tao'.
 *
 * Lưu ý: một thẻ canvas chỉ có MỘT loại ngữ cảnh. Nếu WebGPU đã chiếm thẻ rồi mới hỏng thì
 * `taoRenderer2D` ném lỗi — nơi gọi phải dựng thẻ canvas mới và gọi lại với `tuChoiGpu: true`.
 */
export async function taoRenderer(canvas, { gpu = globalThis.navigator?.gpu, tuChoiGpu = false } = {}) {
  let lyDo = null
  if (tuChoiGpu || !gpu) {
    lyDo = gpu ? 'loi-khoi-tao' : 'khong-co-webgpu'
  } else {
    try {
      return { renderer: await taoRendererWebGPU(canvas, gpu), lyDoLui: null }
    } catch (e) {
      lyDo = e?.message === 'khong-co-adapter' ? 'khong-co-adapter' : 'loi-khoi-tao'
    }
  }
  return { renderer: taoRenderer2D(canvas), lyDoLui: lyDo }
}
