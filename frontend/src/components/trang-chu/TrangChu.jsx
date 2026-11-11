import { useCallback, useEffect, useRef, useState } from 'react'

import * as api from '../../api'
import { useCodex } from '../../lib/dung-codex'
import { chuDemNguoc, conLaiMs, mocHetHanGiuTep } from '../../lib/dem-nguoc'
import Alert from '../ui/Alert'
import Button from '../ui/Button'
import Dropzone from '../ui/Dropzone'
import { chuThoiGianGiu } from '../../lib/thoi-gian-giu.js'
import { HERO_I18N, useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
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
  { ma: 'ja', co: '🇯🇵', nhan: 'Tiếng Nhật (Manga)', nhanEn: 'Japanese (Manga)' },
  { ma: 'ko', co: '🇰🇷', nhan: 'Tiếng Hàn (Manhwa / Webtoon)', nhanEn: 'Korean (Manhwa / Webtoon)' },
  { ma: 'zh', co: '🇨🇳', nhan: 'Tiếng Trung (Manhua)', nhanEn: 'Chinese (Manhua)' },
  { ma: 'en', co: '🇬🇧', nhan: 'Tiếng Anh (Comic)', nhanEn: 'English (Comic)' },
  { ma: TU_NHAN, co: '🔍', nhan: 'Tự nhận diện (Đọc thử trang đầu)', nhanEn: 'Auto Detect (Sample 1st page)' },
]

const PILL_NGON_NGU_DICH = [
  { ma: 'vi', co: '🇻🇳', nhan: 'Sang Tiếng Việt', nhanEn: 'To Vietnamese' },
  { ma: 'en', co: '🇺🇸', nhan: 'To English', nhanEn: 'To English' },
  { ma: 'zh', co: '🇨🇳', nhan: '简体中文 (Trung Giản thể)', nhanEn: 'Simplified Chinese (简体)' },
  { ma: 'zh-TW', co: '🇹🇼', nhan: '繁體中文 (Đài Loan/HK)', nhanEn: 'Traditional Chinese (繁體)' },
  { ma: 'id', co: '🇮🇩', nhan: 'Bahasa Indonesia', nhanEn: 'Indonesian' },
  { ma: 'es', co: '🇪🇸', nhan: 'Español (Tây Ban Nha)', nhanEn: 'Spanish (Español)' },
  { ma: 'pt', co: '🇧🇷', nhan: 'Português (Brazil)', nhanEn: 'Portuguese (Português)' },
  { ma: 'th', co: '🇹🇭', nhan: 'ภาษาไทย (Tiếng Thái)', nhanEn: 'Thai (ภาษาไทย)' },
  { ma: 'fr', co: '🇫🇷', nhan: 'Français (Tiếng Pháp)', nhanEn: 'French (Français)' },
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
    nhanEn: '🏮 Historical / Martial Arts (Lord / Senior / Junior)',
    giaTri: 'Xưng hô phong cách Cổ trang / Tu tiên: dùng Ta - Ngươi, Huynh - Đệ - Muội, Bản tôn, Tiền bối.',
    giaTriEn: 'Historical / Martial Arts style: use formal/archaic terms, Senior/Junior, Sect Master, keep skill names.',
  },
  {
    nhan: '🌸 Ngôn tình / Học đường (Anh - Em / Tớ - Cậu)',
    nhanEn: '🌸 Romance / School Life (Warm & natural tone)',
    giaTri: 'Xưng hô phong cách Ngôn tình / Học đường: dùng Anh - Em hoặc Tớ - Cậu mềm mại, tự nhiên.',
    giaTriEn: 'Romance / School Life style: warm, natural conversational tone, keep honorifics consistent.',
  },
  {
    nhan: '⚔️ Hành động / Hunter (Tôi - Cậu / Ngài)',
    nhanEn: '⚔️ Action / Hunter (Captain / Sir / Skill names)',
    giaTri: 'Xưng hô phong cách Hành động / Hunter: dùng Tôi - Cậu, Đội trưởng, Ngài; giữ nguyên tên kỹ năng.',
    giaTriEn: 'Action / Hunter style: crisp tone, Captain/Sir, keep rank & skill names consistent.',
  },
]

const TEN_NGON_NGU = {
  ja: 'Tiếng Nhật',
  en: 'Tiếng Anh',
  zh: 'Tiếng Trung',
  ko: 'Tiếng Hàn',
}

const TEN_NGON_NGU_EN = {
  ja: 'Japanese',
  en: 'English',
  zh: 'Chinese',
  ko: 'Korean',
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

const TEN_BUOC_EN = {
  detect: 'Detect bubbles',
  ocr: 'Read source text',
  inpaint: 'Erase source text',
  translate: 'Translate',
  typeset: 'Typeset bubbles',
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
function tinhBuocCaMe(trang, laEn = false) {
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
    return { ma, nhan: laEn ? TEN_BUOC_EN[ma] : TEN_BUOC[ma], tt }
  })
}

const DUOI_GOI = /\.(zip|cbz|epub|pdf)$/i

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
function TienDoTrang({ tienDo, laEn = false }) {
  const ten = laEn
    ? (TEN_BUOC_EN[tienDo?.buoc] || 'Preparing')
    : (TEN_BUOC[tienDo?.buoc] || 'Đang chuẩn bị')
  if (!tienDo?.dang_chay && tienDo?.so_viec_cho_truoc > 0) {
    return (
      <span className="nhan-cho">
        <Icon ten="dong-ho" co={16} />{' '}
        {laEn
          ? `Queued — ${tienDo.so_viec_cho_truoc} job(s) ahead`
          : `Đang chờ — còn ${tienDo.so_viec_cho_truoc} việc trước`}
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
  const { lang, laEn } = useNgonNguUI()
  const heroText = HERO_I18N[lang] || HERO_I18N.en
  const [files, setFiles] = useState([])
  const [ngonNgu, setNgonNgu] = useState('ja')
  const [ngonNguDich, setNgonNguDich] = useState('vi')
  const [fontChu, setFontChu] = useState('bangers')
  const [tuDienRieng, setTuDienRieng] = useState('')
  const [moTuDien, setMoTuDien] = useState(false)

  useEffect(() => {
    if (['vi', 'en', 'es', 'pt', 'fr'].includes(lang)) {
      setNgonNguDich(lang)
    } else {
      setNgonNguDich(laEn ? 'en' : 'vi')
    }
  }, [lang, laEn])
  // E67 — mặc định MIỄN PHÍ. Chủ dự án chốt: người dùng tự chọn, không ai bị tính tiền ngoài ý
  // muốn. Đây là lựa chọn của TRANG CHỦ, gửi thẳng lên máy chủ — E58 đã chốt rằng lựa chọn này
  // phải được LƯU chứ không để `NULL` thừa hưởng mặc định hệ thống.
  const [cachDich, setCachDich] = useState('google_fast')
  const [byokCfg, setByokCfg] = useState(() => api.docCauHinhByok())
  const [moByok, setMoByok] = useState(false)
  const [dangThuByok, setDangThuByok] = useState(false)
  const [ketQuaByok, setKetQuaByok] = useState(null)
  const capDoByok = hanMuc?.la_quan_tri ? 5 : Number(hanMuc?.cap_do || 0)
  const choPhepByok = Boolean(hanMuc?.cho_phep_byok ?? (capDoByok >= 1))
  const dangBatByokHieuLuc = Boolean(choPhepByok && byokCfg.bat && byokCfg.key.length >= 12)
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
  const chuGiu = chuThoiGianGiu(giuPhut, laEn)
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
            💬 &ldquo;{heroText.bubbleLeft}&rdquo;
          </span>
          <span className="manga-bubble-tag tag-phai">⚡ &ldquo;Manga · Manhwa · Manhua · Comic!&rdquo;</span>
        </div>
        <div className="manga-genre-strip" aria-hidden="true">
          <span>⚔️ {laEn ? 'Action' : 'Hành động'}</span>
          <span>🌸 {laEn ? 'Romance' : 'Ngôn tình'}</span>
          <span>📜 {laEn ? 'Historical' : 'Cổ trang'}</span>
          <span>💬 {laEn ? 'Comics & Webtoon' : 'Truyện tranh'}</span>
          <span>🌍 {laEn ? '9 Global Languages' : 'Việt & Quốc tế'}</span>
        </div>
        <h1>{heroText.h1}</h1>
        <p className="dan">{heroText.subtitle}</p>
        <div className="manga-hero-actions">
          <a href="#tien-ich" className="nut-manga nut-manga-chinh">
            🧩 {laEn ? 'Install Chrome Extension & Windows App' : 'Cài Tiện Ích Chrome & App Windows'}
          </a>
          <a href="#ket-noi-api" className="nut-manga nut-manga-win">
            ⚡ {laEn ? 'Developer API Integration' : 'Kết Nối API Cho Tool / Web'}
          </a>
          <a href="#tien-ich" className="nut-manga nut-manga-video">
            🎬 {laEn ? 'Auto AI Video Review Studio' : 'Phần Mềm Dựng Video Review Truyện Tự Động'}
          </a>
        </div>

        {/* 3 hộp gợi ý tính năng ngắn gọn tạo ấn tượng ngay dưới 3 nút chính */}
        <div className="luoi-hero-3-cot" aria-label={laEn ? 'Featured Ecosystem Tools' : '3 Công cụ nổi bật'}>
          <div className="the-hero-goi-y">
            <div>
              <strong>🧩 {laEn ? 'Live Browser Extension & Auto Windows App' : 'Tiện Ích Dịch Trực Tiếp & App Windows Tự Động'}</strong>
              <span>
                {laEn
                  ? 'Translate live while reading on any comic site (Alt+Q), or paste 1 series link on Windows to auto-crawl & batch-translate chapters into clean folders.'
                  : 'Đọc tới đâu dịch tới đó ngay trên web đang coi (Alt+Q), hoặc dán 1 Link vào App Windows để tự động tải & dịch cả bộ truyện chia sẵn thư mục Chapter.'}
              </span>
            </div>
            <div className="day-link-nhanh">
              <a href={api.urlTaiTienIchChrome()} download="dich-truyen-chrome-extension-v0.3.2.zip">
                ⬇️ {laEn ? 'Extension (.ZIP)' : 'Tải Tiện Ích (.ZIP)'}
              </a>
              <span>·</span>
              <a href={api.urlTaiBoCaiWindowsExe()} download="Manga-Studio-Pro-Setup-v1.1.exe" style={{ color: '#059669' }}>
                🚀 {laEn ? 'Windows App (.EXE)' : 'Tải App Windows (.EXE)'}
              </a>
              <span>·</span>
              <a href="#tien-ich">{laEn ? 'Guide →' : 'Hướng dẫn →'}</a>
            </div>
          </div>

          <div className="the-hero-goi-y">
            <div>
              <strong>⚡ {laEn ? 'High-Speed Developer API (tr_live_...)' : 'Kết Nối API Cho Tool / Web Truyện (tr_live_...)'}</strong>
              <span>
                {laEn
                  ? 'Plug-and-play REST API for comic websites, apps & automation tools: smart background reconstruction, studio typesetting & context-aware translation in 9 languages.'
                  : 'Đấu nối REST API siêu tốc cho Web truyện, App đọc truyện & Tool tự động: tự động tái tạo nền sạch, dàn trang chuẩn thẩm mỹ & dịch bám sát ngữ cảnh ra 9 ngôn ngữ.'}
              </span>
            </div>
            <div className="day-link-nhanh">
              <a href="#ket-noi-api" style={{ color: '#0d9488' }}>
                🔑 {laEn ? 'Get API Key & Docs →' : 'Lấy Mã API Key & Xem Tài Liệu Đấu Nối →'}
              </a>
            </div>
          </div>

          <div className="the-hero-goi-y">
            <div>
              <strong>🎬 {laEn ? 'Auto AI Comic Video Review Studio' : 'Phần Mềm Dựng Video Review Truyện Tự Động'}</strong>
              <span>
                {laEn
                  ? 'Turn comic chapters into viral TikTok/Shorts/YouTube Recap videos: AI dramatic scriptwriter + 36 expressive studio voices + smooth cinematic camera motion!'
                  : 'Biến chapter truyện thành Video Review triệu view (TikTok / Shorts / YouTube): AI biên kịch bám sát cốt truyện + Giọng thuyết minh cảm xúc & chuyển động khung hình mượt mà!'}
              </span>
            </div>
            <div className="day-link-nhanh">
              <a href={api.urlTaiVideoReviewExe()} download="Manga-Video-Review-Studio-Setup-v1.0.exe" style={{ color: '#db2777' }}>
                🎬 {laEn ? 'Download Setup (.EXE)' : 'Tải Bộ Cài Video (.EXE)'}
              </a>
              <span>·</span>
              <a href={api.urlTaiVideoReviewZip()} download="Manga-Video-Review-Studio-v1.0.zip">
                📦 {laEn ? 'Portable (.ZIP)' : 'Bản .ZIP'}
              </a>
              <span>·</span>
              <a href="#tien-ich">{laEn ? 'Details →' : 'Chi tiết →'}</a>
            </div>
          </div>
        </div>
      </header>

      {loiChung && (
        <Alert
          sac="loi"
          tieuDe={
            loiChung.ma === 402
              ? `🔒 Cần nâng cấp gói ${loiChung.chiTiet?.ten_cap_yeu_cau || 'Pro'}`
              : loiChung.ma === 429
                ? 'Hết lượt'
                : 'Không chạy được'
          }
        >
          {String(loiChung.cauNguoiDoc || loiChung.message || loiChung).replace(/^\d+:\s*/, '')}
          {loiChung.ma === 402 && (
            <>
              {' '}
              <a
                href="#bang-gia"
                style={{ fontWeight: 700, textDecoration: 'underline', marginLeft: 6 }}
              >
                💎 Xem Bảng Giá & Nâng Cấp Ngay →
              </a>
            </>
          )}
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

        {/* Bảng điều khiển nhanh kiểu Dropdown gọn gàng (Đồng bộ Tiện Ích v0.3.1) */}
        <div className="bo-chon-manga">
          <div className="luoi-dropdown-manga">
            <div className="nhom-chon-manga">
              <label className="nhan-nhom-chon" htmlFor="select-nn-goc-nhanh">
                <span>{laEn ? 'Source Language on Page:' : 'Ngôn ngữ gốc trên trang:'}</span>
              </label>
              <select
                id="select-nn-goc-nhanh"
                className="o-select-manga"
                value={ngonNgu}
                disabled={dangChay}
                onChange={(e) => setNgonNgu(e.target.value)}
              >
                {PILL_NGON_NGU_GOC.map((item) => (
                  <option key={item.ma} value={item.ma}>
                    {item.co} {laEn ? item.nhanEn : item.nhan}
                  </option>
                ))}
              </select>
            </div>

            <div className="nhom-chon-manga">
              <label className="nhan-nhom-chon" htmlFor="select-nn-dich-nhanh">
                <span>{laEn ? 'Target Language (9 Global):' : 'Ngôn ngữ dịch ra (9 Ngôn ngữ):'}</span>
              </label>
              <select
                id="select-nn-dich-nhanh"
                className="o-select-manga"
                value={ngonNguDich}
                disabled={dangChay}
                onChange={(e) => setNgonNguDich(e.target.value)}
              >
                {PILL_NGON_NGU_DICH.map((item) => (
                  <option key={item.ma} value={item.ma}>
                    {item.co} {laEn ? item.nhanEn : item.nhan}
                  </option>
                ))}
              </select>
            </div>

            <div className="nhom-chon-manga">
              <label className="nhan-nhom-chon" htmlFor="select-engine-nhanh">
                <span>{laEn ? 'Translation Engine:' : 'Bộ máy dịch thuật:'}</span>
              </label>
              <select
                id="select-engine-nhanh"
                className="o-select-manga"
                value={cachDich}
                disabled={dangChay}
                onChange={(e) => setCachDich(e.target.value)}
              >
                <option value="llm_context">
                  {dangBatByokHieuLuc
                    ? (laEn
                        ? '✨ SoM Vision + LaMa · 1.5 credits/page (🔑 BYOK -50%)'
                        : '✨ SoM Vision + LaMa · 1,5 lượt/trang (🔑 BYOK -50%)')
                    : (laEn
                        ? '✨ SoM Vision + LaMa Pro · 3 credits/page (Context-Aware)'
                        : '✨ SoM Vision + LaMa Đám Mây · 3 lượt/trang (Đọc biểu cảm & tái tạo nét tranh)')}
                </option>
                <option value="google_fast">
                  {laEn ? '⚡ Fast Cloud · 1 credit/page (High Speed)' : '⚡ Dịch Nhanh Tốc Độ Cao · 1 lượt/trang'}
                </option>
              </select>
            </div>

            <div className="nhom-chon-manga">
              <label className="nhan-nhom-chon" htmlFor="select-font-nhanh">
                <span>{laEn ? 'Genre Font Style:' : 'Font chữ theo thể loại truyện:'}</span>
              </label>
              <select
                id="select-font-nhanh"
                className="o-select-manga"
                value={fontChu}
                disabled={dangChay}
                onChange={(e) => setFontChu(e.target.value)}
              >
                {PILL_FONT_THE_LOAI.map((item) => (
                  <option key={item.ma} value={item.ma}>
                    {item.bieuTuong} {laEn ? item.nhanEn : item.nhan}
                  </option>
                ))}
              </select>
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
                  {MAU_XUNG_HO.map((m) => {
                    const gt = laEn ? m.giaTriEn : m.giaTri
                    return (
                      <span
                        key={m.nhan}
                        role="button"
                        tabIndex={0}
                        className="chip-mau-xung-ho"
                        onClick={() => setTuDienRieng((cu) => (cu ? `${cu}\n${gt}` : gt))}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') setTuDienRieng((cu) => (cu ? `${cu}\n${gt}` : gt))
                        }}
                      >
                        {laEn ? m.nhanEn : m.nhan}
                      </span>
                    )
                  })}
                </div>
                <textarea
                  className="o o-tu-dien"
                  rows={3}
                  disabled={dangChay}
                  value={tuDienRieng}
                  onChange={(e) => setTuDienRieng(e.target.value)}
                  placeholder={
                    laEn
                      ? 'Example:\n- Sung Jin-Woo: main protagonist\n- Cha Hae-In: S-Rank Hunter\n- 影の君主 = Shadow Monarch'
                      : 'Ví dụ:\n- Sung Jin-Woo: xưng tôi, gọi cậu\n- Cha Hae-In: xưng em, gọi anh\n- Shadow Monarch = Quân Vương Bóng Tối'
                  }
                />
              </div>
            )}
          </div>

          <div className="nhom-chon-manga" style={{ marginTop: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
              <span className="nhan-nhom-chon">
                🔑 {laEn
                  ? 'Bring Your Own API Key (BYOK — 50% Credit Discount: Model 2 = 1, Model 3 = 1.5):'
                  : 'Cắm API Key cá nhân (BYOK — Giảm 50% lượt: Model 2 còn 1 lượt, Model 3 còn 1,5 lượt):'}
              </span>
              <span
                role="button"
                tabIndex={0}
                className="nut-chu"
                style={{ fontSize: 12.5, fontWeight: 700, cursor: 'pointer', color: dangBatByokHieuLuc ? '#059669' : undefined }}
                onClick={() => setMoByok(!moByok)}
                onKeyDown={(e) => { if (e.key === 'Enter') setMoByok(!moByok) }}
              >
                {dangBatByokHieuLuc
                  ? (laEn ? '✅ BYOK Active (-50% Credits)' : '✅ Đang bật BYOK (-50% lượt)')
                  : (moByok
                      ? (laEn ? '▲ Hide BYOK Panel' : '▲ Thu gọn khung BYOK')
                      : (choPhepByok
                          ? (laEn ? '🔑 Plug API Key (-50% Credits)' : '🔑 Mở cắm API Key riêng (-50% lượt)')
                          : (laEn ? '🔒 Unlocks from Starter Tier 1+' : '🔒 Mở khóa từ Gói 1 trở lên')))}
              </span>
            </div>
            {moByok && (
              <div className="khung-tu-dien-nhanh" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {!choPhepByok && (
                  <div style={{ fontSize: 12.5, color: '#b45309', background: '#fffbeb', border: '1px solid #fde68a', padding: '8px 10px', borderRadius: 8 }}>
                    🔒 {laEn
                      ? 'BYOK (50% credit discount: Model 2 drops to 1 credit/page, Model 3 SoM Vision + LaMa unlocks at 1.5 credits/page) is available for Starter Tier 1+ subscribers.'
                      : 'Quyền lợi cắm API Key cá nhân (giảm 50% lượt: Model 2 còn 1 lượt/trang, mở khóa luôn Model 3 SoM Vision + LaMa chỉ 1,5 lượt/trang) dành riêng cho tài khoản từ Gói 1 trở lên.'}
                  </div>
                )}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                  <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: 13, cursor: choPhepByok ? 'pointer' : 'not-allowed' }}>
                    <input
                      type="checkbox"
                      checked={Boolean(byokCfg.bat && choPhepByok)}
                      disabled={!choPhepByok || dangChay}
                      onChange={(e) => {
                        const moi = api.luuCauHinhByok({ bat: e.target.checked })
                        setByokCfg(moi)
                      }}
                    />
                    <span>{laEn ? 'Enable Personal API Key (-50% credits)' : 'Bật dùng API Key riêng (-50% số lượt trừ)'}</span>
                  </label>
                  <select
                    className="o-select-manga"
                    style={{ maxWidth: 260, padding: '6px 28px 6px 10px', fontSize: 12.5 }}
                    value={byokCfg.provider}
                    disabled={dangChay}
                    onChange={(e) => {
                      const moi = api.luuCauHinhByok({ provider: e.target.value })
                      setByokCfg(moi)
                    }}
                  >
                    <option value="gemini">✨ Google Gemini (2.5 Flash)</option>
                    <option value="deepseek">🧠 DeepSeek V3 (deepseek-chat)</option>
                    <option value="openai">🤖 OpenAI GPT-4o mini</option>
                    <option value="claude">🎭 Anthropic Claude Sonnet / Haiku</option>
                    <option value="openrouter">🌐 OpenRouter</option>
                    <option value="groq">⚡ Groq Cloud (Llama 3.3 70B)</option>
                  </select>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <input
                    type="password"
                    className="o"
                    style={{ flex: '1 1 240px', fontSize: 13 }}
                    disabled={dangChay}
                    value={byokCfg.key}
                    placeholder={laEn ? 'Paste AIza... / sk-... / sk-ant-... (stored in browser only)' : 'Dán AIza... / sk-... / sk-ant-... (chỉ lưu trên trình duyệt của bạn)'}
                    onChange={(e) => {
                      const moi = api.luuCauHinhByok({ key: e.target.value })
                      setByokCfg(moi)
                    }}
                  />
                  <button
                    type="button"
                    className="nut-phu"
                    style={{ whiteSpace: 'nowrap', padding: '6px 14px', fontSize: 12.5 }}
                    disabled={dangThuByok || byokCfg.key.length < 12}
                    onClick={async () => {
                      setDangThuByok(true)
                      setKetQuaByok(null)
                      try {
                        const kq = await api.kiemTraByok({
                          provider: byokCfg.provider,
                          apiKey: byokCfg.key,
                          model: byokCfg.model,
                        })
                        if (choPhepByok) {
                          const moi = api.luuCauHinhByok({ bat: true })
                          setByokCfg(moi)
                        }
                        setKetQuaByok({ ok: true, msg: kq.thong_diep || 'Kết nối API Key thành công!' })
                      } catch (err) {
                        setKetQuaByok({ ok: false, msg: err?.cauNguoiDoc || err?.message || String(err) })
                      } finally {
                        setDangThuByok(false)
                      }
                    }}
                  >
                    {dangThuByok ? (laEn ? '⏳ Testing...' : '⏳ Đang thử...') : (laEn ? '🔌 Test Key' : '🔌 Kiểm tra Key')}
                  </button>
                </div>
                {ketQuaByok && (
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: ketQuaByok.ok ? '#059669' : '#dc2626' }}>
                    {ketQuaByok.ok ? '✅ ' : '❌ '}{ketQuaByok.msg}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="huy-hieu-gpu-khach">
            {laEn
              ? '🚀 Ultra-Fast Auto Translation ~3s · Double-Click to Edit'
              : '🚀 Dịch tự động siêu tốc ~3s · Nhấp đúp sửa câu trực tiếp'}
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
                lyDoKhoa={!files.length ? (laEn ? 'Select at least one page first' : 'Chọn ít nhất một trang trước') : undefined}
              >
                {dangNhanDang
                  ? (laEn ? 'Reading sample…' : 'Đang đọc thử…')
                  : (laEn ? 'Detect language from 1st page' : 'Đọc thử trang đầu')}
              </Button>
              <p className="ghi-chu">
                {laEn
                  ? 'Reads text on the first page to detect the language. Does not consume your translation quota.'
                  : 'Máy đọc chữ trên trang đầu rồi đoán. Không tính vào lượt dịch của bạn.'}
              </p>
            </div>
          )}

          {loiNhanDang && (
            <Alert sac="canh" tieuDe={laEn ? 'Could not auto-detect' : 'Chưa đọc thử được'}>
              {String(loiNhanDang.cauNguoiDoc || loiNhanDang.message || loiNhanDang)
                .replace(/^\d+:\s*/, '')}
              {' '}{laEn ? 'Please select the source language manually above.' : 'Bạn chọn tay ở ô trên giúp nhé.'}
            </Alert>
          )}

          {ketQuaNhanDang && (
            ketQuaNhanDang.ngon_ngu
              ? (
                <Alert
                  sac="ok"
                  tieuDe={
                    laEn
                      ? `Detected: ${TEN_NGON_NGU_EN[ketQuaNhanDang.ngon_ngu] || ketQuaNhanDang.ngon_ngu}`
                      : `Máy đoán: ${TEN_NGON_NGU[ketQuaNhanDang.ngon_ngu]}`
                  }
                >
                  {/* HIỆN SỐ ĐO, không chỉ nói "đã nhận dạng": một kết luận không kèm bằng chứng
                      thì người dùng không có cách nào biết nên tin bao nhiêu. */}
                  {ketQuaNhanDang.bang_chung && (
                    laEn ? (
                      <>
                        Read <strong>{ketQuaNhanDang.bang_chung.tong_co_nghia}</strong> characters
                        {ketQuaNhanDang.bang_chung.kana > 0 && <> (<strong>{ketQuaNhanDang.bang_chung.kana}</strong> Japanese kana)</>}
                        {ketQuaNhanDang.bang_chung.kana === 0 && ketQuaNhanDang.bang_chung.han > 0 && <> (<strong>{ketQuaNhanDang.bang_chung.han}</strong> Han characters, no kana)</>}
                        .{' '}
                      </>
                    ) : (
                      <>
                        Đọc được <strong>{ketQuaNhanDang.bang_chung.tong_co_nghia}</strong> ký tự
                        {ketQuaNhanDang.bang_chung.kana > 0 && <> (<strong>{ketQuaNhanDang.bang_chung.kana}</strong> chữ kana của tiếng Nhật)</>}
                        {ketQuaNhanDang.bang_chung.kana === 0 && ketQuaNhanDang.bang_chung.han > 0 && <> (<strong>{ketQuaNhanDang.bang_chung.han}</strong> chữ Hán, không có kana)</>}
                        .{' '}
                      </>
                    )
                  )}
                  {laEn ? (
                    <>The language selector above has been updated. <strong>Change it if needed</strong>.</>
                  ) : (
                    <>
                      Ô chọn ở trên đã đổi theo. <strong>Sai thì bạn sửa lại</strong> — máy đoán từ chữ
                      đọc được, không phải luôn đúng.
                    </>
                  )}
                </Alert>
              )
              : (
                <Alert sac="canh" tieuDe={laEn ? 'Could not determine language' : 'Máy không đoán được'}>
                  {ketQuaNhanDang.ly_do?.startsWith('khong_doc_duoc_chu_nao')
                    ? (laEn
                        ? 'No readable text found on this page (it might be a cover image or low-contrast art).'
                        : 'Trang này máy không đọc ra chữ nào (có thể là trang bìa, hoặc chữ quá mờ).')
                    : (laEn
                        ? 'Found text, but not enough to be certain.'
                        : 'Máy đọc được chữ nhưng không đủ để chắc chắn.')}
                  {' '}
                  {laEn
                    ? 'Please choose the source language manually above.'
                    : 'Bạn chọn tay ở ô trên giúp nhé (nếu là truyện Hàn Quốc thì chọn "Tiếng Hàn (Manhwa)") — chọn sai thì chữ dịch ra vô nghĩa.'}
                </Alert>
              )
          )}
        </div>

        {thieuLuot && (
          <Alert sac="canh" tieuDe={laEn ? 'Not enough remaining quota' : 'Nhiều hơn số lượt còn lại'}>
            {laEn
              ? `You selected ${files.length} page(s), but only ${conLai} page(s) remain today. Remove some pages or wait until 00:00 GMT+7.`
              : `Bạn chọn ${files.length} trang nhưng chỉ còn ${conLai} lượt. Bỏ bớt trang, hoặc đợi tới 0h00 giờ Việt Nam.`}
          </Alert>
        )}

        <Button
          kieu="chinh" onClick={batDau} dangChay={dangChay}
          lyDoKhoa={
            !files.length ? (laEn ? 'Select at least one page' : 'Chọn ít nhất một trang')
              // Gửi `tu-nhan` lên đường dịch là nhận 422 — người dùng sẽ đọc một lỗi kỹ thuật cho
              // một lựa chọn mà chính giao diện mời họ chọn.
              : ngonNgu === TU_NHAN ? (laEn ? 'Click "Detect language from 1st page" or pick a language manually' : 'Bấm "Đọc thử trang đầu", hoặc chọn tay một ngôn ngữ')
                : thieuLuot ? (laEn ? 'Exceeds remaining quota' : 'Nhiều hơn số lượt còn lại')
                  : conLai === 0 ? (laEn ? 'Out of quota for today' : 'Hết lượt hôm nay')
                    : undefined
          }
        >
          {dangChay
            ? (laEn ? 'Translating…' : 'Đang dịch…')
            : (laEn
                ? (files.length ? `Translate ${files.length} page(s)` : 'Translate pages')
                : `Dịch ${files.length || ''} trang`.trim())}
        </Button>
      </section>


      {trang.length > 0 && (
        <section className="the-man tien-do-trang" aria-labelledby="tieu-de-tien-do" aria-live="polite">
          <h2 id="tieu-de-tien-do" className="nho">
            {laEn
              ? `Progress — ${trangXong.length}/${trang.length} page(s) completed`
              : `Tiến độ — xong ${trangXong.length}/${trang.length} trang`}
          </h2>
          <ol className="cac-buoc" aria-label={laEn ? 'Processing steps' : 'Các bước xử lý'}>
            {tinhBuocCaMe(trang, laEn).map((b) => (
              <li key={b.ma} className={`buoc-the buoc-the-${b.tt}`}>
                <span className="buoc-the-tren">
                  <Icon ten={b.tt === 'xong' ? 'circle-check' : b.tt === 'chay' ? 'loader' : ICON_BUOC[b.ma]} />
                  {b.nhan}
                </span>
                <span className="buoc-the-tt">
                  {b.tt === 'xong'
                    ? (laEn ? 'Done' : NHAN_BUOC_XONG)
                    : b.tt === 'chay'
                      ? (laEn ? 'Running' : NHAN_BUOC_CHAY)
                      : (laEn ? 'Waiting' : NHAN_BUOC_CHO)}
                </span>
              </li>
            ))}
          </ol>
          <div
            className="thanh-tien" role="progressbar" aria-label={laEn ? 'Translation progress' : 'Tiến độ dịch'}
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
                    ? <span className="nhan-xong"><Icon ten="tich" co={16} /> {laEn ? 'Done' : 'Xong'}</span>
                    : <TienDoTrang tienDo={t.tienDo} laEn={laEn} />}
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
        <summary>{laEn ? 'Good to know before starting' : 'Cần biết trước khi bắt đầu'}</summary>
        <ul>
          <li>
            <Icon ten="dong-ho" co={16} />{' '}
            {laEn ? (
              <>Each page takes <strong>about 30 seconds</strong>. Keep this tab open while it runs.</>
            ) : (
              <>Mỗi trang mất <strong>khoảng 30 giây</strong>. Máy không treo — cứ để tab mở.</>
            )}
          </li>
          {/* Câu này phải khớp CẤU HÌNH THẬT của máy chủ. Hứa xoá trong khi không xoá, hay hứa
              giữ trong khi sẽ xoá — cả hai đều là nói sai với người dùng về dữ liệu của họ. */}
          {coTuXoa ? (
            <li>
              {laEn ? (
                <>
                  <strong>Results are kept for {chuGiu}</strong> after completion. After that,{' '}
                  <strong>original images, translations, and archives are permanently deleted</strong>.
                </>
              ) : (
                <>
                  <strong>Kết quả chỉ giữ {chuGiu}</strong> kể từ lúc dịch xong. Sau đó{' '}
                  <strong>ảnh gốc, bản dịch và tệp đã gói đều bị xoá</strong>: không chạy lại được,
                  không sửa lại được. Muốn làm lại phải tải lên từ đầu và tốn thêm lượt.
                </>
              )}
            </li>
          ) : (
            <li>
              {laEn ? (
                <>Results are <strong>not auto-deleted</strong> on a timer, but please download them right away.</>
              ) : (
                <>
                  Kết quả <strong>không tự xoá</strong> theo giờ. Nhưng vẫn nên tải về ngay — đây
                  không phải chỗ lưu trữ lâu dài, và chính sách có thể đổi.
                </>
              )}
            </li>
          )}
          <li>
            {laEn ? (
              <>Supports <strong>PNG, JPG, WebP</strong> images (up to 25 MB/image) and <strong>ZIP, CBZ, PDF</strong> chapter archives.</>
            ) : (
              <>Nhận ảnh <strong>PNG, JPG, WebP</strong> (tối đa 25 MB/ảnh) và gói truyện <strong>ZIP, CBZ, PDF</strong>.</>
            )}
          </li>
          <li>
            {laEn ? (
              <>Translates <strong>Japanese, Korean, English, Chinese</strong> → Vietnamese &amp; Global English.</>
            ) : (
              <>Dịch được chữ <strong>Nhật, Hàn, Anh, Trung</strong> → tiếng Việt.</>
            )}
          </li>
        </ul>
      </details>
      </div>

      <aside className="cot-phai-khach" aria-label={laEn ? 'Quota' : 'Hạn mức'}>
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
            <Icon ten="dong-ho" co={16} />{' '}
            {laEn ? (
              <>Remember to download right away: files are <strong>auto-deleted after {chuGiu}</strong> once completed.</>
            ) : (
              <>Nhớ tải về ngay: tệp <strong>tự xoá sau {chuGiu}</strong> kể từ lúc dịch xong.</>
            )}
          </p>
        )}
      </aside>
      </div>

      {xongLuc && trangXong.length > 0 && (
        <section className="ket-qua" aria-labelledby="tieu-de-ket-qua">
          <h2 id="tieu-de-ket-qua" className="nho">{laEn ? 'Results' : 'Kết quả'}</h2>

          {!coTuXoa ? (
            <Alert sac="tin" tieuDe={laEn ? 'Remember to download' : 'Nhớ tải về'}>
              {laEn ? (
                <>Results are <strong>not auto-deleted</strong> on a timer, but please download your files before closing this tab.</>
              ) : (
                <>
                  Kết quả <strong>không tự xoá</strong> theo giờ, nhưng đây không phải chỗ lưu trữ lâu
                  dài — tải về rồi hãy đóng tab.
                </>
              )}
            </Alert>
          ) : daHetHan ? (
            <Alert sac="loi" tieuDe={laEn ? `Expired after ${chuGiu} — files removed` : `Đã quá ${chuGiu} — tệp không còn nữa`}>
              {laEn
                ? 'Original images, translations, and archives have been deleted. Please upload again if needed.'
                : 'Ảnh gốc, bản dịch và tệp đã gói đều đã bị xoá. Muốn có lại thì phải tải lên từ đầu và tốn thêm lượt.'}
            </Alert>
          ) : (
            <Alert sac="canh" tieuDe={laEn ? 'Download before expiration' : 'Tải về trước khi hết giờ'}>
              {laEn ? (
                <>
                  <strong>{chuDemNguoc(mocHetHan, Date.now(), true)}</strong> remaining before all results
                  (original images, translations, and packages) are automatically deleted.
                </>
              ) : (
                <>
                  Còn <strong>{chuDemNguoc(mocHetHan)}</strong> trước khi toàn bộ kết quả bị xoá —
                  ảnh gốc, bản dịch, tệp đã gói. Xoá rồi thì không chạy lại và không sửa lại được.
                </>
              )}
            </Alert>
          )}

          {/* Nút thủ công LUÔN hiện, kèm câu nói rõ. Trình duyệt thường chặn lượt tải không do
              người bấm, và JavaScript không có cách nào biết nó đã bị chặn — nên không giả vờ dò
              được, chỉ nói thật. */}
          <div className="hang-tai-ve">
            <Button kieu="chinh" onClick={() => taiKetQua(false)} dangChay={dangTai} icon="download">
              {trangXong.length > 1
                ? (laEn ? `Download full package (${dinhDangXuat.toUpperCase()})` : `Tải cả gói (${dinhDangXuat.toUpperCase()}) về`)
                : (laEn ? 'Download translated image' : 'Tải ảnh đã dịch về')}
            </Button>
            {trangXong.length > 1 && (
              <label className="chon-dinh-dang-xuat" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                <span>{laEn ? 'Package format:' : 'Định dạng gói:'}</span>
                <select
                  aria-label={laEn ? 'Download package format' : 'Định dạng gói tải về'}
                  className="o"
                  style={{ width: 'auto', padding: '4px 10px' }}
                  value={dinhDangXuat}
                  onChange={(e) => setDinhDangXuat(e.target.value)}
                  disabled={dangTai}
                >
                  <option value="cbz">{laEn ? '.CBZ (Comic Reader)' : '.CBZ (Trình đọc truyện)'}</option>
                  <option value="zip">{laEn ? '.ZIP (PNG Images)' : '.ZIP (Giải nén ảnh PNG)'}</option>
                </select>
              </label>
            )}
            <div className="bo-chuyen-che-do-xem" role="group" aria-label={laEn ? 'Result view mode' : 'Chế độ xem kết quả'} style={{ display: 'inline-flex', gap: 6, marginLeft: 'auto' }}>
              <Button
                kieu={cheDoXem === 'so_sanh' ? 'phu' : 'ghost'}
                co="nho"
                onClick={() => setCheDoXem('so_sanh')}
              >
                {laEn ? 'Compare Before – After' : 'So sánh Trước – Sau'}
              </Button>
              <Button
                kieu={cheDoXem === 'doc_doc' ? 'phu' : 'ghost'}
                co="nho"
                onClick={() => setCheDoXem('doc_doc')}
              >
                {laEn ? 'Vertical Webtoon Reader' : 'Đọc dọc liền mạch'}
              </Button>
            </div>
            {daThuTuTai && !tenTepDaTai && (
              <p className="ghi-chu" style={{ width: '100%' }}>
                {laEn ? (
                  <>Auto-download attempted. <strong>If you don’t see the file</strong>, your browser blocked automatic downloads — click the button above.</>
                ) : (
                  <>
                    Đã thử tải tự động. <strong>Nếu không thấy tệp nào</strong>, trình duyệt đã chặn
                    lượt tải không do bạn bấm — bấm nút trên là được.
                  </>
                )}
              </p>
            )}
            {tenTepDaTai && (
              <p className="ghi-chu" style={{ width: '100%' }}>
                <Icon ten="tich" co={16} />{' '}
                {laEn ? (
                  <>Saved <strong>{tenTepDaTai}</strong>. Check your browser’s Downloads folder.</>
                ) : (
                  <>
                    Đã lưu <strong>{tenTepDaTai}</strong>. Không thấy thì
                    xem lại thư mục Tải về của trình duyệt.
                  </>
                )}
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
                        <span>{laEn ? `Page ${idx + 1}/${trangXong.length}` : `Trang ${idx + 1}/${trangXong.length}`} · {t.ten}</span>
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
                          {dangGiu
                            ? (laEn ? 'Showing original' : 'Đang hiện bản gốc')
                            : (laEn ? 'Hold / Click for original' : 'Giữ / Bấm xem bản gốc')}
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
                          <figcaption>{laEn ? 'Before' : NHAN_TRUOC}</figcaption>
                        </figure>
                        <figure>
                          <img src={api.urlAnhDaDich(t.page_id)} alt={`Trang đã dịch: ${t.ten}`} loading="lazy" />
                          <figcaption>{laEn ? 'After' : NHAN_SAU}</figcaption>
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

      <ChanTrangManga />
    </main>
  )
}
