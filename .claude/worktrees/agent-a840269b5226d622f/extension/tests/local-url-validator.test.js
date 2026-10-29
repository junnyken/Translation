import { describe, expect, it } from 'vitest'
import { chuanHoaMa, kiemDiaChiLocal } from '../src/lib/local-url-validator.js'

describe('kiemDiaChiLocal — địa chỉ được nhận', () => {
  it.each([
    ['http://127.0.0.1:8010', 'http://127.0.0.1:8010'],
    ['http://localhost:5174', 'http://localhost:5174'],
    ['http://127.0.0.1:5174/', 'http://127.0.0.1:5174'],
    ['  http://localhost:5173  ', 'http://localhost:5173'],
    ['HTTP://LOCALHOST:5174', 'http://localhost:5174'],
    ['http://127.0.0.1:1', 'http://127.0.0.1:1'],
    ['http://127.0.0.1:65535', 'http://127.0.0.1:65535'],
  ])('nhận %s', (vao, ra) => {
    const kq = kiemDiaChiLocal(vao)
    expect(kq.ok).toBe(true)
    expect(kq.dia_chi).toBe(ra)
  })
})

describe('kiemDiaChiLocal — kho SSRF / lách loopback', () => {
  // Danh sách này là lý do tệp validator tồn tại. Mỗi dòng là một cách người ta thật sự dùng
  // để lách bộ lọc "chỉ localhost".
  it.each([
    ['localhost.evil.example', 'http://localhost.evil.example:8010'],
    ['tiền tố 127.0.0.1 nhưng tên miền khác', 'http://127.0.0.1.evil.example:8010'],
    ['loopback khác 127.0.0.2', 'http://127.0.0.2:8010'],
    ['IPv6 loopback', 'http://[::1]:8010'],
    ['IPv6 ánh xạ IPv4', 'http://[::ffff:127.0.0.1]:8010'],
    ['LAN riêng', 'http://192.168.1.5:8010'],
    ['LAN riêng 10.x', 'http://10.0.0.7:8010'],
    ['metadata cloud', 'http://169.254.169.254:80'],
    ['tên miền công cộng', 'http://example.com:8010'],
    ['tài khoản nhúng', 'http://admin:matkhau@127.0.0.1:8010'],
    ['tên đăng nhập nhúng', 'http://localhost@evil.example:8010'],
    ['giao thức https', 'https://127.0.0.1:8010'],
    ['giao thức file', 'file:///etc/passwd'],
    ['giao thức javascript', 'javascript:alert(1)'],
    ['giao thức data', 'data:text/html,<h1>x</h1>'],
    ['không giao thức (tương đối theo giao thức)', '//127.0.0.1:8010'],
    ['chỉ đường dẫn', '/api/v1/health'],
    ['có đường dẫn', 'http://127.0.0.1:8010/api'],
    ['đi lùi thư mục', 'http://127.0.0.1:8010/../quan-tri'],
    ['có query', 'http://127.0.0.1:8010?next=http://evil.example'],
    ['có hash', 'http://127.0.0.1:8010#project=x'],
    ['thiếu cổng', 'http://127.0.0.1'],
    ['thiếu cổng (localhost)', 'http://localhost'],
    ['cổng 0', 'http://127.0.0.1:0'],
    ['dấu chấm mã hoá', 'http://localhost%2eevil.example:8010'],
    ['xuống dòng chèn giữa', 'http://127.0.0.1:8010\nGET /x'],
    ['tab chèn giữa', 'http://127.0.0.1\t.evil.example:8010'],
    ['chuỗi rỗng', ''],
    ['chỉ khoảng trắng', '   '],
  ])('từ chối: %s', (_ten, vao) => {
    const kq = kiemDiaChiLocal(vao)
    expect(kq.ok).toBe(false)
    expect(typeof kq.ly_do).toBe('string')
    expect(kq.ly_do.length).toBeGreaterThan(0)
  })

  it.each([[null], [undefined], [123], [{}], [[]], [true]])(
    'từ chối kiểu dữ liệu không phải chuỗi: %s', (vao) => {
      expect(kiemDiaChiLocal(vao).ok).toBe(false)
    })

  it('từ chối địa chỉ quá dài', () => {
    expect(kiemDiaChiLocal(`http://127.0.0.1:8010${'a'.repeat(300)}`).ok).toBe(false)
  })

  it('không bao giờ trả về địa chỉ có đường dẫn/query/hash', () => {
    for (const v of ['http://127.0.0.1:8010', 'http://localhost:5174/']) {
      const kq = kiemDiaChiLocal(v)
      expect(kq.ok).toBe(true)
      expect(kq.dia_chi).toMatch(/^http:\/\/(localhost|127\.0\.0\.1):\d+$/)
    }
  })
})

describe('kiemDiaChiLocal — dạng IPv4 lạ được CHUẨN HOÁ, không phải bị chặn', () => {
  // Đo thật ngày 2026-08-30 trên Node 22 (cùng bộ phân tích WHATWG với trình duyệt):
  // `new URL('http://2130706433:8010').hostname` === '127.0.0.1'.
  //
  // Nên bốn dạng dưới đây KHÔNG phải đường lách — chúng đúng là loopback. Tính chất an toàn
  // thật sự nằm ở chỗ khác: hàm trả về địa chỉ **đã chuẩn hoá**, và mọi lượt `fetch`/`tabs.create`
  // về sau dùng chuỗi trả về đó chứ không bao giờ dùng lại chuỗi người dùng gõ. Không có khe hở
  // "bộ kiểm đọc một đằng, bộ gọi đọc một nẻo".
  it.each([
    ['thập phân', 'http://2130706433:8010'],
    ['hex', 'http://0x7f000001:8010'],
    ['bát phân', 'http://0177.0.0.1:8010'],
    ['rút gọn 127.1', 'http://127.1:8010'],
  ])('%s -> http://127.0.0.1:8010', (_ten, vao) => {
    const kq = kiemDiaChiLocal(vao)
    expect(kq.ok).toBe(true)
    expect(kq.dia_chi).toBe('http://127.0.0.1:8010')
  })

  it('dấu chấm mã hoá KHÔNG biến thành loopback', () => {
    // `localhost%2eevil.example` -> `localhost.evil.example`, tên miền của người khác.
    expect(kiemDiaChiLocal('http://localhost%2eevil.example:8010').ok).toBe(false)
  })
})

describe('chuanHoaMa', () => {
  it('nhận UUID và hạ về chữ thường', () => {
    expect(chuanHoaMa('67094721-C9E4-4231-896D-83B555205A42'))
      .toBe('67094721-c9e4-4231-896d-83b555205a42')
  })

  it.each([
    ['rỗng', ''],
    ['không phải uuid', 'chapter-1'],
    ['đi lùi thư mục', '../../etc/passwd'],
    ['chèn query', '67094721-c9e4-4231-896d-83b555205a42?x=1'],
    ['chèn hash', '67094721-c9e4-4231-896d-83b555205a42#y'],
    ['javascript', 'javascript:alert(1)'],
    ['data url', 'data:text/html,x'],
    ['thiếu ký tự', '67094721-c9e4-4231-896d-83b555205a4'],
    ['thừa ký tự', '67094721-c9e4-4231-896d-83b555205a422'],
    ['phiên bản 0 (không hợp lệ)', '67094721-c9e4-0231-896d-83b555205a42'],
    ['biến thể sai', '67094721-c9e4-4231-096d-83b555205a42'],
    ['kèm khoảng trắng giữa', '67094721 c9e4 4231 896d 83b555205a42'],
  ])('từ chối: %s', (_ten, vao) => {
    expect(chuanHoaMa(vao)).toBeNull()
  })

  it.each([[null], [undefined], [123], [{}]])('từ chối kiểu %s', (vao) => {
    expect(chuanHoaMa(vao)).toBeNull()
  })
})
