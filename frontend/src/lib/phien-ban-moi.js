/** Phát hiện tab đang chạy bundle CŨ sau khi frontend đã deploy bản mới.
 *
 * ## Vì sao cần
 *
 * `REPORT_E21b.md §11.3`: ai mở sẵn tab từ trước lúc deploy thì chạy **frontend cũ trên backend
 * mới** — đúng tổ hợp vỡ. Cụ thể đã xảy ra: sửa chữ gốc OCR rồi Lưu ⇒ phần sửa **đã ghi thành
 * công** nhưng giao diện báo lỗi tải job (`/jobs/null`), người dùng không biết đã lưu hay chưa.
 * Dữ liệu không mất, nhưng đó là một thông báo SAI. Deploy frontend trước **không** đóng được cửa
 * sổ này vì tab đang mở không tự nạp lại bundle.
 *
 * Lưu ý phạm vi: cơ chế này **không cứu được tab đang chạy bundle cũ hiện tại** — bundle cũ không
 * có mã này. Nó chỉ có tác dụng từ lần deploy SAU.
 *
 * ## Phép so
 *
 * Không đoán tên chunk (`index-<hash>.js`) vì tên đó do bộ đóng gói quyết định và đổi được. Câu
 * hỏi thực sự là: **bundle tôi đang chạy có còn được `index.html` hiện tại tham chiếu không?**
 * Không còn ⇒ tab đã cũ. Cách này tự đúng ở chế độ dev (bundle là `/src/main.jsx`, vẫn được
 * `index.html` trỏ tới) nên không cần nhánh đặc biệt cho dev.
 *
 * ## Nguyên tắc: thà bỏ sót hơn báo sai
 *
 * Mọi lỗi (mạng, HTML lạ, không parse được) đều trả `false`. Một banner "có bản mới" hiện sai sẽ
 * dạy người dùng phớt lờ nó, và lần thật sự cần thì họ cũng bỏ qua.
 */

/** Bỏ query/hash và lấy tên tệp cuối đường dẫn. `/assets/index-a1.js?t=9` -> `index-a1.js` */
export function tenTep(duong) {
  if (typeof duong !== 'string' || duong === '') return ''
  const sach = duong.split('?')[0].split('#')[0]
  const doan = sach.split('/')
  return doan[doan.length - 1] || ''
}

/** Rút tên tệp của mọi `<script src=...>` trong HTML. */
export function cacScriptTrongHtml(html) {
  if (typeof html !== 'string') return []
  const ra = []
  // Cố ý dùng regex chứ không DOMParser: chỉ cần src, và không muốn HTML lạ chạy được gì.
  const mau = /<script\b[^>]*\bsrc\s*=\s*["']([^"']+)["'][^>]*>/gi
  let khop = mau.exec(html)
  while (khop !== null) {
    const ten = tenTep(khop[1])
    if (ten !== '') ra.push(ten)
    khop = mau.exec(html)
  }
  return ra
}

/** `true` khi bundle đang chạy KHÔNG còn được index.html tham chiếu. */
export function bundleDaCu({ urlDangChay, html }) {
  const dangChay = tenTep(urlDangChay)
  if (dangChay === '') return false // không biết mình đang chạy gì ⇒ không phán xét
  const cacScript = cacScriptTrongHtml(html)
  if (cacScript.length === 0) return false // không parse được ⇒ im lặng, không báo sai
  return !cacScript.includes(dangChay)
}

/**
 * Tải lại `index.html` bỏ qua cache rồi so bundle.
 *
 * `cache: 'no-store'` là bắt buộc — thiếu nó thì trình duyệt trả đúng bản đã cache và phép so
 * luôn nói "không có bản mới", tức tự vô hiệu hoá chính mình. Đây là cách đã dùng để phân biệt
 * dứt điểm "cache trình duyệt" với "deploy hỏng" ở `REPORT_E21b.md §11.3`.
 */
export async function kiemBanMoi({ urlDangChay, duongIndex = '/index.html', fetchFn } = {}) {
  const layVe = fetchFn || (typeof fetch === 'function' ? fetch : null)
  if (!layVe) return false
  try {
    const res = await layVe(`${duongIndex}?_=${Date.now()}`, { cache: 'no-store' })
    if (!res || !res.ok) return false
    const html = await res.text()
    return bundleDaCu({ urlDangChay, html })
  } catch {
    return false // mạng hỏng không phải bằng chứng có bản mới
  }
}
