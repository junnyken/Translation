import { useState } from 'react'
import * as api from '../api.js'

const NGON_NGU = [
  { ma: 'en', ten: 'Tiếng Anh' },
  { ma: 'ja', ten: 'Tiếng Nhật (manga)' },
  { ma: 'zh', ten: 'Tiếng Trung' },
]
// Cố ý KHÔNG có lựa chọn nào được chọn sẵn: chọn hộ người dùng là suy đoán mục đích sử dụng
// thay họ, mà đây đúng là chỗ họ phải tự khai và tự chịu trách nhiệm.
const MUC_DICH = [
  { ma: 'personal', ten: 'Đọc cá nhân', mo_ta: 'Tự dịch để mình đọc, không đưa cho ai khác.' },
  { ma: 'study', ten: 'Học tập / nghiên cứu', mo_ta: 'Học ngôn ngữ, làm bài tập, nghiên cứu dịch thuật.' },
  { ma: 'other', ten: 'Khác', mo_ta: 'Mục đích khác — bạn tự chịu trách nhiệm về bản quyền nội dung gốc.' },
]

/** Tạo chapter mới rồi tải các trang lên — bước đầu tiên, trước đây chỉ làm được qua Swagger. */
export default function NewProjectPanel({ onXong }) {
  const [ten, setTen] = useState('')
  const [nguon, setNguon] = useState('en')
  const [mucDich, setMucDich] = useState('')
  const [files, setFiles] = useState([])
  const [dangChay, setDangChay] = useState(false)
  const [daXong, setDaXong] = useState(0)
  const [loi, setLoi] = useState(null)

  const batDau = async () => {
    // Chặn ngay ở đây nữa, không chỉ dựa vào nút mờ: nút mờ không phải là ràng buộc.
    if (!ten.trim() || !files.length || !mucDich) return
    setDangChay(true); setLoi(null); setDaXong(0)
    try {
      const project = await api.taoProject({
        name: ten.trim(), source_lang: nguon, intended_use: mucDich,
      })
      // Tải tuần tự chứ không song song: mỗi trang vào hàng đợi rồi chạy AI, dồn một lúc
      // chỉ làm máy chủ nghẹn chứ không nhanh hơn.
      for (let i = 0; i < files.length; i++) {
        await api.taiTrangLen(project.id, files[i])
        setDaXong(i + 1)
      }
      onXong(project.id)
    } catch (e) {
      setLoi(e.message)
    } finally {
      setDangChay(false)
    }
  }

  return (
    <section className="bang-tao">
      <h2>Dịch một chapter mới</h2>
      <p className="ghi-chu">
        Chọn các trang truyện (PNG/JPG), hệ thống sẽ tự nhận diện khung chữ → đọc chữ →
        xoá chữ gốc → dịch → chèn chữ Việt vào đúng bong bóng.
      </p>

      <label className="nhan">
        Tên chapter
        <input value={ten} onChange={(e) => setTen(e.target.value)} disabled={dangChay}
               placeholder="ví dụ: One Piece — chương 1" />
      </label>

      <div className="hang">
        <label className="nhan cot">
          Ngôn ngữ gốc
          <select value={nguon} onChange={(e) => setNguon(e.target.value)} disabled={dangChay}>
            {NGON_NGU.map((n) => <option key={n.ma} value={n.ma}>{n.ten}</option>)}
          </select>
        </label>
        <label className="nhan cot">
          Mục đích sử dụng
          <select value={mucDich} onChange={(e) => setMucDich(e.target.value)} disabled={dangChay}>
            <option value="" disabled>— hãy chọn —</option>
            {MUC_DICH.map((m) => <option key={m.ma} value={m.ma}>{m.ten}</option>)}
          </select>
        </label>
      </div>

      <p className="ghi-chu">
        {mucDich
          ? MUC_DICH.find((m) => m.ma === mucDich).mo_ta
          : 'Bạn cần tự khai mục đích sử dụng — hệ thống không chọn hộ. Khai báo này gắn với '
            + 'chapter và không sửa được về sau.'}
      </p>

      <label className="nhan">
        Các trang truyện
        <input type="file" accept="image/png,image/jpeg,image/webp" multiple
               disabled={dangChay}
               onChange={(e) => setFiles(Array.from(e.target.files))} />
      </label>
      {files.length > 0 && (
        <p className="ghi-chu">
          Đã chọn <b>{files.length}</b> trang. Thứ tự tải lên chính là thứ tự trang trong chapter —
          nên đặt tên file theo số thứ tự (001, 002…) cho chắc.
        </p>
      )}

      <button className="chinh" onClick={batDau}
              disabled={dangChay || !ten.trim() || !files.length || !mucDich}>
        {dangChay ? `Đang tải lên ${daXong}/${files.length}…` : 'Tạo & bắt đầu dịch'}
      </button>

      {dangChay && (
        <div className="thanh-tien" style={{ marginTop: 10 }}>
          <div className="thanh-tien-trong"
               style={{ width: `${Math.round((daXong / Math.max(files.length, 1)) * 100)}%` }} />
        </div>
      )}
      <p className="ghi-chu">
        Tải xong là máy bắt đầu chạy nền — mỗi trang mất khoảng <b>3–6 phút</b> (nhận diện, đọc chữ
        và xoá chữ đều là mô hình AI chạy trên CPU). Bạn cứ để tab mở rồi bấm tải lại xem tiến độ.
      </p>

      {loi && <div className="bang-loi">Lỗi: {loi}</div>}
    </section>
  )
}
