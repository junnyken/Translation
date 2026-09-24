import { useEffect, useRef, useState } from 'react'
import * as api from '../../api.js'
import { hangCuaTrang } from '../../lib/chapter-progress.js'
import { CACH_DICH, MUC_DICH, NGON_NGU } from '../../lib/status-presentation.js'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import Dropzone from '../ui/Dropzone.jsx'
import { Select } from '../ui/Field.jsx'

/** Hạng của `ready_for_export` — trang đi tới đây là xong cả chuỗi. Lấy từ `chapter-progress`
 *  thay vì gõ lại con số: thêm một bước vào pipeline mà quên sửa chỗ này sẽ làm màn Dịch nhanh
 *  báo "xong" sớm hơn sự thật. */
const HANG_XONG = hangCuaTrang('ready_for_export')

const MO_TA_MUC_DICH = {
  personal: 'Tự dịch để mình đọc, không đưa cho ai khác.',
  study: 'Học ngôn ngữ, làm bài tập, nghiên cứu dịch thuật.',
  other: 'Mục đích khác — bạn tự chịu trách nhiệm về bản quyền nội dung gốc.',
}

const MO_TA_ENGINE = {
  google_fast: 'Miễn phí. Dịch từng dòng, không nhìn câu trước sau.',
  llm_context: 'Giữ mạch văn cả trang và tự sửa lỗi đọc chữ — TỐN token AI.',
}

/** P1 — đếm số vùng chữ đáng xem lại từ cảnh báo xuất ĐÃ CÓ của backend.
 *
 * Dùng lại đúng `/projects/{id}/export-warnings` (E12/E14/F1) thay vì dựng phép đếm mới: dựng
 * mới sẽ tạo **nguồn sự thật thứ hai** cho cùng một khái niệm, và hai nguồn sẽ lệch nhau.
 *
 * Đếm theo **VÙNG CHỮ**, không theo trang — đó là thứ backend thật sự đo được. Viết "N trang"
 * sẽ là một con số không ai kiểm chứng được.
 *
 * Bốn loại gộp lại vì với người đi đường nhanh chúng dẫn tới cùng một hành động (mở màn rà
 * soát); chi tiết từng loại đã có sẵn ở đường đầy đủ.
 */
export function demVungDangNgo(canhBao) {
  if (!canhBao) return 0
  return (canhBao.needs_manual_count ?? 0)
    + (canhBao.quality_needs_review_count ?? 0)
    + (canhBao.overflow_warning_count ?? 0)
    + (canhBao.font_missing_count ?? 0)
}

/** Vì sao chưa chạy được — `null` nghĩa là chạy được. Tách riêng để test không cần dựng DOM. */
export function lyDoChuaChayDuoc({ mucDich, files }) {
  // M10 giữ nguyên ở đây: người dùng tự khai mục đích, hệ thống KHÔNG chọn hộ. Màn này rút gọn
  // số bước, không rút gọn phần khai báo trách nhiệm bản quyền.
  if (!mucDich) return 'Cần chọn mục đích sử dụng — hệ thống không chọn hộ.'
  if (!files.length) return 'Cần chọn ít nhất một ảnh, hoặc một gói ZIP/CBZ.'
  return null
}

/** Đếm trang đã xong / hỏng trong một danh sách trang.
 *
 * `hong` tính riêng chứ không gộp vào `xong`: gộp vào sẽ làm thanh tiến độ chạy tới 100% rồi
 * người dùng nhận một file thiếu trang mà không hiểu vì sao.
 */
export function demTienDo(trang = []) {
  const xong = trang.filter((t) => hangCuaTrang(t.status) >= HANG_XONG).length
  const hong = trang.filter((t) => t.status === 'detection_failed').length
  return { xong, hong, tong: trang.length, chayXong: trang.length > 0 && xong + hong === trang.length }
}

/** Tên chapter tự đặt — màn này không hỏi tên.
 *
 * Vẫn phải là tên có nghĩa để tìm lại được trong danh sách chapter: lấy tên file đầu tiên
 * (bỏ đuôi) rồi gắn ngày. Đặt trùng nhau hết thì người dùng có 12 chapter tên giống nhau.
 */
export function datTenTuDong(files, luc = new Date()) {
  const dau = files[0]?.name || 'Chapter'
  const goc = dau.replace(/\.[^.]+$/, '').slice(0, 60) || 'Chapter'
  const ngay = `${String(luc.getDate()).padStart(2, '0')}-${String(luc.getMonth() + 1).padStart(2, '0')}`
  return `${goc} (${ngay})`
}

/**
 * ĐX-1 — đường "Dịch nhanh": một màn, thả file là chạy, xong thì tự tải về.
 *
 * Đây là đường vào SONG SONG, không thay thế màn tạo chapter đầy đủ: ai cần rà soát, sửa tay,
 * chốt thuật ngữ thì vẫn đi đường cũ. Màn này cắt các bước điều phối (đặt tên chapter, tải từng
 * trang, tự bấm xuất) chứ **không** cắt bước nào của pipeline dịch.
 *
 * Giữ nguyên có chủ đích: đăng nhập và khai báo mục đích sử dụng (M10). Công cụ cùng loại không
 * có hai cổng này, nhưng bỏ chúng đi để cho giống thì mất đúng phần nhắc trách nhiệm bản quyền.
 */
export default function DichNhanh({ onMoChapter }) {
  const [nguon, setNguon] = useState('ja')
  const [engine, setEngine] = useState('google_fast')
  const [mucDich, setMucDich] = useState('')
  const [files, setFiles] = useState([])
  const [tuTaiVe, setTuTaiVe] = useState(true)
  const [giaiDoan, setGiaiDoan] = useState('cho')   // cho | tai_len | dang_chay | xuat | xong
  const [tien, setTien] = useState({ xong: 0, hong: 0, tong: 0 })
  const [ketQua, setKetQua] = useState(null)
  const [loi, setLoi] = useState(null)
  const huy = useRef(false)

  // Rời màn giữa chừng (đổi sang tab "Tạo chapter mới", mở một chapter khác) thì dừng hẳn vòng
  // hỏi tiến độ. Không có dòng này, vòng lặp chạy tiếp tới hết trần và gọi `setState` trên một
  // component đã tháo — chapter vẫn dịch bình thường ở máy chủ, nhưng tab thì hỏi vô ích hàng
  // trăm lượt.
  useEffect(() => () => { huy.current = true }, [])

  const lyDo = lyDoChuaChayDuoc({ mucDich, files })
  const dangChay = giaiDoan !== 'cho' && giaiDoan !== 'xong'

  const batDau = async () => {
    if (lyDo || dangChay) return   // chặn cả double-click, không chỉ dựa vào nút mờ
    huy.current = false
    setLoi(null); setKetQua(null); setGiaiDoan('tai_len'); setTien({ xong: 0, hong: 0, tong: 0 })

    let projectId = null
    try {
      const project = await api.taoProject({
        name: datTenTuDong(files), source_lang: nguon, intended_use: mucDich,
      })
      projectId = project.id

      // --- Tải lên: gói đi đường gói, ảnh lẻ đi đường ảnh ---
      let soTrang = 0, boQua = 0
      for (const f of files) {
        if (api.laGoiNen(f)) {
          const g = await api.taiGoiLen(projectId, f, engine)
          soTrang += g.so_trang
          boQua += g.bo_qua
        } else {
          await api.taiTrangLen(projectId, f, engine)
          soTrang += 1
        }
        setTien((t) => ({ ...t, tong: soTrang }))
      }

      // --- Chờ pipeline chạy xong ---
      setGiaiDoan('dang_chay')
      const dem = await choChapterXong(projectId, (t) => setTien(t), {
        nenDung: () => huy.current,
      })
      if (huy.current) return

      // --- Xuất + tải về ---
      let taiVe = null
      if (tuTaiVe && dem.xong > 0) {
        setGiaiDoan('xuat')
        // ZIP chứ không CBZ: E40 đo được người dùng tải `.cbz` về KHÔNG mở được trên Windows.
        // Đường "nhanh" mà giao một file không mở được thì không nhanh.
        const job = await api.xuatChapter(projectId, 'zip')
        await api.choXuatXong(job.job_id)
        taiVe = await api.taiFileXuatVe(job.job_id)
      }

      // P1 — hỏi cảnh báo SAU KHI file đã về máy. Thứ tự này là cố ý: quyết định Phase 0 chốt
      // "hiện thông tin, KHÔNG chặn tải". Hỏi trước sẽ biến nó thành một bước chắn đường.
      //
      // Hỏng ở đây KHÔNG được làm hỏng kết quả: người dùng đã có file rồi, mất dòng cảnh báo
      // thì tiếc, nhưng nuốt mất cả màn kết quả vì một lời gọi phụ thì tệ hơn nhiều.
      let canhBao = null
      try {
        canhBao = await api.layCanhBaoXuat(projectId)
      } catch {
        canhBao = null
      }

      setKetQua({ projectId, ...dem, boQua, taiVe, soVungDangNgo: demVungDangNgo(canhBao) })
      setGiaiDoan('xong')
    } catch (e) {
      // Giữ lại projectId: chapter đã tạo và có thể đã dịch xong vài trang — chỉ chỗ đó cho
      // người dùng vào xem còn hơn để họ tưởng mất trắng.
      setLoi({ thongDiep: e.message, projectId })
      setGiaiDoan('cho')
    }
  }

  return (
    <section className="the-lon" aria-labelledby="tieu-de-nhanh">
      <header className="the-dau">
        <h2 id="tieu-de-nhanh">Dịch nhanh</h2>
        <p>
          Thả ảnh hoặc cả gói <code>.zip</code>/<code>.cbz</code> vào đây. Xong là tự tải về.
          Cần sửa tay, chốt thuật ngữ hay rà soát từng bong bóng thì dùng <em>Tạo chapter mới</em>.
        </p>
      </header>

      <fieldset className="khoi" disabled={dangChay}>
        <div className="hang-doi">
          <Select nhan="Ngôn ngữ gốc" batBuoc value={nguon}
                  onChange={(e) => setNguon(e.target.value)}>
            {Object.entries(NGON_NGU).map(([ma, ten]) => (
              <option key={ma} value={ma}>{ten}</option>
            ))}
          </Select>
          <Select
            nhan="Cách dịch" batBuoc value={engine} moTa={MO_TA_ENGINE[engine]}
            onChange={(e) => setEngine(e.target.value)}
          >
            {Object.entries(CACH_DICH).map(([ma, ten]) => (
              <option key={ma} value={ma}>{ten}</option>
            ))}
          </Select>
          <Select
            nhan="Mục đích sử dụng" batBuoc value={mucDich}
            moTa={mucDich
              ? MO_TA_MUC_DICH[mucDich]
              : 'Bạn tự khai — hệ thống không chọn hộ. Khai báo gắn với chapter và không sửa được.'}
            onChange={(e) => setMucDich(e.target.value)}
          >
            <option value="" disabled>— hãy chọn —</option>
            {Object.entries(MUC_DICH).map(([ma, ten]) => (
              <option key={ma} value={ma}>{ten}</option>
            ))}
          </Select>
        </div>

        <Dropzone files={files} onDoi={setFiles} tatCa={dangChay} chapNhanGoi id="vung-tha-nhanh" />

        <label className="o-tick">
          <input
            type="checkbox" checked={tuTaiVe}
            onChange={(e) => setTuTaiVe(e.target.checked)}
          />
          <span>Tự tải về khi xong</span>
        </label>
      </fieldset>

      <fieldset className="khoi khoi-cuoi">
        <Button kieu="chinh" id="nut-dich-nhanh" onClick={batDau}
                dangChay={dangChay} lyDoKhoa={lyDo}>
          {NHAN_NUT[giaiDoan] ?? 'Dịch ngay'}
        </Button>

        {giaiDoan === 'dang_chay' && tien.tong > 0 && (
          <>
            <div className="thanh-tien" aria-hidden="true">
              <div className="thanh-tien-trong"
                   style={{ width: `${Math.round((tien.xong / Math.max(tien.tong, 1)) * 100)}%` }} />
            </div>
            <p className="ghi-chu" role="status">
              Đã xong {tien.xong}/{tien.tong} trang
              {tien.hong > 0 && ` · ${tien.hong} trang không nhận diện được`}.
              Khoảng một tiếng cho chapter 24 trang — bạn rời trang được, chapter vẫn chạy tiếp.
            </p>
          </>
        )}

        {ketQua && (
          <Alert sac={ketQua.hong > 0 ? 'canh' : 'ok'}
                 tieuDe={ketQua.hong > 0 ? 'Xong, nhưng thiếu trang' : 'Xong'}>
            <p>
              Dịch xong {ketQua.xong}/{ketQua.tong} trang
              {ketQua.hong > 0 && ` · ${ketQua.hong} trang không nhận diện được chữ nên không có trong file`}
              {ketQua.boQua > 0 && ` · bỏ qua ${ketQua.boQua} mục trong gói không phải ảnh`}.
            </p>
            {ketQua.taiVe
              ? <p>File đã tải về máy bạn.</p>
              : <p>Chưa tải về — bật “Tự tải về khi xong”, hoặc mở chapter rồi tự xuất.</p>}
            {/* P1 — im lặng khi sạch. Không hiện "0 vùng cần xem lại — mọi thứ ổn": đó là một
                lời khẳng định mà phép đo hiện tại KHÔNG chứng minh được, và nói thừa một câu
                trấn an sai còn tệ hơn không nói gì. */}
            {ketQua.soVungDangNgo > 0 && (
              <p>
                <b>{ketQua.soVungDangNgo} vùng chữ</b> nên xem lại (đọc chưa chắc, tràn khung,
                hoặc bong bóng bị bỏ trống). File vẫn đã tải về — mở chapter bên dưới nếu muốn
                sửa trước khi dùng.
              </p>
            )}
            <Button kieu="ghost" onClick={() => onMoChapter?.(ketQua.projectId)}>
              Mở chapter để xem lại / sửa tay
            </Button>
          </Alert>
        )}

        {loi && (
          <Alert sac="loi" tieuDe="Không chạy xong được">
            <p>{loi.thongDiep}</p>
            {loi.projectId && (
              <Button kieu="ghost" onClick={() => onMoChapter?.(loi.projectId)}>
                Mở chapter đã tạo để xem đã chạy tới đâu
              </Button>
            )}
          </Alert>
        )}
      </fieldset>
    </section>
  )
}

const NHAN_NUT = {
  tai_len: 'Đang tải lên…',
  dang_chay: 'Đang dịch…',
  xuat: 'Đang đóng gói…',
}

/** Hỏi lại chapter tới khi mọi trang đã xong hoặc hỏng.
 *
 * Nhịp 3 giây: một trang mất trung vị ~107 giây (E23), hỏi mỗi giây chỉ tạo tải vô ích.
 * Có trần số lần hỏi để một chapter kẹt không làm tab quay vòng mãi mãi.
 */
export async function choChapterXong(
  projectId, onTien, { soLanToiDa = 2400, nhipMs = 3000, nenDung } = {},
) {
  let cuoi = { xong: 0, hong: 0, tong: 0, chayXong: false }
  for (let i = 0; i < soLanToiDa; i++) {
    if (nenDung?.()) return cuoi   // người dùng rời màn — dừng hẳn, đừng hỏi thêm lượt nào
    const ct = await api.layProject(projectId)
    cuoi = demTienDo(ct.pages || [])
    onTien?.(cuoi)
    if (cuoi.chayXong) return cuoi
    await new Promise((r) => setTimeout(r, nhipMs))
  }
  // Hết trần mà chưa xong: trả về số đo THẬT tại thời điểm bỏ cuộc, không báo là đã xong.
  return cuoi
}
