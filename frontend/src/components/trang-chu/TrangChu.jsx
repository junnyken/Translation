import { useCallback, useEffect, useRef, useState } from 'react'

import * as api from '../../api'
import { useCodex } from '../../lib/dung-codex'
import { chuDemNguoc, conLaiMs, mocHetHanGiuTep } from '../../lib/dem-nguoc'
import Alert from '../ui/Alert'
import Button from '../ui/Button'
import Dropzone from '../ui/Dropzone'
import { chuThoiGianGiu } from '../../lib/thoi-gian-giu.js'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
import Icon from '../ui/Icon'
import ChanTrangManga from './ChanTrangManga'
import TheHanMuc from './TheHanMuc'

/** Ngôn ngữ chữ TRÊN ẢNH. Sai ngôn ngữ ra chữ vô nghĩa chứ không phải lỗi rõ ràng, nên phải để
 *  người dùng tự chọn — không đoán hộ. */
/** E57 — giá trị của ô chọn khi người dùng muốn MÁY đoán.
 *
 * Cố ý KHÔNG phải một `source_lang` hợp lệ: nó không bao giờ được gửi lên đường dịch. Nút "Dịch
 * trang" bị khoá khi ô còn ở giá trị này, vì gửi nó đi là nhận 422 — và người dùng sẽ đọc một lỗi
 * kỹ thuật cho một lựa chọn mà chính giao diện mời họ chọn.
 */
const TU_NHAN = 'tu-nhan'

const NGON_NGU = [
  { ma: TU_NHAN, nhan: 'Tự nhận — để máy đọc thử và đoán' },
  { ma: 'ja', nhan: 'Tiếng Nhật' },
  { ma: 'en', nhan: 'Tiếng Anh' },
  { ma: 'zh', nhan: 'Tiếng Trung' },
  { ma: 'ko', nhan: 'Tiếng Hàn (Manhwa)' },
]

const PILL_NGON_NGU_GOC = [
  { ma: 'ja', co: 'JP', nhan: 'Tiếng Nhật', nhanEn: 'Japanese' },
  { ma: 'ko', co: 'KR', nhan: 'Tiếng Hàn', nhanEn: 'Korean' },
  { ma: 'zh', co: 'CN', nhan: 'Tiếng Trung', nhanEn: 'Chinese' },
  { ma: 'en', co: 'GB', nhan: 'Tiếng Anh', nhanEn: 'English' },
  { ma: TU_NHAN, co: '🔍', nhan: 'Tự nhận diện', nhanEn: 'Auto Detect' },
]

const PILL_NGON_NGU_DICH = [
  { ma: 'vi', co: 'VN', nhan: 'Sang Tiếng Việt', nhanEn: 'To Vietnamese' },
  { ma: 'en', co: 'US', nhan: 'To English', nhanEn: 'To English' },
]

const PILL_FONT_THE_LOAI = [
  { ma: 'bangers', bieuTuong: '⚔️', nhan: 'Hành động (Đậm)', nhanEn: 'Action (Bold)' },
  { ma: 'romance', bieuTuong: '🌸', nhan: 'Ngôn tình (Mềm)', nhanEn: 'Romance (Soft)' },
  { ma: 'historical', bieuTuong: '🏮', nhan: 'Cổ trang (Bút)', nhanEn: 'Historical (Brush)' },
  { ma: 'comic', bieuTuong: '💥', nhan: 'Hài hước (Tròn)', nhanEn: 'Comedy (Rounded)' },
]

const MAU_XUNG_HO = [
  {
    nhan: '🏮 Cổ trang / Tu tiên (Ta - Ngươi / Huynh - Muội)',
    giaTri: 'Xưng hô phong cách Cổ trang / Tu tiên: dùng Ta - Ngươi, Huynh - Đệ - Muội, Bản tôn, Tiền bối.',
  },
  {
    nhan: '🌸 Ngôn tình / Học đường (Anh - Em / Tớ - Cậu)',
    giaTri: 'Xưng hô phong cách Ngôn tình / Học đường: dùng Anh - Em hoặc Tớ - Cậu mềm mại, tự nhiên.',
  },
  {
    nhan: '⚔️ Hành động / Hunter (Tôi - Cậu / Ngài)',
    giaTri: 'Xưng hô phong cách Hành động / Hunter: dùng Tôi - Cậu, Đội trưởng, Ngài; giữ nguyên tên kỹ năng.',
  },
]

const TEN_NGON_NGU = {
  ja: 'Tiếng Nhật',
  en: 'Tiếng Anh',
  zh: 'Tiếng Trung',
  ko: 'Tiếng Hàn',
}

/** Số phút giữ kết quả lấy từ MÁY CHỦ (`han_muc.giu_ket_qua_phut`), không gõ cứng ở đây.
 *
 * `null` nghĩa là **không tự xoá**. Gõ cứng 30 là nói sai với người dùng ngay khi lịch dọn tắt —
 * và nó đã sai thật: E50 ship với lịch mặc định tắt trong khi màn hình vẫn hứa xoá sau 30 phút.
 */

/** Tên bước cho người đọc. Máy chủ trả tên máy (`detect`, `ocr`…) ở `tien_do.buoc`. */
const TEN_BUOC = {
  detect: 'Tìm khung chữ',
  ocr: 'Đọc chữ gốc',
  inpaint: 'Xoá chữ gốc',
  translate: 'Dịch',
  typeset: 'Căn chữ vào bong bóng',
}

/** Thứ tự năm bước theo máy chủ — dùng để suy "bước nào đang chạy / đã xong" cho CẢ mẻ từ trạng
 *  thái THẬT của từng trang. Không có phần trăm giả: số hiện ra là số trang đã xong. */
const THU_TU_BUOC = ['detect', 'ocr', 'inpaint', 'translate', 'typeset']
const ICON_BUOC = {
  detect: 'scan', ocr: 'scan-text', inpaint: 'eraser', translate: 'languages', typeset: 'type',
}
// wording: BA review — nhãn trạng thái của thanh bước (mockup-v2 trang-chu-khach)
const NHAN_BUOC_XONG = 'Xong'
const NHAN_BUOC_CHAY = 'Đang chạy'
const NHAN_BUOC_CHO = 'Chờ tới lượt'
// wording: BA review — chú thích ảnh trước/sau ở phần kết quả
const NHAN_TRUOC = 'Trước'
const NHAN_SAU = 'Sau'
const ALT_TRUOC = 'Trang gốc'

/** Trạng thái từng bước của cả mẻ, suy từ danh sách trang. Trang lỗi không chặn các bước khác. */
function tinhBuocCaMe(trang) {
  const conLai = trang.filter((t) => !t.loi)
  // -1 = chưa có tin gì từ máy chủ (chưa gửi xong / chưa hỏi lần nào): không tính vào bước nào.
  const viTri = conLai.map((t) => {
    if (t.xong) return THU_TU_BUOC.length
    const k = THU_TU_BUOC.indexOf(t.tienDo?.buoc)
    return k < 0 ? -1 : k
  })
  return THU_TU_BUOC.map((ma, k) => {
    let tt = 'cho'
    if (conLai.length && viTri.every((v) => v > k)) tt = 'xong'
    else if (conLai.some((t, i) => viTri[i] === k && t.tienDo?.dang_chay)) tt = 'chay'
    return { ma, nhan: TEN_BUOC[ma], tt }
  })
}

const DUOI_GOI = /\.(zip|cbz|pdf)$/i

/** Ảnh GỐC người dùng vừa chọn, dựng từ chính tệp trong máy (không gọi máy chủ). Nếu trang đến từ
 *  gói zip/cbz/pdf (không có tệp ảnh rời trong RAM), lấy qua đường dẫn ảnh gốc của trang dịch nhanh. */
function AnhTruoc({ file, ten, pageId }) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    if (!file || !/^image\//.test(file.type || '') || typeof URL.createObjectURL !== 'function') {
      setUrl(null)
      return undefined
    }
    const u = URL.createObjectURL(file)
    setUrl(u)
    return () => { if (typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(u) }
  }, [file])
  const src = url || (pageId ? api.urlAnhGocDichNhanh(pageId) : null)
  if (!src) return null
  return <img src={src} alt={`${ALT_TRUOC}: ${ten}`} loading="lazy" />
}

/** Một dòng tiến độ của một trang.
 *
 * Dùng ĐÚNG ba trường máy chủ trả, và phân biệt **đang chờ** với **đang chạy**: gộp hai thứ đó
 * làm thanh tiến độ nói dối — người dùng thấy "đang xử lý" trong khi việc còn nằm sau 6 trang
 * khác. `so_viec_cho_truoc` là con số duy nhất giải thích được vì sao phải đợi.
 */
function TienDoTrang({ tienDo }) {
  const ten = TEN_BUOC[tienDo?.buoc] || 'Đang chuẩn bị'
  if (!tienDo?.dang_chay && tienDo?.so_viec_cho_truoc > 0) {
    return (
      <span className="nhan-cho">
        <Icon ten="dong-ho" co={16} /> Đang chờ — còn {tienDo.so_viec_cho_truoc} việc trước
      </span>
    )
  }
  return (
    <span className="nhan-chay">
      <Icon ten="quay" co={16} /> {ten}…
    </span>
  )
}

/** Trang chủ: thả tệp là chạy.
 *
 * ## Nguyên tắc §4.1 đặc tả
 *
 * Không bắt khai báo gì trước. Đăng ký là thứ người dùng chọn khi muốn nhiều hơn, không phải cổng
 * chặn ở cửa — nên trang này chạy được khi CHƯA đăng nhập.
 *
 * ## Bốn thứ phải nói TRƯỚC khi người dùng bắt đầu (§4.2)
 *
 * 1. còn bao nhiêu lượt, bao giờ có lại — `TheHanMuc`;
 * 2. **tệp chỉ giữ 30 phút**, và nói đúng mức hậu quả §2.9;
 * 3. hỗ trợ ngôn ngữ/định dạng nào;
 * 4. một trang mất **~30 giây** — thiếu câu này người dùng tưởng máy treo.
 *
 * ## Tự động tải về: NỖ LỰC TỐT NHẤT, và nói thẳng là như vậy
 *
 * Trình duyệt thường chặn lượt tải không do người bấm, và **JavaScript không có cách nào biết nó
 * đã bị chặn** — không có sự kiện, không có ngoại lệ. Nên ở đây không giả vờ dò được: nút tải
 * thủ công **luôn** hiện, kèm câu nói rõ "nếu tệp không tự tải về thì bấm đây". Im lặng coi như
 * xong là đúng thứ §3.2 cấm.
 */
/* E64 — `onMoDangNhap` đã bỏ: lối đăng nhập nay nằm trên THANH ĐẦU TRANG (`App.jsx`), chỗ mọi
   trang web đặt nó. Trước đây nó là một liên kết gạch chân đứng trơ giữa khoảng trắng, dưới khối
   hạn mức, và trang này không hề có thanh đầu trang nào để neo nó vào. */
export default function TrangChu() {
  const { laEn } = useNgonNguUI()
  const [files, setFiles] = useState([])
  const [ngonNgu, setNgonNgu] = useState('ja')
  const [ngonNguDich, setNgonNguDich] = useState('vi')
  const [fontChu, setFontChu] = useState('bangers')
  const [tuDienRieng, setTuDienRieng] = useState('')
  const [moTuDien, setMoTuDien] = useState(false)

  useEffect(() => {
    setNgonNguDich(laEn ? 'en' : 'vi')
  }, [laEn])
  // E67 — mặc định MIỄN PHÍ. Chủ dự án chốt: người dùng tự chọn, không ai bị tính tiền ngoài ý
  // muốn. Đây là lựa chọn của TRANG CHỦ, gửi thẳng lên máy chủ — E58 đã chốt rằng lựa chọn này
  // phải được LƯU chứ không để `NULL` thừa hưởng mặc định hệ thống.
  const [cachDich, setCachDich] = useState('google_fast')
  const codex = useCodex()
  const [dangNhanDang, setDangNhanDang] = useState(false)
  const [ketQuaNhanDang, setKetQuaNhanDang] = useState(null)
  const [loiNhanDang, setLoiNhanDang] = useState(null)
  const [dangChay, setDangChay] = useState(false)
  const [trang, setTrang] = useState([])          // [{page_id, ten, xong, buoc, loi}]
  const [projectId, setProjectId] = useState(null)
  const [loiChung, setLoiChung] = useState(null)
  const [xongLuc, setXongLuc] = useState(null)
  const [daThuTuTai, setDaThuTuTai] = useState(false)
  const [dangTai, setDangTai] = useState(false)
  const [tenTepDaTai, setTenTepDaTai] = useState(null)
  // E99 (Chuẩn Ichigo Reader) — Chế độ đọc dọc liền mạch vs So sánh Trước-Sau & tuỳ chọn định dạng gói tải về
  const [cheDoXem, setCheDoXem] = useState('so_sanh') // 'so_sanh' | 'doc_doc'
  const [dinhDangXuat, setDinhDangXuat] = useState('cbz') // 'cbz' | 'zip'
  const [trangDangXemGoc, setTrangDangXemGoc] = useState(null)

  const [hanMuc, setHanMuc] = useState(null)
  const [dangTaiHanMuc, setDangTaiHanMuc] = useState(true)
  const [loiHanMuc, setLoiHanMuc] = useState(null)

  const huy = useRef(false)
  // Đặt lại `false` lúc gắn: React.StrictMode (chế độ dev) gắn → gỡ → gắn lại, và nếu chỉ có
  // nhánh gỡ thì cờ kẹt ở `true` mãi, mọi `setState` sau đó bị bỏ — hạn mức treo ở khung chờ.
  useEffect(() => { huy.current = false; return () => { huy.current = true } }, [])

  const napHanMuc = useCallback(async () => {
    setDangTaiHanMuc(true)
    setLoiHanMuc(null)
    try {
      const hm = await api.layHanMuc()
      if (!huy.current) setHanMuc(hm)
    } catch (e) {
      if (!huy.current) setLoiHanMuc(e)
    } finally {
      if (!huy.current) setDangTaiHanMuc(false)
    }
  }, [])

  useEffect(() => { napHanMuc() }, [napHanMuc])

  const conLai = hanMuc?.con_lai ?? null
  //: `null`/`undefined` ⇒ KHÔNG tự xoá. Phân biệt với `0` (xoá ngay) nên dùng `?? null`, không `||`.
  const giuPhut = hanMuc?.giu_ket_qua_phut ?? null
  const coTuXoa = typeof giuPhut === 'number'
  const chuGiu = chuThoiGianGiu(giuPhut)
  const thieuLuot = conLai !== null && files.length > conLai

  /** E57 — đọc thử trang ĐẦU rồi đặt ô chọn theo kết quả.
   *
   * Chỉ trang đầu: một chapter cùng một ngôn ngữ, đọc thử cả mẻ là tốn công và tốn lượt vô ích.
   *
   * KHÔNG tự chạy khi người dùng chọn tệp: nó tốn một lượt của bộ đếm riêng, và tự tiêu lượt của
   * người dùng cho một việc họ chưa yêu cầu là sai. Phải bấm.
   */
  async function nhanDangNgonNgu() {
    if (!files.length) return
    setDangNhanDang(true)
    setKetQuaNhanDang(null)
    setLoiNhanDang(null)
    try {
      const { id } = await api.guiNhanDangNgonNgu(files[0])
      // Hỏi lại tới khi `xong`. Trần lượt hỏi để một việc kẹt không làm vòng lặp chạy mãi.
      let kq = null
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 1500))
        if (huy.current) return
        kq = await api.layNhanDangNgonNgu(id)
        if (kq.xong) break
      }
      if (huy.current) return
      if (!kq?.xong) {
        setLoiNhanDang(new Error('Đọc thử lâu hơn bình thường. Bạn chọn tay giúp nhé.'))
        return
      }
      setKetQuaNhanDang(kq)
      // Đặt ô chọn theo kết quả — người dùng vẫn sửa lại được, đó là điểm chính của cách này.
      if (kq.ngon_ngu) setNgonNgu(kq.ngon_ngu)
    } catch (e) {
      setLoiNhanDang(e)
    } finally {
      if (!huy.current) setDangNhanDang(false)
    }
  }

  async function batDau() {
    setDangChay(true)
    setLoiChung(null)
    setXongLuc(null)
    setDaThuTuTai(false)
    setTenTepDaTai(null)

    const dsTrang = files.map((f, idx) => ({
      槽: idx, ten: f.name, page_id: null, xong: false, tienDo: null, loi: null,
    }))
    setTrang(dsTrang)

    let pid = null
    const idTrang = []
    for (let i = 0; i < files.length; i++) {
      const tep = files[i]
      const laGoi = DUOI_GOI.test(tep.name || '')
      try {
        if (laGoi) {
          const raGoi = await api.guiGoiDichNhanh(
            tep,
            {
              sourceLang: ngonNgu,
              targetLang: ngonNguDich,
              cheDo: 'day_du',
              engine: cachDich,
              fontStyle: fontChu,
              tuDienRieng,
            },
          )
          if (!pid && raGoi.project_id) pid = raGoi.project_id
          const trangMoRong = (raGoi.trang || []).map((tr) => ({
            槽: i,
            ten: tr.ten_trong_goi || tep.name,
            page_id: tr.page_id,
            xong: false,
            tienDo: null,
            loi: null,
          }))
          for (const tr of trangMoRong) idTrang.push(tr.page_id)
          if (!huy.current) {
            setTrang((cu) => {
              const truoc = cu.filter((t) => t.槽 < i)
              const sau = cu.filter((t) => t.槽 > i)
              return [...truoc, ...trangMoRong, ...sau]
            })
          }
        } else {
          const ra = await api.guiTrangDichNhanh(
            tep,
            {
              sourceLang: ngonNgu,
              targetLang: ngonNguDich,
              cheDo: 'day_du',
              engine: cachDich,
              fontStyle: fontChu,
              tuDienRieng,
            },
          )
          idTrang.push(ra.page_id)
          if (!huy.current) {
            setTrang((cu) => cu.map((t) => (t.槽 === i ? { ...t, page_id: ra.page_id } : t)))
          }
        }
      } catch (e) {
        // 429 = hết hạn mức. Máy chủ đã gửi đủ thông tin để nói câu tử tế; `doc()` đính nó vào
        // `e.chiTiet`. Dừng NGUYÊN mẻ chứ không gửi tiếp: gửi tiếp chỉ nhận thêm 429.
        if (!huy.current) {
          setLoiChung(e)
          setTrang((cu) => cu.map((t) => (t.槽 >= i ? { ...t, loi: 'chưa gửi được' } : t)))
        }
        break
      }
    }

    if (!idTrang.length) {
      if (!huy.current) { setDangChay(false); napHanMuc() }
      return
    }

    // Hỏi tiến độ tới khi mọi trang `xong`. Đọc trường `xong` của máy chủ, KHÔNG tự suy từ
    // `trang_thai`: `translated` là đích của chế độ chỉ-chữ nhưng là giữa đường của chế độ đầy đủ.
    const conCho = new Set(idTrang)
    for (let vong = 0; vong < 900 && conCho.size && !huy.current; vong++) {
      for (const id of Array.from(conCho)) {
        try {
          const ra = await api.layTrangDichNhanh(id)
          if (huy.current) return
          setTrang((cu) => cu.map((t) => (t.page_id === id
            ? { ...t, xong: ra.xong, tienDo: ra.tien_do ?? null, loi: ra.loi ?? null }
            : t)))
          if (!pid && ra.project_id) pid = ra.project_id
          if (ra.xong || ra.loi) conCho.delete(id)
        } catch (e) {
          if (!huy.current) {
            setTrang((cu) => cu.map((t) => (t.page_id === id ? { ...t, loi: String(e.message || e) } : t)))
          }
          conCho.delete(id)
        }
      }
      if (conCho.size) await new Promise((r) => setTimeout(r, 2000))
    }

    if (!huy.current) {
      setProjectId(pid)
      setXongLuc(new Date().toISOString())
      setDangChay(false)
      napHanMuc()
    }
  }

  const trangXong = trang.filter((t) => t.xong && t.page_id)

  /** Tải kết quả về. `tuDong = true` là lượt thử KHÔNG do người bấm — có thể bị chặn im lặng. */
  const taiKetQua = useCallback(async (tuDong = false) => {
    if (!trangXong.length) return
    setDangTai(true)
    try {
      if (trangXong.length === 1) {
        // Một trang thì tải thẳng ảnh — không cần gói, và gói một tệp là thêm một lượt chờ worker.
        //
        // PHẢI đi qua `blob:`: thuộc tính `download` của <a> bị trình duyệt **bỏ qua** khi href
        // trỏ sang nguồn khác, và API nằm ở tên miền khác giao diện. Gán href thẳng vào URL API
        // thì trình duyệt MỞ ảnh thay vì lưu về — trông như "không tải được" mà không có lỗi nào.
        const ten = `${trangXong[0].ten.replace(/\.[^.]+$/, '')}-da-dich.png`
        const blobUrl = await api.taiVeBlobUrl(api.urlAnhDaDich(trangXong[0].page_id))
        const a = document.createElement('a')
        a.href = blobUrl
        a.download = ten
        document.body.appendChild(a)
        a.click()
        a.remove()
        // Thu hồi ngay là có trình duyệt huỷ luôn lượt tải đang chạy — chờ một nhịp, giống
        // `taiFileXuatVe` đã làm.
        setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000)
        setTenTepDaTai(ten)
      } else if (projectId) {
        // §3.3 — nhiều trang thì MỘT tệp nén. Tải 24 tệp rời là 24 lần bị trình duyệt hỏi.
        const job = await api.xuatChapterDichNhanh(projectId, dinhDangXuat)
        await api.choXuatXong(job.job_id)
        const ten = await api.taiFileXuatVe(job.job_id, dinhDangXuat)
        setTenTepDaTai(ten)
      }
    } catch (e) {
      if (!huy.current) setLoiChung(e)
    } finally {
      if (!huy.current) { setDangTai(false); if (tuDong) setDaThuTuTai(true) }
    }
  }, [trangXong, projectId, dinhDangXuat])

  // Thử tải tự động MỘT lần khi vừa xong. Không lặp lại: bấm tải nhiều lần là đúng thứ làm trình
  // duyệt chặn hẳn về sau.
  useEffect(() => {
    if (xongLuc && trangXong.length && !daThuTuTai) taiKetQua(true)
  }, [xongLuc, trangXong.length, daThuTuTai, taiKetQua])

  const mocHetHan = coTuXoa ? mocHetHanGiuTep(xongLuc, giuPhut) : null
  const daHetHan = Boolean(mocHetHan) && conLaiMs(mocHetHan) <= 0

  return (
    <main className="trang-chu manga-world-page">
      {/* ĐỢT 2 + E107 — Hero phong cách Thế Giới Truyện Tranh (Manga/Manhwa Studio) */}
      <header className="trang-chu-dau manga-hero-banner">
        <div className="manga-hero-fx" aria-hidden="true">
          <span className="manga-bubble-tag tag-trai">
            💬 &ldquo;{laEn ? 'Clean Inpainting — Keep Bubble Borders Intact!' : 'Xoá sạch chữ gốc — Giữ nguyên viền bong bóng!'}&rdquo;
          </span>
          <span className="manga-bubble-tag tag-phai">⚡ &ldquo;Manga · Manhwa · Manhua · Comic!&rdquo;</span>
        </div>
        <div className="manga-genre-strip" aria-hidden="true">
          <span>⚔️ {laEn ? 'Action' : 'Hành động'}</span>
          <span>🌸 {laEn ? 'Romance' : 'Ngôn tình'}</span>
          <span>📜 {laEn ? 'Historical' : 'Cổ trang'}</span>
          <span>💬 {laEn ? 'Comics & Webtoon' : 'Truyện tranh'}</span>
          <span>🌍 {laEn ? 'VN & Global English' : 'Việt & Quốc tế'}</span>
        </div>
        <h1>
          {laEn
            ? 'AI Manga, Manhwa & Webtoon Translator'
            : 'Dịch truyện tranh sang tiếng Việt'}
        </h1>
        <p className="dan">
          {laEn
            ? 'Drop comic pages or chapter archives (.zip / .cbz / .pdf) here to translate instantly — no sign-up required.'
            : 'Thả ảnh trang truyện vào đây là chạy — không cần đăng ký trước.'}
        </p>
        <div className="manga-hero-actions">
          <a href="#tien-ich" className="nut-manga nut-manga-chinh">
            🧩 {laEn ? 'Install Chrome Extension & Windows App' : 'Cài Tiện Ích Chrome & App Windows'}
          </a>
          <a href="#ket-noi-api" className="nut-manga nut-manga-win">
            ⚡ {laEn ? 'Developer API Integration' : 'Kết Nối API Cho Tool / Web'}
          </a>
          <a href="#bang-gia" className="nut-manga nut-manga-phu">
            💎 {laEn ? 'Pricing & VIP Top-up' : 'Bảng Giá & Nạp Lượt VIP'}
          </a>
        </div>
      </header>

      {loiChung && (
        <Alert sac="loi" tieuDe={loiChung.ma === 429 ? 'Hết lượt' : 'Không chạy được'}>
          {String(loiChung.message || loiChung).replace(/^\d+:\s*/, '')}
          {loiChung.chiTiet?.reset_luc && (
            <> Có lại sau <strong>{chuDemNguoc(loiChung.chiTiet.reset_luc)}</strong>.</>
          )}
        </Alert>
      )}

      <div className="luoi-khach">
      <div className="cot-chinh">
      <section className="vung-gui" aria-labelledby="tieu-de-gui">
        {/* Giữ cho trình đọc màn hình (vùng này cần có tên), ẩn khỏi mắt: ngay dưới nó ô thả
            đã tự nói "Kéo ảnh vào đây hoặc bấm để chọn" — hiện cả hai là lặp. */}
        <h2 id="tieu-de-gui" className="an-di">Chọn trang truyện</h2>

        <Dropzone files={files} onDoi={setFiles} chapNhanGoi id="tha-trang-chu" />

        {/* Bảng điều khiển nhanh kiểu Pill-Grid (Chuẩn Tiện Ích v0.4.0 / Hình 3) */}
        <div className="bo-chon-manga">
          <div className="nhom-chon-manga">
            <span className="nhan-nhom-chon">
              {laEn ? 'Source Language on Page (Instant switch):' : 'Ngôn ngữ gốc trên trang (Đổi tức thì):'}
            </span>
            <div className="luoi-nut-chon" role="radiogroup" aria-label="Ngôn ngữ gốc trên trang">
              {PILL_NGON_NGU_GOC.map((item) => {
                const dangChon = ngonNgu === item.ma
                return (
                  <button
                    key={item.ma}
                    type="button"
                    role="radio"
                    aria-checked={dangChon}
                    disabled={dangChay}
                    className={`nut-chon-pill ${dangChon ? 'dang-chon' : ''}`}
                    onClick={() => setNgonNgu(item.ma)}
                  >
                    <span className="pill-co">{item.co}</span>
                    <span>{laEn ? item.nhanEn : item.nhan}</span>
                  </button>
                )
              })}
            </div>
          </div>

          <div className="nhom-chon-manga">
            <span className="nhan-nhom-chon">
              {laEn ? 'Target Language (Vietnamese & International):' : 'Ngôn ngữ dịch ra (Việt Nam & Quốc tế):'}
            </span>
            <div className="luoi-nut-chon luoi-2-cot" role="radiogroup" aria-label="Ngôn ngữ dịch ra">
              {PILL_NGON_NGU_DICH.map((item) => {
                const dangChon = ngonNguDich === item.ma
                return (
                  <button
                    key={item.ma}
                    type="button"
                    role="radio"
                    aria-checked={dangChon}
                    disabled={dangChay}
                    className={`nut-chon-pill ${dangChon ? 'dang-chon' : ''}`}
                    onClick={() => setNgonNguDich(item.ma)}
                  >
                    <span className="pill-co">{item.co}</span>
                    <span>{laEn ? item.nhanEn : item.nhan}</span>
                  </button>
                )
              })}
            </div>
          </div>

          <div className="nhom-chon-manga">
            <span className="nhan-nhom-chon">
              {laEn ? 'Translation Engine:' : 'Bộ máy dịch thuật:'}
            </span>
            <div className="luoi-nut-chon luoi-2-cot" role="radiogroup" aria-label="Bộ máy dịch thuật">
              <button
                type="button"
                role="radio"
                aria-checked={cachDich === 'llm_context'}
                disabled={dangChay}
                className={`nut-chon-pill ${cachDich === 'llm_context' ? 'dang-chon' : ''}`}
                onClick={() => setCachDich('llm_context')}
              >
                <span className="pill-co">✨</span>
                <span>{laEn ? 'Gemini AI (Context-Aware)' : 'Gemini AI (Chuẩn ngữ cảnh)'}</span>
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={cachDich === 'google_fast'}
                disabled={dangChay}
                className={`nut-chon-pill ${cachDich === 'google_fast' ? 'dang-chon' : ''}`}
                onClick={() => setCachDich('google_fast')}
              >
                <span className="pill-co">⚡</span>
                <span>{laEn ? 'Google Fast (Free)' : 'Google Nhanh'}</span>
              </button>
            </div>
          </div>

          <div className="nhom-chon-manga">
            <span className="nhan-nhom-chon">
              {laEn ? 'Genre Font Style (Direct typesetting):' : 'Font chữ theo thể loại truyện (Đổi trực tiếp trên trang):'}
            </span>
            <div className="luoi-nut-chon luoi-2-cot" role="radiogroup" aria-label="Font chữ theo thể loại">
              {PILL_FONT_THE_LOAI.map((item) => {
                const dangChon = fontChu === item.ma
                return (
                  <button
                    key={item.ma}
                    type="button"
                    role="radio"
                    aria-checked={dangChon}
                    disabled={dangChay}
                    className={`nut-chon-pill ${dangChon ? 'dang-chon' : ''}`}
                    onClick={() => setFontChu(item.ma)}
                  >
                    <span className="pill-co">{item.bieuTuong}</span>
                    <span>{laEn ? item.nhanEn : item.nhan}</span>
                  </button>
                )
              })}
            </div>
          </div>

          <div className="nhom-chon-manga">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
              <span className="nhan-nhom-chon">
                📖 {laEn ? 'Character & Pronoun Glossary (Consistent across chapters):' : 'Sổ tay Nhân vật & Xưng hô cố định (Chuẩn xuyên suốt các chương):'}
              </span>
              <span
                role="button"
                tabIndex={0}
                className="nut-chu"
                style={{ fontSize: 12.5, fontWeight: 700, cursor: 'pointer' }}
                onClick={() => setMoTuDien(!moTuDien)}
                onKeyDown={(e) => { if (e.key === 'Enter') setMoTuDien(!moTuDien) }}
              >
                {moTuDien
                  ? (laEn ? '▲ Hide Glossary' : '▲ Thu gọn sổ tay')
                  : (laEn ? '➕ Open Character & Pronoun Glossary' : '➕ Mở thiết lập Xưng hô & Tên nhân vật')}
              </span>
            </div>
            {moTuDien && (
              <div className="khung-tu-dien-nhanh">
                <div className="day-mau-xung-ho">
                  {MAU_XUNG_HO.map((m) => (
                    <span
                      key={m.nhan}
                      role="button"
                      tabIndex={0}
                      className="chip-mau-xung-ho"
                      onClick={() => setTuDienRieng((cu) => (cu ? `${cu}\n${m.giaTri}` : m.giaTri))}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') setTuDienRieng((cu) => (cu ? `${cu}\n${m.giaTri}` : m.giaTri))
                      }}
                    >
                      {m.nhan}
                    </span>
                  ))}
                </div>
                <textarea
                  className="o o-tu-dien"
                  rows={3}
                  disabled={dangChay}
                  value={tuDienRieng}
                  onChange={(e) => setTuDienRieng(e.target.value)}
                  placeholder="Ví dụ:&#10;- Sung Jin-Woo: xưng tôi, gọi cậu&#10;- Cha Hae-In: xưng em, gọi anh&#10;- Shadow Monarch = Quân Vương Bóng Tối"
                />
              </div>
            )}
          </div>

          <div className="huy-hieu-gpu-khach">
            {laEn
              ? '🚀 Client GPU Inpainting · Double-click to Edit — Ultra-fast ~3s'
              : '🚀 Xoá chữ GPU khách · Nhấp đúp sửa câu — Siêu tốc ~3s'}
          </div>
        </div>

        <div className="hang-chon">
          {/* Ẩn khỏi màn hình vì đã có bảng Pill-Grid ở trên; giữ trong DOM cho trình đọc màn hình & bài kiểm thử */}
          <div className="o-chon-khach an-di">
            <label htmlFor="chon-ngon-ngu">Chữ trên ảnh là tiếng gì?</label>
            <select
              id="chon-ngon-ngu" className="o" value={ngonNgu}
              onChange={(e) => setNgonNgu(e.target.value)}
              disabled={dangChay}
            >
              {NGON_NGU.map((n) => <option key={n.ma} value={n.ma}>{n.nhan}</option>)}
            </select>
          </div>

          <div className="o-chon-khach an-di">
            <label htmlFor="chon-cach-dich">Dịch bằng gì?</label>
            <select
              id="chon-cach-dich" className="o" value={cachDich}
              onChange={(e) => setCachDich(e.target.value)}
              disabled={dangChay}
            >
              <option value="google_fast">Nhanh — miễn phí</option>
              <option value="llm_context">Kỹ — AI đọc cả trang</option>
              {codex.bat && (
                <option value="chatgpt_codex" disabled={!codex.da_dang_nhap}>
                  ChatGPT (tài khoản của bạn){codex.da_dang_nhap ? '' : ' — quản trị cần đăng nhập ChatGPT trước'}
                </option>
              )}
            </select>
          </div>

          {ngonNgu === TU_NHAN && (
            <div className="khoi-nhan-dang">
              <Button
                onClick={nhanDangNgonNgu} dangChay={dangNhanDang}
                lyDoKhoa={!files.length ? 'Chọn ít nhất một trang trước' : undefined}
              >
                {dangNhanDang ? 'Đang đọc thử…' : 'Đọc thử trang đầu'}
              </Button>
              <p className="ghi-chu">
                Máy đọc chữ trên trang đầu rồi đoán. Không tính vào lượt dịch của bạn.
              </p>
            </div>
          )}

          {loiNhanDang && (
            <Alert sac="canh" tieuDe="Chưa đọc thử được">
              {String(loiNhanDang.cauNguoiDoc || loiNhanDang.message || loiNhanDang)
                .replace(/^\d+:\s*/, '')}
              {' '}Bạn chọn tay ở ô trên giúp nhé.
            </Alert>
          )}

          {ketQuaNhanDang && (
            ketQuaNhanDang.ngon_ngu
              ? (
                <Alert sac="ok" tieuDe={`Máy đoán: ${TEN_NGON_NGU[ketQuaNhanDang.ngon_ngu]}`}>
                  {/* HIỆN SỐ ĐO, không chỉ nói "đã nhận dạng": một kết luận không kèm bằng chứng
                      thì người dùng không có cách nào biết nên tin bao nhiêu. */}
                  {ketQuaNhanDang.bang_chung && (
                    <>
                      Đọc được <strong>{ketQuaNhanDang.bang_chung.tong_co_nghia}</strong> ký tự
                      {ketQuaNhanDang.bang_chung.kana > 0 && <> (<strong>{ketQuaNhanDang.bang_chung.kana}</strong> chữ kana của tiếng Nhật)</>}
                      {ketQuaNhanDang.bang_chung.kana === 0 && ketQuaNhanDang.bang_chung.han > 0 && <> (<strong>{ketQuaNhanDang.bang_chung.han}</strong> chữ Hán, không có kana)</>}
                      .{' '}
                    </>
                  )}
                  Ô chọn ở trên đã đổi theo. <strong>Sai thì bạn sửa lại</strong> — máy đoán từ chữ
                  đọc được, không phải luôn đúng.
                </Alert>
              )
              : (
                <Alert sac="canh" tieuDe="Máy không đoán được">
                  {ketQuaNhanDang.ly_do?.startsWith('khong_doc_duoc_chu_nao')
                    ? 'Trang này máy không đọc ra chữ nào (có thể là trang bìa, hoặc chữ quá mờ).'
                    : 'Máy đọc được chữ nhưng không đủ để chắc chắn.'}
                  {' '}Bạn chọn tay ở ô trên giúp nhé (nếu là truyện Hàn Quốc thì chọn "Tiếng Hàn (Manhwa)") — chọn sai thì chữ dịch ra vô nghĩa.
                </Alert>
              )
          )}
        </div>

        {thieuLuot && (
          <Alert sac="canh" tieuDe="Nhiều hơn số lượt còn lại">
            Bạn chọn {files.length} trang nhưng chỉ còn {conLai} lượt. Bỏ bớt trang, hoặc đợi tới
            0h00 giờ Việt Nam.
          </Alert>
        )}

        <Button
          kieu="chinh" onClick={batDau} dangChay={dangChay}
          lyDoKhoa={
            !files.length ? 'Chọn ít nhất một trang'
              // Gửi `tu-nhan` lên đường dịch là nhận 422 — người dùng sẽ đọc một lỗi kỹ thuật cho
              // một lựa chọn mà chính giao diện mời họ chọn.
              : ngonNgu === TU_NHAN ? 'Bấm "Đọc thử trang đầu", hoặc chọn tay một ngôn ngữ'
                : thieuLuot ? 'Nhiều hơn số lượt còn lại'
                  : conLai === 0 ? 'Hết lượt hôm nay'
                    : undefined
          }
        >
          {dangChay ? 'Đang dịch…' : `Dịch ${files.length || ''} trang`.trim()}
        </Button>
      </section>


      {trang.length > 0 && (
        <section className="the-man tien-do-trang" aria-labelledby="tieu-de-tien-do" aria-live="polite">
          <h2 id="tieu-de-tien-do" className="nho">
            Tiến độ — xong {trangXong.length}/{trang.length} trang
          </h2>
          <ol className="cac-buoc" aria-label="Các bước xử lý">
            {tinhBuocCaMe(trang).map((b) => (
              <li key={b.ma} className={`buoc-the buoc-the-${b.tt}`}>
                <span className="buoc-the-tren">
                  <Icon ten={b.tt === 'xong' ? 'circle-check' : b.tt === 'chay' ? 'loader' : ICON_BUOC[b.ma]} />
                  {b.nhan}
                </span>
                <span className="buoc-the-tt">
                  {b.tt === 'xong' ? NHAN_BUOC_XONG : b.tt === 'chay' ? NHAN_BUOC_CHAY : NHAN_BUOC_CHO}
                </span>
              </li>
            ))}
          </ol>
          <div
            className="thanh-tien" role="progressbar" aria-label="Tiến độ dịch"
            aria-valuemin={0} aria-valuemax={100}
            aria-valuenow={Math.round((trangXong.length / trang.length) * 100)}
          >
            <div
              className="thanh-tien-trong"
              style={{ width: `${Math.round((trangXong.length / trang.length) * 100)}%` }}
            />
          </div>
          <ol className="ds-trang">
            {trang.map((t, i) => (
              <li key={t.page_id || i}>
                <span className="ten-trang">{t.ten}</span>
                {t.loi
                  ? <span className="nhan-loi"><Icon ten="canh" co={16} /> {t.loi}</span>
                  : t.xong
                    ? <span className="nhan-xong"><Icon ten="tich" co={16} /> Xong</span>
                    : <TienDoTrang tienDo={t.tienDo} />}
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* E61 — THU GỌN, không bỏ chữ. Bốn ý này mỗi ý được thêm vì một lần hiểu nhầm có thật
          (người dùng tưởng máy treo; tưởng tệp giữ mãi; thả nhầm định dạng; thả truyện tiếng
          Hàn). Bỏ là quay lại đúng những lần đó. Nhưng bày cả bốn ngay màn đầu thì chúng đứng
          CHẮN việc chính. `<details>` giữ đủ chữ mà trả lại màn đầu cho ô thả ảnh. */}
      <details className="can-biet the-man">
        <summary>Cần biết trước khi bắt đầu</summary>
        <ul>
          <li>
            <Icon ten="dong-ho" co={16} /> Mỗi trang mất <strong>khoảng 30 giây</strong>. Máy
            không treo — cứ để tab mở.
          </li>
          {/* Câu này phải khớp CẤU HÌNH THẬT của máy chủ. Hứa xoá trong khi không xoá, hay hứa
              giữ trong khi sẽ xoá — cả hai đều là nói sai với người dùng về dữ liệu của họ. */}
          {coTuXoa ? (
            <li>
              <strong>Kết quả chỉ giữ {chuGiu}</strong> kể từ lúc dịch xong. Sau đó
              {' '}<strong>ảnh gốc, bản dịch và tệp đã gói đều bị xoá</strong>: không chạy lại được,
              không sửa lại được. Muốn làm lại phải tải lên từ đầu và tốn thêm lượt.
            </li>
          ) : (
            <li>
              Kết quả <strong>không tự xoá</strong> theo giờ. Nhưng vẫn nên tải về ngay — đây
              không phải chỗ lưu trữ lâu dài, và chính sách có thể đổi.
            </li>
          )}
          <li>Nhận ảnh <strong>PNG, JPG, WebP</strong> (tối đa 25 MB/ảnh) và gói truyện <strong>ZIP, CBZ, PDF</strong>.</li>
          <li>Dịch được chữ <strong>Nhật, Hàn, Anh, Trung</strong> → tiếng Việt.</li>
        </ul>
      </details>
      </div>

      <aside className="cot-phai-khach" aria-label="Hạn mức">
        <div className="the-man">
          <TheHanMuc
            hanMuc={hanMuc} dangTai={dangTaiHanMuc} loi={loiHanMuc} onTaiLai={napHanMuc}
          />
        </div>
        {/* E61 — luật giữ tệp phải tới mắt người dùng TRƯỚC khi họ bỏ công chờ, không phải sau khi
            mất tệp. Chú thích cũ của `.can-biet` chốt đúng điều đó, và việc thu khối kia vào
            `<details>` sẽ xoá mất bảo đảm ấy.
            Nên giữ lại đúng MỘT dòng, và CHỈ khi chính sách xoá đang bật — lúc nó không bật thì
            câu này là chữ thừa. Nội dung đầy đủ vẫn nằm trong `<details>` bên dưới. */}
        {coTuXoa && (
          <p className="luu-y-giu-tep">
            {/* Cố ý KHÔNG lặp lại đúng câu trong `<details>`: hai câu y hệt trên cùng một màn là
                bắt người dùng đọc hai lần. Dòng này nói phần HÀNH ĐỘNG (tải về ngay), khối kia nói
                phần HẬU QUẢ đầy đủ (mất cả ảnh gốc lẫn tệp đã gói, không chạy lại được). */}
            <Icon ten="dong-ho" co={16} /> Nhớ tải về ngay: tệp <strong>tự xoá sau {chuGiu}
            </strong> kể từ lúc dịch xong.
          </p>
        )}
      </aside>
      </div>

      {xongLuc && trangXong.length > 0 && (
        <section className="ket-qua" aria-labelledby="tieu-de-ket-qua">
          <h2 id="tieu-de-ket-qua" className="nho">Kết quả</h2>

          {!coTuXoa ? (
            <Alert sac="tin" tieuDe="Nhớ tải về">
              Kết quả <strong>không tự xoá</strong> theo giờ, nhưng đây không phải chỗ lưu trữ lâu
              dài — tải về rồi hãy đóng tab.
            </Alert>
          ) : daHetHan ? (
            <Alert sac="loi" tieuDe={`Đã quá ${chuGiu} — tệp không còn nữa`}>
              Ảnh gốc, bản dịch và tệp đã gói đều đã bị xoá. Muốn có lại thì phải tải lên từ đầu
              và tốn thêm lượt.
            </Alert>
          ) : (
            <Alert sac="canh" tieuDe="Tải về trước khi hết giờ">
              Còn <strong>{chuDemNguoc(mocHetHan)}</strong> trước khi toàn bộ kết quả bị xoá —
              ảnh gốc, bản dịch, tệp đã gói. Xoá rồi thì không chạy lại và không sửa lại được.
            </Alert>
          )}

          {/* Nút thủ công LUÔN hiện, kèm câu nói rõ. Trình duyệt thường chặn lượt tải không do
              người bấm, và JavaScript không có cách nào biết nó đã bị chặn — nên không giả vờ dò
              được, chỉ nói thật. */}
          <div className="hang-tai-ve">
            <Button kieu="chinh" onClick={() => taiKetQua(false)} dangChay={dangTai} icon="download">
              {trangXong.length > 1 ? `Tải cả gói (${dinhDangXuat.toUpperCase()}) về` : 'Tải ảnh đã dịch về'}
            </Button>
            {trangXong.length > 1 && (
              <label className="chon-dinh-dang-xuat" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                <span>Định dạng gói:</span>
                <select
                  aria-label="Định dạng gói tải về"
                  className="o"
                  style={{ width: 'auto', padding: '4px 10px' }}
                  value={dinhDangXuat}
                  onChange={(e) => setDinhDangXuat(e.target.value)}
                  disabled={dangTai}
                >
                  <option value="cbz">.CBZ (Trình đọc truyện)</option>
                  <option value="zip">.ZIP (Giải nén ảnh PNG)</option>
                </select>
              </label>
            )}
            <div className="bo-chuyen-che-do-xem" role="group" aria-label="Chế độ xem kết quả" style={{ display: 'inline-flex', gap: 6, marginLeft: 'auto' }}>
              <Button
                kieu={cheDoXem === 'so_sanh' ? 'phu' : 'ghost'}
                co="nho"
                onClick={() => setCheDoXem('so_sanh')}
              >
                So sánh Trước – Sau
              </Button>
              <Button
                kieu={cheDoXem === 'doc_doc' ? 'phu' : 'ghost'}
                co="nho"
                onClick={() => setCheDoXem('doc_doc')}
              >
                Đọc dọc liền mạch
              </Button>
            </div>
            {daThuTuTai && !tenTepDaTai && (
              <p className="ghi-chu" style={{ width: '100%' }}>
                Đã thử tải tự động. <strong>Nếu không thấy tệp nào</strong>, trình duyệt đã chặn
                lượt tải không do bạn bấm — bấm nút trên là được.
              </p>
            )}
            {tenTepDaTai && (
              <p className="ghi-chu" style={{ width: '100%' }}>
                <Icon ten="tich" co={16} /> Đã lưu <strong>{tenTepDaTai}</strong>. Không thấy thì
                xem lại thư mục Tải về của trình duyệt.
              </p>
            )}
          </div>

          {!daHetHan && (
            cheDoXem === 'doc_doc' ? (
              <ul className="ds-anh ds-anh-doc-doc" style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 820, margin: '16px auto 0', padding: 0, listStyle: 'none' }}>
                {trangXong.map((t, idx) => {
                  const dangGiu = trangDangXemGoc === t.page_id
                  return (
                    <li
                      key={t.page_id}
                      style={{ position: 'relative', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--vien, #e2e8f0)', background: '#0f172a' }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 12px', background: 'rgba(15,23,42,0.88)', color: '#f8fafc', fontSize: 12 }}>
                        <span>Trang {idx + 1}/{trangXong.length} · {t.ten}</span>
                        <button
                          type="button"
                          onMouseDown={() => setTrangDangXemGoc(t.page_id)}
                          onMouseUp={() => setTrangDangXemGoc(null)}
                          onMouseLeave={() => setTrangDangXemGoc(null)}
                          onTouchStart={() => setTrangDangXemGoc(t.page_id)}
                          onTouchEnd={() => setTrangDangXemGoc(null)}
                          onClick={() => setTrangDangXemGoc((cu) => (cu === t.page_id ? null : t.page_id))}
                          style={{
                            border: '1px solid rgba(255,255,255,0.28)', borderRadius: 999,
                            padding: '2px 10px', background: dangGiu ? '#2563eb' : 'transparent',
                            color: '#fff', cursor: 'pointer', fontSize: 12,
                          }}
                        >
                          {dangGiu ? 'Đang hiện bản gốc' : 'Giữ / Bấm xem bản gốc'}
                        </button>
                      </div>
                      <img
                        src={dangGiu ? api.urlAnhGocDichNhanh(t.page_id) : api.urlAnhDaDich(t.page_id)}
                        alt={dangGiu ? `${ALT_TRUOC}: ${t.ten}` : `Trang đã dịch: ${t.ten}`}
                        loading="lazy"
                        style={{ display: 'block', width: '100%', height: 'auto' }}
                      />
                    </li>
                  )
                })}
              </ul>
            ) : (
              <ul className="ds-anh">
                {trangXong.map((t) => {
                  const file = files.find((f) => f.name === t.ten)
                  return (
                    <li key={t.page_id}>
                      <div className="cap-anh">
                        <figure>
                          <AnhTruoc file={file} ten={t.ten} pageId={t.page_id} />
                          <figcaption>{NHAN_TRUOC}</figcaption>
                        </figure>
                        <figure>
                          <img src={api.urlAnhDaDich(t.page_id)} alt={`Trang đã dịch: ${t.ten}`} loading="lazy" />
                          <figcaption>{NHAN_SAU}</figcaption>
                        </figure>
                      </div>
                      <span className="ghi-chu">{t.ten}</span>
                    </li>
                  )
                })}
              </ul>
            )
          )}
        </section>
      )}

      {/* E64 — trang này trước đây KẾT THÚC ngay sau khối `<details>`, ở khoảng 3/4 chiều cao màn,
          để lại một mảng trắng lớn bên dưới: nhìn như trang tải dở.

          Ba bước dưới đây không phải chữ độn. Chúng trả lời đúng câu hỏi mà một người lần đầu vào
          đây phải tự đoán: thả ảnh xong thì CHUYỆN GÌ xảy ra, và cuối cùng mình nhận được cái gì.

          Cố ý KHÔNG nhắc lại "khoảng 30 giây mỗi trang" và "tệp giữ 30 phút" — khối `<details>`
          ngay trên đã nói cả hai, và lặp lại là đúng thứ đang làm màn này rối. */}
      <section className="cach-chay" aria-labelledby="tieu-de-cach-chay">
        <h2 id="tieu-de-cach-chay">Cách hoạt động</h2>
        <ol className="ds-buoc">
          <li>
            <span className="so-buoc" aria-hidden="true">01</span>
            <b>Thả ảnh trang truyện</b>
            <span>Chọn một hay nhiều trang cùng lúc. Không cần tài khoản.</span>
          </li>
          <li>
            <span className="so-buoc" aria-hidden="true">02</span>
            <b>Máy đọc chữ rồi dịch</b>
            <span>Nhận ra chữ trên ảnh, dịch sang tiếng Việt, rồi căn vào đúng bong bóng.</span>
          </li>
          <li>
            <span className="so-buoc" aria-hidden="true">03</span>
            <b>Tải ảnh đã dịch về</b>
            <span>Nhiều trang thì tải một gói. Xem trước ngay trên trang này trước khi tải.</span>
          </li>
        </ol>
      </section>

      <ChanTrangManga />
    </main>
  )
}
