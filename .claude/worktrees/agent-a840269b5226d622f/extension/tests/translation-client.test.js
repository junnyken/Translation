import { describe, expect, it, vi } from 'vitest'
import { LOI, kiemKetNoi, layChapter } from '../src/lib/translation-client.js'

const GOC = 'http://127.0.0.1:8010'
const MA = '67094721-c9e4-4231-896d-83b555205a42'
const MA_TRANG = 'd6c604ed-75f0-4fcf-b2f8-1afe25ae8cb5'

const traLoi = (than, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => than,
})

describe('kiemKetNoi', () => {
  it('gọi ĐÚNG /api/v1/health — KHÔNG gọi /healthz', async () => {
    // Đo thật 2026-08-30: `/healthz` ở cổng giao diện (5174) trả về trang HTML của web app kèm
    // `Access-Control-Allow-Origin: *`, tức là "200 OK" ngay cả khi API đã chết. Chỉ đường
    // `/api/v1/*` mới thật sự đi xuống backend qua proxy.
    const fetchFn = vi.fn(async () => traLoi({ status: 'ok' }))
    const kq = await kiemKetNoi(GOC, { fetchFn })
    expect(fetchFn).toHaveBeenCalledOnce()
    expect(fetchFn.mock.calls[0][0]).toBe(`${GOC}/api/v1/health`)
    expect(fetchFn.mock.calls[0][0]).not.toContain('/healthz')
    expect(kq.ok).toBe(true)
  })

  it('200 kèm HTML (máy chủ giao diện trả trang SPA) KHÔNG được tính là kết nối được', async () => {
    // Đây chính là ca đã làm lượt đo đầu tiên báo sai.
    const fetchFn = vi.fn(async () => ({
      ok: true, status: 200, json: async () => { throw new SyntaxError('Unexpected token <') },
    }))
    const kq = await kiemKetNoi(GOC, { fetchFn })
    expect(kq.ok).toBe(false)
    expect(kq.ma).toBe(LOI.du_lieu_la)
  })

  it('không gửi cookie và không dùng bộ nhớ đệm', async () => {
    const fetchFn = vi.fn(async () => traLoi({ status: 'ok' }))
    await kiemKetNoi(GOC, { fetchFn })
    const tuy_chon = fetchFn.mock.calls[0][1]
    expect(tuy_chon.credentials).toBe('omit')
    expect(tuy_chon.cache).toBe('no-store')
    expect(tuy_chon.method).toBe('GET')
  })

  it('địa chỉ không hợp lệ thì KHÔNG gọi mạng', async () => {
    const fetchFn = vi.fn()
    const kq = await kiemKetNoi('http://evil.example:8010', { fetchFn })
    expect(fetchFn).not.toHaveBeenCalled()
    expect(kq.ma).toBe(LOI.dia_chi_sai)
  })

  it('mạng hỏng / CORS chặn -> một mã lỗi kể CẢ HAI khả năng', async () => {
    // Trình duyệt cố ý không phân biệt hai ca này, nên chữ hiển thị phải nêu cả hai.
    const fetchFn = vi.fn(async () => { throw new TypeError('Failed to fetch') })
    const kq = await kiemKetNoi(GOC, { fetchFn })
    expect(kq.ok).toBe(false)
    expect(kq.ma).toBe(LOI.khong_noi_duoc)
    expect(kq.mo_ta).toContain('chưa chạy')
    expect(kq.mo_ta).toContain('CORS')
  })

  it('quá hạn giờ -> mã riêng, không lẫn với mạng hỏng', async () => {
    const fetchFn = vi.fn(async () => {
      const e = new Error('abort'); e.name = 'AbortError'; throw e
    })
    expect((await kiemKetNoi(GOC, { fetchFn })).ma).toBe(LOI.het_gio)
  })

  it('máy chủ 500 -> lỗi máy chủ', async () => {
    const fetchFn = vi.fn(async () => traLoi({}, 500))
    expect((await kiemKetNoi(GOC, { fetchFn })).ma).toBe(LOI.loi_may_chu)
  })

  it('thân trả về không đúng khuôn -> KHÔNG coi là kết nối được', async () => {
    for (const than of [{ status: 'degraded' }, {}, null, 'ok']) {
      const fetchFn = vi.fn(async () => traLoi(than))
      const kq = await kiemKetNoi(GOC, { fetchFn })
      expect(kq.ok).toBe(false)
    }
  })

  it('thật sự huỷ khi quá hạn giờ (AbortController được nối dây)', async () => {
    const fetchFn = vi.fn((_d, { signal }) => new Promise((_giai, tu_choi) => {
      signal.addEventListener('abort', () => {
        const e = new Error('aborted'); e.name = 'AbortError'; tu_choi(e)
      })
    }))
    const kq = await kiemKetNoi(GOC, { fetchFn, het_gio: 10 })
    expect(kq.ma).toBe(LOI.het_gio)
  })
})

describe('layChapter', () => {
  const than_that = {
    id: MA,
    name: 'Chương 1',
    source_lang: 'en',
    target_lang: 'vi',
    intended_use: 'personal',
    status: 'active',
    created_at: '2026-08-30T09:00:00Z',
    updated_at: '2026-08-30T10:00:00Z',
    pages: [
      { id: MA_TRANG, order: 1, status: 'typeset_done' },
      { id: '5031a72b-40cc-4818-8734-db9ec0b831e4', order: 2, status: 'queued' },
    ],
  }

  it('gọi đúng endpoint có sẵn GET /api/v1/projects/{id}', async () => {
    const fetchFn = vi.fn(async () => traLoi(than_that))
    await layChapter(GOC, MA, { fetchFn })
    expect(fetchFn.mock.calls[0][0]).toBe(`${GOC}/api/v1/projects/${MA}`)
  })

  it('chỉ giữ lại các trường cần hiển thị', async () => {
    const fetchFn = vi.fn(async () => traLoi(than_that))
    const kq = await layChapter(GOC, MA, { fetchFn })
    expect(kq.ok).toBe(true)
    expect(Object.keys(kq.chapter).sort())
      .toEqual(['projectId', 'soTrang', 'status', 'title', 'trang', 'updatedAt'])
    // Ngôn ngữ nguồn/đích và mục đích sử dụng KHÔNG được mang về — panel không hiện chúng.
    expect(JSON.stringify(kq.chapter)).not.toContain('personal')
  })

  it('mã không hợp lệ thì KHÔNG gọi mạng', async () => {
    const fetchFn = vi.fn()
    const kq = await layChapter(GOC, '../../etc/passwd', { fetchFn })
    expect(fetchFn).not.toHaveBeenCalled()
    expect(kq.ok).toBe(false)
  })

  it('404 -> mã "không thấy" riêng để panel bỏ ghim mục chết', async () => {
    const fetchFn = vi.fn(async () => traLoi({ detail: 'Project không tồn tại' }, 404))
    expect((await layChapter(GOC, MA, { fetchFn })).ma).toBe(LOI.khong_thay)
  })

  it('thân trả về thiếu id -> dữ liệu lạ, không dựng chapter rỗng giả', async () => {
    const fetchFn = vi.fn(async () => traLoi({ name: 'x' }))
    expect((await layChapter(GOC, MA, { fetchFn })).ma).toBe(LOI.du_lieu_la)
  })

  it('bỏ qua trang có id hỏng thay vì để lọt vào địa chỉ', async () => {
    const fetchFn = vi.fn(async () => traLoi({
      ...than_that, pages: [{ id: '../x', order: 1, status: 'queued' }, than_that.pages[0]],
    }))
    const kq = await layChapter(GOC, MA, { fetchFn })
    expect(kq.chapter.trang).toHaveLength(1)
    expect(kq.chapter.trang[0].id).toBe(MA_TRANG)
  })

  it('pages không phải mảng -> danh sách trang rỗng, không sập', async () => {
    const fetchFn = vi.fn(async () => traLoi({ ...than_that, pages: null }))
    const kq = await layChapter(GOC, MA, { fetchFn })
    expect(kq.ok).toBe(true)
    expect(kq.chapter.trang).toEqual([])
    expect(kq.chapter.soTrang).toBe(0)
  })

  it('cắt tên chapter quá dài', async () => {
    const fetchFn = vi.fn(async () => traLoi({ ...than_that, name: 'x'.repeat(500) }))
    const kq = await layChapter(GOC, MA, { fetchFn })
    expect(kq.chapter.title.length).toBe(120)
  })
})
