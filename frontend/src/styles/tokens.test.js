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

/** Đọc một token màu dạng hex. Cố ý KHÔNG chấp nhận thiếu: token không còn là hex (đổi sang
 *  `color-mix`, `rgb()`…) thì bài này phải đỏ để người đổi biết phép đo đã hết hiệu lực. */
function mau(ten) {
  const m = NGUON.match(new RegExp(`--${ten}:\\s*(#[0-9a-fA-F]{6})\\s*;`))
  if (!m) throw new Error(`không đọc được --${ten} dạng hex trong tokens.css`)
  return m[1]
}

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

describe('bảng màu — tương phản đo từ tokens.css', () => {
  it('phép đo tự kiểm: trắng trên đen là 21:1, cùng một màu là 1:1', () => {
    // Không có bài tự kiểm này thì một lỗi trong chính `tiLe` sẽ làm MỌI khẳng định dưới đây
    // thành vô nghĩa mà vẫn xanh.
    expect(tiLe('#ffffff', '#000000')).toBeCloseTo(21, 1)
    expect(tiLe('#5546cc', '#5546cc')).toBeCloseTo(1, 5)
  })

  it.each([
    ['chữ thường trên nền', 'chu', 'nen', 12],
    ['chữ thường trên thẻ', 'chu', 'the', 12],
    ['chữ phụ trên nền', 'mo', 'nen', 4.5],
    ['chữ phụ trên thẻ', 'mo', 'the', 4.5],
    ['liên kết trên nền', 'mau-chinh-dam', 'nen', 4.5],
    ['màu chính trên nền tím nhạt', 'mau-chinh', 'mau-chinh-nhat', 4.5],
    ['nhãn ok', 'ok', 'ok-nen', 4.5],
    ['nhãn cảnh báo', 'canh', 'canh-nen', 4.5],
    ['nhãn lỗi', 'loi', 'loi-nen', 4.5],
    ['nhãn tin', 'tin', 'tin-nen', 4.5],
  ])('%s đạt AA', (_ten, truoc, sau, can) => {
    expect(tiLe(mau(truoc), mau(sau))).toBeGreaterThanOrEqual(can)
  })

  it('chữ TRẮNG trên nút chính đạt AA — nút chính là chỗ chữ trắng duy nhất', () => {
    expect(tiLe('#ffffff', mau('mau-chinh'))).toBeGreaterThanOrEqual(4.5)
  })

  it('`--mo-nhat` đạt 3:1 (chỉ dùng cho chữ giảm nhấn), nhưng KHÔNG được dùng thay `--mo`', () => {
    // Hai đầu của cùng một ràng buộc: đủ sáng cho thành phần giao diện, và *không* đủ cho chữ
    // thường — để không ai lặng lẽ hạ `--mo` xuống mức này.
    const r = tiLe(mau('mo-nhat'), mau('nen'))
    expect(r).toBeGreaterThanOrEqual(3)
    expect(r).toBeLessThan(4.5)
  })

  it('màu ngữ nghĩa PHÂN BIỆT được với màu chính — không được trùng họ', () => {
    // `--tin` từng là xanh dương lúc màu chính cũng xanh, và khối thông tin trông y hệt nút hành
    // động. Bài này giữ lại bài học đó dưới dạng số: hai màu phải cách nhau về độ sáng.
    for (const ten of ['tin', 'ok', 'canh', 'loi']) {
      expect(mau(ten)).not.toBe(mau('mau-chinh'))
    }
  })
})
