import { useState } from 'react'
import * as api from '../../api.js'
import { MUC_DICH, NGON_NGU } from '../../lib/status-presentation.js'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import Dropzone from '../ui/Dropzone.jsx'
import { Input, Select } from '../ui/Field.jsx'

const MO_TA_MUC_DICH = {
  personal: 'Tự dịch để mình đọc, không đưa cho ai khác.',
  study: 'Học ngôn ngữ, làm bài tập, nghiên cứu dịch thuật.',
  other: 'Mục đích khác — bạn tự chịu trách nhiệm về bản quyền nội dung gốc.',
}

/** Vì sao nút bị khoá — trả về `null` khi form đã hợp lệ. Tách riêng để test được. */
export function lyDoChuaTaoDuoc({ ten, mucDich, files }) {
  if (!ten.trim()) return 'Cần đặt tên cho chapter.'
  if (!mucDich) return 'Cần chọn mục đích sử dụng — hệ thống không chọn hộ.'
  if (!files.length) return 'Cần chọn ít nhất một ảnh PNG hoặc JPG.'
  return null
}

/** Tạo chapter theo 3 khối: thông tin → chọn trang → bắt đầu. */
export default function ChapterCreateForm({ onXong }) {
  const [ten, setTen] = useState('')
  const [nguon, setNguon] = useState('en')
  const [mucDich, setMucDich] = useState('')
  const [files, setFiles] = useState([])
  const [dangChay, setDangChay] = useState(false)
  const [daXong, setDaXong] = useState(0)
  const [loi, setLoi] = useState(null)

  const lyDo = lyDoChuaTaoDuoc({ ten, mucDich, files })

  const batDau = async () => {
    if (lyDo || dangChay) return   // chặn cả double-click, không chỉ dựa vào nút mờ
    setDangChay(true); setLoi(null); setDaXong(0)
    try {
      const project = await api.taoProject({
        name: ten.trim(), source_lang: nguon, intended_use: mucDich,
      })
      // Tải tuần tự: mỗi trang vào hàng đợi rồi chạy AI, dồn một lúc chỉ làm máy chủ nghẹn.
      for (let i = 0; i < files.length; i++) {
        await api.taiTrangLen(project.id, files[i])
        setDaXong(i + 1)
      }
      onXong(project.id)
    } catch (e) {
      // Giữ nguyên tên chapter và danh sách file: bắt người dùng chọn lại từ đầu vì lỗi mạng
      // là cách nhanh nhất để họ bỏ cuộc.
      setLoi(e.message)
    } finally {
      setDangChay(false)
    }
  }

  return (
    <section className="the-lon" aria-labelledby="tieu-de-tao">
      <header className="the-dau">
        <h2 id="tieu-de-tao">Tạo chapter mới</h2>
        <p>Tải ảnh PNG hoặc JPG. Hệ thống sẽ nhận diện chữ, dịch sang tiếng Việt và tự căn vào
           bong bóng.</p>
      </header>

      <fieldset className="khoi" disabled={dangChay}>
        <legend>1 · Thông tin chapter</legend>
        <Input
          nhan="Tên chapter" batBuoc
          value={ten} onChange={(e) => setTen(e.target.value)}
          placeholder="ví dụ: One Piece — chương 1"
        />
        <div className="hang-doi">
          <Select nhan="Ngôn ngữ gốc" batBuoc value={nguon}
                  onChange={(e) => setNguon(e.target.value)}>
            {Object.entries(NGON_NGU).map(([ma, ten_nn]) => (
              <option key={ma} value={ma}>{ten_nn}</option>
            ))}
          </Select>
          <Select
            nhan="Mục đích sử dụng" batBuoc value={mucDich}
            moTa={mucDich
              ? MO_TA_MUC_DICH[mucDich]
              : 'Bạn tự khai — hệ thống không chọn hộ. Khai báo gắn với chapter và không sửa được.'}
            onChange={(e) => setMucDich(e.target.value)}
          >
            <option value="" disabled>— hãy chọn —</option>
            {Object.entries(MUC_DICH).map(([ma, ten_md]) => (
              <option key={ma} value={ma}>{ten_md}</option>
            ))}
          </Select>
        </div>
      </fieldset>

      <fieldset className="khoi">
        <legend>2 · Chọn trang truyện</legend>
        <Dropzone files={files} onDoi={setFiles} tatCa={dangChay} />
      </fieldset>

      <fieldset className="khoi khoi-cuoi">
        <legend>3 · Bắt đầu</legend>
        <Button
          kieu="chinh" id="nut-tao" onClick={batDau}
          dangChay={dangChay} lyDoKhoa={lyDo}
        >
          {dangChay ? `Đang tải lên ${daXong}/${files.length}…` : 'Tạo chapter & bắt đầu dịch'}
        </Button>
        {dangChay && (
          <div className="thanh-tien" aria-hidden="true">
            <div className="thanh-tien-trong"
                 style={{ width: `${Math.round((daXong / Math.max(files.length, 1)) * 100)}%` }} />
          </div>
        )}
        <p className="ghi-chu">
          Xử lý chạy nền. Bạn có thể rời trang và mở lại chapter để xem tiến độ.
        </p>
        {loi && <Alert sac="loi" tieuDe="Không tạo được chapter">{loi}</Alert>}
      </fieldset>
    </section>
  )
}
