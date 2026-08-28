import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../api.js'

const TRANG_THAI_ME = {
  queued: { chu: 'Đang xếp hàng', lop: 'cho' },
  running: { chu: 'Đang chạy', lop: 'cho' },
  completed: { chu: 'Xong tất cả', lop: 'ok' },
  partial_failed: { chu: 'Xong một phần — còn trang hỏng', lop: 'canh' },
  blocked_quota: { chu: 'Dừng vì hết lượt gọi', lop: 'canh' },
  failed: { chu: 'Hỏng', lop: 'loi' },
  cancelled: { chu: 'Đã dừng', lop: 'cho' },
}

const TRANG_THAI_MUC = {
  pending: { chu: 'Chờ tới lượt', lop: 'cho' },
  running: { chu: 'Đang chạy', lop: 'cho' },
  completed: { chu: 'Xong', lop: 'ok' },
  failed: { chu: 'Hỏng', lop: 'loi' },
  blocked_quota: { chu: 'Hết lượt gọi', lop: 'canh' },
  skipped: { chu: 'Bỏ qua', lop: 'cho' },
}

const LY_DO_BO_QUA = {
  da_xong: 'trang này đã chèn chữ xong từ trước',
  cancelled: 'mẻ đã bị dừng trước khi tới lượt',
  dang_chay: 'trang đang chạy dở bởi việc khác',
}

const DANG_CHAY = (tt) => tt === 'queued' || tt === 'running'
const CAN_CHAY_LAI = (tt) => tt === 'failed' || tt === 'blocked_quota'

function batDauTuBuoc(giay) {
  if (giay == null) return '—'
  const p = Math.floor(giay / 60)
  return p > 0 ? `${p} phút ${giay % 60} giây` : `${giay} giây`
}

/** Chạy cả chapter bằng một mẻ: chọn cách dịch → theo dõi → chạy lại trang hỏng. */
export default function BatchPanel({ projectId, soTrang }) {
  const [cauHinh, setCauHinh] = useState(null)
  const [me, setMe] = useState(null)
  const [muc, setMuc] = useState([])
  const [engine, setEngine] = useState('google_fast')
  const [dangBan, setDangBan] = useState(false)
  const [loi, setLoi] = useState(null)
  const [bayGio, setBayGio] = useState(() => Date.now())
  const meIdRef = useRef(null)

  useEffect(() => {
    api.layCauHinhMe().then(setCauHinh).catch((e) => setLoi(e.message))
  }, [])

  // Tải lại trang KHÔNG được làm mất dấu mẻ đang chạy — hỏi lại máy chủ mẻ gần nhất.
  useEffect(() => {
    api.layDanhSachMe(projectId)
      .then(({ runs }) => {
        if (runs.length) {
          setMe(runs[0])
          meIdRef.current = runs[0].id
        }
      })
      .catch((e) => setLoi(e.message))
  }, [projectId])

  const napMuc = useCallback(async (id) => {
    const { items } = await api.layMucCuaMe(id)
    setMuc(items)
  }, [])

  useEffect(() => {
    if (me?.id) napMuc(me.id).catch((e) => setLoi(e.message))
  }, [me?.id, napMuc])

  // Nhịp theo dõi: chỉ hỏi máy chủ khi mẻ CÒN chạy, dừng hẳn khi mẻ kết thúc.
  useEffect(() => {
    if (!me?.id || !DANG_CHAY(me.status)) return undefined
    const t = setInterval(async () => {
      try {
        const moi = await api.layMe(me.id)
        setMe(moi)
        await napMuc(me.id)
        setBayGio(Date.now())
      } catch (e) {
        setLoi(e.message)
      }
    }, 2000)
    return () => clearInterval(t)
  }, [me?.id, me?.status, napMuc])

  const chay = async (viec) => {
    setDangBan(true)
    setLoi(null)
    try {
      await viec()
      const id = meIdRef.current
      if (id) {
        setMe(await api.layMe(id))
        await napMuc(id)
      }
    } catch (e) {
      setLoi(e.message)
    } finally {
      setDangBan(false)
    }
  }

  const batDau = () =>
    chay(async () => {
      const { batch_run_id } = await api.taoMe(projectId, { engine })
      meIdRef.current = batch_run_id
    })

  const chayLai = (itemIds) => chay(() => api.chayLaiMe(meIdRef.current, itemIds))
  const dung = () => chay(() => api.huyMe(meIdRef.current))

  const llmDung = cauHinh?.llm_configured === true
  const dangChayMe = me != null && DANG_CHAY(me.status)
  const soCanChayLai = muc.filter((m) => CAN_CHAY_LAI(m.status)).length
  const dangLam = muc.find((m) => m.status === 'running')
  const nhan = me ? TRANG_THAI_ME[me.status] ?? { chu: me.status, lop: 'cho' } : null

  const troi = me?.started_at
    ? Math.max(0, Math.round(
        ((me.finished_at ? Date.parse(me.finished_at) : bayGio) - Date.parse(me.started_at)) / 1000,
      ))
    : null

  // Thanh tiến độ đo bằng số trang ĐÃ XONG, nên còn trang hỏng/bị chặn thì không bao giờ đầy.
  const phanTram = me && me.total_pages > 0
    ? Math.round((me.completed_pages / me.total_pages) * 100)
    : 0

  return (
    <section className="bang-me">
      <h2>Chạy cả chapter</h2>

      {!me && (
        <p className="ghi-chu">
          Chạy lần lượt tất cả các trang qua toàn bộ các bước. Mỗi trang tiếp tục từ đúng bước nó
          đang dừng — trang đã xong sẽ được bỏ qua chứ không làm lại.
        </p>
      )}

      <label className="nhan">
        Cách dịch
        <select value={engine} onChange={(e) => setEngine(e.target.value)} disabled={dangBan || dangChayMe}>
          <option value="google_fast">Dịch nhanh (miễn phí)</option>
          <option value="llm_context" disabled={!llmDung}>
            Dịch theo ngữ cảnh {llmDung ? '' : '— chưa cấu hình khoá dịch'}
          </option>
        </select>
      </label>

      <ul className="tom-tat-xuat">
        <li><b>{soTrang}</b> trang sẽ được chụp vào mẻ ngay lúc bấm chạy</li>
        <li className="ghi-chu">
          Trang tải lên <b>sau</b> lúc bấm sẽ không lẫn vào mẻ này.
        </li>
        {engine === 'llm_context' && cauHinh && (
          cauHinh.llm_project_rpm > 0 ? (
            <li>
              Giới hạn gọi: <b>{cauHinh.llm_project_rpm}</b> lượt/phút cho cả dự án dịch —
              vượt thì mẻ chờ, không đập thêm vào nhà cung cấp.
            </li>
          ) : (
            <li className="canh-bao">
              Chưa đặt giới hạn lượt gọi (<code>LLM_PROJECT_RPM=0</code>) — mẻ sẽ gọi thẳng, dễ hết lượt.
            </li>
          )
        )}
        {cauHinh && (
          <li className="ghi-chu">
            Chạy {cauHinh.batch_max_concurrent_pages} trang một lúc · lỗi tạm thời thử lại tối đa{' '}
            {cauHinh.batch_max_retries} lần
          </li>
        )}
      </ul>

      {!dangChayMe && (
        <button className="chinh" onClick={batDau} disabled={dangBan || soTrang === 0}>
          {me ? 'Chạy mẻ mới' : 'Chạy cả chapter'}
        </button>
      )}
      {soTrang === 0 && <p className="ghi-chu">Chapter chưa có trang nào.</p>}

      {me && (
        <div className="ket-qua-xuat">
          <div className="hang-tieu-de">
            <span className={`badge ${nhan.lop}`}>{nhan.chu}</span>
            <span className="ghi-chu">Thời gian: {batDauTuBuoc(troi)}</span>
          </div>

          <div className="thanh-tien">
            <div className="thanh-tien-trong" style={{ width: `${phanTram}%` }} />
          </div>
          <p className="ghi-chu">
            <b>{me.completed_pages}</b>/{me.total_pages} trang xong
            {me.failed_pages > 0 && <> · <b className="do">{me.failed_pages} hỏng</b></>}
            {me.blocked_pages > 0 && <> · <b className="vang">{me.blocked_pages} hết lượt gọi</b></>}
            {dangLam && <> · đang làm trang {dangLam.page_order}</>}
          </p>

          <div className="hang nut">
            {soCanChayLai > 0 && (
              <button onClick={() => chayLai(null)} disabled={dangBan}>
                Chạy lại {soCanChayLai} trang hỏng/bị chặn
              </button>
            )}
            {dangChayMe && (
              <button onClick={dung} disabled={dangBan}>Dừng mẻ</button>
            )}
          </div>
          {dangChayMe && (
            <p className="ghi-chu">
              Dừng mẻ sẽ <b>không đẩy thêm trang mới</b>; trang đang chạy vẫn chạy cho xong để
              không để lại kết quả dở dang.
            </p>
          )}

          <table className="bang-muc">
            <thead>
              <tr><th>Trang</th><th>Trạng thái</th><th>Thử lại</th><th>Ghi chú</th><th /></tr>
            </thead>
            <tbody>
              {muc.map((m) => {
                const n = TRANG_THAI_MUC[m.status] ?? { chu: m.status, lop: 'cho' }
                return (
                  <tr key={m.id}>
                    <td>{m.page_order}</td>
                    <td><span className={`badge ${n.lop}`}>{n.chu}</span></td>
                    <td>{m.retry_count > 0 ? `${m.retry_count} lần` : '—'}</td>
                    <td className="o-loi">
                      {m.status === 'skipped'
                        ? LY_DO_BO_QUA[m.error_code] ?? m.error_code ?? '—'
                        : m.error_message || (m.error_code === 'dang_chay' ? 'đang chạy bởi việc khác' : '—')}
                    </td>
                    <td>
                      {CAN_CHAY_LAI(m.status) && (
                        <button onClick={() => chayLai([m.id])} disabled={dangBan}>Chạy lại</button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {loi && <div className="bang-loi">Lỗi: {loi}</div>}
    </section>
  )
}
