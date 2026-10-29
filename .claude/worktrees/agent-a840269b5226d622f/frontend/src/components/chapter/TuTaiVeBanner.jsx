import { boTuTaiVe, useTuTaiVe } from '../../lib/tu-tai-ve.js'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'

// wording: BA review — các dòng trạng thái "Tự tải về khi xong" trên màn chapter
const TIEU_DE_CHO = 'Đang dịch — xong sẽ tự tải về'
const TIEU_DE_XUAT = 'Đang đóng gói để tải về…'
const GHI_CHU_CHO = 'Giữ tab này mở. Bạn vẫn xem và sửa tay các trang đã xong trong lúc chờ.'

/** Trạng thái việc "tự xuất + tải về" của chapter đang mở. Không có tác vụ ⇒ không vẽ gì. */
export default function TuTaiVeBanner({ projectId }) {
  const tv = useTuTaiVe(projectId)
  if (!tv) return null

  if (tv.giaiDoan === 'cho' || tv.giaiDoan === 'xuat') {
    const t = tv.tien
    return (
      <Alert sac="tin" tieuDe={tv.giaiDoan === 'xuat' ? TIEU_DE_XUAT : TIEU_DE_CHO}>
        <p role="status">
          {t.tong > 0 && <>Đã xong {t.xong}/{t.tong} trang{t.hong > 0 && ` · ${t.hong} trang không nhận diện được`}. </>}
          {GHI_CHU_CHO}
        </p>
      </Alert>
    )
  }

  if (tv.giaiDoan === 'loi') {
    return (
      <Alert sac="loi" tieuDe="Không tự tải về được">
        <p>{tv.loi}</p>
        <Button kieu="ghost" onClick={() => boTuTaiVe(projectId)}>Đóng</Button>
      </Alert>
    )
  }

  const k = tv.ketQua
  return (
    <Alert sac={k.hong > 0 ? 'canh' : 'ok'}
           tieuDe={k.hong > 0 ? 'Xong, nhưng thiếu trang' : 'Xong'}>
      <p>
        Dịch xong {k.xong}/{k.tong} trang
        {k.hong > 0 && ` · ${k.hong} trang không nhận diện được chữ nên không có trong file`}
        {k.boQua > 0 && ` · bỏ qua ${k.boQua} mục trong gói không phải ảnh`}.
      </p>
      {k.taiVe
        ? <p>File đã tải về máy bạn.</p>
        : <p>Chưa tải về được — mở tab “Xuất” bên dưới để tự xuất.</p>}
      {/* P1 — im lặng khi sạch: không khẳng định "mọi thứ ổn" khi phép đo không chứng minh được. */}
      {k.soVungDangNgo > 0 && (
        <p>
          <b>{k.soVungDangNgo} vùng chữ</b> nên xem lại (đọc chưa chắc, tràn khung, hoặc bong
          bóng bị bỏ trống). File vẫn đã tải về — sửa tay trước khi dùng nếu cần.
        </p>
      )}
      <Button kieu="ghost" onClick={() => boTuTaiVe(projectId)}>Đóng</Button>
    </Alert>
  )
}
