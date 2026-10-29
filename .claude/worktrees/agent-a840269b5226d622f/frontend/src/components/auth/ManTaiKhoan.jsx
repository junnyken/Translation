import { useEffect, useState } from 'react'

import * as api from '../../api'
import { chuDemNguoc } from '../../lib/dem-nguoc'
import { chuThoiGianGiu } from '../../lib/thoi-gian-giu.js'
import Alert from '../ui/Alert'
import Button from '../ui/Button'
import Dialog from '../ui/Dialog'
import Icon from '../ui/Icon'
import { Input } from '../ui/Field'

/** Màn tài khoản (§4.4 đặc tả) — xem và SỬA (E56).
 *
 * ## Nguyên tắc: hiện ĐÚNG những gì có thật
 *
 * §4.4 nói rõ: *"Hiện đúng những gì có thật: email, tên hiển thị, hạn mức đã dùng / còn lại, mốc
 * reset. **Không** bịa thêm hạng thành viên hay số liệu chưa có thật."*
 *
 * Nên ở đây **không** có: hạng thành viên, tổng số trang đã dịch từ đầu, số chapter, ngày tham
 * gia, chuỗi ngày liên tiếp — hệ thống **không lưu** những thứ đó. Một màn tài khoản trông đầy
 * đặn bằng số liệu bịa thì tệ hơn một màn ngắn nói thật.
 *
 * ## Vì sao hạn mức lấy từ `/han-muc` chứ không tự tính
 *
 * `con_lai` là **nhỏ nhất** trong các chốt, không phải `tran - da_dung`. Tự tính lại ở đây sẽ cho
 * một con số khác với con số ở trang chủ, và người dùng thấy hai số vênh nhau trên cùng một sản
 * phẩm thì không biết tin cái nào.
 *
 * ## E56 — vì sao ô "nhập lại mật khẩu mới" là BẮT BUỘC
 *
 * Hệ thống **không có hạ tầng gửi thư** (giới hạn đã ghi ở `REPORT_E52.md`), nên **không có đường
 * lấy lại mật khẩu**. Gõ sai mật khẩu mới một lần là mất tài khoản vĩnh viễn — không phải "bất
 * tiện", mà là mất hẳn dữ liệu. Ô nhập lại là thứ duy nhất chặn được chuyện đó, và nó so ở NGAY
 * trình duyệt để người dùng biết trước khi bấm.
 *
 * ## Nói TRƯỚC hệ quả, không phải báo sau
 *
 * Đổi mật khẩu thu hồi mọi phiên khác (`services/tai_khoan.doi_mat_khau` giải thích vì sao). Câu
 * cảnh báo nằm cạnh nút, **trước** khi bấm — báo sau khi đã đăng xuất điện thoại của người ta thì
 * đã muộn.
 */
export default function ManTaiKhoan({ nguoiDung, onDong, onDoiNguoiDung }) {
  const [hanMuc, setHanMuc] = useState(null)
  const [loi, setLoi] = useState(null)

  useEffect(() => {
    let huy = false
    api.layHanMuc()
      .then((hm) => { if (!huy) setHanMuc(hm) })
      .catch((e) => { if (!huy) setLoi(e) })
    return () => { huy = true }
  }, [])

  const giuPhut = hanMuc?.giu_ket_qua_phut ?? null

  return (
    <Dialog tieuDe="Tài khoản của bạn" onDong={onDong}>
      <dl className="man-tai-khoan">
        <dt>Email</dt>
        <dd>{nguoiDung.email}</dd>
      </dl>
      {/* Email KHÔNG sửa được ở đây — có chủ đích, xem docstring của `SuaTaiKhoanRequest`. */}
      <p className="ghi-chu">
        Email là tên đăng nhập nên không đổi được ở đây. Cần đổi thì nhờ người quản trị.
      </p>

      <OTenHien nguoiDung={nguoiDung} onXong={onDoiNguoiDung} />

      {nguoiDung.la_quan_tri && (
        <dl className="man-tai-khoan">
          <dt>Quyền</dt>
          <dd>Quản trị</dd>
        </dl>
      )}

      <OMatKhau email={nguoiDung.email} />

      <h3 className="nho">Lượt dịch hôm nay</h3>

      {loi && (
        <Alert sac="canh" tieuDe="Chưa lấy được hạn mức">{String(loi.message || loi)}</Alert>
      )}

      {!loi && !hanMuc && <p className="ghi-chu" aria-live="polite">Đang xem…</p>}

      {hanMuc && (
        <>
          <p className="so-luot">
            <strong>{hanMuc.con_lai}</strong> / {hanMuc.tran} trang còn lại
            {' '}<span className="ghi-chu">(đã dùng {hanMuc.da_dung})</span>
          </p>
          <p className="ghi-chu">
            <Icon ten="dong-ho" co={16} /> Có lại sau{' '}
            <strong>{chuDemNguoc(hanMuc.reset_luc)}</strong> (0h00 giờ Việt Nam)
          </p>

          {/* `con_lai` khác `tran - da_dung` khi một chốt khác thấp hơn. Nói ra khi hai số vênh,
              thay vì để người dùng tự trừ rồi thấy mình tính sai. */}
          {hanMuc.con_lai !== hanMuc.tran - hanMuc.da_dung && (
            <p className="ghi-chu">
              Số còn lại thấp hơn phép trừ vì lượt còn được tính theo <strong>địa chỉ mạng</strong>
              {' '}dùng chung.
            </p>
          )}

          <h3 className="nho">Kết quả được giữ bao lâu</h3>
          <p className="ghi-chu">
            {typeof giuPhut === 'number'
              ? <>Tự xoá <strong>{chuThoiGianGiu(giuPhut)}</strong> sau khi dịch xong — ảnh gốc, bản dịch và
                  tệp đã gói đều mất, không chạy lại và không sửa lại được.</>
              : <>Hiện <strong>không tự xoá</strong> theo giờ. Vẫn nên tải về: đây không phải chỗ
                  lưu trữ lâu dài, và chính sách có thể đổi.</>}
          </p>
        </>
      )}

      <OKhoaApiDeveloper />
    </Dialog>
  )
}

/** Cổng Developer API Key (`tr_live_...`) để khách hàng tích hợp vào Tool riêng / Website đọc truyện. */
function OKhoaApiDeveloper() {
  const [tt, setTt] = useState(null)
  const [keyMoi, setKeyMoi] = useState('')
  const [dangChay, setDangChay] = useState(false)
  const [daCopy, setDaCopy] = useState(false)
  const [moDoc, setMoDoc] = useState(false)
  const [loi, setLoi] = useState(null)

  useEffect(() => {
    let huy = false
    api.xemTrangThaiApiKey()
      .then((d) => { if (!huy) setTt(d) })
      .catch(() => {})
    return () => { huy = true }
  }, [])

  const xuLyTaoKey = async () => {
    setDangChay(true); setLoi(null); setDaCopy(false)
    try {
      const kq = await api.taoMoiApiKey()
      setKeyMoi(kq.api_key || '')
      setTt({
        co_api_key: true,
        tao_luc: kq.tao_luc,
        dung_lan_cuoi: null,
      })
    } catch (e) {
      setLoi(e)
    } finally {
      setDangChay(false)
    }
  }

  const xuLyThuHoi = async () => {
    setDangChay(true); setLoi(null)
    try {
      await api.thuHoiApiKey()
      setKeyMoi('')
      setTt({ co_api_key: false, tao_luc: null, dung_lan_cuoi: null })
    } catch (e) {
      setLoi(e)
    } finally {
      setDangChay(false)
    }
  }

  const apiOrigin = api.API_BASE || window.location.origin
  const keyMau = keyMoi || 'tr_live_YOUR_API_KEY_HERE'

  return (
    <div style={{
      marginTop: 18,
      paddingTop: 14,
      borderTop: '1px solid var(--vien, #334155)',
    }}>
      <h3 className="nho">🔑 Cổng Developer API (Cho Tool / Web Khách Hàng Kéo Về)</h3>
      <p className="ghi-chu">
        Dùng <strong>API Key cá nhân (<code>tr_live_...</code>)</strong> để kết nối tool tự động, plugin WordPress, bot Discord hoặc web đọc truyện của bạn với máy chủ dịch thuật. Lượt dịch qua API được trừ trực tiếp vào số dư lượt của tài khoản này.
      </p>

      {loi && <Alert sac="loi" tieuDe="Lỗi thao tác API Key">{thongDiep(loi)}</Alert>}

      {keyMoi && (
        <div style={{
          background: 'rgba(16, 185, 129, 0.12)',
          border: '1px solid rgba(16, 185, 129, 0.45)',
          borderRadius: 10,
          padding: '12px 14px',
          marginBottom: 12,
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#10b981', marginBottom: 6 }}>
            ✅ Đã tạo API Key mới — Hãy sao chép ngay (chỉ hiện đầy đủ 1 lần):
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <code style={{
              flex: 1,
              padding: '8px 10px',
              background: 'rgba(15, 23, 42, 0.75)',
              color: '#f8fafc',
              borderRadius: 6,
              fontSize: 13,
              wordBreak: 'break-all',
            }}>
              {keyMoi}
            </code>
            <Button
              kieu="chinh"
              onClick={() => {
                navigator.clipboard?.writeText(keyMoi)
                setDaCopy(true)
              }}
            >
              {daCopy ? 'Đã Copy!' : '📋 Copy Key'}
            </Button>
          </div>
        </div>
      )}

      {tt && (
        <p className="ghi-chu" style={{ marginBottom: 10 }}>
          Trạng thái:{' '}
          {tt.co_api_key ? (
            <strong style={{ color: '#10b981' }}>
              Đang hoạt động (tr_live_••••••••)
            </strong>
          ) : (
            <span>Chưa kích hoạt API Key</span>
          )}
          {tt.dung_lan_cuoi && (
            <> · Gọi lần cuối: <strong>{new Date(tt.dung_lan_cuoi).toLocaleString('vi-VN')}</strong></>
          )}
        </p>
      )}

      <div className="hang-nut" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Button kieu="chinh" dangChay={dangChay} onClick={xuLyTaoKey}>
          {tt?.co_api_key ? '🔄 Đổi API Key mới' : '🔑 Tạo API Key ngay'}
        </Button>
        {tt?.co_api_key && (
          <Button dangChay={dangChay} onClick={xuLyThuHoi}>
            🗑️ Thu hồi Key
          </Button>
        )}
        <Button kieu="phu" onClick={() => setMoDoc((v) => !v)}>
          {moDoc ? 'Ẩn tài liệu nối API' : '📖 Xem Code mẫu nối vào Tool'}
        </Button>
      </div>

      {moDoc && (
        <div style={{
          marginTop: 12,
          padding: 12,
          borderRadius: 10,
          background: 'rgba(15, 23, 42, 0.65)',
          border: '1px solid var(--vien, #334155)',
          fontSize: 12.5,
        }}>
          <p style={{ margin: '0 0 8px', fontWeight: 600 }}>
            1. Dịch 1 trang ảnh (Truyền file hoặc link ảnh `image_url`) — Trả về JSON toạ độ + Link ảnh đã ghép chữ:
          </p>
          <pre style={{
            margin: '0 0 10px',
            padding: 10,
            borderRadius: 8,
            background: '#090d16',
            color: '#e2e8f0',
            overflowX: 'auto',
          }}>{`# Python (requests)
import requests

resp = requests.post(
    "${apiOrigin}/api/v1/developer/translate-image",
    headers={"X-Customer-Api-Key": "${keyMau}"},
    data={
        "image_url": "https://example.com/manga-page-01.jpg",
        "source_lang": "ja",   # ja | ko | zh | en
        "target_lang": "vi",   # vi | en
        "engine": "llm_context", # google_fast | llm_context
        "mode": "day_du",      # day_du (có ảnh ghép chữ) | chi_chu (nhanh)
        "wait": "true"
    }
).json()

print("Link tải ảnh đã dịch:", resp["rendered_image_url"])
print("Các khung thoại:", resp["regions"])
print("Số lượt còn lại:", resp["quota"]["total_usable_pages"])`}</pre>

          <p style={{ margin: '0 0 6px', fontWeight: 600 }}>
            2. Kiểm tra số dư lượt (`GET /api/v1/developer/quota`) &amp; Dịch văn bản (`POST /api/v1/developer/translate-text`):
          </p>
          <pre style={{
            margin: 0,
            padding: 10,
            borderRadius: 8,
            background: '#090d16',
            color: '#e2e8f0',
            overflowX: 'auto',
          }}>{`curl -X GET "${apiOrigin}/api/v1/developer/quota" \\
  -H "X-Customer-Api-Key: ${keyMau}"`}</pre>
        </div>
      )}
    </div>
  )
}

/** Tên hiển thị — sửa tại chỗ, KHÔNG đòi mật khẩu.
 *
 * Đòi mật khẩu cho một thao tác vô hại là dạy người dùng gõ mật khẩu vào bất cứ ô nào hỏng ra —
 * đó là huấn luyện cho lừa đảo, không phải bảo mật.
 */
function OTenHien({ nguoiDung, onXong }) {
  const [moSua, setMoSua] = useState(false)
  const [ten, setTen] = useState(nguoiDung.ten_hien || '')
  const [dangLuu, setDangLuu] = useState(false)
  const [loi, setLoi] = useState(null)
  const [xong, setXong] = useState(false)

  const luu = async () => {
    setDangLuu(true); setLoi(null)
    try {
      const kq = await api.suaTaiKhoanCuaToi({ ten_hien: ten })
      onXong?.(kq.nguoi_dung)
      setXong(true)
      setMoSua(false)
    } catch (e) {
      setLoi(e)
    } finally {
      setDangLuu(false)
    }
  }

  if (!moSua) {
    return (
      <>
        <dl className="man-tai-khoan">
          <dt>Tên hiển thị</dt>
          <dd>
            {nguoiDung.ten_hien
              ? nguoiDung.ten_hien
              : <span className="ghi-chu">(chưa đặt — đang dùng phần trước @)</span>}
            {' '}
            <Button kieu="phu" onClick={() => { setMoSua(true); setXong(false) }}>Sửa</Button>
          </dd>
        </dl>
        {xong && <Alert sac="ok" tieuDe="Đã lưu tên hiển thị" />}
      </>
    )
  }

  return (
    <form className="khoi-sua" onSubmit={(e) => { e.preventDefault(); luu() }}>
      <Input
        nhan="Tên hiển thị" value={ten} onChange={(e) => setTen(e.target.value)}
        moTa="Để trống thì hệ thống lấy phần trước @ của email."
        maxLength={120}
      />
      {loi && <Alert sac="loi" tieuDe="Chưa lưu được">{thongDiep(loi)}</Alert>}
      <div className="hang-nut">
        <Button type="submit" kieu="chinh" dangChay={dangLuu}>Lưu</Button>
        <Button onClick={() => { setMoSua(false); setTen(nguoiDung.ten_hien || ''); setLoi(null) }}>
          Huỷ
        </Button>
      </div>
    </form>
  )
}

/** Đổi mật khẩu. Đóng sẵn — mở ra mới hiện ô, để màn chính không thành một rừng ô nhập. */
function OMatKhau({ email }) {
  const [mo, setMo] = useState(false)
  const [cu, setCu] = useState('')
  const [moi, setMoi] = useState('')
  const [lai, setLai] = useState('')
  const [dangLuu, setDangLuu] = useState(false)
  const [loi, setLoi] = useState(null)
  const [ketQua, setKetQua] = useState(null)

  const dong = () => {
    setMo(false); setCu(''); setMoi(''); setLai(''); setLoi(null)
  }

  // Kiểm NGAY ở trình duyệt: không có đường lấy lại mật khẩu, nên gõ lệch hai ô là mất tài khoản.
  const lechNhau = lai.length > 0 && moi !== lai
  const quaNgan = moi.length > 0 && moi.length < 8
  const lyDoKhoa = !cu || !moi || !lai
    ? 'Nhập đủ ba ô.'
    : lechNhau
      ? 'Hai ô mật khẩu mới chưa khớp.'
      : quaNgan
        ? 'Mật khẩu mới phải dài ít nhất 8 ký tự.'
        : undefined

  const luu = async () => {
    setDangLuu(true); setLoi(null)
    try {
      const kq = await api.suaTaiKhoanCuaToi({ mat_khau_cu: cu, mat_khau_moi: moi })
      setKetQua(kq)
      dong()
    } catch (e) {
      setLoi(e)
    } finally {
      setDangLuu(false)
    }
  }

  if (!mo) {
    return (
      <>
        <h3 className="nho">Mật khẩu</h3>
        {ketQua && (
          <Alert sac="ok" tieuDe="Đã đổi mật khẩu">
            {ketQua.so_phien_khac_da_thu_hoi > 0
              ? <>Đã đăng xuất <strong>{ketQua.so_phien_khac_da_thu_hoi}</strong> thiết bị khác.
                  Máy này vẫn đang đăng nhập.</>
              : <>Không có thiết bị nào khác đang đăng nhập. Máy này vẫn đang đăng nhập.</>}
          </Alert>
        )}
        <p className="ghi-chu">
          <Button onClick={() => { setMo(true); setKetQua(null) }}>Đổi mật khẩu</Button>
        </p>
      </>
    )
  }

  return (
    /* PHẢI là <form>. Ô mật khẩu ngoài form thì Chrome ghi thẳng vào console
       ("Password field is not contained in a form") và — quan trọng hơn — trình quản lý mật khẩu
       KHÔNG nhận ra đây là lượt đổi mật khẩu, nên nó giữ nguyên mật khẩu cũ đã lưu. Lần đăng nhập
       sau nó tự điền mật khẩu cũ và người dùng tưởng việc đổi đã thất bại. Bọc form cũng cho phép
       bấm Enter để gửi, thứ mọi người đều thử. */
    <form className="khoi-sua" onSubmit={(e) => { e.preventDefault(); if (!lyDoKhoa) luu() }}>
      <h3 className="nho">Đổi mật khẩu</h3>
      {/* Ô tên đăng nhập ẩn — KHÔNG phải để hiển thị.
          Chrome nói thẳng: "Password forms should have (optionally hidden) username fields".
          Không có nó thì trình quản lý mật khẩu biết đây là form mật khẩu nhưng KHÔNG biết của tài
          khoản nào, nên vẫn không cập nhật đúng bản ghi — đúng cái hại mà việc bọc <form> định vá.
          `readOnly` để không ai sửa được, `tabIndex={-1}` + `aria-hidden` để không lọt vào luồng
          bàn phím và không đọc lặp email (email đã hiện ngay phía trên màn này). */}
      <input
        type="text" name="email" value={email} readOnly autoComplete="username"
        className="an-di" tabIndex={-1} aria-hidden="true"
      />
      <Input
        nhan="Mật khẩu hiện tại" type="password" autoComplete="current-password" batBuoc
        value={cu} onChange={(e) => setCu(e.target.value)}
      />
      <Input
        nhan="Mật khẩu mới" type="password" autoComplete="new-password" batBuoc
        value={moi} onChange={(e) => setMoi(e.target.value)}
        moTa="Ít nhất 8 ký tự."
        loi={quaNgan ? 'Mật khẩu mới phải dài ít nhất 8 ký tự.' : undefined}
      />
      <Input
        nhan="Nhập lại mật khẩu mới" type="password" autoComplete="new-password" batBuoc
        value={lai} onChange={(e) => setLai(e.target.value)}
        loi={lechNhau ? 'Hai ô chưa khớp.' : undefined}
        moTa="Không có đường lấy lại mật khẩu, nên phải gõ đúng hai lần."
      />

      {/* Nói TRƯỚC khi bấm. Báo sau khi đã đăng xuất điện thoại của người ta thì đã muộn. */}
      <Alert sac="canh" tieuDe="Các thiết bị khác sẽ bị đăng xuất">
        Đổi mật khẩu sẽ thu hồi mọi phiên đăng nhập khác. Máy bạn đang dùng thì vẫn đăng nhập.
      </Alert>

      {loi && <Alert sac="loi" tieuDe="Chưa đổi được">{thongDiep(loi)}</Alert>}

      <div className="hang-nut">
        <Button
          type="submit" kieu="chinh" dangChay={dangLuu} lyDoKhoa={lyDoKhoa} id="nut-doi-mk"
        >
          Đổi mật khẩu
        </Button>
        <Button onClick={dong}>Huỷ</Button>
      </div>
    </form>
  )
}

/** Lấy câu của MÁY CHỦ, không thay bằng câu chung.
 *
 * Máy chủ phân biệt "mật khẩu hiện tại không đúng" với "mật khẩu mới phải khác" — thay cả hai
 * bằng "có lỗi xảy ra" là bắt người dùng đoán xem mình sai ở đâu.
 */
function thongDiep(e) {
  if (typeof e?.cauNguoiDoc === 'string' && e.cauNguoiDoc) return e.cauNguoiDoc
  return String(e?.message || e)
}
