import { useEffect, useRef, useState } from 'react'
import * as api from '../../api.js'
import { chayTuTaiVe } from '../../lib/tu-tai-ve.js'
import { CACH_DICH, MUC_DICH, NGON_NGU } from '../../lib/status-presentation.js'
import { useCodex } from '../../lib/dung-codex.js'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import Dropzone from '../ui/Dropzone.jsx'
import { Input, Select } from '../ui/Field.jsx'

// wording: BA review — nhãn nút duy nhất của form gộp (thay "Dịch ngay" và "Tạo chapter & bắt đầu dịch")
const NHAN_NUT_CHINH = 'Tạo chapter & dịch'
// wording: BA review — nhãn + chú thích của ô tên (tuỳ chọn)
const NHAN_TEN = 'Tên chapter (không bắt buộc)'
const GOI_Y_TEN = 'Để trống thì hệ thống tự đặt theo tên tệp đầu tiên và ngày hôm nay.'
const MAU_TEN = 'ví dụ: One Piece — chương 1'
// wording: BA review — ghi chú dưới nút
const GHI_CHU_CHAY_NEN = 'Xử lý chạy nền. Dịch xong, bạn sẽ được đưa tới chapter để theo dõi và sửa tay.'
// wording: BA review — chú thích dưới ô "Tự tải về khi xong"
const GHI_CHU_TU_TAI_VE = 'Giữ tab này mở: tệp ZIP sẽ tự tải về khi cả chapter dịch xong.'

const MO_TA_MUC_DICH = {
  personal: 'Tự dịch để mình đọc, không đưa cho ai khác.',
  study: 'Học ngôn ngữ, làm bài tập, nghiên cứu dịch thuật.',
  other: 'Mục đích khác — bạn tự chịu trách nhiệm về bản quyền nội dung gốc.',
}

const MO_TA_ENGINE = {
  google_fast: 'Miễn phí. Dịch từng dòng, không nhìn câu trước sau.',
  llm_context: 'Giữ mạch văn cả trang và tự sửa lỗi đọc chữ — TỐN token AI.',
  chatgpt_codex: 'Dịch bằng tài khoản ChatGPT của chính bạn (thử nghiệm) — có thể bị giới hạn lượt dùng.',
}

const PILL_NGON_NGU_GOC = [
  { ma: 'ja', co: '🇯🇵', nhan: 'Tiếng Nhật (Manga)', nhanEn: 'Japanese (Manga)' },
  { ma: 'ko', co: '🇰🇷', nhan: 'Tiếng Hàn (Manhwa / Webtoon)', nhanEn: 'Korean (Manhwa / Webtoon)' },
  { ma: 'zh', co: '🇨🇳', nhan: 'Tiếng Trung (Manhua)', nhanEn: 'Chinese (Manhua)' },
  { ma: 'en', co: '🇬🇧', nhan: 'Tiếng Anh (Comic)', nhanEn: 'English (Comic)' },
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

/** Vì sao chưa chạy được — `null` nghĩa là chạy được. Tách riêng để test không cần dựng DOM. */
export function lyDoChuaChayDuoc({ mucDich, files }) {
  // M10 giữ nguyên ở đây: người dùng tự khai mục đích, hệ thống KHÔNG chọn hộ. Tên chapter
  // không còn bắt buộc, nhưng phần khai báo trách nhiệm bản quyền thì không rút gọn.
  if (!mucDich) return 'Cần chọn mục đích sử dụng — hệ thống không chọn hộ.'
  if (!files.length) return 'Cần chọn ít nhất một ảnh, hoặc một gói ZIP/CBZ.'
  return null
}

/** Tên chapter tự đặt khi người dùng để trống.
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
 * MỘT luồng duy nhất cho người đã đăng nhập: thả file → khai báo → tạo chapter + dịch.
 *
 * Gộp từ hai form cũ ("Dịch nhanh" và "Tạo chapter mới") vì bắt người dùng chọn giữa hai tab
 * là một quyết định không cần có. Luồng này làm cả hai việc: tạo chapter, tải trang, chạy
 * pipeline, rồi MỞ màn chapter để theo dõi; nếu bật "Tự tải về" thì việc chờ + xuất + tải về
 * chạy tiếp ở `lib/tu-tai-ve.js` (không bị tháo theo form).
 *
 * Giữ nguyên có chủ đích: khai báo mục đích sử dụng (M10) và mọi kiểm tra của máy chủ.
 */
export default function DichChapter({ onMoChapter }) {
  const { laEn } = useNgonNguUI()
  const [ten, setTen] = useState('')
  const [nguon, setNguon] = useState('ja')
  const [dich, setDich] = useState('vi')
  const [fontChu, setFontChu] = useState('bangers')
  const [tuDienRieng, setTuDienRieng] = useState('')
  const [moTuDien, setMoTuDien] = useState(false)
  const [engine, setEngine] = useState('google_fast')
  const codex = useCodex()
  const [mucDich, setMucDich] = useState('')
  const [files, setFiles] = useState([])
  const [tuTaiVe, setTuTaiVe] = useState(true)
  const [dangChay, setDangChay] = useState(false)
  const [daXong, setDaXong] = useState(0)
  const [loi, setLoi] = useState(null)

  // Đã cấu hình AI (`llm_configured`, cùng nguồn `/batch-config` mà BatchPanel dùng) thì mặc
  // định "Dịch theo ngữ cảnh". Chỉ đặt MỘT lần và chỉ khi người dùng chưa tự chọn — kết quả về
  // muộn không được đè lựa chọn của họ. Lỗi mạng ⇒ giữ mặc định miễn phí.
  const daChonEngine = useRef(false)
  useEffect(() => {
    let huy = false
    Promise.resolve()
      .then(() => api.layCauHinhMe())
      .then((c) => {
        if (!huy && !daChonEngine.current && c?.llm_configured === true) setEngine('llm_context')
      })
      .catch(() => {})
    return () => { huy = true }
  }, [])
  const doiEngine = (v) => { daChonEngine.current = true; setEngine(v) }

  const lyDo = lyDoChuaChayDuoc({ mucDich, files })

  const batDau = async () => {
    if (lyDo || dangChay) return   // chặn cả double-click, không chỉ dựa vào nút mờ
    setDangChay(true); setLoi(null); setDaXong(0)
    let projectId = null
    try {
      const payload = {
        name: ten.trim() || datTenTuDong(files), source_lang: nguon, intended_use: mucDich,
      }
      if (dich !== 'vi') payload.target_lang = dich
      if (fontChu !== 'bangers') payload.font_style = fontChu
      if (tuDienRieng.trim()) payload.tu_dien_rieng = tuDienRieng.trim()
      const project = await api.taoProject(payload)
      projectId = project.id

      // Tải tuần tự: gói đi đường gói, ảnh lẻ đi đường ảnh; dồn một lúc chỉ làm máy chủ nghẹn.
      let boQua = 0
      for (let i = 0; i < files.length; i++) {
        const f = files[i]
        if (api.laGoiNen(f)) {
          const g = await api.taiGoiLen(projectId, f, engine)
          boQua += g.bo_qua ?? 0
        } else {
          await api.taiTrangLen(projectId, f, engine)
        }
        setDaXong(i + 1)
      }

      // Chạy nền, KHÔNG await: form sắp bị tháo khi chuyển sang màn chapter.
      if (tuTaiVe) chayTuTaiVe(projectId, { boQua })
      onMoChapter?.(projectId)
    } catch (e) {
      // Giữ nguyên mọi ô đã nhập và danh sách file; nếu chapter đã tạo thì chỉ đường vào xem.
      setLoi({ thongDiep: e.message, projectId })
    } finally {
      setDangChay(false)
    }
  }

  return (
    <section className="the-lon" aria-labelledby="tieu-de-dich">
      <header className="the-dau">
        <h2 id="tieu-de-dich">{laEn ? 'Translate Comic Chapter' : 'Dịch truyện tranh'}</h2>
        <p>
          {laEn ? (
            <>Drop images or a full <code>.zip</code>/<code>.cbz</code>/<code>.pdf</code> chapter archive here.</>
          ) : (
            <>Thả ảnh hoặc cả gói <code>.zip</code>/<code>.cbz</code>/<code>.pdf</code> vào đây.</>
          )}
        </p>
      </header>

      <div className="luoi-dich-chapter-ngang">
        <fieldset className="khoi cot-trai-dich-chapter" disabled={dangChay}>
          <Dropzone files={files} onDoi={setFiles} tatCa={dangChay} chapNhanGoi id="vung-tha-nhanh" />
        </fieldset>

        <div className="cot-phai-dich-chapter">
          <fieldset className="khoi" disabled={dangChay}>
            <div className="bo-chon-manga">
              <div className="luoi-dropdown-manga">
                <div className="nhom-chon-manga">
                  <label className="nhan-nhom-chon" htmlFor="select-chapter-nn-goc">
                    <span>{laEn ? 'Source Language on Page:' : 'Ngôn ngữ gốc trên trang:'}</span>
                  </label>
                  <select
                    id="select-chapter-nn-goc"
                    className="o-select-manga"
                    value={nguon}
                    disabled={dangChay}
                    onChange={(e) => setNguon(e.target.value)}
                  >
                    {PILL_NGON_NGU_GOC.map((item) => (
                      <option key={item.ma} value={item.ma}>
                        {item.co} {laEn ? item.nhanEn : item.nhan}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="nhom-chon-manga">
                  <label className="nhan-nhom-chon" htmlFor="select-chapter-nn-dich">
                    <span>{laEn ? 'Target Language (9 Global):' : 'Ngôn ngữ dịch ra (9 Ngôn ngữ):'}</span>
                  </label>
                  <select
                    id="select-chapter-nn-dich"
                    className="o-select-manga"
                    value={dich}
                    disabled={dangChay}
                    onChange={(e) => setDich(e.target.value)}
                  >
                    {PILL_NGON_NGU_DICH.map((item) => (
                      <option key={item.ma} value={item.ma}>
                        {item.co} {laEn ? item.nhanEn : item.nhan}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="nhom-chon-manga">
                  <label className="nhan-nhom-chon" htmlFor="select-chapter-engine">
                    <span>{laEn ? 'Translation Engine:' : 'Bộ máy dịch thuật:'}</span>
                  </label>
                  <select
                    id="select-chapter-engine"
                    className="o-select-manga"
                    value={engine}
                    disabled={dangChay}
                    onChange={(e) => doiEngine(e.target.value)}
                  >
                    <option value="llm_context">
                      {laEn ? '✨ Context AI Pro (Context-Aware)' : '✨ AI Chuẩn Ngữ Cảnh (Đọc mạch văn cả trang)'}
                    </option>
                    <option value="google_fast">
                      {laEn ? '⚡ Fast Cloud (High Speed)' : '⚡ Dịch Nhanh Tốc Độ Cao (Miễn phí token)'}
                    </option>
                  </select>
                </div>

                <div className="nhom-chon-manga">
                  <label className="nhan-nhom-chon" htmlFor="select-chapter-font">
                    <span>{laEn ? 'Genre Font Style:' : 'Font chữ theo thể loại truyện:'}</span>
                  </label>
                  <select
                    id="select-chapter-font"
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
                    📖 {laEn ? 'Character & Pronoun Glossary:' : 'Sổ tay Nhân vật & Xưng hô cố định:'}
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

              <div className="huy-hieu-gpu-khach">
                {laEn
                  ? '🚀 Ultra-Fast Auto Translation ~3s · Double-Click to Edit'
                  : '🚀 Dịch tự động siêu tốc ~3s · Nhấp đúp sửa câu trực tiếp'}
              </div>
            </div>
          </fieldset>

          <fieldset className="khoi" disabled={dangChay}>
            <div className="an-di">
              <Select nhan="Ngôn ngữ gốc" batBuoc value={nguon}
                      onChange={(e) => setNguon(e.target.value)}>
                {Object.entries(NGON_NGU).map(([ma, tenNn]) => (
                  <option key={ma} value={ma}>{tenNn}</option>
                ))}
              </Select>
              <Select
                nhan="Cách dịch" batBuoc value={engine} moTa={MO_TA_ENGINE[engine]}
                onChange={(e) => doiEngine(e.target.value)}
              >
                {Object.entries(CACH_DICH).map(([ma, tenCd]) => (
                  <option key={ma} value={ma}>{tenCd}</option>
                ))}
                {codex.bat && (
                  <option value="chatgpt_codex" disabled={!codex.da_dang_nhap}>
                    ChatGPT (tài khoản của bạn){codex.da_dang_nhap ? '' : ' — quản trị cần đăng nhập ChatGPT trước'}
                  </option>
                )}
              </Select>
            </div>

            <div className="hang-muc-dich-ten">
              <Select
                nhan="Mục đích sử dụng" batBuoc value={mucDich}
                moTa={mucDich
                  ? MO_TA_MUC_DICH[mucDich]
                  : 'Bạn tự khai — hệ thống không chọn hộ. Khai báo gắn với chapter và không sửa được.'}
                onChange={(e) => setMucDich(e.target.value)}
              >
                <option value="" disabled>— hãy chọn —</option>
                {Object.entries(MUC_DICH).map(([ma, tenMd]) => (
                  <option key={ma} value={ma}>{tenMd}</option>
                ))}
              </Select>

              <Input
                nhan={NHAN_TEN} moTa={GOI_Y_TEN}
                value={ten} onChange={(e) => setTen(e.target.value)} placeholder={MAU_TEN}
              />
            </div>

            <div className="hang-chan-nut-chapter">
              <div className="khoi-tu-tai-ve">
                <label className="o-tick">
                  <input
                    type="checkbox" checked={tuTaiVe}
                    onChange={(e) => setTuTaiVe(e.target.checked)}
                  />
                  <span>Tự tải về khi xong</span>
                </label>
                {tuTaiVe && <p className="ghi-chu">{GHI_CHU_TU_TAI_VE}</p>}
              </div>

              <div className="khoi-nut-tao-chapter">
                <Button kieu="chinh" id="nut-tao" onClick={batDau}
                        dangChay={dangChay} lyDoKhoa={lyDo}>
                  {dangChay ? `Đang tải lên ${daXong}/${files.length}…` : NHAN_NUT_CHINH}
                </Button>
                <p className="ghi-chu">{GHI_CHU_CHAY_NEN}</p>
              </div>
            </div>

            {dangChay && (
              <div className="thanh-tien" aria-hidden="true">
                <div className="thanh-tien-trong"
                     style={{ width: `${Math.round((daXong / Math.max(files.length, 1)) * 100)}%` }} />
              </div>
            )}

            {loi && (
              <Alert sac="loi" tieuDe="Không tạo được chapter">
                <p>{loi.thongDiep}</p>
                {loi.projectId && (
                  <Button kieu="ghost" onClick={() => onMoChapter?.(loi.projectId)}>
                    Mở chapter đã tạo để xem đã chạy tới đâu
                  </Button>
                )}
              </Alert>
            )}
          </fieldset>
        </div>
      </div>
    </section>
  )
}
