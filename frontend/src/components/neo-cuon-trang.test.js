/** Mọi `getElementById(...)` phải trỏ tới một `id` CÓ THẬT trong mã nguồn.
 *
 * ## Vì sao cần test này
 *
 * Nút "Xuất chapter" ở bảng tóm tắt chapter gọi:
 *
 *     document.getElementById('bang-xuat')?.scrollIntoView(...)
 *
 * `ExportPanel` khai `className="bang-xuat"` — **class, không phải id**. Nên
 * `getElementById` trả `null`, `?.` nuốt gọn, và nút **không làm gì cả**: không lỗi, không
 * cảnh báo, không dấu hiệu nào. Người dùng bấm nút to nhất trên màn và không có gì xảy ra.
 *
 * Đây là lớp lỗi mà test render thường không bắt: `scrollIntoView` không tồn tại trong jsdom
 * nên test nào có mock nó cũng "xanh" bất kể id đúng hay sai. Nên kiểm ở **tầng mã nguồn**.
 *
 * Test này quét cả `src/`, nên nút cuộn thêm về sau cũng tự động được kiểm.
 */
import { describe, expect, it } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

function moiTep(thuMuc) {
  return readdirSync(thuMuc).flatMap((ten) => {
    const duong = join(thuMuc, ten)
    if (statSync(duong).isDirectory()) return moiTep(duong)
    // Bỏ file test ra khỏi phạm vi quét. Chính test này có chứa chuỗi `id="bang-xuat"` trong
    // biểu thức kiểm — để nguyên thì nó tự thoả mãn chính mình và xanh kể cả khi mã thật hỏng.
    // Đo được: bỏ bản sửa ra, test quét chung vẫn XANH cho tới khi loại file test.
    if (/\.test\.(jsx?|tsx?)$/.test(ten)) return []
    return /\.(jsx?|tsx?)$/.test(ten) ? [duong] : []
  })
}

describe('neo cuộn trang', () => {
  it('mọi getElementById đều trỏ tới một id có thật', () => {
    // Kèm `index.html`: `getElementById('root')` trỏ tới id khai trong đó, không phải trong src/.
    const tep = [...moiTep('src'), 'index.html']
    const tatCa = tep.map((d) => readFileSync(d, 'utf8')).join('\n')

    const canCo = new Set()
    for (const [, ten] of tatCa.matchAll(/getElementById\(\s*['"`]([^'"`]+)['"`]\s*\)/g)) {
      canCo.add(ten)
    }
    expect(canCo.size, 'không tìm thấy getElementById nào — test này đang rỗng nghĩa').toBeGreaterThan(0)

    const thieu = [...canCo].filter(
      (ten) => !new RegExp(`id=["'\`]${ten}["'\`]|id=\\{\\s*['"\`]${ten}['"\`]`).test(tatCa)
    )
    expect(thieu, `getElementById trỏ tới id KHÔNG tồn tại: ${thieu.join(', ')}`).toEqual([])
  })

  it('bảng xuất mang đúng id mà nút "Xuất chapter" cuộn tới', () => {
    // Kiểm riêng ca đã hỏng thật, bằng tên cụ thể — để nếu ai đó đổi tên một bên thì test
    // trên bắt được, còn nếu xoá cả hai bên thì test này bắt được.
    const panel = readFileSync('src/components/ExportPanel.jsx', 'utf8')
    // Đếm nhánh return thì mong manh (một nhánh viết một dòng, nhánh kia xuống dòng). Kiểm
    // thẳng điều cần đúng: KHÔNG được còn <section> nào mang class này mà thiếu id.
    const thieuId = panel.match(/<section(?![^>]*\bid=)[^>]*className="bang-xuat"/g) || []
    expect(thieuId, 'còn <section className="bang-xuat"> thiếu id — bấm lúc đó sẽ không cuộn đi đâu').toEqual([])
    expect((panel.match(/<section id="bang-xuat"/g) || []).length).toBeGreaterThanOrEqual(2)

    const tomTat = readFileSync('src/components/chapter/ChapterSummary.jsx', 'utf8')
    expect(tomTat).toMatch(/onXuat/)
  })
})
