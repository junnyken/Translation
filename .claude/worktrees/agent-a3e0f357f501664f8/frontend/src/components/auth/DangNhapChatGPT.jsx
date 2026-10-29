import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../../api.js'
import { lamMoiCodex, useCodex } from '../../lib/dung-codex.js'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'

// wording: BA review
const CHU = {
  tieuDe: 'Dịch bằng tài khoản ChatGPT của bạn',
  canhBao:
    'Tính năng thử nghiệm: dùng tài khoản ChatGPT của chính bạn, không phải API chính thức của ' +
    'OpenAI. Tài khoản có thể bị giới hạn lượt dùng.',
  nutDangNhap: 'Đăng nhập ChatGPT',
  dangMo: 'Đang lấy mã…',
  huongDan: 'Mở trang OpenAI bên dưới và nhập mã này:',
  nutSaoChep: 'Sao chép mã',
  daSaoChep: 'Đã sao chép',
  moTrang: 'Mở trang OpenAI',
  conLai: (phut, giay) => `Mã hết hạn sau ${phut}:${String(giay).padStart(2, '0')}`,
  dangCho: 'Đang chờ bạn xác nhận trên trang OpenAI…',
  hetHan: 'Mã đã hết hạn. Bấm đăng nhập để lấy mã mới.',
  chuaBatDau: 'Phiên đăng nhập không còn. Bấm đăng nhập để lấy mã mới.',
  daDangNhap: 'Đã đăng nhập',
  goi: 'Gói',
  nutDangXuat: 'Đăng xuất',
  xacNhanDangXuat:
    'Đăng xuất ChatGPT?\n\nToken sẽ bị xoá khỏi máy này; engine ChatGPT ngừng dùng được tới khi ' +
    'bạn đăng nhập lại.',
  loiTaiTrangThai: 'Không đọc được trạng thái đăng nhập ChatGPT',
  tieuDeLoi: 'Không làm được',
}

const CHU_KY_HOI_MS = 5000

/** Đăng nhập ChatGPT kiểu device-code (như Codex CLI) — chỉ quản trị thấy, chỉ khi máy chủ bật.
 *
 * Người dùng mở `link`, gõ `ma`; trong lúc đó ta hỏi `/hoi` mỗi 5 giây. Dừng hỏi khi: đăng nhập
 * xong, mã hết hạn, gặp lỗi, hoặc component bị gỡ — không để vòng hỏi chạy mồ côi.
 */
export default function DangNhapChatGPT() {
  const codex = useCodex()
  const [tt, setTt] = useState(null)        // {da_dang_nhap, email, goi}
  const [phien, setPhien] = useState(null)  // {ma, link, hetHanLuc}
  const [thongBao, setThongBao] = useState(null)
  const [loi, setLoi] = useState(null)
  const [dangLam, setDangLam] = useState(false)
  const [conGiay, setConGiay] = useState(0)
  const [daChep, setDaChep] = useState(false)
  const conSong = useRef(true)

  const nap = useCallback(async () => {
    try {
      const t = await api.layTrangThaiCodex()
      if (conSong.current) setTt(t)
    } catch (e) {
      if (conSong.current) setLoi(cauLoi(e) || CHU.loiTaiTrangThai)
    }
  }, [])

  useEffect(() => {
    conSong.current = true
    return () => { conSong.current = false }
  }, [])
  useEffect(() => { if (codex.bat) nap() }, [codex.bat, nap])

  // Vòng hỏi: chỉ chạy khi đang có mã chờ xác nhận.
  const coPhien = Boolean(phien)
  useEffect(() => {
    if (!coPhien) return undefined
    let dung = false
    const id = setInterval(async () => {
      try {
        const { trang_thai: ttHoi } = await api.hoiDangNhapCodex()
        if (dung) return
        if (ttHoi === 'da_dang_nhap') {
          setPhien(null); setThongBao(null)
          await nap(); await lamMoiCodex()
        } else if (ttHoi === 'het_han' || ttHoi === 'chua_bat_dau') {
          setPhien(null)
          setThongBao(ttHoi === 'het_han' ? CHU.hetHan : CHU.chuaBatDau)
        }
      } catch (e) {
        if (dung) return
        setPhien(null); setLoi(cauLoi(e))
      }
    }, CHU_KY_HOI_MS)
    return () => { dung = true; clearInterval(id) }
  }, [coPhien, nap])

  // Đếm ngược theo MỐC tuyệt đối, không trừ dần: tab bị trình duyệt làm chậm vẫn đúng.
  const hetHanLuc = phien?.hetHanLuc
  useEffect(() => {
    if (!hetHanLuc) return undefined
    const tinh = () => setConGiay(Math.max(0, Math.ceil((hetHanLuc - Date.now()) / 1000)))
    tinh()
    const id = setInterval(tinh, 1000)
    return () => clearInterval(id)
  }, [hetHanLuc])

  if (!codex.bat) return null

  async function batDau() {
    setDangLam(true); setLoi(null); setThongBao(null); setDaChep(false)
    try {
      const r = await api.batDauDangNhapCodex()
      setPhien({ ma: r.ma, link: r.link, hetHanLuc: Date.now() + r.het_han_giay * 1000 })
    } catch (e) { setLoi(cauLoi(e)) }
    finally { setDangLam(false) }
  }

  async function dangXuat() {
    if (!window.confirm(CHU.xacNhanDangXuat)) return
    setDangLam(true); setLoi(null)
    try {
      await api.dangXuatCodex()
      await nap(); await lamMoiCodex()
    } catch (e) { setLoi(cauLoi(e)) }
    finally { setDangLam(false) }
  }

  async function saoChep() {
    try { await navigator.clipboard.writeText(phien.ma); setDaChep(true) } catch { /* trình duyệt chặn */ }
  }

  return (
    <section className="quan-tri dang-nhap-codex">
      <h2>{CHU.tieuDe}</h2>
      <p className="ghi-chu">{CHU.canhBao}</p>
      {loi && <Alert sac="loi" tieuDe={CHU.tieuDeLoi} onDong={() => setLoi(null)}>{loi}</Alert>}
      {thongBao && <Alert sac="canh" onDong={() => setThongBao(null)}>{thongBao}</Alert>}

      {phien ? (
        <div className="ma-codex">
          <p>{CHU.huongDan}</p>
          <p className="ma-codex-so" aria-label="Mã đăng nhập">{phien.ma}</p>
          <div className="hang-cong-cu">
            <Button kieu="phu" onClick={saoChep}>{daChep ? CHU.daSaoChep : CHU.nutSaoChep}</Button>
            <a className="nut nut-chinh" href={phien.link} target="_blank" rel="noopener noreferrer">
              {CHU.moTrang}
            </a>
          </div>
          <p className="ghi-chu">
            {CHU.conLai(Math.floor(conGiay / 60), conGiay % 60)} · {CHU.dangCho}
          </p>
        </div>
      ) : tt?.da_dang_nhap ? (
        <div>
          <p>
            <b>{CHU.daDangNhap}</b>: {tt.email}
            {tt.goi && <> · {CHU.goi} {tt.goi}</>}
          </p>
          <Button kieu="phu" disabled={dangLam} onClick={dangXuat}>{CHU.nutDangXuat}</Button>
        </div>
      ) : (
        <Button kieu="chinh" dangChay={dangLam} onClick={batDau}>
          {dangLam ? CHU.dangMo : CHU.nutDangNhap}
        </Button>
      )}
    </section>
  )
}

function cauLoi(e) {
  return String(e?.cauNguoiDoc ?? e?.message ?? e).replace(/^\d+:\s*/, '')
}
