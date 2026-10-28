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
})
