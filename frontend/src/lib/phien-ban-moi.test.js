import { describe, expect, it, vi } from 'vitest'
import { bundleDaCu, cacScriptTrongHtml, kiemBanMoi, tenTep } from './phien-ban-moi.js'

const HTML_MOI = `<!doctype html><html><head>
  <script type="module" crossorigin src="/assets/index-MOI123.js"></script>
  <link rel="modulepreload" href="/assets/vendor-abc.js">
</head><body><div id="root"></div></body></html>`

describe('tenTep', () => {
  it('lấy tên tệp và bỏ query/hash', () => {
    expect(tenTep('/assets/index-a1.js')).toBe('index-a1.js')
    expect(tenTep('/assets/index-a1.js?t=99')).toBe('index-a1.js')
    expect(tenTep('https://x.dev/assets/index-a1.js#z')).toBe('index-a1.js')
  })

  it('không nổ với giá trị lạ', () => {
    expect(tenTep('')).toBe('')
    expect(tenTep(undefined)).toBe('')
    expect(tenTep(null)).toBe('')
    expect(tenTep(123)).toBe('')
  })
})

describe('cacScriptTrongHtml', () => {
  it('rút mọi script có src, cả nháy đơn lẫn nháy kép', () => {
    const html = `<script src="/a/one.js"></script><script type='module' src='/b/two.js'></script>`
    expect(cacScriptTrongHtml(html)).toEqual(['one.js', 'two.js'])
  })

  it('bỏ qua script nội tuyến (không có src)', () => {
    expect(cacScriptTrongHtml('<script>var a = 1</script>')).toEqual([])
  })

  it('trả rỗng với đầu vào không phải HTML', () => {
    expect(cacScriptTrongHtml('')).toEqual([])
    expect(cacScriptTrongHtml(undefined)).toEqual([])
  })
})

describe('bundleDaCu', () => {
  it('ĐÃ CŨ khi bundle đang chạy không còn được index.html trỏ tới', () => {
    expect(bundleDaCu({ urlDangChay: '/assets/index-CU999.js', html: HTML_MOI })).toBe(true)
  })

  it('CHƯA cũ khi bundle đang chạy vẫn có trong index.html', () => {
    expect(bundleDaCu({ urlDangChay: '/assets/index-MOI123.js', html: HTML_MOI })).toBe(false)
  })

  it('CHƯA cũ khi so URL tuyệt đối với src tương đối (cùng tên tệp)', () => {
    const url = 'https://translation-web.example/assets/index-MOI123.js'
    expect(bundleDaCu({ urlDangChay: url, html: HTML_MOI })).toBe(false)
  })

  // Chế độ dev: bundle là /src/main.jsx và index.html vẫn trỏ tới nó ⇒ tự đúng, không cần
  // nhánh đặc biệt cho dev.
  it('CHƯA cũ ở chế độ dev', () => {
    const html = '<script type="module" src="/src/main.jsx"></script>'
    expect(bundleDaCu({ urlDangChay: 'http://localhost:5173/src/main.jsx?t=1', html })).toBe(false)
  })

  describe('thà bỏ sót hơn báo sai', () => {
    it('không phán xét khi không biết mình đang chạy gì', () => {
      expect(bundleDaCu({ urlDangChay: '', html: HTML_MOI })).toBe(false)
      expect(bundleDaCu({ urlDangChay: undefined, html: HTML_MOI })).toBe(false)
    })

    it('không báo cũ khi HTML không parse ra script nào', () => {
      expect(bundleDaCu({ urlDangChay: '/assets/index-CU999.js', html: '<html>?</html>' }))
        .toBe(false)
      expect(bundleDaCu({ urlDangChay: '/assets/index-CU999.js', html: '' })).toBe(false)
    })
  })
})

describe('kiemBanMoi', () => {
  const dap = (html, ok = true) => vi.fn(async () => ({ ok, text: async () => html }))

  it('báo có bản mới khi bundle đang chạy đã bị thay', async () => {
    const f = dap(HTML_MOI)
    await expect(kiemBanMoi({ urlDangChay: '/assets/index-CU999.js', fetchFn: f })).resolves
      .toBe(true)
  })

  it('không báo khi vẫn là bundle mới nhất', async () => {
    const f = dap(HTML_MOI)
    await expect(kiemBanMoi({ urlDangChay: '/assets/index-MOI123.js', fetchFn: f })).resolves
      .toBe(false)
  })

  /** Test quan trọng nhất của tệp này. Mất `cache: 'no-store'` thì trình duyệt trả đúng bản đã
   *  cache, phép so luôn nói "không có bản mới", và cơ chế tự vô hiệu hoá — KHÔNG có lỗi nào nổ
   *  ra để ai đó phát hiện. Đây chính là cách đã dùng để phân biệt cache với deploy hỏng
   *  (REPORT_E21b §11.3). */
  it('LUÔN tải index.html với cache no-store', async () => {
    const f = dap(HTML_MOI)
    await kiemBanMoi({ urlDangChay: '/assets/index-CU999.js', fetchFn: f })
    expect(f).toHaveBeenCalledTimes(1)
    const [duong, tuyChon] = f.mock.calls[0]
    expect(tuyChon).toMatchObject({ cache: 'no-store' })
    expect(duong).toContain('/index.html')
  })

  it('im lặng khi mạng hỏng', async () => {
    const f = vi.fn(async () => { throw new Error('mất mạng') })
    await expect(kiemBanMoi({ urlDangChay: '/assets/index-CU999.js', fetchFn: f })).resolves
      .toBe(false)
  })

  it('im lặng khi index.html trả lỗi HTTP', async () => {
    const f = dap('', false)
    await expect(kiemBanMoi({ urlDangChay: '/assets/index-CU999.js', fetchFn: f })).resolves
      .toBe(false)
  })
})
