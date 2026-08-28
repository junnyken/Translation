import { useRef, useState } from 'react'
import Icon from './Icon.jsx'
import Button from './Button.jsx'

/** Chọn ảnh bằng cách kéo-thả hoặc bấm — nhưng vẫn là `<input type="file">` thật, chỉ ẩn đi.
 *
 * Giữ input thật là điều kiện để trình duyệt, trình đọc màn hình và bàn phím hoạt động đúng;
 * tự vẽ một vùng thả rồi bỏ input là đánh đổi độ tin cậy lấy vẻ đẹp.
 * Vùng thả nhận cả Enter và Space vì người dùng bàn phím mong nó cư xử như một nút.
 */
const LOAI_HO_TRO = ['image/png', 'image/jpeg', 'image/webp']

export function locFileHopLe(files) {
  const nhan = [], loai = []
  for (const f of files) {
    (LOAI_HO_TRO.includes(f.type) ? nhan : loai).push(f)
  }
  return { nhan, loai }
}

export function coChuoi(so) {
  if (so < 1024) return `${so} B`
  if (so < 1024 * 1024) return `${(so / 1024).toFixed(0)} KB`
  return `${(so / 1024 / 1024).toFixed(1)} MB`
}

export default function Dropzone({ files, onDoi, tatCa = false, id = 'vung-tha' }) {
  const oFile = useRef(null)
  const [dangKeo, setDangKeo] = useState(false)
  const [loi, setLoi] = useState(null)

  const them = (danhSach) => {
    const { nhan, loai } = locFileHopLe(Array.from(danhSach || []))
    setLoi(loai.length
      ? `Bỏ qua ${loai.length} tệp không phải ảnh PNG/JPG/WebP: ${loai.map((f) => f.name).join(', ')}`
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
        aria-label="Chọn ảnh trang truyện: bấm hoặc kéo tệp vào đây"
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
        <Icon ten="tai-len" co={26} />
        <b>Kéo ảnh vào đây hoặc bấm để chọn</b>
        <span>Hỗ trợ PNG, JPG. Có thể chọn nhiều trang một lúc.</span>
      </div>

      {/* Input THẬT, chỉ ẩn khỏi mắt — vẫn nằm trong cây tiếp cận của trình duyệt. */}
      <input
        ref={oFile}
        type="file"
        className="o-file-an"
        accept="image/png,image/jpeg,image/webp"
        multiple
        tabIndex={-1}
        disabled={tatCa}
        onChange={(e) => { them(e.target.files); e.target.value = '' }}
      />

      {loi && <div className="bang-loi nho">{loi}</div>}

      {files.length > 0 && (
        <>
          <p className="ghi-chu">
            <b>{files.length}</b> trang · thứ tự dưới đây <b>chính là thứ tự trang</b> trong chapter.
          </p>
          <ol className="ds-file">
            {files.map((f, i) => (
              <li key={`${f.name}-${i}`}>
                <span className="stt">{i + 1}</span>
                <span className="ten-file" title={f.name}>{f.name}</span>
                <span className="co-file">{coChuoi(f.size)}</span>
                <button
                  type="button" className="nut-bo"
                  aria-label={`Bỏ trang ${i + 1}: ${f.name}`}
                  disabled={tatCa}
                  onClick={() => onDoi(files.filter((_, j) => j !== i))}
                >
                  <Icon ten="x" co={14} />
                </button>
              </li>
            ))}
          </ol>
          <Button kieu="ghost" onClick={() => onDoi([])} disabled={tatCa}>Bỏ hết</Button>
        </>
      )}
    </div>
  )
}
