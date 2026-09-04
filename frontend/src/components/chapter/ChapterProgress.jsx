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
  // Việc HỎNG của từng trang, khoá theo page_id. Hỏi một lời gọi cho cả chapter mỗi nhịp — chứ
  // không đợi người dùng bấm "Vì sao?" mới biết là có thứ đã chết (F1).
  const [viecHong, setViecHong] = useState({})
  const hen = useRef(null)
  const trang = project?.pages ?? []
  const tien_do = tinhTienDoChapter(trang, {
    soTran: canhBao?.overflow_warning_count, soCanDocLai: canhBao?.needs_manual_count,
    soThieuFont: canhBao?.font_missing_count,
  })
  // Một trang có việc hỏng thì KHÔNG còn "đang chạy" nữa, dù trạng thái trang chưa tới đích.
  //
  // Đây là chỗ đã làm mất 10 phút của người dùng thật 04/09: bước căn chữ chết sau 34 mili giây,
  // trang đứng ở `translated`, mà `translated` không nằm trong danh sách "đã xong" nên màn hình
  // cứ quay "đang cập nhật…" mãi. Quay vòng vô hạn quanh một cái xác là nói dối bằng hoạt hình.
  const con_chay = trang.some((t) => CHUA_XONG(t.status) && !viecHong[t.id])

  const nhip = useCallback(async () => {
    await onNapLai()
    if (project?.id) {
      try {
        const js = await api.layViecHongCuaChapter(project.id)
        setViecHong(Object.fromEntries(js.map((j) => [j.page_id, j])))
      } catch {
        // Không hỏi được danh sách việc hỏng thì im lặng bỏ qua vòng này: đây là lớp giải
        // thích thêm, làm hỏng luôn màn tiến độ vì nó là đánh đổi sai.
      }
    }
    setDem((n) => n + 1)
  }, [onNapLai, project?.id])

  // Hỏi NGAY lần đầu, không đợi hết 4 giây: trang mở ra mà việc đã hỏng từ trước thì phải thấy
  // ngay, không phải chờ một nhịp.
  useEffect(() => {
    if (!project?.id) return undefined
    let huy = false
    api.layViecHongCuaChapter(project.id)
      .then((js) => { if (!huy) setViecHong(Object.fromEntries(js.map((j) => [j.page_id, j]))) })
      .catch(() => {})
    return () => { huy = true }
  }, [project?.id])

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
            {viecHong[t.id]
              ? <LoiCuaTrang job={viecHong[t.id]} />
              : <LyDoDung pageId={t.id} trangThai={t.status} />}
          </li>
        ))}
      </ul>

      {!con_chay && (
        <p className="ghi-chu">
          {Object.keys(viecHong).length > 0
            ? 'Không còn việc nào đang chạy — có bước đã hỏng, xem lý do ở từng trang bên trên.'
            : 'Không còn việc nào đang chạy.'}{' '}
          <Button kieu="ghost" onClick={nhip}>Kiểm tra lại</Button>
        </p>
      )}
    </section>
  )
}


const XONG = ['typeset_done', 'ready_for_export']

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
/** Lỗi ĐÃ BIẾT của một trang — hiện thẳng, không bắt bấm mới cho xem.
 *
 * `LyDoDung` bên dưới vẫn giữ nguyên cho trường hợp trang đứng im mà KHÔNG có job hỏng nào
 * (worker chết giữa chừng, việc còn treo ở `running`): lúc đó không có gì để hiện sẵn, phải
 * hỏi máy chủ mới biết.
 */
function LoiCuaTrang({ job }) {
  return (
    <span className="canh-bao">
      Bước <b>{TEN_BUOC[job.type] ?? job.type}</b> hỏng: {job.error_log || 'không ghi lý do'}
    </span>
  )
}


function LyDoDung({ pageId, trangThai }) {
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
    // Nói đúng tình trạng THẬT. Trang đã xong mà báo "đang chờ tới lượt" là một câu nói dối nhỏ
    // — và nó khiến người dùng ngồi đợi một thứ không bao giờ tới.
    return (
      <span className="ghi-chu">
        {XONG.includes(trangThai)
          ? 'Không có bước nào hỏng — trang này đã xong.'
          : 'Không có bước nào hỏng — trang này đang chờ tới lượt.'}
      </span>
    )
  }
  return (
    <span className="canh-bao">
      Bước <b>{TEN_BUOC[job.type] ?? job.type}</b> hỏng: {job.error_log || 'không ghi lý do'}
    </span>
  )
}
