import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../../api.js'
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
            <LyDoDung pageId={t.id} />
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


const TEN_BUOC = {
  detect: 'nhận diện khung chữ', ocr: 'đọc chữ gốc', inpaint: 'xoá chữ gốc',
  translate: 'dịch', typeset: 'căn chữ', refit: 'căn lại chữ',
}

/** "Vì sao trang này đứng im?" — hỏi máy chủ CHỈ KHI người dùng bấm.
 *
 * Trước P3j, một trang dừng vì worker chết nhìn **y hệt** một trang đang chạy chậm: cùng một nhãn
 * trạng thái, không một chữ nào về lý do. Người vận hành chỉ còn cách đoán, hoặc mở log máy chủ —
 * thứ mà họ không có quyền và cũng không nên cần.
 */
function LyDoDung({ pageId }) {
  const [mo, setMo] = useState(false)
  const [job, setJob] = useState(undefined)   // undefined = chưa hỏi · null = hỏi rồi, không có
  const [loi, setLoi] = useState(null)

  async function hoi() {
    setMo(true)
    if (job !== undefined) return
    try {
      setJob(await api.layLyDoDung(pageId))
    } catch (e) {
      setLoi(e.message)
    }
  }

  if (!mo) {
    return (
      <button className="lien-ket" onClick={hoi} aria-label={`Vì sao trang này dừng`}>
        Vì sao?
      </button>
    )
  }
  if (loi) return <span className="ghi-chu">Không hỏi được máy chủ: {loi}</span>
  if (job === undefined) return <span className="ghi-chu">Đang hỏi…</span>
  if (job === null) {
    return <span className="ghi-chu">Không có bước nào hỏng — trang này đang chờ tới lượt.</span>
  }
  return (
    <span className="canh-bao">
      Bước <b>{TEN_BUOC[job.type] ?? job.type}</b> hỏng: {job.error_log || 'không ghi lý do'}
    </span>
  )
}
