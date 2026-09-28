import { useCallback, useEffect, useRef, useState } from 'react'

import * as api from '../../api'
import { chuDemNguoc, conLaiMs, mocHetHanGiuTep } from '../../lib/dem-nguoc'
import Alert from '../ui/Alert'
import Button from '../ui/Button'
import Dropzone from '../ui/Dropzone'
import Icon from '../ui/Icon'
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
]

const TEN_NGON_NGU = { ja: 'Tiếng Nhật', en: 'Tiếng Anh', zh: 'Tiếng Trung' }

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
        <Icon ten="dong-ho" co={14} /> Đang chờ — còn {tienDo.so_viec_cho_truoc} việc trước
      </span>
    )
  }
  return (
    <span className="nhan-chay">
      <Icon ten="quay" co={14} /> {ten}…
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
export default function TrangChu({ onMoDangNhap }) {
  const [files, setFiles] = useState([])
  const [ngonNgu, setNgonNgu] = useState('ja')
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

  const [hanMuc, setHanMuc] = useState(null)
  const [dangTaiHanMuc, setDangTaiHanMuc] = useState(true)
  const [loiHanMuc, setLoiHanMuc] = useState(null)

  const huy = useRef(false)
  useEffect(() => () => { huy.current = true }, [])

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

    const dsTrang = files.map((f) => ({ ten: f.name, page_id: null, xong: false, tienDo: null, loi: null }))
    setTrang(dsTrang)

    let pid = null
    const idTrang = []
    for (let i = 0; i < files.length; i++) {
      try {
        const ra = await api.guiTrangDichNhanh(files[i], { sourceLang: ngonNgu, cheDo: 'day_du' })
        idTrang.push(ra.page_id)
        if (!huy.current) {
          setTrang((cu) => cu.map((t, j) => (j === i ? { ...t, page_id: ra.page_id } : t)))
        }
      } catch (e) {
        // 429 = hết hạn mức. Máy chủ đã gửi đủ thông tin để nói câu tử tế; `doc()` đính nó vào
        // `e.chiTiet`. Dừng NGUYÊN mẻ chứ không gửi tiếp: gửi tiếp chỉ nhận thêm 429.
        if (!huy.current) {
          setLoiChung(e)
          setTrang((cu) => cu.map((t, j) => (j >= i ? { ...t, loi: 'chưa gửi được' } : t)))
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
        const job = await api.xuatChapterDichNhanh(projectId, 'cbz')
        await api.choXuatXong(job.job_id)
        const ten = await api.taiFileXuatVe(job.job_id)
        setTenTepDaTai(ten)
      }
    } catch (e) {
      if (!huy.current) setLoiChung(e)
    } finally {
      if (!huy.current) { setDangTai(false); if (tuDong) setDaThuTuTai(true) }
    }
  }, [trangXong, projectId])

  // Thử tải tự động MỘT lần khi vừa xong. Không lặp lại: bấm tải nhiều lần là đúng thứ làm trình
  // duyệt chặn hẳn về sau.
  useEffect(() => {
    if (xongLuc && trangXong.length && !daThuTuTai) taiKetQua(true)
  }, [xongLuc, trangXong.length, daThuTuTai, taiKetQua])

  const mocHetHan = coTuXoa ? mocHetHanGiuTep(xongLuc, giuPhut) : null
  const daHetHan = Boolean(mocHetHan) && conLaiMs(mocHetHan) <= 0

  return (
    <main className="trang-chu">
      {/* Tiêu đề và hạn mức nằm CÙNG một hàng: hạn mức là thứ liếc qua, không phải thứ đọc.
          Trước đây nó là một thẻ viền xanh to chiếm trọn bề ngang, đẩy ô thả ảnh xuống dưới. */}
      <header className="trang-chu-dau">
        <div className="dau-hang">
          <div className="dau-chu">
            <h1>Dịch truyện tranh sang tiếng Việt</h1>
            <p className="dan">Thả ảnh trang truyện vào đây là chạy — không cần đăng ký trước.</p>
          </div>
          <div className="dau-han-muc">
            <TheHanMuc
              hanMuc={hanMuc} dangTai={dangTaiHanMuc} loi={loiHanMuc} onTaiLai={napHanMuc}
            />
          </div>
        </div>

        {/* Dòng đăng nhập TÁCH khỏi góc hạn mức: nhét chung làm cột phải chật cứng và vỡ chữ
            ("Đăng nhập hoặc tạo tài khoản" / "để" / "được nhiều lượt…" rơi ba dòng). Nó cũng không
            gấp — người dùng dịch được ngay mà không cần tài khoản. */}
        {!hanMuc?.co_tai_khoan && onMoDangNhap && (
          <p className="ghi-chu dong-dang-nhap">
            {/* Không lặp lại "để được nhiều lượt hơn mỗi ngày" — khối hạn mức ngay trên đã nói
                đúng câu đó. Cùng một câu hai lần trên một màn là thứ làm trang trông rối. */}
            <button type="button" className="nut-chu" onClick={onMoDangNhap}>
              Đăng nhập hoặc tạo tài khoản
            </button>
          </p>
        )}
      </header>


      <section className="vung-gui" aria-labelledby="tieu-de-gui">
        {/* Giữ cho trình đọc màn hình (vùng này cần có tên), ẩn khỏi mắt: ngay dưới nó ô thả
            đã tự nói "Kéo ảnh vào đây hoặc bấm để chọn" — hiện cả hai là lặp. */}
        <h2 id="tieu-de-gui" className="an-di">Chọn trang truyện</h2>

        <Dropzone files={files} onDoi={setFiles} id="tha-trang-chu" />

        <div className="hang-chon">
          <label htmlFor="chon-ngon-ngu">Chữ trên ảnh là tiếng gì?</label>
          <select
            id="chon-ngon-ngu" value={ngonNgu} onChange={(e) => setNgonNgu(e.target.value)}
            disabled={dangChay}
          >
            {NGON_NGU.map((n) => <option key={n.ma} value={n.ma}>{n.nhan}</option>)}
          </select>
          <p className="ghi-chu">
            Chọn sai thì chữ dịch ra vô nghĩa mà không có báo lỗi nào — nên chọn đúng tiếng của
            trang bạn đang đọc.
          </p>

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
                  {' '}Bạn chọn tay ở ô trên giúp nhé — chọn sai thì chữ dịch ra vô nghĩa.
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
            <Icon ten="dong-ho" co={14} /> Nhớ tải về ngay: tệp <strong>tự xoá sau {giuPhut} phút
            </strong> kể từ lúc dịch xong.
          </p>
        )}
      </section>

      {/* E61 — THU GỌN, không bỏ chữ. Bốn ý này mỗi ý được thêm vì một lần hiểu nhầm có thật
          (người dùng tưởng máy treo; tưởng tệp giữ mãi; thả nhầm định dạng; thả truyện tiếng
          Hàn). Bỏ là quay lại đúng những lần đó. Nhưng bày cả bốn ngay màn đầu thì chúng đứng
          CHẮN việc chính. `<details>` giữ đủ chữ mà trả lại màn đầu cho ô thả ảnh. */}
      <details className="can-biet">
        <summary>Cần biết trước khi bắt đầu</summary>
        <ul>
          <li>
            <Icon ten="dong-ho" co={14} /> Mỗi trang mất <strong>khoảng 30 giây</strong>. Máy
            không treo — cứ để tab mở.
          </li>
          {/* Câu này phải khớp CẤU HÌNH THẬT của máy chủ. Hứa xoá trong khi không xoá, hay hứa
              giữ trong khi sẽ xoá — cả hai đều là nói sai với người dùng về dữ liệu của họ. */}
          {coTuXoa ? (
            <li>
              <strong>Kết quả chỉ giữ {giuPhut} phút</strong> kể từ lúc dịch xong. Sau đó
              {' '}<strong>ảnh gốc, bản dịch và tệp đã gói đều bị xoá</strong>: không chạy lại được,
              không sửa lại được. Muốn làm lại phải tải lên từ đầu và tốn thêm lượt.
            </li>
          ) : (
            <li>
              Kết quả <strong>không tự xoá</strong> theo giờ. Nhưng vẫn nên tải về ngay — đây
              không phải chỗ lưu trữ lâu dài, và chính sách có thể đổi.
            </li>
          )}
          <li>Nhận ảnh <strong>PNG, JPG, WebP</strong>. Mỗi tệp tối đa 25 MB.</li>
          <li>Dịch được chữ <strong>Nhật, Anh, Trung</strong> → tiếng Việt.</li>
        </ul>
      </details>

      {loiChung && (
        <Alert sac="loi" tieuDe={loiChung.ma === 429 ? 'Hết lượt' : 'Không chạy được'}>
          {String(loiChung.message || loiChung).replace(/^\d+:\s*/, '')}
          {loiChung.chiTiet?.reset_luc && (
            <> Có lại sau <strong>{chuDemNguoc(loiChung.chiTiet.reset_luc)}</strong>.</>
          )}
        </Alert>
      )}

      {trang.length > 0 && (
        <section className="tien-do-trang" aria-labelledby="tieu-de-tien-do" aria-live="polite">
          <h2 id="tieu-de-tien-do" className="nho">
            Tiến độ — xong {trangXong.length}/{trang.length} trang
          </h2>
          <ol className="ds-trang">
            {trang.map((t, i) => (
              <li key={t.page_id || i}>
                <span className="ten-trang">{t.ten}</span>
                {t.loi
                  ? <span className="nhan-loi"><Icon ten="canh" co={14} /> {t.loi}</span>
                  : t.xong
                    ? <span className="nhan-xong"><Icon ten="tich" co={14} /> Xong</span>
                    : <TienDoTrang tienDo={t.tienDo} />}
              </li>
            ))}
          </ol>
        </section>
      )}

      {xongLuc && trangXong.length > 0 && (
        <section className="ket-qua" aria-labelledby="tieu-de-ket-qua">
          <h2 id="tieu-de-ket-qua" className="nho">Kết quả</h2>

          {!coTuXoa ? (
            <Alert sac="tin" tieuDe="Nhớ tải về">
              Kết quả <strong>không tự xoá</strong> theo giờ, nhưng đây không phải chỗ lưu trữ lâu
              dài — tải về rồi hãy đóng tab.
            </Alert>
          ) : daHetHan ? (
            <Alert sac="loi" tieuDe={`Đã quá ${giuPhut} phút — tệp không còn nữa`}>
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
            <Button kieu="chinh" onClick={() => taiKetQua(false)} dangChay={dangTai} icon="tai-len">
              {trangXong.length > 1 ? 'Tải cả gói về' : 'Tải ảnh đã dịch về'}
            </Button>
            {daThuTuTai && !tenTepDaTai && (
              <p className="ghi-chu">
                Đã thử tải tự động. <strong>Nếu không thấy tệp nào</strong>, trình duyệt đã chặn
                lượt tải không do bạn bấm — bấm nút trên là được.
              </p>
            )}
            {tenTepDaTai && (
              <p className="ghi-chu">
                <Icon ten="tich" co={14} /> Đã lưu <strong>{tenTepDaTai}</strong>. Không thấy thì
                xem lại thư mục Tải về của trình duyệt.
              </p>
            )}
          </div>

          {!daHetHan && (
            <ul className="ds-anh">
              {trangXong.map((t) => (
                <li key={t.page_id}>
                  <img src={api.urlAnhDaDich(t.page_id)} alt={`Trang đã dịch: ${t.ten}`} loading="lazy" />
                  <span className="ghi-chu">{t.ten}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  )
}
