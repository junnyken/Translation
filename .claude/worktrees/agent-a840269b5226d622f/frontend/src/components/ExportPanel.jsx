import { useCallback, useEffect, useState } from 'react'
import * as api from '../api.js'
import ExportWarningModal from './ExportWarningModal.jsx'
import Alert from './ui/Alert.jsx'
import Button from './ui/Button.jsx'
import Icon from './ui/Icon.jsx'
import Skeleton from './ui/Skeleton.jsx'

// wording: BA review — nhãn mới của khung xuất (mockup-v2/xuat)
const NHAN_XEM_TRUOC = 'Xem trước'
const NHAN_DINH_DANG = 'Định dạng'
const NHAN_CHON_DINH_DANG = 'Chọn định dạng file xuất'
const NHAN_DA_XUAT = 'Đã xuất'
const ICON_DINH_DANG = { cbz: 'book-open', zip: 'file-archive', png_single: 'image', psd: 'layers' }

const DINH_DANG = [
  {
    ma: 'cbz',
    ten: 'CBZ — cho ứng dụng đọc truyện',
    goiY: 'Đọc bằng Tachiyomi, Perfect Viewer, YACReader… Windows và macOS KHÔNG mở sẵn đuôi .cbz — '
      + 'bấm đúp sẽ không ra gì.',
  },
  {
    ma: 'zip',
    ten: 'ZIP — mở được ngay trên mọi máy',
    goiY: 'Cùng nội dung với CBZ, chỉ khác đuôi .zip. Bấm đúp là xem được ảnh từng trang, không cần '
      + 'cài thêm gì.',
  },
  { ma: 'png_single', ten: 'PNG — mỗi trang một ảnh', goiY: 'Lưu thành nhiều ảnh rời trên máy chủ; không tải một lần được' },
  {
    // E78 — cho nhóm dịch chỉnh tiếp. Lớp chữ là ẢNH, chưa phải chữ gõ lại được: nói trước để
    // người dùng không mở Photoshop rồi tưởng file hỏng vì không bấm vào sửa chữ được.
    ma: 'psd',
    ten: 'PSD — nhiều lớp, mở bằng Photoshop/Photopea',
    goiY: 'Một file .zip, mỗi trang một file .psd gồm: ảnh gốc (đang ẩn), ảnh đã xoá chữ và mỗi '
      + 'bong bóng chữ một lớp riêng. Chữ là lớp ảnh — dời, ẩn, xoá được, nhưng chưa gõ sửa chữ được.',
  },
]

/** Bảng xuất chapter: xem trước cảnh báo → chọn định dạng → theo dõi → tải về. */
export default function ExportPanel({
  projectId, tenProject, nhatQuan, onRaSoat, chuKyTrang,
}) {
  const [xemTruoc, setXemTruoc] = useState(null)
  const [canhBao, setCanhBao] = useState(null)
  const [hienCanhBao, setHienCanhBao] = useState(false)
  const [dinhDang, setDinhDang] = useState('cbz')
  const [job, setJob] = useState(null)
  const [dangChay, setDangChay] = useState(false)
  const [dangTai, setDangTai] = useState(false)
  const [loi, setLoi] = useState(null)

  // `chuKyTrang` là chuỗi trạng thái của mọi trang, do App truyền xuống. Nó nằm trong danh
  // sách phụ thuộc CÓ CHỦ Ý: `ChapterProgress` nạp lại chapter mỗi 4 giây khi còn trang đang
  // chạy, nên `project.pages` cập nhật — nhưng bảng này chỉ phụ thuộc `projectId` nên con số
  // của nó ĐÓNG BĂNG ở lần nạp đầu.
  //
  // Hậu quả đo được trên bản chạy 05/09: người dùng mở chapter lúc pipeline còn chạy, bảng ghi
  // "0 / 2 trang sẽ được xuất" và nút xuất bị khoá; pipeline xong, badge trang đổi thành "Đã
  // căn chữ" — mà bảng xuất vẫn 0/2 và nút vẫn khoá cho tới khi tải lại cả trang. API thì
  // không sai: đo cùng lúc, `export-preview` trả đúng 2/2.
  const nap = useCallback(() => {
    setLoi(null)
    api.xemTruocXuat(projectId).then(setXemTruoc).catch((e) => setLoi(e.message))
    api.layCanhBaoXuat(projectId).then(setCanhBao).catch((e) => setLoi(e.message))
  }, [projectId, chuKyTrang])

  useEffect(() => { nap() }, [nap])

  /** Bấm "Xuất": chapter chưa xác nhận bản quyền lần nào thì hỏi trước, đã xác nhận thì đi thẳng. */
  const bamXuat = () => {
    if (canhBao && !canhBao.acknowledged) return setHienCanhBao(true)
    xuat(false)
  }

  const xuat = async (vuaTick, dinhDangDung = dinhDang) => {
    setHienCanhBao(false)
    setDangChay(true)
    setLoi(null)
    setJob(null)
    try {
      const { job_id } = await api.xuatChapter(projectId, dinhDangDung)
      // Ghi lại việc đã đọc cảnh báo NGAY khi có mã việc xuất, trước lúc tải file về.
      // Không để việc ghi nhận làm hỏng lần xuất: file vẫn phải ra.
      if (vuaTick) {
        try {
          await api.xacNhanXuat(job_id, true)
        } catch (e) {
          setLoi(`Không ghi được xác nhận: ${e.message}`)
        }
      }
      const xong = await api.choXuatXong(job_id, { onTien: setJob })
      setJob(xong)
      nap()
    } catch (e) {
      setLoi(e.message)
    } finally {
      setDangChay(false)
    }
  }

  if (!xemTruoc) {
    // `id` PHẢI có ở CẢ hai nhánh return: nút "Xuất chapter" ở bảng tóm tắt cuộn tới đúng id
    // này. Thiếu ở nhánh đang tải thì bấm lúc chưa nạp xong sẽ không đi đâu cả.
    return (
      <section id="bang-xuat" className="bang-xuat">
        {loi
          ? <Alert sac="loi">Lỗi: {loi}</Alert>
          : (
            <>
              <p className="ghi-chu" aria-live="polite">Đang xem trước…</p>
              <Skeleton kieu="khoi" cao={160} />
            </>
          )}
      </section>
    )
  }

  const khongCoGiDeXuat = xemTruoc.page_count === 0
  const chon = DINH_DANG.find((d) => d.ma === dinhDang)
  const khongCanhBao = xemTruoc.skipped_page_count === 0 && xemTruoc.overflow_warning_count === 0
    && (xemTruoc.font_missing_count ?? 0) === 0 && (canhBao?.needs_manual_count ?? 0) === 0

  return (
    <section id="bang-xuat" className="bang-xuat" aria-labelledby="tieu-de-bang-xuat">
      <h2 id="tieu-de-bang-xuat" className="an-di">Xuất chapter{tenProject ? ` — ${tenProject}` : ''}</h2>

      <div className="luoi-xuat">
        <div className="cot-xuat-trai">
          <section className="the-man" aria-labelledby="tieu-de-xem-truoc">
            <h3 id="tieu-de-xem-truoc">{NHAN_XEM_TRUOC}</h3>
            <ul className="tom-tat-xuat x-canh-bao">
              <li className="xc-ok">
                <Icon ten="circle-check" co={20} />
                <span><b className="t-so">{xemTruoc.page_count}</b> / {xemTruoc.total_page_count} trang sẽ được xuất</span>
              </li>
              {xemTruoc.skipped_page_count > 0 && (
                <li className="xc-canh">
                  <Icon ten="triangle-alert" co={20} />
                  <span><b className="t-so">{xemTruoc.skipped_page_count}</b> trang sẽ bị <b>bỏ qua</b> vì chưa chèn chữ xong</span>
                </li>
              )}
              {xemTruoc.overflow_warning_count > 0 && (
                <li className="xc-canh">
                  <Icon ten="triangle-alert" co={20} />
                  <span><b className="t-so">{xemTruoc.overflow_warning_count}</b> vùng còn <b>tràn khung</b> — xuất vẫn được,
                  nhưng nên sửa tay trước cho đẹp</span>
                </li>
              )}
              {(canhBao?.needs_manual_count ?? 0) > 0 && (
                <li className="xc-loi">
                  <Icon ten="circle-x" co={20} />
                  <span><b className="t-so">{canhBao.needs_manual_count}</b> bong bóng sẽ <b>trống</b> vì chưa đọc được chữ gốc</span>
                </li>
              )}
              {(xemTruoc.font_missing_count ?? 0) > 0 && (
                <li className="xc-loi">
                  <Icon ten="circle-x" co={20} />
                  <span><b className="t-so">{xemTruoc.font_missing_count}</b> bong bóng sẽ <b>trống</b> vì font không có ký tự
                  trong bản dịch — sửa lại chữ ở vùng đó rồi căn lại</span>
                </li>
              )}
              {khongCanhBao && (
                <li className="on xc-ok"><Icon ten="circle-check" co={20} /><span>Không có cảnh báo nào.</span></li>
              )}
            </ul>
          </section>

          <section className="the-man" aria-labelledby="tieu-de-dinh-dang">
            <h3 id="tieu-de-dinh-dang">{NHAN_DINH_DANG}</h3>
            <fieldset className="nhom-dinh-dang" disabled={dangChay}>
              <legend className="an-di">{NHAN_CHON_DINH_DANG}</legend>
              <div className="luoi-dinh-dang">
                {DINH_DANG.map((d) => (
                  <label key={d.ma} className="the-chon">
                    <input
                      type="radio" name="dinh-dang-xuat" value={d.ma}
                      checked={dinhDang === d.ma} onChange={() => setDinhDang(d.ma)}
                    />
                    <span>
                      <b><Icon ten={ICON_DINH_DANG[d.ma]} /> {d.ten}</b>
                      <span className="d">{d.goiY}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          </section>
        </div>

        <aside className="cot-xuat-phai" aria-label="Xuất và tải về">
          <section className="the-man khoi-hanh-dong">
            <h3>Xuất chapter</h3>
            <p className="ghi-chu">Định dạng: <b>{chon.ma === 'png_single' ? 'PNG' : chon.ma.toUpperCase()}</b> · {xemTruoc.page_count} trang</p>
            <Button kieu="chinh" icon={dangChay ? undefined : 'package'} className="rong-het" onClick={bamXuat} dangChay={dangChay} disabled={khongCoGiDeXuat}>
              {dangChay ? 'Đang xuất…' : 'Xuất chapter'}
            </Button>
            {canhBao && !canhBao.acknowledged && (
              <p className="ghi-chu">Lần đầu xuất chapter này, bạn sẽ được nhắc về bản quyền.</p>
            )}
            {canhBao?.acknowledged && (
              <p className="ghi-chu">
                Đã xác nhận trách nhiệm bản quyền cho chapter này
                {canhBao.acknowledged_at
                  ? ` lúc ${new Date(canhBao.acknowledged_at).toLocaleString('vi-VN')}`
                  : ''}
                .
              </p>
            )}
            {khongCoGiDeXuat && (
              <p className="ghi-chu">Chưa có trang nào chèn chữ xong nên chưa xuất được.</p>
            )}
          </section>

          {job && (
            <section className="the-man khoi-hanh-dong ket-qua-xuat" aria-live="polite" aria-label={NHAN_DA_XUAT}>
              <div
                className="thanh-tien" role="progressbar" aria-label="Tiến độ xuất"
                aria-valuemin={0} aria-valuemax={100}
                aria-valuenow={Math.round(((job.page_count || 0) / Math.max(xemTruoc.page_count, 1)) * 100)}
              >
                <div
                  className="thanh-tien-trong"
                  style={{
                    width: `${Math.round(((job.page_count || 0) / Math.max(xemTruoc.page_count, 1)) * 100)}%`,
                  }}
                />
              </div>
              <p className="ghi-chu t-so">
                {job.status === 'done'
                  ? `Đã xuất ${job.page_count}/${xemTruoc.page_count} trang.`
                  : `Đang xử lý… (${job.status})`}
              </p>

              {job.status === 'done' && job.error_log && (
                <Alert sac="canh">Xuất xong nhưng có cảnh báo: {job.error_log}</Alert>
              )}

              {job.status === 'done' && job.format !== 'png_single' && (
                // Nút, KHÔNG phải thẻ <a href>: trình duyệt tự tải link thì không gắn được mã
                // phiên, và từ slice B đường tải trả 401 — nút "Tải file về" bấm vào không ra gì.
                <Button
                  kieu="chinh" icon="download" className="rong-het" dangChay={dangTai}
                  onClick={async () => {
                    setDangTai(true); setLoi(null)
                    try {
                      await api.taiFileXuatVe(job.id, job.format)
                    } catch (e) {
                      setLoi(`Không tải được file: ${e.message}`)
                    } finally {
                      setDangTai(false)
                    }
                  }}
                >
                  {dangTai ? 'Đang tải…' : 'Tải file về'}
                </Button>
              )}
              {job.status === 'done' && job.format === 'cbz' && (
                <Alert sac="tin">
                  <p>
                    File <code>.cbz</code> thực chất là <b>file nén</b>. Máy không mở được thì đổi đuôi
                    <code> .cbz</code> thành <code>.zip</code> rồi giải nén như thường, hoặc xuất lại
                    bằng định dạng ZIP — cùng ảnh, cùng thứ tự trang.
                  </p>
                  <Button
                    dangChay={dangChay}
                    onClick={() => { setDinhDang('zip'); xuat(false, 'zip') }}
                  >
                    {dangChay ? 'Đang xuất…' : 'Xuất lại bằng ZIP'}
                  </Button>
                </Alert>
              )}
              {job.status === 'done' && job.format === 'png_single' && (
                <p className="ghi-chu">
                  Ảnh rời đã lưu trên máy chủ tại <code>{job.output_path}</code> — muốn tải một file
                  thì chọn định dạng CBZ hoặc ZIP.
                </p>
              )}
            </section>
          )}

          {loi && <Alert sac="loi">Lỗi: {loi}</Alert>}
        </aside>
      </div>

      {hienCanhBao && (
        <ExportWarningModal
          canhBao={canhBao}
          nhatQuan={nhatQuan}
          dinhDang={dinhDang}
          onHuy={() => setHienCanhBao(false)}
          onDongY={() => xuat(true)}
          onRaSoat={onRaSoat && (() => { setHienCanhBao(false); onRaSoat() })}
        />
      )}
    </section>
  )
}
