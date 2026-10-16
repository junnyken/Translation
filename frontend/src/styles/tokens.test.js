/** E63 — canh ĐỘ TƯƠNG PHẢN của bảng màu, đo từ chính `tokens.css`.
 *
 * `tokens.css` tự khẳng định ở đầu tệp: *"Mọi tỷ lệ tương phản dưới đây đều ĐO bằng công thức
 * WCAG, không ước lượng bằng mắt."* Trước bài này, câu đó chỉ là một lời hứa trong chú thích —
 * không có gì bắt nó đúng. Lượt 24-09 và lượt 28-09 đều đổi cả bảng màu; lần nào cũng phải đo
 * tay, và một con số gõ nhầm trong chú thích thì không ai biết.
 *
 * Bài này đọc GIÁ TRỊ THẬT trong tệp rồi tự tính lại. Đổi màu mà làm tụt tương phản là đỏ ngay,
 * kể cả khi người đổi quên cập nhật chú thích.
 */
import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

/** `import.meta.url` dưới vitest+jsdom KHÔNG phải URL `file:` (nó là `http://localhost/…`), nên
 *  `fileURLToPath` ném ngay. Dò từ thư mục đang chạy, và nếu không thấy thì ném lỗi NÓI RÕ chỗ
 *  đã tìm — im lặng đọc nhầm tệp còn tệ hơn đỏ. */
const UNG_VIEN = ['src/styles/tokens.css', 'frontend/src/styles/tokens.css']
const DUONG = UNG_VIEN.map((d) => resolve(process.cwd(), d)).find(existsSync)
if (!DUONG) throw new Error(`không thấy tokens.css, đã tìm: ${UNG_VIEN.join(', ')} (từ ${process.cwd()})`)
const NGUON = readFileSync(DUONG, 'utf-8')

/** Tách các khối khai báo token. Ba trạng thái theme (ĐỢT 1 redesign):
 *  - sáng: khối `:root {` ĐẦU TIÊN;
 *  - tối theo máy: `:root:not([data-theme="light"]) {` trong @media (prefers-color-scheme: dark);
 *  - tối ép tay: `:root[data-theme="dark"] {`. */
function khoi(moDau) {
  const i = NGUON.indexOf(moDau)
  if (i < 0) throw new Error(`không thấy khối "${moDau}" trong tokens.css`)
  const bat = i + moDau.length
  let sau = 1
  let k = bat
  while (sau > 0 && k < NGUON.length) { const c = NGUON[k++]; if (c === '{') sau++; else if (c === '}') sau-- }
  return NGUON.slice(bat, k - 1)
}
const KHOI_SANG = khoi(':root {')
const KHOI_TOI_MAY = khoi(':root:not([data-theme="light"]) {')
const KHOI_TOI_TAY = khoi(':root[data-theme="dark"] {')

const chuanHoa = (t) => t.replace(/\s+/g, ' ').trim()

/** Đọc token của một theme. Màu dạng hex, hoặc `color-mix(in srgb, var(--a) P%, var(--b))` (mẫu tối
 *  dùng để suy nền ngữ nghĩa từ nền thẻ) — còn dạng khác thì NÉM LỖI để phép đo không im lặng hết
 *  hiệu lực. Theme tối kế thừa từ sáng những token nó không ghi đè. */
function mauTheme(khoiTheme, ten, sau = 0) {
  if (sau > 6) throw new Error(`vòng lặp var() ở --${ten}`)
  const tim = (k) => k.match(new RegExp(`--${ten}:\\s*([^;]+);`))
  const m = tim(khoiTheme) || tim(KHOI_SANG)
  if (!m) throw new Error(`không đọc được --${ten} trong tokens.css`)
  const v = m[1].trim()
  if (/^#[0-9a-fA-F]{6}$/.test(v)) return v
  const vv = v.match(/^var\(--([\w-]+)\)$/)
  if (vv) return mauTheme(khoiTheme, vv[1], sau + 1)
  const cm = v.match(/^color-mix\(in srgb,\s*var\(--([\w-]+)\)\s+(\d+)%,\s*var\(--([\w-]+)\)\)$/)
  if (cm) {
    const a = mauTheme(khoiTheme, cm[1], sau + 1)
    const b = mauTheme(khoiTheme, cm[3], sau + 1)
    const t = Number(cm[2]) / 100
    return '#' + [1, 3, 5].map((x) => {
      const mixed = Math.round(parseInt(a.slice(x, x + 2), 16) * t + parseInt(b.slice(x, x + 2), 16) * (1 - t))
      return mixed.toString(16).padStart(2, '0')
    }).join('')
  }
  throw new Error(`--${ten} không phải hex/color-mix/var đơn: "${v}"`)
}

const THEME = { sang: KHOI_SANG, toi: KHOI_TOI_TAY }
const mau = (ten) => mauTheme(KHOI_SANG, ten)

function doSang(hex) {
  const v = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
}

/** Công thức WCAG 2.x. */
function tiLe(a, b) {
  const [x, y] = [doSang(a), doSang(b)].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}

describe('bảng màu — tương phản đo từ tokens.css, CẢ hai theme', () => {
  it('phép đo tự kiểm: trắng trên đen là 21:1, cùng một màu là 1:1', () => {
    // Không có bài tự kiểm này thì một lỗi trong chính `tiLe` sẽ làm MỌI khẳng định dưới đây
    // thành vô nghĩa mà vẫn xanh.
    expect(tiLe('#ffffff', '#000000')).toBeCloseTo(21, 1)
    expect(tiLe('#5546cc', '#5546cc')).toBeCloseTo(1, 5)
  })

  it('hai khối tối (theo máy / ép tay) giống hệt nhau', () => {
    expect(chuanHoa(KHOI_TOI_MAY)).toBe(chuanHoa(KHOI_TOI_TAY))
  })

  it('theme tối thật sự tối: nền tối hơn chữ', () => {
    expect(doSang(mauTheme(THEME.toi, 'nen'))).toBeLessThan(doSang(mauTheme(THEME.toi, 'chu')))
    expect(doSang(mauTheme(THEME.toi, 'nen-canvas'))).toBeLessThan(0.02)
  })

  describe.each(Object.keys(THEME))('theme %s', (ten_theme) => {
    const m = (t) => mauTheme(THEME[ten_theme], t)

    it.each([
      ['chữ thường trên nền', 'chu', 'nen', 12],
      ['chữ thường trên thẻ', 'chu', 'the', 12],
      ['chữ phụ trên nền', 'mo', 'nen', 4.5],
      ['chữ phụ trên thẻ', 'mo', 'the', 4.5],
      ['chữ phụ trên thẻ mờ', 'mo', 'the-mo', 4.5],
      ['liên kết trên nền', 'mau-chinh-dam', 'nen', 4.5],
      ['liên kết trên thẻ', 'mau-chinh-dam', 'the', 4.5],
      ['màu chính trên nền tím nhạt', 'mau-chinh', 'mau-chinh-nhat', 4.5],
      ['nhãn ok', 'ok', 'ok-nen', 4.5],
      ['nhãn cảnh báo', 'canh', 'canh-nen', 4.5],
      ['nhãn cảnh báo đậm', 'canh-dam', 'canh-nen', 4.5],
      ['nhãn lỗi', 'loi', 'loi-nen', 4.5],
      ['nhãn tin', 'tin', 'tin-nen', 4.5],
      ['chữ trên canvas', 'chu-tren-canvas', 'nen-canvas', 4.5],
      ['chữ trên nút chính', 'tren-chinh', 'mau-chinh', 4.5],
      ['chữ trên nút nguy hiểm', 'tren-chinh', 'loi', 4.5],
    ])('%s đạt AA', (_ten, truoc, sau, can) => {
      expect(tiLe(m(truoc), m(sau))).toBeGreaterThanOrEqual(can)
    })

    it('viền ô nhập (--vien-o → --mo-nhat) đạt 3:1 trên nền, thẻ và thẻ mờ (WCAG 1.4.11)', () => {
      expect(NGUON).toMatch(/--vien-o:\s*var\(--mo-nhat\)/)
      for (const nen of ['nen', 'the', 'the-mo']) {
        expect(tiLe(m('mo-nhat'), m(nen))).toBeGreaterThanOrEqual(3)
      }
    })

    it('viền trang trí --vien-dam KHÔNG đạt 3:1 — nên không được dùng cho ô nhập', () => {
      // Khẳng định để ai đó "tiện tay" đổi viền ô nhập về --vien-dam sẽ phải đọc dòng này.
      expect(tiLe(m('vien-dam'), m('the'))).toBeLessThan(3)
    })
  })

  it('chữ TRẮNG trên nút chính (sáng) đạt AA', () => {
    expect(tiLe('#ffffff', mau('mau-chinh'))).toBeGreaterThanOrEqual(4.5)
  })

  it('`--mo-nhat` (sáng) chỉ ≥3:1, KHÔNG được thay `--mo` cho chữ thường', () => {
    // Hai đầu của cùng một ràng buộc: đủ sáng cho thành phần giao diện, và *không* đủ cho chữ
    // thường — để không ai lặng lẽ hạ `--mo` xuống mức này.
    const r = tiLe(mau('mo-nhat'), mau('nen'))
    expect(r).toBeGreaterThanOrEqual(3)
    expect(r).toBeLessThan(4.5)
  })

  it('màu ngữ nghĩa PHÂN BIỆT được với màu chính — không được trùng họ', () => {
    for (const ten of ['tin', 'ok', 'canh', 'loi']) {
      expect(mau(ten)).not.toBe(mau('mau-chinh'))
    }
  })

  it('thang chữ không có bậc dưới 12px', () => {
    const co = [...NGUON.matchAll(/--cc-[\w]+:\s*(\d+)px/g)].map((x) => Number(x[1]))
    expect(co.length).toBe(7)
    expect(Math.min(...co)).toBeGreaterThanOrEqual(12)
  })
})
