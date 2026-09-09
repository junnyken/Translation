import { afterEach, describe, expect, it, vi } from 'vitest'
import { choJobXong, layLyDoDung } from './api.js'

afterEach(() => vi.restoreAllMocks())

/** Giả lập máy chủ ở tầng `fetch` — chặn ở tầng hàm không ăn thua vì module gọi thẳng hàm nội bộ,
 *  và chặn ở `fetch` cũng đúng hơn: nó đi qua đúng đường mà mã thật đi. */
function mayChuTraVe(danhSachTrangThai) {
  let i = 0
  vi.stubGlobal('fetch', vi.fn(async () => {
    const tt = danhSachTrangThai[Math.min(i++, danhSachTrangThai.length - 1)]
    return { ok: true, json: async () => (typeof tt === 'string' ? { status: tt } : tt) }
  }))
}

/** Lỗi thật đo ở E11: worker xử lý MỘT việc một lúc, nên khi bận thì việc căn lại chữ mất 108s.
 *  Giao diện cũ bỏ cuộc ở giây 42 rồi báo "quá lâu, chưa xong" — người dùng tưởng hỏng, trong khi
 *  việc vẫn chạy và xong ngay sau đó. */
describe('chờ việc chạy nền', () => {
  it('kiên nhẫn qua giai đoạn xếp hàng dài, không bỏ cuộc sớm', async () => {
    mayChuTraVe([...Array(79).fill('queued'), 'done'])
    const job = await choJobXong('j1', { nhipMs: 0 })
    expect(job.status).toBe('done')
    expect(fetch).toHaveBeenCalledTimes(80)   // giao diện cũ chết ở lần thứ 60
  })

  it('báo được là ĐANG CHỜ TỚI LƯỢT chứ không chỉ "đang chạy"', async () => {
    mayChuTraVe(['queued', 'queued', 'running', 'done'])
    const thay = []
    await choJobXong('j1', { nhipMs: 0, onTien: (j) => thay.push(j.status) })
    expect(thay).toEqual(['queued', 'queued', 'running', 'done'])
  })

  it('việc hỏng thì ném lỗi ngay, không chờ hết giờ', async () => {
    mayChuTraVe([{ status: 'failed', error_log: 'thiếu font' }])
    await expect(choJobXong('j1', { nhipMs: 0 })).rejects.toThrow('thiếu font')
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('hết kiên nhẫn thì nói "vẫn đang chạy", KHÔNG nói là hỏng', async () => {
    mayChuTraVe(['running'])
    const e = await choJobXong('j1', { soLanToiDa: 2, nhipMs: 0 }).catch((x) => x)
    expect(e.vanDangChay).toBe(true)
    expect(e.message).toContain('vẫn đang chạy')
    expect(e.message).not.toMatch(/hỏng|thất bại/i)
  })
})

/** E22 — lý do trang đứng im giờ có HAI nguồn, và thứ tự giữa chúng là một quyết định. */
describe('lý do trang đứng im', () => {
  const traVeDanhSach = (js) =>
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => js })))

  it('job đã hỏng được ưu tiên hơn suy luận theo nhịp tim', async () => {
    // Lý do ĐÃ CHỐT trong CSDL đáng tin hơn một suy luận "chắc là worker chết" theo nhịp tim.
    traVeDanhSach([
      { id: 'a', type: 'ocr', status: 'running', processing_state: 'worker_interrupted' },
      { id: 'b', type: 'inpaint', status: 'failed', error_log: 'thiếu font' },
    ])
    expect((await layLyDoDung('pg1')).id).toBe('b')
  })

  it('không có job hỏng thì mới lấy job bị worker bỏ dở', async () => {
    traVeDanhSach([
      { id: 'a', type: 'detect', status: 'done', processing_state: 'done' },
      { id: 'b', type: 'ocr', status: 'running', processing_state: 'worker_interrupted' },
    ])
    expect((await layLyDoDung('pg1')).id).toBe('b')
  })

  it('việc đang chạy BÌNH THƯỜNG không bị coi là lý do đứng im', async () => {
    // `running` + nhịp tim còn mới = máy đang làm thật. Báo đó là "lý do đứng im" thì lại thành
    // doạ người dùng về một thứ đang chạy đúng.
    traVeDanhSach([{ id: 'a', type: 'ocr', status: 'running', processing_state: 'running' }])
    expect(await layLyDoDung('pg1')).toBeNull()
  })
})
