import { describe, expect, it } from 'vitest'
import {
  duongDanChapter, duongDanRaSoat, duongDanTaoChapter, duongDanTrangChu, duongDanXuat,
} from '../src/lib/navigation.js'

const GOC = 'http://127.0.0.1:5174'
const MA = '67094721-c9e4-4231-896d-83b555205a42'
const MA_TRANG = 'd6c604ed-75f0-4fcf-b2f8-1afe25ae8cb5'

describe('bộ dựng địa chỉ — bám ĐÚNG route thật của web app', () => {
  // Đo ngày 2026-08-30: `frontend/src/App.jsx` chọn màn bằng hash, không có router.
  it('tạo chapter = trang chủ', () => {
    expect(duongDanTaoChapter(GOC)).toBe(`${GOC}/`)
    expect(duongDanTrangChu(GOC)).toBe(`${GOC}/`)
  })

  it('chapter dùng #project=', () => {
    expect(duongDanChapter(GOC, MA)).toBe(`${GOC}/#project=${MA}`)
  })

  it('rà soát dùng #page=', () => {
    expect(duongDanRaSoat(GOC, MA_TRANG)).toBe(`${GOC}/#page=${MA_TRANG}`)
  })

  it('xuất KHÔNG có route riêng — trả về đúng màn chapter, không bịa #export=', () => {
    expect(duongDanXuat(GOC, MA)).toBe(duongDanChapter(GOC, MA))
    expect(duongDanXuat(GOC, MA)).not.toContain('export')
  })

  it('chuẩn hoá địa chỉ gốc trước khi ghép', () => {
    expect(duongDanChapter('http://LOCALHOST:5174/', MA)).toBe(`http://localhost:5174/#project=${MA}`)
  })
})

describe('bộ dựng địa chỉ — từ chối đầu vào bẩn', () => {
  it.each([
    ['gốc không phải loopback', 'http://evil.example:5174', MA],
    ['gốc có đường dẫn', 'http://127.0.0.1:5174/api', MA],
    ['gốc là javascript:', 'javascript:alert(1)', MA],
    ['gốc rỗng', '', MA],
  ])('ném lỗi khi %s', (_ten, goc, ma) => {
    expect(() => duongDanChapter(goc, ma)).toThrow()
  })

  it.each([
    ['đi lùi thư mục', '../../etc/passwd'],
    ['chèn query', `${MA}?next=http://evil.example`],
    ['chèn hash', `${MA}#khac`],
    ['javascript', 'javascript:alert(1)'],
    ['data url', 'data:text/html,x'],
    ['rỗng', ''],
    ['null', null],
    ['số', 7],
  ])('ném lỗi khi mã bẩn: %s', (_ten, ma) => {
    expect(() => duongDanChapter(GOC, ma)).toThrow()
    expect(() => duongDanRaSoat(GOC, ma)).toThrow()
    expect(() => duongDanXuat(GOC, ma)).toThrow()
  })

  it('không có đường nào nối chuỗi tự do vào query', () => {
    // Mã đã qua `chuanHoaMa` nên chỉ còn ký tự [0-9a-f-]; không thể chứa & ? # hay khoảng trắng.
    const d = duongDanChapter(GOC, MA)
    expect(d.split('#')[1]).toMatch(/^project=[0-9a-f-]+$/)
  })
})
