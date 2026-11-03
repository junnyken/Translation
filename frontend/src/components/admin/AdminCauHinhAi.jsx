import { useEffect, useState } from 'react'
import * as api from '../../api.js'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
import Button from '../ui/Button.jsx'

const PRESET_CUSTOM_PROVIDERS = [
  {
    id: 'together',
    ten: 'Together AI (Qwen / Llama)',
    base_url: 'https://api.together.xyz/v1',
    model: 'Qwen/Qwen2.5-72B-Instruct-Turbo',
  },
  {
    id: 'dashscope',
    ten: 'Alibaba Qwen (DashScope Intl)',
    base_url: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1',
    model: 'qwen-plus',
  },
  {
    id: 'xai',
    ten: 'xAI Grok API',
    base_url: 'https://api.x.ai/v1',
    model: 'grok-2-latest',
  },
  {
    id: 'mistral',
    ten: 'Mistral AI',
    base_url: 'https://api.mistral.ai/v1',
    model: 'mistral-small-latest',
  },
  {
    id: 'fireworks',
    ten: 'Fireworks AI',
    base_url: 'https://api.fireworks.ai/inference/v1',
    model: 'accounts/fireworks/models/deepseek-v3',
  },
]

const BIEN_THE_ICON = {
  deepseek: '🐋',
  gemini: '✨',
  openai: '🧠',
  openrouter: '🌐',
  groq: '⚡',
  custom: '🛠️',
}

/**
 * AdminCauHinhAi — Trung tâm Quản lý Đa Mô Hình AI, Kiểm tra Số Dư ($) & Kết nối API.
 *
 * Hiển thị đồng thời DeepSeek, Google Gemini, OpenAI, OpenRouter, Groq LPU và bất kỳ Model mở rộng nào,
 * kèm tra cứu số dư tiền thực tế (DeepSeek / OpenRouter) và trạng thái hoạt động của từng Model.
 */
export default function AdminCauHinhAi({ thongKe, onNap, setLoi, setThongBaoOk }) {
  const { laEn } = useNgonNguUI()
  const heThong = thongKe?.he_thong || {}

  // Tab cấu hình: 'chinh' (DeepSeek + Gemini), 'pho-bien' (OpenAI + OpenRouter + Groq), 'mo-rong' (Custom Endpoint)
  const [tabCauHinh, setTabCauHinh] = useState('chinh')
  const [nhaCungCapChinh, setNhaCungCapChinh] = useState(heThong.nha_cung_cap_chinh || 'tu_dong')

  // Inputs cho từng nhà cung cấp
  const [khoaDeepseekInput, setKhoaDeepseekInput] = useState('')
  const [modelDeepseek, setModelDeepseek] = useState(heThong.deepseek_model || 'deepseek-chat')

  const [khoaGeminiInput, setKhoaGeminiInput] = useState('')
  const [modelGemini, setModelGemini] = useState(heThong.gemini_model || 'gemini-2.5-flash')

  const [khoaOpenaiInput, setKhoaOpenaiInput] = useState('')
  const [modelOpenai, setModelOpenai] = useState('gpt-4o-mini')

  const [khoaOpenrouterInput, setKhoaOpenrouterInput] = useState('')
  const [modelOpenrouter, setModelOpenrouter] = useState('google/gemini-2.5-flash')

  const [khoaGroqInput, setKhoaGroqInput] = useState('')
  const [modelGroq, setModelGroq] = useState('llama-3.3-70b-versatile')

  const [customTen, setCustomTen] = useState('')
  const [customBaseUrl, setCustomBaseUrl] = useState('')
  const [customModel, setCustomModel] = useState('')
  const [customApiKey, setCustomApiKey] = useState('')

  const [hienKhoaAi, setHienKhoaAi] = useState(false)
  const [dangLuuAi, setDangLuuAi] = useState(false)
  const [dangKiemTraAi, setDangKiemTraAi] = useState(false)
  const [ketQuaKiemTraAi, setKetQuaKiemTraAi] = useState(null)
  const [daTuDongKiemTra, setDaTuDongKiemTra] = useState(false)

  // Đồng bộ giá trị mặc định từ heThong khi tải xong
  useEffect(() => {
    if (heThong.nha_cung_cap_chinh) setNhaCungCapChinh(heThong.nha_cung_cap_chinh)
    if (heThong.deepseek_model) setModelDeepseek(heThong.deepseek_model)
    if (heThong.gemini_model) setModelGemini(heThong.gemini_model)
    const dsModels = Array.isArray(heThong.danh_sach_model_ai) ? heThong.danh_sach_model_ai : []
    const mOai = dsModels.find((m) => m.id === 'openai')
    if (mOai?.model) setModelOpenai(mOai.model)
    const mOr = dsModels.find((m) => m.id === 'openrouter')
    if (mOr?.model) setModelOpenrouter(mOr.model)
    const mGroq = dsModels.find((m) => m.id === 'groq')
    if (mGroq?.model) setModelGroq(mGroq.model)
    const mCustom = dsModels.find((m) => m.id === 'custom')
    if (mCustom) {
      if (mCustom.ten && mCustom.ten !== 'Model Mở Rộng (OpenAI-Compatible)') setCustomTen(mCustom.ten)
      if (mCustom.base_url) setCustomBaseUrl(mCustom.base_url)
      if (mCustom.model && mCustom.model !== 'custom-model') setCustomModel(mCustom.model)
    }
  }, [
    heThong.nha_cung_cap_chinh,
    heThong.deepseek_model,
    heThong.gemini_model,
    heThong.danh_sach_model_ai,
  ])

  // Tự động kiểm tra số dư & trạng thái các Model đã gắn khi mở tab Cấu hình AI lần đầu
  useEffect(() => {
    if (
      !daTuDongKiemTra &&
      (heThong.deepseek_configured || heThong.gemini_configured || heThong.du_phong_configured)
    ) {
      setDaTuDongKiemTra(true)
      xuLyKiemTraKetNoiAi(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [heThong.deepseek_configured, heThong.gemini_configured, heThong.du_phong_configured])

  const danhSachModel = Array.isArray(heThong.danh_sach_model_ai) && heThong.danh_sach_model_ai.length > 0
    ? heThong.danh_sach_model_ai
    : [
        {
          id: 'deepseek',
          ten: 'DeepSeek AI',
          mo_ta: 'Dịch ngữ cảnh truyện tranh & Biên kịch Review',
          model: heThong.deepseek_model || 'deepseek-chat',
          da_ket_noi: Boolean(heThong.deepseek_configured),
          so_key: heThong.deepseek_so_key || 0,
          keys_masked: heThong.deepseek_keys_masked || [],
          nguon: heThong.deepseek_configured ? 'Admin / .env' : 'Chưa gắn',
          ho_tro_so_du_tien: true,
          link_quan_ly: 'https://platform.deepseek.com/usage',
        },
        {
          id: 'gemini',
          ten: 'Google Gemini',
          mo_ta: 'Vision OCR Đọc chữ phức tạp & Dịch ngữ cảnh đa phương thức',
          model: heThong.gemini_model || heThong.llm_model_name || 'gemini-2.5-flash',
          da_ket_noi: Boolean(heThong.gemini_configured || heThong.du_phong_configured),
          so_key: heThong.gemini_so_key || heThong.du_phong_so_key || 0,
          keys_masked: heThong.gemini_keys_masked || heThong.du_phong_keys_masked || [],
          nguon: heThong.gemini_nguon || '.env',
          ho_tro_so_du_tien: false,
          link_quan_ly: 'https://aistudio.google.com/apikey',
        },
      ]

  const mapKetQuaTheoId = {}
  if (Array.isArray(ketQuaKiemTraAi?.chi_tiet_models)) {
    for (const item of ketQuaKiemTraAi.chi_tiet_models) {
      if (item.id && !mapKetQuaTheoId[item.id]) {
        mapKetQuaTheoId[item.id] = item
      }
    }
  }

  async function xuLyLuuKhoaAi(e) {
    e.preventDefault()
    setDangLuuAi(true)
    setLoi(null)
    setThongBaoOk(null)
    try {
      const payload = {
        nhaCungCapChinh,
        modelDeepseek: modelDeepseek.trim() || 'deepseek-chat',
        modelGemini: modelGemini.trim() || 'gemini-2.5-flash',
        modelOpenai: modelOpenai.trim() || 'gpt-4o-mini',
        modelOpenrouter: modelOpenrouter.trim() || 'google/gemini-2.5-flash',
        modelGroq: modelGroq.trim() || 'llama-3.3-70b-versatile',
      }
      if (khoaDeepseekInput.trim()) payload.khoaDeepseek = khoaDeepseekInput.trim()
      if (khoaGeminiInput.trim()) payload.khoaGemini = khoaGeminiInput.trim()
      if (khoaOpenaiInput.trim()) payload.khoaOpenai = khoaOpenaiInput.trim()
      if (khoaOpenrouterInput.trim()) payload.khoaOpenrouter = khoaOpenrouterInput.trim()
      if (khoaGroqInput.trim()) payload.khoaGroq = khoaGroqInput.trim()
      if (customTen.trim()) payload.customTen = customTen.trim()
      if (customBaseUrl.trim()) payload.customBaseUrl = customBaseUrl.trim()
      if (customModel.trim()) payload.customModel = customModel.trim()
      if (customApiKey.trim()) payload.customApiKey = customApiKey.trim()

      const kq = await api.quanTriLuuCauHinhAi(payload)
      setThongBaoOk(
        kq?.thong_diep ||
          (laEn ? 'AI Multi-Model configuration saved & synced!' : 'Đã lưu & đồng bộ cấu hình Đa Mô Hình AI!'),
      )
      setKhoaDeepseekInput('')
      setKhoaGeminiInput('')
      setKhoaOpenaiInput('')
      setKhoaOpenrouterInput('')
      setKhoaGroqInput('')
      setCustomApiKey('')
      await onNap()
      await xuLyKiemTraKetNoiAi(null)
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLuuAi(false)
    }
  }

  async function xuLyKiemTraKetNoiAi(khoaTuyChon = null) {
    setDangKiemTraAi(true)
    setLoi(null)
    try {
      const thu =
        typeof khoaTuyChon === 'string' && khoaTuyChon.trim()
          ? khoaTuyChon.trim()
          : khoaDeepseekInput.trim() ||
            khoaGeminiInput.trim() ||
            khoaOpenaiInput.trim() ||
            khoaOpenrouterInput.trim() ||
            khoaGroqInput.trim() ||
            null
      const kq = await api.quanTriKiemTraKetNoiAi(thu)
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

  async function xuLyXoaKhoaTheoNhaCungCap(providerId, tenProvider) {
    if (
      !window.confirm(
        laEn
          ? `Remove saved Admin API key for ${tenProvider}? (Server .env keys if any will remain intact)`
          : `Bạn có chắc muốn gỡ khoá ${tenProvider} đã nhập trên Admin? (Khoá gốc trong .env máy chủ nếu có vẫn được giữ nguyên)`,
      )
    )
      return
    setDangLuuAi(true)
    setLoi(null)
    setThongBaoOk(null)
    try {
      const payload = {}
      if (providerId === 'deepseek') payload.khoaDeepseek = ''
      if (providerId === 'gemini') {
        payload.khoaGemini = ''
        payload.khoaDuPhong = ''
      }
      if (providerId === 'openai') payload.khoaOpenai = ''
      if (providerId === 'openrouter') payload.khoaOpenrouter = ''
      if (providerId === 'groq') payload.khoaGroq = ''
      if (providerId === 'custom') payload.customApiKey = ''
      const kq = await api.quanTriLuuCauHinhAi(payload)
      setThongBaoOk(kq?.thong_diep || `Đã gỡ khoá ${tenProvider} trên Admin.`)
      await onNap()
      await xuLyKiemTraKetNoiAi(null)
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLuuAi(false)
    }
  }

  const soModelDangKetNoi = danhSachModel.filter((m) => m.da_ket_noi).length

  return (
    <>
      {/* ── PHẦN 1: BẢNG SỐ DƯ TIỀN & TRẠNG THÁI TẤT CẢ CÁC MODEL AI ──────────── */}
      <div className="admin-khung">
        <div className="admin-khung-dau">
          <div>
            <h3>
              💳{' '}
              {laEn
                ? 'Connected AI Models, Remaining Balance ($) & Live Health'
                : 'Bảng Trạng Thái, Số Dư Tiền ($) & Sức Khoẻ Các Model AI'}
            </h3>
            <p className="ghi-chu">
              {laEn
                ? 'View all connected AI engines (DeepSeek, Google Gemini, OpenAI, OpenRouter, Groq, Custom) and check real-time account balances.'
                : 'Hiển thị đầy đủ mọi Model đang kết nối (cả DeepSeek, Google Gemini lẫn các Model mở rộng) kèm kiểm tra số tiền còn lại trực tiếp từ hãng.'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <span
              className="admin-huy-hieu"
              style={{
                background: soModelDangKetNoi > 0 ? '#dcfce7' : '#f1f5f9',
                color: soModelDangKetNoi > 0 ? '#15803d' : '#475569',
                fontWeight: 700,
              }}
            >
              🟢 {soModelDangKetNoi} {laEn ? 'Models Connected' : 'Model đang kết nối'}
            </span>
            <Button
              kieu="chinh"
              disabled={dangKiemTraAi}
              onClick={() => xuLyKiemTraKetNoiAi(null)}
            >
              {dangKiemTraAi
                ? `⏳ ${laEn ? 'Checking balance & ping…' : 'Đang tra số dư & ping…'}`
                : `💰 ${laEn ? 'Check Balance & Ping All Models' : 'Kiểm tra Số dư & Kết nối Tất cả'}`}
            </Button>
          </div>
        </div>

        <div className="admin-khung-than">
          {/* Thanh trạng thái ưu tiên tổng quát */}
          <div className="admin-ai-trang-thai" style={{ marginBottom: 16 }}>
            <span>
              🎯 <b>{laEn ? 'Active Routing' : 'Luồng ưu tiên hiện tại'}:</b>{' '}
              <strong style={{ color: '#4f46e5' }}>
                {heThong.nha_cung_cap_uu_tien || 'Google Gemini / DeepSeek'}
              </strong>
            </span>
            <span>·</span>
            <span>
              📦 <b>{laEn ? 'Config Source' : 'Nguồn nạp'}:</b>{' '}
              {heThong.nguon_cau_hinh || 'Mặc định (.env)'}
            </span>
            <span>·</span>
            <span>
              🛡️ <b>{laEn ? 'Auto-Failover' : 'Cơ chế dự phòng'}:</b>{' '}
              {laEn
                ? 'Auto-rotates to next connected model if primary hits HTTP 402/429'
                : 'Tự động chuyển sang Model kế tiếp (VD: DeepSeek → Gemini) nếu hết tiền hoặc quá tải'}
            </span>
          </div>

          {/* Kết quả kiểm tra tổng hợp */}
          {ketQuaKiemTraAi && (
            <div
              className={`admin-ket-qua-kiem-tra ${ketQuaKiemTraAi.ok ? 'ok' : 'loi'}`}
              style={{ marginBottom: 16 }}
            >
              {ketQuaKiemTraAi.ok ? '✅ ' : '⚠️ '}
              {ketQuaKiemTraAi.thong_diep}
            </div>
          )}

          {/* Lưới Thẻ Các Model AI (DeepSeek, Gemini, OpenAI, OpenRouter, Groq, Custom) */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))',
              gap: 14,
            }}
          >
            {danhSachModel.map((m) => {
              const kqLive = mapKetQuaTheoId[m.id]
              const daKetNoi = Boolean(m.da_ket_noi)
              const laUuTienChinh =
                nhaCungCapChinh === m.id ||
                (nhaCungCapChinh === 'tu_dong' && m.id === 'deepseek' && daKetNoi) ||
                (nhaCungCapChinh === 'tu_dong' &&
                  m.id === 'gemini' &&
                  daKetNoi &&
                  !heThong.deepseek_configured)

              return (
                <div
                  key={m.id}
                  style={{
                    border: daKetNoi
                      ? laUuTienChinh
                        ? '2px solid #6366f1'
                        : '1px solid #cbd5e1'
                      : '1px dashed #cbd5e1',
                    borderRadius: 12,
                    padding: '14px 16px',
                    background: daKetNoi ? '#ffffff' : '#f8fafc',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: 10,
                    boxShadow: daKetNoi ? '0 2px 8px rgba(15, 23, 42, 0.04)' : 'none',
                  }}
                >
                  <div>
                    {/* Dòng tiêu đề Model */}
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        gap: 8,
                        marginBottom: 6,
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 18 }}>{BIEN_THE_ICON[m.id] || '🤖'}</span>
                          <strong style={{ fontSize: 15, color: '#0f172a' }}>{m.ten}</strong>
                          {laUuTienChinh && (
                            <span
                              style={{
                                fontSize: 11,
                                fontWeight: 700,
                                padding: '2px 8px',
                                borderRadius: 999,
                                background: '#eef2ff',
                                color: '#4f46e5',
                                border: '1px solid #c7d2fe',
                              }}
                            >
                              ⭐ Ưu tiên chính
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>{m.mo_ta}</div>
                      </div>

                      <span
                        style={{
                          fontSize: 11.5,
                          fontWeight: 700,
                          padding: '3px 9px',
                          borderRadius: 999,
                          whiteSpace: 'nowrap',
                          background: daKetNoi ? '#dcfce7' : '#f1f5f9',
                          color: daKetNoi ? '#15803d' : '#64748b',
                        }}
                      >
                        {daKetNoi ? `🟢 ${m.so_key} key (${m.nguon})` : '⚪ Chưa gắn key'}
                      </span>
                    </div>

                    {/* Thông tin Model ID & Khoá đã che */}
                    <div
                      style={{
                        fontSize: 12.5,
                        color: '#334155',
                        background: '#f8fafc',
                        padding: '8px 10px',
                        borderRadius: 8,
                        border: '1px solid #e2e8f0',
                        marginTop: 8,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                        <span style={{ color: '#64748b' }}>Model đang dùng:</span>
                        <code
                          style={{
                            fontWeight: 700,
                            color: '#0f172a',
                            background: '#e2e8f0',
                            padding: '1px 6px',
                            borderRadius: 4,
                          }}
                        >
                          {m.model}
                        </code>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        <span style={{ color: '#64748b' }}>Khoá API:</span>
                        {Array.isArray(m.keys_masked) && m.keys_masked.length > 0 ? (
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                            {m.keys_masked.map((km, idx) => (
                              <span
                                key={idx}
                                className={`admin-ai-key-badge ${m.id === 'deepseek' ? 'deepseek' : 'du-phong'}`}
                                style={{ fontSize: 11.5 }}
                              >
                                🔑 {km}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>Chưa kết nối</span>
                        )}
                      </div>

                      {/* Hiển thị SỐ DƯ TIỀN ($) hoặc Trạng thái Hạn mức */}
                      <div
                        style={{
                          borderTop: '1px dashed #cbd5e1',
                          paddingTop: 6,
                          marginTop: 2,
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          gap: 6,
                          flexWrap: 'wrap',
                        }}
                      >
                        <span style={{ color: '#64748b', fontWeight: 600 }}>
                          {m.ho_tro_so_du_tien ? '💰 Số dư tài khoản:' : '📊 Trạng thái / Hạn mức:'}
                        </span>
                        {daKetNoi ? (
                          kqLive ? (
                            <span
                              style={{
                                fontWeight: 700,
                                color:
                                  kqLive.con_tien === false || !kqLive.ok
                                    ? '#dc2626'
                                    : kqLive.co_so_du_tien
                                      ? '#059669'
                                      : '#2563eb',
                              }}
                            >
                              {kqLive.so_du_hien_thi ||
                                (kqLive.ok ? `Hoạt động tốt (${kqLive.do_tre_ms}ms)` : 'Lỗi kết nối')}
                            </span>
                          ) : (
                            <span style={{ color: '#64748b', fontSize: 12 }}>
                              {dangKiemTraAi
                                ? '⏳ Đang kiểm tra...'
                                : m.ho_tro_so_du_tien
                                  ? 'Bấm "Kiểm tra Số dư" để xem $'
                                  : m.id === 'gemini'
                                    ? ' Sẵn sàng (Theo gói Google AI Studio)'
                                    : 'Sẵn sàng phục vụ'}
                            </span>
                          )
                        ) : (
                          <span style={{ color: '#94a3b8' }}>—</span>
                        )}
                      </div>

                      {/* Phản hồi ping thực tế nếu có */}
                      {kqLive && (
                        <div
                          style={{
                            fontSize: 11.5,
                            padding: '4px 8px',
                            borderRadius: 6,
                            background: kqLive.ok ? '#f0fdf4' : '#fef2f2',
                            color: kqLive.ok ? '#166534' : '#991b1b',
                          }}
                        >
                          {kqLive.ok
                            ? `⚡ Phản hồi ${kqLive.do_tre_ms}ms · Dịch thử: "${kqLive.ket_qua_mau}"`
                            : `⚠️ ${kqLive.thong_diep}`}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Thanh nút thao tác từng thẻ Model */}
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 8,
                      marginTop: 4,
                      flexWrap: 'wrap',
                    }}
                  >
                    {m.link_quan_ly ? (
                      <a
                        href={m.link_quan_ly}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          fontSize: 12,
                          color: '#4f46e5',
                          textDecoration: 'none',
                          fontWeight: 600,
                        }}
                      >
                        🔗 {m.ho_tro_so_du_tien ? 'Xem Billing / Nạp tiền ↗' : 'Quản lý API Key ↗'}
                      </a>
                    ) : (
                      <span />
                    )}

                    <div style={{ display: 'flex', gap: 6 }}>
                      <button
                        type="button"
                        className="admin-nut-nho"
                        onClick={() => {
                          if (m.id === 'deepseek' || m.id === 'gemini') setTabCauHinh('chinh')
                          else if (m.id === 'custom') setTabCauHinh('mo-rong')
                          else setTabCauHinh('pho-bien')
                          const el = document.getElementById('khung-ket-noi-da-model')
                          if (el) el.scrollIntoView({ behavior: 'smooth' })
                        }}
                      >
                        ⚙️ {daKetNoi ? 'Đổi Key / Model' : '+ Kết nối'}
                      </button>
                      {daKetNoi && m.nguon.includes('Admin') && (
                        <button
                          type="button"
                          className="admin-nut-nho nguy-hiem"
                          disabled={dangLuuAi}
                          onClick={() => xuLyXoaKhoaTheoNhaCungCap(m.id, m.ten)}
                        >
                          🗑️ Gỡ
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── PHẦN 2: KẾT NỐI & THÊM MODEL AI MỚI (ĐA MÔ HÌNH) ───────────────────── */}
      <div className="admin-khung" id="khung-ket-noi-da-model">
        <div className="admin-khung-dau">
          <div>
            <h3>
              🔌{' '}
              {laEn
                ? 'Connect & Configure Multiple AI Models'
                : 'Kết nối & Cấu hình Đa Mô Hình AI (DeepSeek, Gemini, OpenAI, Groq, OpenRouter & Model Mới)'}
            </h3>
            <p className="ghi-chu">
              {laEn
                ? 'Connect multiple AI providers at the same time. Choose which model is primary or let the system auto-rotate.'
                : 'Bạn có thể gắn cùng lúc nhiều khoá của nhiều hãng AI khác nhau. Khi thêm khoá DeepSeek, khoá Google Gemini vẫn được giữ nguyên để phối hợp đọc chữ (Vision OCR) và dự phòng tự động.'}
            </p>
          </div>
        </div>

        <div className="admin-khung-than">
          <form onSubmit={xuLyLuuKhoaAi}>
            {/* Bộ chọn Model ưu tiên chính */}
            <div
              style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 10,
                padding: '12px 14px',
                marginBottom: 16,
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
              }}
            >
              <div>
                <strong style={{ fontSize: 13.5, color: '#0f172a' }}>
                  🎯 Chế độ ưu tiên gọi Model khi dịch ngữ cảnh & viết kịch bản:
                </strong>
                <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
                  Nếu Model ưu tiên đầu hết số dư (HTTP 402) hoặc chạm giới hạn nhịp (HTTP 429), hệ thống tự động xoay sang các Model còn lại.
                </div>
              </div>
              <select
                value={nhaCungCapChinh}
                onChange={(e) => setNhaCungCapChinh(e.target.value)}
                style={{
                  padding: '8px 12px',
                  borderRadius: 8,
                  border: '1px solid #cbd5e1',
                  fontWeight: 600,
                  fontSize: 13,
                  color: '#1e293b',
                  background: '#fff',
                  minWidth: 270,
                }}
              >
                <option value="tu_dong">🔄 Tự động thông minh (DeepSeek → Gemini → Dự phòng)</option>
                <option value="deepseek">🐋 Ưu tiên DeepSeek AI (deepseek-chat / reasoner)</option>
                <option value="gemini">✨ Ưu tiên Google Gemini (gemini-2.5-flash / 3.5-flash)</option>
                <option value="openai">🧠 Ưu tiên OpenAI (gpt-4o-mini / gpt-4.1-mini)</option>
                <option value="openrouter">🌐 Ưu tiên OpenRouter (Claude / Gemini / Qwen)</option>
                <option value="groq">⚡ Ưu tiên Groq LPU Siêu tốc (Llama 3.3 70B)</option>
                <option value="custom">🛠️ Ưu tiên Model Mở Rộng Tuỳ Chỉnh (Custom API)</option>
              </select>
            </div>

            {/* Thanh chuyển Tab nhóm nhà cung cấp */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
              <button
                type="button"
                className={`admin-bo-loc-nut ${tabCauHinh === 'chinh' ? 'active' : ''}`}
                onClick={() => setTabCauHinh('chinh')}
              >
                🐋 DeepSeek & ✨ Google Gemini (Lõi Chính)
              </button>
              <button
                type="button"
                className={`admin-bo-loc-nut ${tabCauHinh === 'pho-bien' ? 'active' : ''}`}
                onClick={() => setTabCauHinh('pho-bien')}
              >
                🧠 OpenAI · 🌐 OpenRouter · ⚡ Groq LPU
              </button>
              <button
                type="button"
                className={`admin-bo-loc-nut ${tabCauHinh === 'mo-rong' ? 'active' : ''}`}
                onClick={() => setTabCauHinh('mo-rong')}
              >
                🛠️ + Kết nối Model Khác Bất Kỳ (Custom API)
              </button>
            </div>

            {/* TAB 1: DEEPSEEK & GOOGLE GEMINI */}
            {tabCauHinh === 'chinh' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 16 }}>
                {/* Khối DeepSeek */}
                <div
                  style={{
                    border: '1px solid #e2e8f0',
                    borderRadius: 10,
                    padding: 14,
                    background: '#ffffff',
                  }}
                >
                  <div style={{ fontWeight: 700, fontSize: 14, color: '#0f172a', marginBottom: 8 }}>
                    🐋 1. DeepSeek AI (Hỗ trợ kiểm tra số dư tiền $ / ¥ trực tiếp)
                  </div>
                  <div className="admin-form-hang">
                    <div className="admin-form-nhom" style={{ flex: 2.2 }}>
                      <label>DeepSeek API Key (sk-...)</label>
                      <input
                        type={hienKhoaAi ? 'text' : 'password'}
                        placeholder={
                          heThong.deepseek_configured
                            ? `Đang gắn: ${(heThong.deepseek_keys_masked || []).join(', ')} (Dán khoá mới nếu muốn thay)`
                            : 'Dán khoá sk-... (nhiều khoá ngăn bằng dấu phẩy)'
                        }
                        value={khoaDeepseekInput}
                        onChange={(e) => setKhoaDeepseekInput(e.target.value)}
                        autoComplete="off"
                      />
                    </div>
                    <div className="admin-form-nhom" style={{ flex: 1 }}>
                      <label>Model DeepSeek</label>
                      <select
                        value={modelDeepseek}
                        onChange={(e) => setModelDeepseek(e.target.value)}
                        style={{
                          padding: '9px 12px',
                          borderRadius: 8,
                          border: '1px solid #cbd5e1',
                          fontSize: 13.5,
                        }}
                      >
                        <option value="deepseek-chat">deepseek-chat (DeepSeek V3 - Nhanh & Rẻ)</option>
                        <option value="deepseek-reasoner">deepseek-reasoner (DeepSeek R1 - Suy luận sâu)</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Khối Google Gemini */}
                <div
                  style={{
                    border: '1px solid #e2e8f0',
                    borderRadius: 10,
                    padding: 14,
                    background: '#ffffff',
                  }}
                >
                  <div style={{ fontWeight: 700, fontSize: 14, color: '#0f172a', marginBottom: 8 }}>
                    ✨ 2. Google Gemini API (Dùng cho cả Vision OCR đọc chữ khó & Dịch ngữ cảnh)
                  </div>
                  <div className="admin-form-hang">
                    <div className="admin-form-nhom" style={{ flex: 2.2 }}>
                      <label>Google Gemini API Key (AIza... / AQ...)</label>
                      <input
                        type={hienKhoaAi ? 'text' : 'password'}
                        placeholder={
                          heThong.gemini_configured || heThong.du_phong_configured
                            ? `Đang gắn (${heThong.gemini_nguon || '.env'}): ${(heThong.gemini_keys_masked || heThong.du_phong_keys_masked || []).join(', ')} — Dán thêm nếu muốn bổ sung`
                            : 'Dán khoá Gemini AIza... (nhiều khoá ngăn bằng dấu phẩy)'
                        }
                        value={khoaGeminiInput}
                        onChange={(e) => setKhoaGeminiInput(e.target.value)}
                        autoComplete="off"
                      />
                    </div>
                    <div className="admin-form-nhom" style={{ flex: 1 }}>
                      <label>Model Google Gemini</label>
                      <input
                        type="text"
                        list="gemini-models-list"
                        value={modelGemini}
                        onChange={(e) => setModelGemini(e.target.value)}
                        placeholder="gemini-2.5-flash"
                      />
                      <datalist id="gemini-models-list">
                        <option value="gemini-2.5-flash" />
                        <option value="gemini-2.5-pro" />
                        <option value="gemini-2.0-flash" />
                        <option value="gemini-3.1-flash-lite" />
                        <option value="gemini-3.5-flash" />
                      </datalist>
                    </div>
                  </div>
                  <div style={{ fontSize: 12, color: '#64748b', marginTop: 6 }}>
                    ℹ️ Khoá Gemini trong <code>.env</code> của máy chủ luôn được giữ tự động và hiển thị ở bảng trên ngay cả khi bạn để trống ô này.
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: OPENAI, OPENROUTER, GROQ */}
            {tabCauHinh === 'pho-bien' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 16 }}>
                {/* OpenAI */}
                <div style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: 14, background: '#fff' }}>
                  <div style={{ fontWeight: 700, fontSize: 14, color: '#0f172a', marginBottom: 8 }}>
                    🧠 3. OpenAI / ChatGPT API (GPT-4o / GPT-4.1 Mini)
                  </div>
                  <div className="admin-form-hang">
                    <div className="admin-form-nhom" style={{ flex: 2.2 }}>
                      <label>OpenAI API Key (sk-proj-...)</label>
                      <input
                        type={hienKhoaAi ? 'text' : 'password'}
                        placeholder="Dán khoá OpenAI sk-proj-... (bỏ trống nếu không đổi)"
                        value={khoaOpenaiInput}
                        onChange={(e) => setKhoaOpenaiInput(e.target.value)}
                        autoComplete="off"
                      />
                    </div>
                    <div className="admin-form-nhom" style={{ flex: 1 }}>
                      <label>Model OpenAI</label>
                      <input
                        type="text"
                        list="openai-models-list"
                        value={modelOpenai}
                        onChange={(e) => setModelOpenai(e.target.value)}
                        placeholder="gpt-4o-mini"
                      />
                      <datalist id="openai-models-list">
                        <option value="gpt-4o-mini" />
                        <option value="gpt-4.1-mini" />
                        <option value="gpt-4.1-nano" />
                        <option value="gpt-4o" />
                      </datalist>
                    </div>
                  </div>
                </div>

                {/* OpenRouter */}
                <div style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: 14, background: '#fff' }}>
                  <div style={{ fontWeight: 700, fontSize: 14, color: '#0f172a', marginBottom: 8 }}>
                    🌐 4. OpenRouter API (Kết nối Claude 3.7, Qwen, Gemini, DeepSeek — Hỗ trợ báo số dư $ trực tiếp)
                  </div>
                  <div className="admin-form-hang">
                    <div className="admin-form-nhom" style={{ flex: 2.2 }}>
                      <label>OpenRouter API Key (sk-or-v1-...)</label>
                      <input
                        type={hienKhoaAi ? 'text' : 'password'}
                        placeholder="Dán khoá OpenRouter sk-or-v1-... (lấy tại openrouter.ai/keys)"
                        value={khoaOpenrouterInput}
                        onChange={(e) => setKhoaOpenrouterInput(e.target.value)}
                        autoComplete="off"
                      />
                    </div>
                    <div className="admin-form-nhom" style={{ flex: 1 }}>
                      <label>Model OpenRouter</label>
                      <input
                        type="text"
                        list="openrouter-models-list"
                        value={modelOpenrouter}
                        onChange={(e) => setModelOpenrouter(e.target.value)}
                        placeholder="google/gemini-2.5-flash"
                      />
                      <datalist id="openrouter-models-list">
                        <option value="google/gemini-2.5-flash" />
                        <option value="deepseek/deepseek-chat-v3-0324" />
                        <option value="anthropic/claude-3.7-sonnet" />
                        <option value="qwen/qwen-2.5-72b-instruct" />
                        <option value="google/gemma-3-27b-it:free" />
                      </datalist>
                    </div>
                  </div>
                </div>

                {/* Groq */}
                <div style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: 14, background: '#fff' }}>
                  <div style={{ fontWeight: 700, fontSize: 14, color: '#0f172a', marginBottom: 8 }}>
                    ⚡ 5. Groq LPU Siêu Tốc (Tốc độ dịch cực nhanh ~200ms/trang)
                  </div>
                  <div className="admin-form-hang">
                    <div className="admin-form-nhom" style={{ flex: 2.2 }}>
                      <label>Groq API Key (gsk_...)</label>
                      <input
                        type={hienKhoaAi ? 'text' : 'password'}
                        placeholder="Dán khoá Groq gsk_... (lấy tại console.groq.com/keys)"
                        value={khoaGroqInput}
                        onChange={(e) => setKhoaGroqInput(e.target.value)}
                        autoComplete="off"
                      />
                    </div>
                    <div className="admin-form-nhom" style={{ flex: 1 }}>
                      <label>Model Groq</label>
                      <input
                        type="text"
                        list="groq-models-list"
                        value={modelGroq}
                        onChange={(e) => setModelGroq(e.target.value)}
                        placeholder="llama-3.3-70b-versatile"
                      />
                      <datalist id="groq-models-list">
                        <option value="llama-3.3-70b-versatile" />
                        <option value="deepseek-r1-distill-llama-70b" />
                        <option value="qwen-qwq-32b" />
                      </datalist>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 3: CUSTOM MODEL MỞ RỘNG BẤT KỲ */}
            {tabCauHinh === 'mo-rong' && (
              <div
                style={{
                  border: '1px solid #e2e8f0',
                  borderRadius: 10,
                  padding: 14,
                  background: '#ffffff',
                  marginBottom: 16,
                }}
              >
                <div style={{ fontWeight: 700, fontSize: 14, color: '#0f172a', marginBottom: 6 }}>
                  🛠️ 6. Kết nối Bất kỳ Model AI Mới Nào (Chuẩn OpenAI-Compatible Endpoint)
                </div>
                <p style={{ fontSize: 12.5, color: '#64748b', marginBottom: 10 }}>
                  Dùng khi trong tương lai bạn muốn gắn thêm API của hãng mới (Together AI, Alibaba Qwen, Mistral, xAI Grok, Fireworks, hoặc Server GPU riêng). Chọn nhanh mẫu bên dưới hoặc tự nhập URL:
                </p>

                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
                  {PRESET_CUSTOM_PROVIDERS.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className="admin-nut-nho"
                      onClick={() => {
                        setCustomTen(p.ten)
                        setCustomBaseUrl(p.base_url)
                        setCustomModel(p.model)
                      }}
                    >
                      ⚡ Mẫu: {p.ten}
                    </button>
                  ))}
                </div>

                <div className="admin-form-hang" style={{ marginBottom: 10 }}>
                  <div className="admin-form-nhom" style={{ flex: 1 }}>
                    <label>Tên gợi nhớ Nhà cung cấp</label>
                    <input
                      type="text"
                      placeholder="VD: Alibaba Qwen / Together AI"
                      value={customTen}
                      onChange={(e) => setCustomTen(e.target.value)}
                    />
                  </div>
                  <div className="admin-form-nhom" style={{ flex: 1.8 }}>
                    <label>Base URL (Endpoint chuẩn OpenAI v1)</label>
                    <input
                      type="text"
                      placeholder="https://api.together.xyz/v1"
                      value={customBaseUrl}
                      onChange={(e) => setCustomBaseUrl(e.target.value)}
                    />
                  </div>
                  <div className="admin-form-nhom" style={{ flex: 1.2 }}>
                    <label>Tên Model (Model ID)</label>
                    <input
                      type="text"
                      placeholder="Qwen/Qwen2.5-72B-Instruct-Turbo"
                      value={customModel}
                      onChange={(e) => setCustomModel(e.target.value)}
                    />
                  </div>
                </div>

                <div className="admin-form-hang">
                  <div className="admin-form-nhom" style={{ flex: 1 }}>
                    <label>API Key của Model mở rộng</label>
                    <input
                      type={hienKhoaAi ? 'text' : 'password'}
                      placeholder="Dán API Key của nhà cung cấp (nhiều khoá ngăn bằng dấu phẩy)"
                      value={customApiKey}
                      onChange={(e) => setCustomApiKey(e.target.value)}
                      autoComplete="off"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Thanh nút Lưu & Kiểm tra */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <Button
                type="button"
                kieu="phu"
                onClick={() => setHienKhoaAi((v) => !v)}
                title={laEn ? 'Show/hide key characters' : 'Hiện/ẩn ký tự khoá'}
              >
                {hienKhoaAi ? `🙈 ${laEn ? 'Hide Keys' : 'Ẩn ký tự khoá'}` : `👁️ ${laEn ? 'Show Keys' : 'Hiện ký tự khoá'}`}
              </Button>
              <Button type="submit" kieu="chinh" disabled={dangLuuAi}>
                {dangLuuAi
                  ? `⏳ ${laEn ? 'Saving…' : 'Đang lưu…'}`
                  : `💾 ${laEn ? 'Save & Sync Multi-Model AI' : 'Lưu & Kích hoạt Cấu hình AI'}`}
              </Button>
              <Button
                type="button"
                kieu="phu"
                disabled={dangKiemTraAi}
                onClick={() => xuLyKiemTraKetNoiAi(null)}
              >
                {dangKiemTraAi
                  ? `⏳ ${laEn ? 'Testing…' : 'Đang kiểm tra…'}`
                  : `🧪 ${laEn ? 'Test All Models & Balances' : 'Test Kết nối & Số dư Tất cả Model'}`}
              </Button>
            </div>
          </form>

          <p style={{ fontSize: 12, color: '#64748b', marginTop: 12 }}>
            💡 <b>{laEn ? 'Multi-Model Tip' : 'Mẹo vận hành Đa Mô Hình'}:</b>{' '}
            {laEn
              ? 'DeepSeek and OpenRouter support exact USD/CNY balance lookup via API. Google Gemini & OpenAI manage billing on their cloud consoles and show live latency & rate-limit health here.'
              : 'DeepSeek và OpenRouter hỗ trợ trả về chính xác số dư tiền ($ USD / ¥ CNY) ngay trên bảng Quản trị. Với Google Gemini & OpenAI, hãng quản lý hạn mức trên Cloud Console nên bảng trên sẽ báo trực tiếp trạng thái Sống/Chết, độ trễ (ms) và link mở nhanh trang Hạn mức của hãng.'}
          </p>
        </div>
      </div>

      {/* ── PHẦN 3: TÀI NGUYÊN HỆ THỐNG ────────────────────────────────────────── */}
      {(heThong.rss_api_mb || heThong.llm_model_name) && (
        <div className="admin-khung">
          <div className="admin-khung-dau">
            <h3>🖥️ {laEn ? 'System Resources' : 'Tài nguyên Hệ thống & Worker'}</h3>
          </div>
          <div className="admin-khung-than">
            <div className="admin-chinh-sach">
              {heThong.nha_cung_cap_uu_tien && (
                <span>
                  🤖 <b>{laEn ? 'Active AI' : 'Tổ hợp AI đang chạy'}:</b> {heThong.nha_cung_cap_uu_tien}
                </span>
              )}
              {heThong.rss_api_mb && (
                <span>
                  🖥️ <b>RAM API:</b> {Math.round(heThong.rss_api_mb)} MB
                  {heThong.rss_worker_mb ? ` · Worker: ${Math.round(heThong.rss_worker_mb)} MB` : ''}
                </span>
              )}
              <span>
                ⚙️ <b>{laEn ? 'Running jobs' : 'Job đang chạy'}:</b> {thongKe?.viec_dang_chay ?? 0}
              </span>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
