import { useEffect, useMemo, useState } from 'react'
import * as api from '../../api.js'
import { tinhTienDoChapter } from '../../lib/chapter-progress.js'
import { useThumbnail } from '../../lib/use-thumbnail.js'
import { NGON_NGU } from '../../lib/status-presentation.js'
import EmptyState from '../ui/EmptyState.jsx'
import Icon from '../ui/Icon.jsx'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import Skeleton from '../ui/Skeleton.jsx'

// wording: BA review — nhãn chip lọc + các câu mới của lưới chapter (mockup-v2/trang-chu)
const TIEU_DE_LUOI = 'Chapter gần đây'
const NHAN_TIM = 'Tìm theo tên chapter hoặc mã…'
const NHAN_TIM_ARIA = 'Tìm chapter'
const NHAN_LOC = 'Lọc theo trạng thái'
const NHAN_KHONG_KHOP = 'Không có chapter nào khớp'
const MO_TA_KHONG_KHOP = 'Thử đổi từ khoá hoặc bỏ bộ lọc.'
const NHAN_LOI_TAI = 'Không tải được tiến độ'
const NHAN_THU_LAI = 'Thử lại'
const NHAN_CHUA_CO_TRANG = 'Chưa có trang'
const NHAN_DANG_TAI_BIA = 'Đang tải ảnh bìa…'

const LOC = [
  { ma: 'tat_ca', nhan: 'Tất cả' },
  { ma: 'dang_chay', nhan: 'Đang xử lý' },
  { ma: 'xong', nhan: 'Đã xong' },
  { ma: 'hong', nhan: 'Có trang hỏng' },
]

/** Suy trạng thái của một chapter từ danh sách trang THẬT (cùng hàm với màn chapter). */
function suyTrangThai(project) {
  const td = tinhTienDoChapter(project.pages ?? [])
  let ma = 'dang_chay'
  if (td.tong === 0) ma = 'trong'
  else if (td.san_sang_ra_soat) ma = 'xong'
  else if (td.so_hong > 0 && !td.dang_chay) ma = 'hong'
  return { ma, td }
}

const HIEN = {
  trong: { nhan: NHAN_CHUA_CO_TRANG, lop: '', icon: 'image', mau: 'var(--mo)', thanh: '' },
  dang_chay: { nhan: 'Đang xử lý', lop: 'badge-tin', icon: 'loader', mau: 'var(--mau-chinh)', thanh: '' },
  xong: { nhan: 'Đã căn chữ xong', lop: 'badge-ok', icon: 'circle-check', mau: 'var(--ok)', thanh: 'thanh-tien-ok' },
  hong: { nhan: 'Có trang hỏng', lop: 'badge-loi', icon: 'circle-x', mau: 'var(--loi)', thanh: 'thanh-tien-loi' },
}

/** Danh sách chapter đã mở **trên trình duyệt này**, dạng lưới thẻ.
 *
 * Nói rõ "trên trình duyệt này" là bắt buộc: backend chưa có endpoint liệt kê project (đã ghi
 * thành khoảng trống trong REPORT_E11), nên danh sách này lấy từ bộ nhớ trình duyệt. Gọi nó là
 * "tất cả chapter của bạn" sẽ là nói quá — mở máy khác là mất.
 *
 * Bìa thẻ là KHỐI MÀU giữ chỗ: backend chưa có ảnh bìa. Tiến độ/trạng thái trên thẻ lấy từ
 * `GET /projects/{id}` (đúng lời gọi màn chapter đang dùng) — mỗi thẻ một lời gọi, tối đa 12.
 * Chưa tải xong thì hiện khung chờ, KHÔNG hiện 0; tải lỗi thì nói là lỗi, không đoán.
 */
export default function ChapterRecentList({ danhSach }) {
  const [tim, setTim] = useState('')
  const [loc, setLoc] = useState('tat_ca')
  const [thongTin, setThongTin] = useState({})   // id → { tt: 'tai' | 'loi' | 'ok', ... }
  const [lanTai, setLanTai] = useState(0)
  const khoaDs = danhSach.map((c) => c.id).join(',')

  useEffect(() => {
    let huy = false
    const ids = khoaDs ? khoaDs.split(',') : []
    setThongTin(Object.fromEntries(ids.map((id) => [id, { tt: 'tai' }])))
    ids.forEach((id) => {
      api.layProject(id)
        .then((p) => { if (!huy) setThongTin((cu) => ({ ...cu, [id]: { tt: 'ok', project: p, ...suyTrangThai(p) } })) })
        .catch(() => { if (!huy) setThongTin((cu) => ({ ...cu, [id]: { tt: 'loi' } })) })
    })
    return () => { huy = true }
  }, [khoaDs, lanTai])

  const dsLoc = useMemo(() => {
    const t = tim.trim().toLowerCase()
    return danhSach.filter((c) => {
      if (t && !`${c.ten} ${c.id}`.toLowerCase().includes(t)) return false
      if (loc === 'tat_ca') return true
      return thongTin[c.id]?.tt === 'ok' && thongTin[c.id].ma === loc
    })
  }, [danhSach, tim, loc, thongTin])

  if (!danhSach.length) {
    // E63 — lúc trống chỉ một khối ngắn, KHÔNG có nút chính thứ hai: "Tạo chapter" đã có ở tab
    // bên trái và trên thanh đầu trang; thêm lối vào thứ ba chỉ làm người dùng đoán chúng khác nhau.
    return (
      <section aria-labelledby="tieu-de-gan-day" className="luoi-chapter-boc">
        <h2 id="tieu-de-gan-day" className="an-di">{TIEU_DE_LUOI}</h2>
        <EmptyState icon="book-open" tieuDe="Chưa có chapter nào trên trình duyệt này">
          Chapter bạn tạo sẽ hiện ở đây; đã có mã sẵn thì dán vào ô tìm ở đầu trang.
        </EmptyState>
      </section>
    )
  }

  const soLoi = Object.values(thongTin).filter((x) => x.tt === 'loi').length

  return (
    <section aria-labelledby="tieu-de-gan-day" className="luoi-chapter-boc">
      <div className="dau-man">
        <div>
          <h2 id="tieu-de-gan-day">{TIEU_DE_LUOI}</h2>
          <p>Ghi nhớ trên trình duyệt này. Mở ở máy khác thì dùng mã chapter.</p>
        </div>
      </div>

      <div className="thanh-loc">
        <div className="o-tim-icon">
          <Icon ten="search" />
          <input
            type="search" className="o" value={tim} onChange={(e) => setTim(e.target.value)}
            placeholder={NHAN_TIM} aria-label={NHAN_TIM_ARIA}
          />
        </div>
        <div className="hang-chip" role="group" aria-label={NHAN_LOC}>
          {LOC.map((l) => (
            <button
              key={l.ma} type="button" className="chip-loc"
              aria-pressed={loc === l.ma} onClick={() => setLoc(l.ma)}
            >
              {l.nhan}
            </button>
          ))}
        </div>
        <span className="ghi-chu t-so" aria-live="polite">
          {dsLoc.length} / {danhSach.length} chapter
        </span>
      </div>

      {soLoi > 0 && (
        <Alert sac="canh" tieuDe={NHAN_LOI_TAI}>
          {soLoi} chapter chưa lấy được tiến độ (chapter có thể thuộc tài khoản khác hoặc mạng đang
          lỗi). Vẫn mở được bằng thẻ bên dưới.{' '}
          <Button kieu="ghost" icon="refresh" onClick={() => setLanTai((n) => n + 1)}>
            {NHAN_THU_LAI}
          </Button>
        </Alert>
      )}

      {dsLoc.length === 0 ? (
        <EmptyState icon="search" tieuDe={NHAN_KHONG_KHOP} moTa={MO_TA_KHONG_KHOP} />
      ) : (
        <ul className="luoi-chapter">
          {dsLoc.map((c) => <TheChapter key={c.id} chapter={c} tt={thongTin[c.id]} />)}
        </ul>
      )}
    </section>
  )
}

function TheChapter({ chapter, tt }) {
  const dangTai = !tt || tt.tt === 'tai'
  const ok = tt?.tt === 'ok'
  const h = ok ? HIEN[tt.ma] : null
  const p = ok ? tt.project : null
  const td = ok ? tt.td : null
  // Bìa = thumbnail của trang có `order` nhỏ nhất. Chưa biết trang (đang tải project) thì chưa tải gì.
  const trangDau = p?.pages?.length
    ? p.pages.reduce((a, b) => (b.order < a.order ? b : a))
    : null
  const bia = useThumbnail(trangDau?.id)
  const phanTram = td && td.tong > 0 ? Math.round((td.so_xong / td.tong) * 100) : 0

  return (
    <li>
      <article className="the-chapter" aria-busy={dangTai || undefined}>
        {bia.tt === 'tai' ? (
          <Skeleton kieu="khoi" nhan={NHAN_DANG_TAI_BIA} className="bia-chapter-cho" />
        ) : bia.tt === 'ok' ? (
          // alt rỗng: ảnh chỉ trang trí — tên chapter đã là chữ của liên kết ngay bên dưới; alt mô tả
          // sẽ khiến trình đọc màn hình đọc lặp tên (và "ảnh bìa" không mang thêm thông tin nào).
          <div className="bia-chapter bia-chapter-anh"><img src={bia.url} alt="" loading="lazy" /></div>
        ) : (
          <div className="bia-chapter" style={{ '--cv': h ? h.mau : 'var(--mo)' }} aria-hidden="true">
            <Icon ten="image" co={24} />
          </div>
        )}
        <div className="than-the-chapter">
          <h3>
            <a href={`#project=${chapter.id}`} className="lien-the">{chapter.ten}</a>
          </h3>
          {p && <p className="ghi-chu">{NGON_NGU[p.source_lang] ?? p.source_lang} → Tiếng Việt</p>}
          <p className="ma">{chapter.id.slice(0, 8)}</p>

          {dangTai && (
            <div className="skeleton" role="status" aria-live="polite">
              <span className="an-di">Đang tải tiến độ…</span>
              <span className="skeleton-dong" aria-hidden="true" />
              <span className="skeleton-dong" aria-hidden="true" />
            </div>
          )}
          {tt?.tt === 'loi' && (
            <p className="ghi-chu" role="status">
              <Icon ten="triangle-alert" /> {NHAN_LOI_TAI}
            </p>
          )}
          {ok && (
            <>
              {td.tong > 0 && (
                <>
                  <div
                    className={`thanh-tien thanh-tien-mong ${h.thanh}`} role="progressbar"
                    aria-label={`Tiến độ ${chapter.ten}`} aria-valuemin={0} aria-valuemax={100}
                    aria-valuenow={phanTram}
                  >
                    <div className="thanh-tien-trong" style={{ width: `${phanTram}%` }} />
                  </div>
                  <p className="ghi-chu t-so">
                    <b>{td.so_xong}</b>/{td.tong} trang đã căn chữ xong
                  </p>
                </>
              )}
              <span className={`badge ${h.lop}`}><Icon ten={h.icon} co={12} /> {h.nhan}</span>
            </>
          )}
        </div>
      </article>
    </li>
  )
}
