import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../../api.js'
import { tinhTienDoChapter } from '../../lib/chapter-progress.js'
import { useThumbnail, useVaoKhungNhin } from '../../lib/use-thumbnail.js'
import Skeleton from '../ui/Skeleton.jsx'
import { MUC_DICH, NGON_NGU, dienGiaiTrangThai } from '../../lib/status-presentation.js'
import Button from '../ui/Button.jsx'
import Icon from '../ui/Icon.jsx'
import ProgressStage from '../ui/ProgressStage.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'
import { ChuRutGon } from '../ui/GiaiThich.jsx'

// wording: BA review — chip lọc trang + trạng thái rỗng (mockup-v2/chapter)
const LOC_TRANG = [
  { ma: 'tat_ca', nhan: 'Tất cả' },
  { ma: 'chua', nhan: 'Chưa xong' },
  { ma: 'xong', nhan: 'Đã xong' },
  { ma: 'hong', nhan: 'Hỏng' },
  { ma: 'tran', nhan: 'Tràn khung' },
  { ma: 'xem', nhan: 'Cần xem lại' },
]
const NHAN_TRAN = 'Tràn khung'
const NHAN_CAN_XEM = 'Cần xem lại'
// wording: BA review — badge lỗi gọn trên thẻ trang
const NHAN_HONG_BUOC = 'Hỏng · bước'
const NHAN_DANG_TAI_ANH = 'Đang tải ảnh trang…'
// null = CHƯA BIẾT (trang chưa canh chữ / chưa chấm) ⇒ không badge, không tính vào chip.
const CO_SO = (n) => typeof n === 'number' && n > 0

const NHAN_LOC_TRANG = 'Lọc trang'
const NHAN_KHONG_CO_TRANG = 'Không có trang nào ở trạng thái này'
const MO_TA_KHONG_CO_TRANG = 'Chọn "Tất cả" để xem lại toàn bộ.'
const TIEU_DE_CHUA_CO_TRANG = 'Chapter chưa có trang nào'
const MO_TA_CHUA_CO_TRANG = 'Tải ảnh PNG hoặc JPG lên để hệ thống nhận diện chữ và dịch.'

const CHUA_XONG = (t) => !['typeset_done', 'ready_for_export', 'detection_failed'].includes(t)

/** Tiến độ chapter: dòng thời gian pipeline + trạng thái từng trang, đọc từ API thật.
 *
 * Chỉ hỏi lại máy chủ khi CÒN việc chạy, và dừng hẳn khi mọi trang tới trạng thái cuối hoặc khi
 * component bị gỡ — vòng hỏi không có điểm dừng là cách làm nóng máy người dùng một cách vô ích.
 */
export default function ChapterProgress({ project, canhBao, onNapLai }) {
  const [dem, setDem] = useState(0)
  const [loc, setLoc] = useState('tat_ca')
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

  // Lọc trang. Chỉ dùng dữ liệu CÓ THẬT trên mỗi trang: trạng thái, việc hỏng, và số vùng tràn khung /
  // cần xem lại do `GET /projects/{id}` trả (null = chưa biết ⇒ không tính, không coi là 0).
  const hong = (t) => t.status === 'detection_failed' || Boolean(viecHong[t.id])
  const xong = (t) => ['typeset_done', 'ready_for_export'].includes(t.status)
  const dsHienThi = trang.filter((t) => {
    if (loc === 'hong') return hong(t)
    if (loc === 'tran') return CO_SO(t.so_vung_tran_khung)
    if (loc === 'xem') return CO_SO(t.so_vung_can_xem)
    if (loc === 'xong') return xong(t)
    if (loc === 'chua') return !xong(t) && !hong(t)
    return true
  })
  const soLoc = {
    tat_ca: trang.length, hong: trang.filter(hong).length,
    tran: trang.filter((t) => CO_SO(t.so_vung_tran_khung)).length,
    xem: trang.filter((t) => CO_SO(t.so_vung_can_xem)).length,
    xong: trang.filter(xong).length, chua: trang.filter((t) => !xong(t) && !hong(t)).length,
  }

  if (!trang.length) {
    // Chapter 0 trang: nói rõ vì sao trống thay vì biến mất khỏi màn.
    return (
      <section className="the-man" aria-labelledby="tieu-de-tien-do">
        <h2 id="tieu-de-tien-do" className="tieu-the">Tiến độ xử lý</h2>
        <EmptyState icon="image" tieuDe={TIEU_DE_CHUA_CO_TRANG} moTa={MO_TA_CHUA_CO_TRANG} />
      </section>
    )
  }

  return (
    <section aria-labelledby="tieu-de-tien-do" className="khu-tien-do">
      <div className="dau-man">
        <div>
          <h2 id="tieu-de-tien-do" className="tieu-the">Tiến độ xử lý</h2>
          <p>
            {NGON_NGU[project.source_lang] ?? project.source_lang} → Tiếng Việt ·{' '}
            {MUC_DICH[project.intended_use] ?? project.intended_use} · {tien_do.tong} trang
            {con_chay && ' · đang cập nhật…'}
          </p>
        </div>
      </div>

      <ProgressStage buoc={tien_do.buoc} />

      <div className="dau-man dau-man-nho">
        <h3 className="tieu-the">Từng trang</h3>
        <span className="ghi-chu t-so" aria-live="polite">{dsHienThi.length} / {trang.length} trang</span>
      </div>
      <div className="hang-chip" role="group" aria-label={NHAN_LOC_TRANG}>
        {LOC_TRANG.map((l) => (
          <button
            key={l.ma} type="button" className="chip-loc"
            aria-pressed={loc === l.ma} onClick={() => setLoc(l.ma)}
          >
            {l.nhan} <span className="so">{soLoc[l.ma]}</span>
          </button>
        ))}
      </div>

      {dsHienThi.length === 0 ? (
        <EmptyState icon="search" tieuDe={NHAN_KHONG_CO_TRANG} moTa={MO_TA_KHONG_CO_TRANG} />
      ) : (
        <ul className="luoi-trang">
          {dsHienThi.map((t) => (
            <li key={t.id}>
              <TheTrang t={t} hong={hong(t)} job={viecHong[t.id]} />
            </li>
          ))}
        </ul>
      )}

      {!con_chay && (
        <p className="ghi-chu">
          {Object.keys(viecHong).length > 0
            ? 'Không còn việc nào đang chạy — có bước đã hỏng, xem lý do ở từng trang bên trên.'
            : 'Không còn việc nào đang chạy.'}{' '}
          <Button kieu="ghost" icon="refresh" onClick={nhip}>Kiểm tra lại</Button>
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
  // Thẻ trang nhỏ: chỉ badge "Hỏng · bước X"; toàn văn lỗi nằm sau nút "Chi tiết" (vẫn là nguyên văn).
  return (
    <span className="canh-bao loi-trang">
      <span className="badge badge-loi">
        <Icon ten="circle-x" co={12} /> {NHAN_HONG_BUOC} {TEN_BUOC[job.type] ?? job.type}
      </span>
      <ChuRutGon dai so={1}>
        Bước <b>{TEN_BUOC[job.type] ?? job.type}</b> hỏng: {job.error_log || 'không ghi lý do'}
      </ChuRutGon>
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
  // E22 — việc còn treo `running` nhưng máy chủ đánh giá worker đã gián đoạn. TRƯỚC E22 nhánh này
  // rơi vào `job === null` ở trên và trả về đúng câu nói dối tệ nhất của màn này: "không có bước
  // nào hỏng — đang chờ tới lượt", trong khi thật ra chẳng chờ ai cả, worker đã chết.
  if (job.processing_state === 'worker_interrupted') {
    const d = dienGiaiTrangThai('tt_xu_ly', 'worker_interrupted')
    return (
      <span className="canh-bao">
        Bước <b>{TEN_BUOC[job.type] ?? job.type}</b>: {d.nhan}. {d.mo_ta}
      </span>
    )
  }
  return (
    <span className="canh-bao">
      Bước <b>{TEN_BUOC[job.type] ?? job.type}</b> hỏng: {job.error_log || 'không ghi lý do'}
    </span>
  )
}

function TheTrang({ t, hong, job }) {
  const ref = useRef(null)
  const thay = useVaoKhungNhin(ref)          // lazy: chỉ tải khi ô vào khung nhìn
  const anh = useThumbnail(t.id, thay)
  const tran = CO_SO(t.so_vung_tran_khung)
  const xem = CO_SO(t.so_vung_can_xem)
  return (
    <div className={`the-trang${hong ? ' the-trang-hong' : ''}`}>
      <div className="thumb-trang" ref={ref} aria-hidden={anh.tt === 'ok' ? undefined : 'true'}>
        {anh.tt === 'ok'
          ? <img src={anh.url} alt={`Trang ${t.order}`} loading="lazy" />
          : anh.tt === 'tai'
            ? <Skeleton kieu="khoi" nhan={NHAN_DANG_TAI_ANH} />
            : <Icon ten="image" co={24} />}
      </div>
      <div className="than-the-trang">
        <a href={`#page=${t.id}`} className="lien-the"><b>Trang {t.order}</b></a>
        <StatusBadge loai="trang" trangThai={t.status} />
        {(tran || xem) && (
          <span className="huy-hieu-trang">
            {tran && (
              <span className="badge badge-canh">
                <Icon ten="triangle-alert" co={12} /> {NHAN_TRAN} · {t.so_vung_tran_khung}
              </span>
            )}
            {xem && (
              <span className="badge badge-canh">
                <Icon ten="triangle-alert" co={12} /> {NHAN_CAN_XEM} · {t.so_vung_can_xem}
              </span>
            )}
          </span>
        )}
        {t.status === 'detection_failed' && (
          <span className="ghi-chu">Mở trang để chạy lại bước nhận diện.</span>
        )}
        {job ? <LoiCuaTrang job={job} /> : <LyDoDung pageId={t.id} trangThai={t.status} />}
      </div>
    </div>
  )
}
