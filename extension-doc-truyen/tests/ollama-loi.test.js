/** Ollama đang chạy nhưng model sập (HTTP 500) phải báo ĐÚNG nguyên nhân, không rơi sang
 * LM Studio rồi nói nhầm "chưa phát hiện Ollama" (ca thật 28/10: runner CUDA sập 0xc0000409).
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { dichTrangLocalGguf, LoiApi } from '../src/lib/api.js'

const blob = new Blob([new Uint8Array([1, 2, 3])], { type: 'image/png' })
const json = (body, status = 200) => new Response(JSON.stringify(body), { status })

afterEach(() => vi.unstubAllGlobals())

describe('dịch cục bộ bằng Ollama', () => {
  it('chat 500 do runner sập: báo lỗi model, KHÔNG thử LM Studio, KHÔNG nói "chưa phát hiện"', async () => {
    const goi = []
    vi.stubGlobal('fetch', async (url) => {
      goi.push(url)
      if (url.endsWith('/api/tags')) return json({ models: [{ name: 'qwen3-vl:8b' }] })
      return new Response('{"error":"exit status 0xc0000409 CUDA error"}', { status: 500 })
    })
    const loi = await dichTrangLocalGguf(blob).catch((e) => e)
    expect(loi).toBeInstanceOf(LoiApi)
    expect(loi.ma).toBe(500)
    expect(loi.message).toMatch(/0xc0000409/)
    expect(loi.message).toMatch(/server\.log/)
    expect(loi.message).not.toMatch(/chưa phát hiện/i)
    expect(goi.some((u) => u.includes(':1234'))).toBe(false)
  })

  it('Ollama không chạy: vẫn thử LM Studio rồi mới báo "chưa phát hiện"', async () => {
    vi.stubGlobal('fetch', async () => { throw new TypeError('Failed to fetch') })
    const loi = await dichTrangLocalGguf(blob).catch((e) => e)
    expect(loi.message).toMatch(/chưa phát hiện/i)
  })

  it('ưu tiên chọn đúng qwen3-vl:8b khi Ollama có nhiều model văn bản khác đứng trước', async () => {
    let modelDaGoi = ''
    vi.stubGlobal('fetch', async (url, init) => {
      if (url.endsWith('/api/tags')) {
        return json({ models: [{ name: 'llama3:8b' }, { name: 'qwen3-vl:8b' }] })
      }
      if (url.endsWith('/api/chat')) {
        modelDaGoi = JSON.parse(init.body).model
        return json({
          message: {
            content: JSON.stringify([{ box_2d: [100, 100, 300, 400], chu_goc: 'Hello', ban_dich: 'Xin chào' }]),
          },
        })
      }
      throw new TypeError('Failed to fetch')
    })
    const kq = await dichTrangLocalGguf(blob)
    expect(modelDaGoi).toBe('qwen3-vl:8b')
    expect(kq.vung).toHaveLength(1)
    expect(kq.vung[0].ban_dich).toBe('Xin chào')
  })

  it('tự động dùng Cầu nối App Windows (127.0.0.1:17890) khi đang mở để lấy OCR ONNX + ảnh đã xóa chữ 0đ', async () => {
    vi.stubGlobal('fetch', async (url) => {
      if (url.includes('127.0.0.1:17890/api/v1/local-bridge/dich-trang')) {
        return json({
          xong: true,
          engine: 'local_bridge_windows_app',
          vung: [{ x: 20, y: 30, w: 120, h: 60, chu_goc: 'ダンダダン', ban_dich: 'Dandadan!' }],
          anh_da_dich_data_url: 'data:image/jpeg;base64,AAA=',
        })
      }
      throw new Error('Không được gọi Ollama trực tiếp khi Local Bridge đã xử lý xong')
    })
    const kq = await dichTrangLocalGguf(blob)
    expect(kq.che_do).toBe('day_du')
    expect(kq.anh_da_dich_data_url).toBe('data:image/jpeg;base64,AAA=')
    expect(kq.vung[0].ban_dich).toBe('Dandadan!')
  })
})
