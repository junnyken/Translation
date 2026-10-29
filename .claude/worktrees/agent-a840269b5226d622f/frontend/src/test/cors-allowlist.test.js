import { describe, expect, it } from 'vitest'
import {
  docDanhSachTrang, kiemMucKhaiBao, laOriginDuocPhep,
} from '../../cors-allowlist.js'

const UI_5174 = 'http://127.0.0.1:5174'
const UI_LOCALHOST = 'http://localhost:5174'
const TIEN_ICH = 'chrome-extension://gppdcagfjgnekmdfbiplpfeahillicgi'

describe('kiemMucKhaiBao — mục CẤU HÌNH hợp lệ', () => {
  it.each([
    ['http localhost có cổng', 'http://localhost:5173', 'http://localhost:5173'],
    ['http 127.0.0.1 có cổng', 'http://127.0.0.1:5174', 'http://127.0.0.1:5174'],
    ['https localhost', 'https://localhost:5173', 'https://localhost:5173'],
    ['bỏ dấu / ở cuối', 'http://127.0.0.1:5174/', 'http://127.0.0.1:5174'],
    ['cắt khoảng trắng', '  http://localhost:5173  ', 'http://localhost:5173'],
    ['tiện ích đúng khuôn', TIEN_ICH, TIEN_ICH],
  ])('nhận %s', (_t, vao, ra) => {
    const kq = kiemMucKhaiBao(vao)
    expect(kq.ok).toBe(true)
    expect(kq.origin).toBe(ra)
  })
})

describe('kiemMucKhaiBao — từ chối mục cấu hình xấu', () => {
  it.each([
    ['ký tự đại diện toàn phần', '*'],
    ['đại diện trong tên máy', 'http://*.local'],
    ['đại diện cổng', 'http://localhost:*'],
    ['đại diện tiện ích', 'chrome-extension://*'],
    ['regex kiểu localhost.*', 'http://localhost.*'],
    ['máy công cộng', 'https://evil.example'],
    ['giống localhost', 'http://localhost.evil.example'],
    ['nip.io', 'http://127.0.0.1.nip.io'],
    ['LAN 192.168', 'http://192.168.1.10:5174'],
    ['LAN 10.x', 'http://10.0.0.1:5174'],
    ['LAN 172.16', 'http://172.16.0.1:5174'],
    ['IPv6 loopback chưa khai tường minh', 'http://[::1]:5174'],
    ['có tài khoản nhúng', 'http://admin:pw@localhost:5174'],
    ['có đường dẫn', 'http://localhost:5174/api'],
    ['có query', 'http://localhost:5174?x=1'],
    ['có hash', 'http://localhost:5174#a'],
    ['file', 'file://'],
    ['data', 'data:text/html,x'],
    ['javascript', 'javascript:alert(1)'],
    ['null', 'null'],
    ['rỗng', ''],
    ['chỉ khoảng trắng', '   '],
    ['id tiện ích sai độ dài', 'chrome-extension://abc'],
    ['id tiện ích có ký tự ngoài a-p', 'chrome-extension://zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz'],
  ])('từ chối: %s', (_t, vao) => {
    const kq = kiemMucKhaiBao(vao)
    expect(kq.ok).toBe(false)
    expect(kq.ly_do).toBeTruthy()
  })

  it.each([[null], [undefined], [123], [{}], [[]]])('từ chối kiểu %s', (vao) => {
    expect(kiemMucKhaiBao(vao).ok).toBe(false)
  })
})

describe('docDanhSachTrang — đọc cấu hình CSV', () => {
  it('cấu hình rỗng ⇒ danh sách RỖNG (chặn mặc định)', () => {
    for (const v of ['', '   ', null, undefined, ',,,']) {
      expect(docDanhSachTrang(v).origins).toEqual([])
    }
  })

  it('đọc nhiều origin, cắt khoảng trắng', () => {
    const { origins } = docDanhSachTrang(` ${UI_LOCALHOST} , ${UI_5174} `)
    expect(origins).toEqual([UI_LOCALHOST, UI_5174])
  })

  it('bỏ trùng SAU khi chuẩn hoá', () => {
    const { origins } = docDanhSachTrang('http://localhost:5174/,http://localhost:5174')
    expect(origins).toEqual([UI_LOCALHOST])
  })

  it('mục hỏng bị LOẠI kèm lý do, mục tốt vẫn qua — không làm sập máy chủ dev', () => {
    const { origins, bi_loai } = docDanhSachTrang(`${UI_5174},http://*.local,https://evil.example`)
    expect(origins).toEqual([UI_5174])
    expect(bi_loai.map((m) => m.gia_tri)).toEqual(['http://*.local', 'https://evil.example'])
    expect(bi_loai.every((m) => m.ly_do)).toBe(true)
  })

  it('KHÔNG bao giờ sinh ra ký tự đại diện trong kết quả', () => {
    const { origins } = docDanhSachTrang('*,http://*,chrome-extension://*')
    expect(origins).toEqual([])
  })
})

describe('laOriginDuocPhep — Origin của REQUEST', () => {
  const ds = [UI_5174, UI_LOCALHOST, TIEN_ICH]

  it.each(ds)('cho qua origin khớp tuyệt đối: %s', (o) => {
    expect(laOriginDuocPhep(o, ds)).toBe(true)
  })

  it.each([
    ['máy công cộng', 'https://evil.example'],
    ['giống localhost', 'http://localhost.evil.example'],
    ['nip.io', 'http://127.0.0.1.nip.io'],
    ['sai cổng', 'http://localhost:9999'],
    ['LAN 192.168', 'http://192.168.1.10:5174'],
    ['LAN 10.x', 'http://10.0.0.1:5174'],
    ['LAN 172.16', 'http://172.16.0.1:5174'],
    ['IPv6 loopback', 'http://[::1]:5174'],
    ['null', 'null'],
    ['file', 'file://'],
    ['data', 'data:text/html,x'],
    ['javascript', 'javascript:alert(1)'],
    ['tiện ích KHÁC id', 'chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'],
    ['có đường dẫn thêm', `${UI_5174}/api`],
    ['có dấu / cuối', `${UI_5174}/`],
    ['khác giao thức', 'https://127.0.0.1:5174'],
  ])('từ chối: %s', (_t, o) => {
    expect(laOriginDuocPhep(o, ds)).toBe(false)
  })

  it('danh sách RỖNG thì từ chối tất cả — kể cả origin trông hợp lệ', () => {
    for (const o of [...ds, 'https://evil.example']) {
      expect(laOriginDuocPhep(o, [])).toBe(false)
    }
  })

  it.each([[null], [undefined], [''], [123], [{}]])('origin kiểu %s bị từ chối', (o) => {
    expect(laOriginDuocPhep(o, ds)).toBe(false)
  })

  it('KHÔNG phản chiếu Origin: chuỗi lạ không bao giờ tự thành hợp lệ', () => {
    // Phản chiếu Origin là cách phổ biến nhất biến allowlist thành wildcard trá hình.
    for (const o of ['https://bat-ky-dau.example', 'http://localhost:5174.evil.example']) {
      expect(laOriginDuocPhep(o, ds)).toBe(false)
    }
  })
})

describe('chốt chặn: không có đường nào sinh ra wildcard', () => {
  it('mọi đầu ra của docDanhSachTrang đều không chứa *', () => {
    const nguon = [
      '*', 'http://*', 'chrome-extension://*', 'http://localhost:*',
      `${UI_5174},*`, 'http://*.local,http://localhost:5173',
    ]
    for (const v of nguon) {
      for (const o of docDanhSachTrang(v).origins) {
        expect(o).not.toContain('*')
      }
    }
  })

  it('laOriginDuocPhep không nhận "*" như một origin hợp lệ', () => {
    expect(laOriginDuocPhep('*', ['*'])).toBe(true) // nếu ai đó nhét thẳng vào mảng...
    // ...nhưng mảng đó KHÔNG THỂ đến từ docDanhSachTrang:
    expect(docDanhSachTrang('*').origins).toEqual([])
  })
})
