import { useRef, useState } from 'react'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui'
import Icon from './Icon.jsx'
import Button from './Button.jsx'

/** Chọn ảnh bằng cách kéo-thả hoặc bấm — nhưng vẫn là `<input type="file">` thật, chỉ ẩn đi.
 *
 * Giữ input thật là điều kiện để trình duyệt, trình đọc màn hình và bàn phím hoạt động đúng;
 * tự vẽ một vùng thả rồi bỏ input là đánh đổi độ tin cậy lấy vẻ đẹp.
 * Vùng thả nhận cả Enter và Space vì người dùng bàn phím mong nó cư xử như một nút.
 */
const LOAI_HO_TRO = ['image/png', 'image/jpeg', 'image/webp']

/** ĐX-2 — gói `.zip`/`.cbz` nhận diện bằng ĐUÔI FILE, không bằng `f.type`.
 *
 * Lý do: trình duyệt báo MIME của `.cbz` rất tuỳ hệ điều hành — có máy trả
 * `application/x-zip-compressed`, có máy trả chuỗi RỖNG. Lọc theo `f.type` sẽ im lặng vứt đúng
 * cái gói người dùng vừa thả vào, và họ không hiểu vì sao. Phía máy chủ vẫn xét chữ ký đầu file
 * nên đuôi file sai cũng không lọt được.
 */
const DUOI_GOI = /\.(zip|cbz|pdf)$/i

export function locFileHopLe(files, chapNhanGoi = false) {
  const nhan = [], loai = []
  for (const f of files) {
    const duoc = LOAI_HO_TRO.includes(f.type) || (chapNhanGoi && DUOI_GOI.test(f.name || ''))
    ;(duoc ? nhan : loai).push(f)
  }
  return { nhan, loai }
}

export function coChuoi(so) {
  if (so < 1024) return `${so} B`
  if (so < 1024 * 1024) return `${(so / 1024).toFixed(0)} KB`
  return `${(so / 1024 / 1024).toFixed(1)} MB`
}

export default function Dropzone({
  files, onDoi, tatCa = false, id = 'vung-tha', chapNhanGoi = false,
}) {
  const { laEn } = useNgonNguUI()
  const oFile = useRef(null)
  const [dangKeo, setDangKeo] = useState(false)
  const [loi, setLoi] = useState(null)

  const them = (danhSach) => {
    const { nhan, loai } = locFileHopLe(Array.from(danhSach || []), chapNhanGoi)
    const mong = chapNhanGoi
      ? (laEn ? 'PNG/JPG/WebP images or ZIP/CBZ/PDF archives' : 'ảnh PNG/JPG/WebP hoặc gói ZIP/CBZ/PDF')
      : (laEn ? 'PNG/JPG/WebP images' : 'ảnh PNG/JPG/WebP')
    setLoi(loai.length
      ? (laEn
          ? `Skipped ${loai.length} unsupported file(s) (expected ${mong}): ${loai.map((f) => f.name).join(', ')}`
          : `Bỏ qua ${loai.length} tệp không phải ${mong}: ${loai.map((f) => f.name).join(', ')}`)
      : null)
    if (nhan.length) onDoi([...files, ...nhan])
  }

  const moChon = () => oFile.current?.click()

  return (
    <div className="vung-tha-boc">
      <div
        id={id}
        className={`vung-tha${dangKeo ? ' dang-keo' : ''}`}
        role="button"
        tabIndex={0}
        aria-label={laEn ? 'Select comic pages: click or drag files here' : 'Chọn ảnh trang truyện: bấm hoặc kéo tệp vào đây'}
        aria-disabled={tatCa || undefined}
        onClick={() => !tatCa && moChon()}
        onKeyDown={(e) => {
          if (tatCa) return
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); moChon() }
        }}
        onDragOver={(e) => { e.preventDefault(); setDangKeo(true) }}
        onDragLeave={() => setDangKeo(false)}
        onDrop={(e) => { e.preventDefault(); setDangKeo(false); them(e.dataTransfer.files) }}
      >
        <Icon ten="tai-len" co={24} />
        {/* Dòng chữ này phải nói ĐÚNG thứ ô file thật sự nhận. Lúc thêm ĐX-2 nó vẫn ghi mỗi
            "PNG, JPG" trong khi `accept` đã có `.zip,.cbz` — người dùng đọc dòng đó thì không
            bao giờ biết là thả được cả gói. Test jsdom soi `accept` nên không thấy; chỉ bấm
            tay trên trình duyệt thật mới lộ ra. */}
        <b>
          {chapNhanGoi
            ? (laEn
                ? 'Drag & drop comic images or archives here, or click to browse'
                : 'Kéo ảnh hoặc gói truyện vào đây, hoặc bấm để chọn')
            : (laEn
                ? 'Drag & drop images here or click to browse'
                : 'Kéo ảnh vào đây hoặc bấm để chọn')}
        </b>
        <span>
          {chapNhanGoi
            ? (laEn
                ? 'Supports PNG, JPG, WebP and .zip / .cbz / .pdf packages (1 package = full chapter).'
                : 'Hỗ trợ PNG, JPG, WebP và cả gói .zip / .cbz / .pdf (một gói = cả chapter).')
            : (laEn
                ? 'Supports PNG, JPG. You can select multiple pages at once.'
                : 'Hỗ trợ PNG, JPG. Có thể chọn nhiều trang một lúc.')}
        </span>
      </div>

      {/* Input THẬT, chỉ ẩn khỏi mắt — vẫn nằm trong cây tiếp cận của trình duyệt. */}
      <input
        ref={oFile}
        type="file"
        className="o-file-an"
        accept={chapNhanGoi
          ? 'image/png,image/jpeg,image/webp,.zip,.cbz,.pdf'
          : 'image/png,image/jpeg,image/webp'}
        multiple
        tabIndex={-1}
        disabled={tatCa}
        onChange={(e) => { them(e.target.files); e.target.value = '' }}
      />

      {loi && <div className="bang-loi nho">{loi}</div>}

      {files.length > 0 && (
        <>
          {/* Đếm và nói theo ĐÚNG thứ người dùng vừa chọn.
              Bắt được khi bấm tay trên Chromium: một gói `.cbz` chứa 3 trang bị đếm là
              "1 trang", kèm câu "thứ tự dưới đây chính là thứ tự trang trong chapter" — sai,
              vì với gói thì thứ tự nằm BÊN TRONG gói chứ không phải thứ tự trong danh sách này.
              Số file thì đếm đúng; chữ "trang" mới là chỗ nói sai. */}
          <p className="ghi-chu">
            {(() => {
              const soGoi = files.filter((f) => DUOI_GOI.test(f.name || '')).length
              const soAnh = files.length - soGoi
              if (soGoi === 0) {
                return laEn ? (
                  <>
                    <b>{soAnh}</b> page(s) · the order below{' '}
                    <b>is the exact page order</b> in the chapter.
                  </>
                ) : (
                  <>
                    <b>{soAnh}</b> trang · thứ tự dưới đây{' '}
                    <b>chính là thứ tự trang</b> trong chapter.
                  </>
                )
              }
              const phan = [
                soGoi > 0 && (laEn ? `${soGoi} archive(s)` : `${soGoi} gói`),
                soAnh > 0 && (laEn ? `${soAnh} loose image(s)` : `${soAnh} ảnh lẻ`),
              ].filter(Boolean).join(' + ')
              return laEn ? (
                <>
                  <b>{phan}</b> · actual page count is determined after unpacking. Pages inside an
                  archive are sorted by <b>filename</b>.
                </>
              ) : (
                <>
                  <b>{phan}</b> · số trang thật biết được sau khi mở gói. Trang trong gói được
                  xếp theo <b>tên tệp</b> bên trong nó, không theo thứ tự danh sách này.
                </>
              )
            })()}
          </p>
          <ol className="ds-file">
            {files.map((f, i) => (
              <li key={`${f.name}-${i}`}>
                <span className="stt">{i + 1}</span>
                <span className="ten-file" title={f.name}>{f.name}</span>
                <span className="co-file">{coChuoi(f.size)}</span>
                <button
                  type="button" className="nut-bo"
                  aria-label={laEn ? `Remove page ${i + 1}: ${f.name}` : `Bỏ trang ${i + 1}: ${f.name}`}
                  title={laEn ? `Remove page ${i + 1}: ${f.name}` : `Bỏ trang ${i + 1}: ${f.name}`}
                  disabled={tatCa}
                  onClick={() => onDoi(files.filter((_, j) => j !== i))}
                >
                  <Icon ten="x" co={16} />
                </button>
              </li>
            ))}
          </ol>
          <Button kieu="ghost" onClick={() => onDoi([])} disabled={tatCa}>
            {laEn ? 'Clear all' : 'Bỏ hết'}
          </Button>
        </>
      )}
    </div>
  )
}
