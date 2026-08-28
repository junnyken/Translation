import { useCallback, useEffect, useRef, useState } from 'react'
import { tinhTienDoChapter } from '../../lib/chapter-progress.js'
import { MUC_DICH, NGON_NGU } from '../../lib/status-presentation.js'
import Button from '../ui/Button.jsx'
import ProgressStage from '../ui/ProgressStage.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'

const CHUA_XONG = (t) => !['typeset_done', 'ready_for_export', 'detection_failed'].includes(t)

/** Tiến độ chapter: dòng thời gian pipeline + trạng thái từng trang, đọc từ API thật.
 *
 * Chỉ hỏi lại máy chủ khi CÒN việc chạy, và dừng hẳn khi mọi trang tới trạng thái cuối hoặc khi
 * component bị gỡ — vòng hỏi không có điểm dừng là cách làm nóng máy người dùng một cách vô ích.
 */
export default function ChapterProgress({ project, canhBao, onNapLai }) {
  const [dem, setDem] = useState(0)
  const hen = useRef(null)
  const trang = project?.pages ?? []
  const tien_do = tinhTienDoChapter(trang, {
    soTran: canhBao?.overflow_warning_count, soCanDocLai: canhBao?.needs_manual_count,
  })
  const con_chay = trang.some((t) => CHUA_XONG(t.status))

  const nhip = useCallback(async () => {
    await onNapLai()
    setDem((n) => n + 1)
  }, [onNapLai])

  useEffect(() => {
    if (!con_chay) return undefined
    hen.current = setTimeout(nhip, 4000)
    return () => clearTimeout(hen.current)   // gỡ component / hết việc là dừng, không để trôi
  }, [con_chay, nhip, dem])

  if (!trang.length) return null

  return (
    <section className="the-lon" aria-labelledby="tieu-de-tien-do">
      <header className="the-dau">
        <h2 id="tieu-de-tien-do">Tiến độ xử lý</h2>
        <p>
          {NGON_NGU[project.source_lang] ?? project.source_lang} → Tiếng Việt ·{' '}
          {MUC_DICH[project.intended_use] ?? project.intended_use} · {tien_do.tong} trang
          {con_chay && ' · đang cập nhật…'}
        </p>
      </header>

      <ProgressStage buoc={tien_do.buoc} />

      <h3 className="tieu-de-nho">Từng trang</h3>
      <ul className="ds-trang">
        {trang.map((t) => (
          <li key={t.id}>
            <a href={`#page=${t.id}`}>Trang {t.order}</a>
            <StatusBadge loai="trang" trangThai={t.status} />
            {t.status === 'detection_failed' && (
              <span className="ghi-chu">Mở trang để chạy lại bước nhận diện.</span>
            )}
          </li>
        ))}
      </ul>

      {!con_chay && (
        <p className="ghi-chu">
          Không còn việc nào đang chạy.{' '}
          <Button kieu="ghost" onClick={nhip}>Kiểm tra lại</Button>
        </p>
      )}
    </section>
  )
}
