import { useEffect, useState } from 'react'
import * as api from '../../api'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui'
import ChanTrangManga from './ChanTrangManga'

export default function TrangBangGia({ nguoiDung, onQuayLai, onMoDangNhap }) {
  const { laEn } = useNgonNguUI()
  const [thongTinNap, setThongTinNap] = useState(null)
  const [emailNhapTay, setEmailNhapTay] = useState(nguoiDung?.email || '')
  const [daChepNoiDung, setDaChepNoiDung] = useState(false)
  const donGia = thongTinNap?.ty_le_vnd_moi_trang || 500

  const DANH_SACH_GOI = [
    {
      ma: 'khoi_dong',
      nhan: laEn ? 'STARTER' : 'KHỞI ĐỘNG',
      ten: laEn ? 'Starter Pack (100 Pages)' : 'Gói Khởi Động (100 trang)',
      giaVnd: 100 * donGia,
      soTrang: 100,
      uocChap: '~5 chapter',
      khuyenMai: '0%',
      donGiaThuc: `${donGia.toLocaleString('vi-VN')}đ/trang`,
      diemManh: laEn
        ? [
            '100 translated comic pages',
            'Use on Web (comic.io.vn) + Chrome Extension',
            'Purchased pages never expire overnight',
          ]
        : [
            '100 trang dịch truyện tranh chất lượng cao',
            'Dùng trên Web (comic.io.vn) + Tiện ích Chrome',
            'Lượt mua tích luỹ không bao giờ hết hạn qua đêm',
          ],
      noiBat: false,
    },
    {
      ma: 'tieu_chuan',
      nhan: laEn ? '⭐ POPULAR VIP' : '⭐ ĐỘC GIẢ CÀY TRUYỆN',
      ten: laEn ? 'Reader VIP (550 Pages)' : 'Gói Cày Truyện (550 trang)',
      giaVnd: 500 * donGia,
      soTrang: 550,
      uocChap: '~28 chapter',
      khuyenMai: '+10%',
      donGiaThuc: `${Math.round((500 * donGia) / 550).toLocaleString('vi-VN')}đ/trang`,
      diemManh: laEn
        ? [
            'Includes +10% bonus pages (500 + 50 free)',
            'Sync across Web + Chrome Extension + Windows App',
            'Double-click bubble editor & 4 genre fonts',
            'Purchased quota never expires',
          ]
        : [
            'Tặng thêm +10% số trang (mua 500 nhận 550 trang)',
            'Đồng bộ trên Web + Tiện ích Chrome + App Windows',
            'Nhấp đúp sửa thoại & chọn 4 bộ Font thể loại',
            'Lượt mua tích luỹ vĩnh viễn theo tài khoản',
          ],
      noiBat: false,
    },
    {
      ma: 'nhom_dich',
      nhan: laEn ? '🎨 SCANLATION STUDIO' : '🎨 NHÓM DỊCH / STUDIO',
      ten: laEn ? 'Studio Pack (1,200 Pages)' : 'Gói Studio (1.200 trang)',
      giaVnd: 1000 * donGia,
      soTrang: 1200,
      uocChap: '~60 chapter',
      khuyenMai: '+20%',
      donGiaThuc: `${Math.round((1000 * donGia) / 1200).toLocaleString('vi-VN')}đ/trang`,
      diemManh: laEn
        ? [
            'Includes +20% bonus pages (1,000 + 200 free)',
            'Full Windows App auto-crawl & chapter folder split',
            'Export high-res JPG, .CBZ, .ZIP, .PDF & Long-Strip',
            'Character & pronoun consistency glossary',
          ]
        : [
            'Tặng thêm +20% số trang (mua 1.000 nhận 1.200 trang)',
            'Mở toàn bộ App Windows cày link & chia thư mục Chapter',
            'Xuất ảnh rời, gói .CBZ, .ZIP, .PDF & dải Webtoon dài',
            'Sổ tay nhân vật & xưng hô nhất quán xuyên suốt bộ truyện',
          ],
      noiBat: true,
    },
    {
      ma: 'doanh_nghiep_api',
      nhan: laEn ? '🏢 BUSINESS API PRO' : '🏢 DOANH NGHIỆP / WEB API PRO',
      ten: laEn ? 'Business API (6,500 Pages)' : 'Gói Doanh Nghiệp API (6.500 trang)',
      giaVnd: 5000 * donGia,
      soTrang: 6500,
      uocChap: '~325 chapter',
      khuyenMai: '+30%',
      donGiaThuc: `${Math.round((5000 * donGia) / 6500).toLocaleString('vi-VN')}đ/trang`,
      diemManh: laEn
        ? [
            'Includes +30% bonus pages (5,000 + 1,500 free)',
            'Personal Developer API Key (tr_live_...) — no 14-day expiry',
            '1-call Translate Image & Batch Chapter URL endpoints',
            'Automatic Anti-Hotlink bypass & SHA-256 Cache',
          ]
        : [
            'Tặng thêm +30% số trang (mua 5.000 nhận 6.500 trang)',
            'Cấp Khoá Developer API cố định (tr_live_...) cho Tool/Web',
            'Đẩy cả Chapter qua URL + Tự động vượt chặn Hotlink',
            'Tích hợp Bảng Cache Cộng đồng SHA-256 (0.15s)',
          ],
      noiBat: true,
    },
    {
      ma: 'enterprise_scale',
      nhan: laEn ? '🏛️ ENTERPRISE SCALE' : '🏛️ HỆ THỐNG CỔNG TRUYỆN LỚN',
      ten: laEn ? 'Enterprise (28,000 Pages)' : 'Gói Enterprise (28.000 trang)',
      giaVnd: 20000 * donGia,
      soTrang: 28000,
      uocChap: '~1.400 chapter',
      khuyenMai: '+40%',
      donGiaThuc: `${Math.round((20000 * donGia) / 28000).toLocaleString('vi-VN')}đ/trang`,
      diemManh: laEn
        ? [
            'Includes +40% bonus pages (20,000 + 8,000 free)',
            'Lowest cost per page (~357 VND / page)',
            'Multi-worker concurrency + 0.15s Community Cache',
            'Unlimited integration with WordPress/Madara CMS & Bots',
          ]
        : [
            'Tặng thêm +40% số trang (mua 20.000 nhận 28.000 trang)',
            'Đơn giá tối ưu nhất hệ thống (chỉ ~357đ / trang)',
            'Luồng Worker đa nhân + Cache Cộng đồng SHA-256 siêu tốc',
            'Đấu nối không giới hạn vào CMS WordPress/Madara & Bot',
          ],
      noiBat: true,
    },
  ]

  const [goiDangChon, setGoiDangChon] = useState(DANH_SACH_GOI[1])

  useEffect(() => {
    let huy = false
    api.layThongTinNapLuot()
      .then((tt) => {
        if (!huy) setThongTinNap(tt)
      })
      .catch(() => {})
    return () => { huy = true }
  }, [])

  useEffect(() => {
    if (nguoiDung?.email) setEmailNhapTay(nguoiDung.email)
  }, [nguoiDung?.email])

  const emailHienTai = (nguoiDung?.email || emailNhapTay || '').trim()
  const noiDungChuyenKhoan = emailHienTai
    ? `NAP ${emailHienTai}`
    : (thongTinNap?.noi_dung_chuyen_khoan || 'NAP <EMAIL_CUA_BAN>')

  const nganHangTen = thongTinNap?.ngan_hang_ten || 'MB'
  const nganHangSoTk = thongTinNap?.ngan_hang_so_tk || ''
  const nganHangChuTk = thongTinNap?.ngan_hang_chu_tk || ''
  const urlQr = nganHangSoTk
    ? `https://img.vietqr.io/image/${encodeURIComponent(nganHangTen)}-${encodeURIComponent(nganHangSoTk)}-compact2.png?amount=${goiDangChon.giaVnd}&addInfo=${encodeURIComponent(noiDungChuyenKhoan)}&accountName=${encodeURIComponent(nganHangChuTk)}`
    : ''

  function saoChepNoiDung() {
    navigator.clipboard?.writeText(noiDungChuyenKhoan)
    setDaChepNoiDung(true)
    setTimeout(() => setDaChepNoiDung(false), 2000)
  }

  return (
    <main className="than-trang" style={{ maxWidth: 1160, margin: '0 auto', padding: '24px 16px 48px' }}>
      {/* Hero Banner */}
      <div style={{
        textAlign: 'center',
        padding: '28px 22px',
        marginBottom: 24,
        borderRadius: 20,
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(6, 78, 59, 0.9))',
        border: '1px solid rgba(16, 185, 129, 0.45)',
        color: '#f8fafc',
        boxShadow: '0 20px 45px rgba(2, 6, 23, 0.35)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
          <span style={{
            display: 'inline-block',
            background: 'rgba(16, 185, 129, 0.2)',
            color: '#34d399',
            border: '1px solid rgba(16, 185, 129, 0.45)',
            padding: '5px 14px',
            borderRadius: 999,
            fontSize: 12.5,
            fontWeight: 700,
          }}>
            💎 {laEn ? 'PRICING & 24/7 INSTANT VIETQR TOP-UP' : 'BẢNG GIÁ GÓI CƯỚC CÁ NHÂN, STUDIO & DOANH NGHIỆP (API)'}
          </span>
          <a
            href="#"
            onClick={(e) => {
              if (onQuayLai) {
                e.preventDefault()
                onQuayLai()
              }
            }}
            className="nut nut-phu"
          >
            ← {laEn ? 'Back to Translator' : 'Quay về Trang Dịch Truyện'}
          </a>
        </div>

        <h1 style={{ fontSize: 30, margin: '4px 0 10px', color: '#ffffff' }}>
          {laEn
            ? 'Purchased Pages Never Expire — Shared Across Web, Extension, App & API'
            : 'Lượt Mua Tích Luỹ Không Bao Giờ Hết Hạn — Dùng Chung Web, App & Cổng API'}
        </h1>
        <p style={{ maxWidth: 820, margin: '0 auto', fontSize: 15.5, color: '#cbd5e1', lineHeight: 1.6 }}>
          {laEn
            ? 'Automatic 24/7 VietQR activation in 5–15 seconds. Enterprise plans include up to +40% bonus pages and full Developer REST API access.'
            : 'Nạp tự động 24/7 qua mã VietQR, cộng lượt tức thì sau 5–15 giây. Gói Studio & Doanh nghiệp tặng thêm tới +40% số trang và mở toàn bộ Cổng Developer API (tr_live_...).'}
        </p>
      </div>

      {/* Tầng miễn phí mỗi ngày */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: 16,
        marginBottom: 24,
      }}>
        <div style={{
          background: 'rgba(15, 23, 42, 0.9)',
          border: '1px solid rgba(148, 163, 184, 0.28)',
          borderRadius: 14,
          padding: '16px 18px',
          color: '#e2e8f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#94a3b8' }}>👤 KHÁCH VÃNG LAI (KHÔNG CẦN ĐĂNG KÝ)</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#ffffff', marginTop: 2 }}>
              {laEn ? 'Free 2 Pages / Day' : 'Miễn phí 2 trang / ngày'}
            </div>
            <div style={{ fontSize: 13, color: '#cbd5e1' }}>
              {laEn ? 'Test translation quality immediately on Web or Extension.' : 'Dùng thử ngay trên Web hoặc Tiện ích Chrome không cần tạo tài khoản.'}
            </div>
          </div>
          <span style={{ fontSize: 22, fontWeight: 800, color: '#94a3b8' }}>0đ</span>
        </div>

        <div style={{
          background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.92), rgba(15, 23, 42, 0.94))',
          border: '1px solid rgba(129, 140, 248, 0.45)',
          borderRadius: 14,
          padding: '16px 18px',
          color: '#e2e8f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#818cf8' }}>✨ TÀI KHOẢN ĐĂNG KÝ MIỄN PHÍ</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#ffffff', marginTop: 2 }}>
              {laEn ? 'Free 20 Pages / Day (1 Full Chapter)' : 'Miễn phí 20 trang / ngày (Trọn 1 Chapter)'}
            </div>
            <div style={{ fontSize: 13, color: '#cbd5e1' }}>
              {laEn ? 'Resets automatically at 00:00 Vietnam time every day.' : 'Tự động hồi lại 20 trang mới vào 00:00 mỗi ngày. Chỉ mất 5 giây đăng ký.'}
            </div>
          </div>
          {!nguoiDung && onMoDangNhap ? (
            <button type="button" className="nut-manga nut-manga-chinh" onClick={onMoDangNhap} style={{ whiteSpace: 'nowrap' }}>
              {laEn ? 'Sign Up Free' : 'Đăng ký nhận 20 trang'}
            </button>
          ) : (
            <span style={{ fontSize: 14, fontWeight: 700, color: '#34d399', whiteSpace: 'nowrap' }}>✅ Đang kích hoạt</span>
          )}
        </div>
      </div>

      {/* Lưới 5 gói cước trả phí */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(215px, 1fr))',
        gap: 14,
        marginBottom: 26,
      }}>
        {DANH_SACH_GOI.map((g) => {
          const dangChon = goiDangChon.ma === g.ma
          return (
            <div
              key={g.ma}
              style={{
                borderRadius: 16,
                padding: '20px 16px',
                background: dangChon
                  ? 'linear-gradient(160deg, rgba(15, 23, 42, 0.98), rgba(30, 58, 138, 0.92))'
                  : 'rgba(15, 23, 42, 0.92)',
                border: dangChon
                  ? '2px solid #38bdf8'
                  : (g.noiBat ? '2px solid rgba(249, 115, 22, 0.7)' : '1px solid rgba(148, 163, 184, 0.28)'),
                color: '#f8fafc',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                boxShadow: dangChon ? '0 12px 30px rgba(56, 189, 248, 0.22)' : '0 8px 20px rgba(2, 6, 23, 0.25)',
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                  <span style={{
                    display: 'inline-block',
                    fontSize: 10.5,
                    fontWeight: 800,
                    padding: '3px 8px',
                    borderRadius: 999,
                    background: g.noiBat ? 'rgba(249, 115, 22, 0.2)' : 'rgba(148, 163, 184, 0.16)',
                    color: g.noiBat ? '#fb923c' : '#cbd5e1',
                  }}>
                    {g.nhan}
                  </span>
                  {g.khuyenMai !== '0%' && (
                    <span style={{
                      fontSize: 11,
                      fontWeight: 800,
                      color: '#34d399',
                      background: 'rgba(16, 185, 129, 0.16)',
                      padding: '2px 7px',
                      borderRadius: 999,
                    }}>
                      {g.khuyenMai}
                    </span>
                  )}
                </div>

                <h2 style={{ margin: '0 0 6px', fontSize: 16.5, color: '#ffffff' }}>{g.ten}</h2>
                <div style={{ fontSize: 23, fontWeight: 800, color: '#38bdf8', marginBottom: 2 }}>
                  {g.giaVnd.toLocaleString('vi-VN')}đ
                </div>
                <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 12 }}>
                  ⚡ <b>{g.soTrang.toLocaleString('vi-VN')} trang</b> ({g.uocChap}) · {g.donGiaThuc}
                </div>

                <ul style={{ margin: '0 0 16px', paddingLeft: 18, fontSize: 12.8, lineHeight: 1.6, color: '#e2e8f0' }}>
                  {g.diemManh.map((dm, idx) => (
                    <li key={idx} style={{ marginBottom: 4 }}>{dm}</li>
                  ))}
                </ul>
              </div>

              <button
                type="button"
                className={dangChon ? 'nut-manga nut-manga-win' : (g.noiBat ? 'nut-manga nut-manga-chinh' : 'nut-manga nut-manga-phu')}
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => {
                  setGoiDangChon(g)
                  document.getElementById('khung-thanh-toan-qr')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
                }}
              >
                {dangChon
                  ? (laEn ? '✅ Selected below' : '✅ Đang chọn gói này')
                  : (laEn ? '💳 Select & Get VietQR' : '💳 Chọn Gói & Lấy Mã QR')}
              </button>
            </div>
          )
        })}
      </div>

      {/* Khung thanh toán VietQR tự động 24/7 */}
      <section
        id="khung-thanh-toan-qr"
        style={{
          padding: '24px 22px',
          borderRadius: 18,
          background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 23, 0.96))',
          border: '2px solid #10b981',
          color: '#f8fafc',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 24,
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 18px 40px rgba(16, 185, 129, 0.15)',
        }}
      >
        <div style={{ flex: '1 1 380px' }}>
          <div style={{ color: '#34d399', fontWeight: 800, fontSize: 15, marginBottom: 6 }}>
            ⚡ {laEn ? '24/7 AUTOMATIC VIETQR ACTIVATION:' : 'THANH TOÁN & CỘNG LƯỢT TỰ ĐỘNG 24/7:'} {goiDangChon.ten}
          </div>
          <p style={{ margin: '0 0 12px', fontSize: 14, color: '#cbd5e1', lineHeight: 1.6 }}>
            {laEn
              ? 'Scan the VietQR code with any banking app. Our Webhook system automatically credits your account within 5–15 seconds after transfer!'
              : 'Quét mã VietQR bên phải bằng ứng dụng Ngân hàng bất kỳ. Hệ thống Webhook sẽ tự động cộng ngay số trang (kèm % khuyến mãi) vào tài khoản của bạn chỉ sau 5–15 giây!'}
          </p>

          {!nguoiDung && (
            <div style={{ marginBottom: 12 }}>
              <label htmlFor="o-email-nap" style={{ display: 'block', fontSize: 13, fontWeight: 700, color: '#fbbf24', marginBottom: 4 }}>
                📧 {laEn ? 'Enter your Account Email to generate your personal QR code:' : 'Nhập Email tài khoản của bạn để mã QR tự điền đúng nội dung:'}
              </label>
              <input
                id="o-email-nap"
                type="email"
                value={emailNhapTay}
                onChange={(e) => setEmailNhapTay(e.target.value)}
                placeholder="vi-du@gmail.com"
                style={{
                  width: '100%',
                  maxWidth: 420,
                  padding: '9px 12px',
                  borderRadius: 8,
                  border: '1px solid #38bdf8',
                  background: '#0f172a',
                  color: '#fff',
                  fontSize: 14,
                }}
              />
            </div>
          )}

          <div style={{
            fontSize: 13.8,
            background: '#090d16',
            padding: '14px 16px',
            borderRadius: 12,
            border: '1px solid #334155',
            lineHeight: 1.75,
          }}>
            <div>
              🏦 {laEn ? 'Bank:' : 'Ngân hàng:'} <b>{nganHangTen}</b>
              {nganHangSoTk ? <> · STK: <b style={{ color: '#38bdf8' }}>{nganHangSoTk}</b></> : null}
              {nganHangChuTk ? <> ({nganHangChuTk})</> : null}
            </div>
            <div>
              💰 {laEn ? 'Amount:' : 'Số tiền chuyển khoản:'}{' '}
              <strong style={{ color: '#38bdf8', fontSize: 16 }}>{goiDangChon.giaVnd.toLocaleString('vi-VN')} VNĐ</strong>{' '}
              (Nhận <b>{goiDangChon.soTrang.toLocaleString('vi-VN')} trang</b>)
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginTop: 4 }}>
              <span>
                📝 {laEn ? 'Required Memo:' : 'Nội dung chuyển khoản bắt buộc:'}{' '}
                <code style={{ color: '#f97316', fontWeight: 800, fontSize: 15, background: 'rgba(249,115,22,0.12)', padding: '2px 8px', borderRadius: 6 }}>
                  {noiDungChuyenKhoan}
                </code>
              </span>
              <button
                type="button"
                onClick={saoChepNoiDung}
                style={{
                  padding: '4px 10px',
                  borderRadius: 6,
                  border: '1px solid #475569',
                  background: daChepNoiDung ? '#059669' : '#1e293b',
                  color: '#fff',
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {daChepNoiDung ? '✅ Đã chép' : '📋 Sao chép nội dung'}
              </button>
            </div>
          </div>
        </div>

        {urlQr && (
          <div style={{
            background: '#ffffff',
            padding: 12,
            borderRadius: 14,
            textAlign: 'center',
            boxShadow: '0 10px 25px rgba(0,0,0,0.4)',
            margin: '0 auto',
          }}>
            <img
              src={urlQr}
              alt={`VietQR ${goiDangChon.ten}`}
              style={{ width: 210, height: 'auto', display: 'block', borderRadius: 8 }}
            />
            <div style={{ color: '#0f172a', fontWeight: 700, fontSize: 12, marginTop: 6 }}>
              Quét mã bằng App Ngân hàng
            </div>
          </div>
        )}
      </section>

      <div style={{ marginTop: 36 }}>
        <ChanTrangManga />
      </div>
    </main>
  )
}
