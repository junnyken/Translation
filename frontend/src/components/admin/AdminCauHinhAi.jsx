import { useState } from 'react'
import * as api from '../../api.js'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
import Button from '../ui/Button.jsx'

/**
 * AdminCauHinhAi — Quản lý khoá DeepSeek API & AI dự phòng.
 *
 * Cho phép thêm/thay khoá, kiểm tra kết nối, xoá khoá đã lưu.
 */
export default function AdminCauHinhAi({ thongKe, onNap, setLoi, setThongBaoOk }) {
  const { laEn } = useNgonNguUI()
  const heThong = thongKe?.he_thong || {}

  const [khoaDeepseekInput, setKhoaDeepseekInput] = useState('')
  const [khoaDuPhongInput, setKhoaDuPhongInput] = useState('')
  const [hienKhoaAi, setHienKhoaAi] = useState(false)
  const [dangLuuAi, setDangLuuAi] = useState(false)
  const [dangKiemTraAi, setDangKiemTraAi] = useState(false)
  const [ketQuaKiemTraAi, setKetQuaKiemTraAi] = useState(null)

  async function xuLyLuuKhoaAi(e) {
    e.preventDefault()
    if (!khoaDeepseekInput.trim() && !khoaDuPhongInput.trim()) {
      setLoi(
        laEn
          ? 'Please paste at least one DeepSeek key (starting with sk-…).'
          : 'Vui lòng dán ít nhất 1 khoá DeepSeek (bắt đầu bằng sk-...) trước khi bấm Lưu.',
      )
      return
    }
    setDangLuuAi(true)
    setLoi(null)
    setThongBaoOk(null)
    setKetQuaKiemTraAi(null)
    try {
      const payload = {}
      if (khoaDeepseekInput.trim()) payload.khoaDeepseek = khoaDeepseekInput.trim()
      if (khoaDuPhongInput.trim()) payload.khoaDuPhong = khoaDuPhongInput.trim()
      const kq = await api.quanTriLuuCauHinhAi(payload)
      setThongBaoOk(
        kq?.thong_diep ||
          (laEn ? 'DeepSeek key saved & activated!' : 'Đã lưu & kích hoạt khoá DeepSeek!'),
      )
      setKhoaDeepseekInput('')
      setKhoaDuPhongInput('')
      await onNap()
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLuuAi(false)
    }
  }

  async function xuLyKiemTraKetNoiAi() {
    setDangKiemTraAi(true)
    setLoi(null)
    setKetQuaKiemTraAi(null)
    try {
      const kq = await api.quanTriKiemTraKetNoiAi(
        khoaDeepseekInput.trim() || khoaDuPhongInput.trim() || null,
      )
      setKetQuaKiemTraAi(kq)
    } catch (err) {
      setKetQuaKiemTraAi({
        ok: false,
        thong_diep: String(err?.message || err).replace(/^\d+:\s*/, ''),
      })
    } finally {
      setDangKiemTraAi(false)
    }
  }

  async function xuLyXoaKhoaAi() {
    if (
      !window.confirm(
        laEn
          ? 'Delete all saved AI keys from Admin?'
          : 'Bạn có chắc muốn xoá khoá AI đã lưu trên trang Quản trị?',
      )
    )
      return
    setDangLuuAi(true)
    setLoi(null)
    setThongBaoOk(null)
    setKetQuaKiemTraAi(null)
    try {
      const kq = await api.quanTriLuuCauHinhAi({ khoaDeepseek: '', khoaDuPhong: '' })
      setThongBaoOk(kq?.thong_diep || (laEn ? 'AI keys deleted.' : 'Đã xoá khoá AI.'))
      await onNap()
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLuuAi(false)
    }
  }

  return (
    <>
      {/* ── Current Status ─────────────────────────────────────────────── */}
      <div className="admin-khung">
        <div className="admin-khung-dau">
          <div>
            <h3>
              🤖 {laEn
                ? 'DeepSeek & AI Engine Configuration'
                : 'Quản lý Khoá API DeepSeek & Động cơ Dịch Ngữ Cảnh'}
            </h3>
            <p className="ghi-chu">
              {laEn
                ? 'Add or replace DeepSeek keys directly — auto-syncs to Web, Chrome Extension, Windows App & Worker.'
                : 'Thêm/thay khoá DeepSeek trực tiếp — tự động đồng bộ cho Web, Tiện ích Chrome, App Windows & Worker.'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <span
              className="admin-huy-hieu"
              style={{
                background: heThong.deepseek_configured ? '#dcfce7' : heThong.llm_configured ? '#fef3c7' : '#f1f5f9',
                color: heThong.deepseek_configured ? '#15803d' : heThong.llm_configured ? '#b45309' : '#475569',
              }}
            >
              {heThong.deepseek_configured
                ? `🟢 DeepSeek (${heThong.deepseek_so_key} key)`
                : heThong.llm_configured
                  ? `🟡 ${laEn ? 'Fallback AI' : 'AI dự phòng'} (${heThong.du_phong_so_key || 1} key)`
                  : `⚪ ${laEn ? 'No AI Key' : 'Chưa gắn Key AI'}`}
            </span>
            <Button kieu="phu" disabled={dangKiemTraAi} onClick={xuLyKiemTraKetNoiAi}>
              {dangKiemTraAi
                ? `⏳ ${laEn ? 'Testing…' : 'Đang ping…'}`
                : `🧪 ${laEn ? 'Test Connection' : 'Kiểm tra kết nối'}`}
            </Button>
          </div>
        </div>
        <div className="admin-khung-than">
          {/* Current keys info */}
          <div className="admin-ai-trang-thai">
            <span>
              <b>{laEn ? 'Provider' : 'Nhà cung cấp'}:</b>{' '}
              {heThong.nha_cung_cap_uu_tien || (heThong.llm_configured ? heThong.llm_model_name : (laEn ? 'Free translate' : 'Dịch nhanh miễn phí'))}
            </span>
            <span>·</span>
            <span>
              <b>{laEn ? 'Source' : 'Nguồn nạp'}:</b> {heThong.nguon_cau_hinh || (laEn ? 'Default' : 'Mặc định')}
            </span>
            {Array.isArray(heThong.deepseek_keys_masked) && heThong.deepseek_keys_masked.length > 0 && (
              <>
                <span>·</span>
                <span style={{ display: 'inline-flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                  <b>DeepSeek:</b>
                  {heThong.deepseek_keys_masked.map((k, idx) => (
                    <span key={idx} className="admin-ai-key-badge deepseek">🔑 {k}</span>
                  ))}
                </span>
              </>
            )}
            {Array.isArray(heThong.du_phong_keys_masked) && heThong.du_phong_keys_masked.length > 0 && (
              <>
                <span>·</span>
                <span style={{ display: 'inline-flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                  <b>{laEn ? 'Backup' : 'Dự phòng'}:</b>
                  {heThong.du_phong_keys_masked.map((k, idx) => (
                    <span key={idx} className="admin-ai-key-badge du-phong">🛡️ {k}</span>
                  ))}
                </span>
              </>
            )}
          </div>

          {/* Test result */}
          {ketQuaKiemTraAi && (
            <div className={`admin-ket-qua-kiem-tra ${ketQuaKiemTraAi.ok ? 'ok' : 'loi'}`}>
              {ketQuaKiemTraAi.ok ? '✅ ' : '⚠️ '}
              {ketQuaKiemTraAi.thong_diep}
            </div>
          )}

          {/* Key input form */}
          <form onSubmit={xuLyLuuKhoaAi}>
            <div className="admin-form-hang" style={{ marginBottom: 10 }}>
              <div className="admin-form-nhom" style={{ flex: 2 }}>
                <label>DeepSeek API Key</label>
                <input
                  type={hienKhoaAi ? 'text' : 'password'}
                  placeholder={laEn ? 'Paste key (sk-…), multiple keys separated by comma' : 'Dán khoá (sk-…), nhiều khoá ngăn bằng dấu phẩy'}
                  value={khoaDeepseekInput}
                  onChange={(e) => setKhoaDeepseekInput(e.target.value)}
                  autoComplete="off"
                />
              </div>
              <div className="admin-form-nhom" style={{ flex: 1.4 }}>
                <label>{laEn ? 'Backup Key (optional)' : 'Khoá dự phòng (tuỳ chọn)'}</label>
                <input
                  type={hienKhoaAi ? 'text' : 'password'}
                  placeholder={laEn ? 'Backup AI key when DeepSeek is down' : 'Khoá AI dự phòng khi DeepSeek bảo trì'}
                  value={khoaDuPhongInput}
                  onChange={(e) => setKhoaDuPhongInput(e.target.value)}
                  autoComplete="off"
                />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <Button
                type="button"
                kieu="phu"
                onClick={() => setHienKhoaAi((v) => !v)}
                title={laEn ? 'Show/hide key characters' : 'Hiện/ẩn ký tự khoá'}
              >
                {hienKhoaAi ? `🙈 ${laEn ? 'Hide' : 'Ẩn'}` : `👁️ ${laEn ? 'Show' : 'Hiện'}`}
              </Button>
              <Button type="submit" kieu="chinh" disabled={dangLuuAi}>
                {dangLuuAi
                  ? `⏳ ${laEn ? 'Saving…' : 'Đang lưu…'}`
                  : `💾 ${laEn ? 'Save & Activate' : 'Lưu & Kích hoạt'}`}
              </Button>
              {(heThong.deepseek_configured || heThong.du_phong_configured) && (
                <Button type="button" kieu="phu" disabled={dangLuuAi} onClick={xuLyXoaKhoaAi}>
                  🗑️ {laEn ? 'Delete Keys' : 'Xoá key'}
                </Button>
              )}
            </div>
          </form>

          <p style={{ fontSize: 12, color: '#94a3b8', marginTop: 12 }}>
            💡 <b>{laEn ? 'Tip' : 'Mẹo'}:</b>{' '}
            {laEn
              ? 'Get keys at platform.deepseek.com/api_keys. Multiple keys separated by comma will auto-rotate when one hits rate limit (HTTP 402/429).'
              : 'Lấy khoá tại platform.deepseek.com/api_keys. Nhiều khoá cách nhau bằng dấu phẩy sẽ tự động xoay vòng khi 1 khoá chạm giới hạn (HTTP 402/429).'}
          </p>
        </div>
      </div>

      {/* ── System AI Info ─────────────────────────────────────────────── */}
      {(heThong.rss_api_mb || heThong.llm_model_name) && (
        <div className="admin-khung">
          <div className="admin-khung-dau">
            <h3>🖥️ {laEn ? 'System Resources' : 'Tài nguyên Hệ thống'}</h3>
          </div>
          <div className="admin-khung-than">
            <div className="admin-chinh-sach">
              {heThong.llm_model_name && (
                <span>🤖 <b>{laEn ? 'AI Model' : 'Mô hình AI'}:</b> {heThong.llm_model_name}</span>
              )}
              {heThong.rss_api_mb && (
                <span>
                  🖥️ <b>RAM API:</b> {Math.round(heThong.rss_api_mb)} MB
                  {heThong.rss_worker_mb ? ` · Worker: ${Math.round(heThong.rss_worker_mb)} MB` : ''}
                </span>
              )}
              <span>⚙️ <b>{laEn ? 'Running jobs' : 'Job đang chạy'}:</b> {thongKe?.viec_dang_chay ?? 0}</span>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
