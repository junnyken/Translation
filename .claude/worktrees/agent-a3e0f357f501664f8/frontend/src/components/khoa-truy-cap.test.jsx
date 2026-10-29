/** Auth slice A — giao diện nhập khoá truy cập.
 *
 * Máy chủ CÓ THỂ bật một khoá chung. Giao diện phải: chỉ hỏi khi máy chủ đòi, nhớ lại khoá, và
 * KHÔNG báo thành công trước khi thật sự thử được.
 */
import { describe, expect, it, beforeEach, vi } from 'vitest'
import * as api from '../api.js'

beforeEach(() => { localStorage.clear(); vi.restoreAllMocks() })

describe('lưu và đọc khoá', () => {
  it('lưu rồi đọc lại được, và cắt khoảng trắng thừa', () => {
    api.luuKhoa('  abc123  ')
    expect(api.docKhoa()).toBe('abc123')
  })

  it('chưa lưu thì trả chuỗi rỗng, KHÔNG phải null', () => {
    expect(api.docKhoa()).toBe('')
  })

  it('xoá được', () => {
    api.luuKhoa('abc'); api.xoaKhoa()
    expect(api.docKhoa()).toBe('')
  })
})

describe('nhận biết lỗi thiếu khoá', () => {
  it('401 là lỗi thiếu khoá — dạng Error', () => {
    expect(api.laLoiThieuKhoa(new Error('401: Thiếu hoặc sai khoá truy cập.'))).toBe(true)
  })

  it('401 là lỗi thiếu khoá — dạng CHUỖI (đúng thứ App truyền vào)', () => {
    // App lưu lỗi bằng `setLoi(e.message)` nên biến `loi` là một CHUỖI. Bản đầu của hàm này chỉ
    // đọc `e.message` ⇒ luôn trả false ⇒ ô nhập khoá KHÔNG BAO GIỜ hiện. Test cũ vẫn xanh vì nó
    // truyền `new Error(...)` — sai hình dạng so với mã thật, nên nó che mất đúng lỗi này.
    expect(api.laLoiThieuKhoa('401: Thiếu hoặc sai khoá truy cập.')).toBe(true)
  })

  it('các lỗi khác KHÔNG bị nhầm thành thiếu khoá', () => {
    // Nhầm 404/500 thành "thiếu khoá" sẽ bắt người dùng nhập lại một khoá vốn đang đúng.
    for (const m of ['404: không thấy', '500: lỗi máy chủ', 'Failed to fetch']) {
      expect(api.laLoiThieuKhoa(new Error(m))).toBe(false)
    }
    expect(api.laLoiThieuKhoa(undefined)).toBe(false)
  })
})

describe('gắn khoá vào request', () => {
  it('CÓ khoá thì mọi lời gọi đều mang header X-API-Key', async () => {
    api.luuKhoa('k-123')
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, json: async () => ({}),
    })
    await api.kiemKhoa()
    expect(spy.mock.calls[0][1].headers['X-API-Key']).toBe('k-123')
  })

  it('KHÔNG có khoá thì không gửi header rỗng', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, json: async () => ({}),
    })
    await api.kiemKhoa()
    const h = spy.mock.calls[0][1].headers
    expect(h?.['X-API-Key']).toBeUndefined()
  })
})
