import { useCallback, useEffect, useState } from 'react'
import * as api from './api.js'
import BatchPanel from './components/BatchPanel.jsx'
import BboxOverlay from './components/BboxOverlay.jsx'
import ExportPanel from './components/ExportPanel.jsx'
import RegionPanel from './components/RegionPanel.jsx'
import RegionQualityBox from './components/RegionQualityBox.jsx'
import OrientationBox from './components/OrientationBox.jsx'
import OrientationSummaryCard from './components/OrientationSummaryCard.jsx'
import ChapterCreateForm from './components/chapter/ChapterCreateForm.jsx'
import ChapterProgress from './components/chapter/ChapterProgress.jsx'
import QualityPanel from './components/chapter/QualityPanel.jsx'
import ChapterRecentList from './components/chapter/ChapterRecentList.jsx'
import ChapterSummary from './components/chapter/ChapterSummary.jsx'
import ConsistencyPanel from './components/consistency/ConsistencyPanel.jsx'
import ConsistencyReviewQueue from './components/consistency/ConsistencyReviewQueue.jsx'
import GlossaryManager from './components/consistency/GlossaryManager.jsx'
import VoiceProfileManager from './components/consistency/VoiceProfileManager.jsx'
import ReviewToolbar from './components/chapter/ReviewToolbar.jsx'
import ManDangNhap from './components/auth/ManDangNhap.jsx'
import BangChuaCoChu from './components/auth/BangChuaCoChu.jsx'
import QuanTriNguoiDung from './components/auth/QuanTriNguoiDung.jsx'
import Alert from './components/ui/Alert.jsx'
import Button from './components/ui/Button.jsx'
import StatusBadge from './components/ui/StatusBadge.jsx'
import { tinhTienDoChapter } from './lib/chapter-progress.js'
import { LOC_HUONG_CHU, nhanHuongChu } from './lib/status-presentation.js'
import { MUC_DICH } from './lib/status-presentation.js'

/** Lấy id trang/chapter từ địa chỉ (#page=… hoặc #project=…) để chia sẻ link được.
 *  Giữ nguyên dạng địa chỉ cũ: link đã gửi cho nhau vẫn phải mở được. */
function docDiaChi() {
  const p = new URLSearchParams(window.location.hash.slice(1))
  return { pageId: p.get('page') || '', projectId: p.get('project') || '' }
}

const KHOA_NHO = 'translation:chapter-gan-day'

function docChapterDaLuu() {
  try { return JSON.parse(localStorage.getItem(KHOA_NHO) || '[]') } catch { return [] }
}
function luuChapter(id, ten) {
  try {
    const cu = docChapterDaLuu().filter((c) => c.id !== id)
    localStorage.setItem(KHOA_NHO, JSON.stringify([{ id, ten }, ...cu].slice(0, 12)))
  } catch { /* trình duyệt chặn lưu thì bỏ qua, không phải lỗi */ }
}

export default function App() {
  // Auth slice B — ba trạng thái, KHÔNG phải hai:
  //   undefined = đang hỏi máy chủ xem mã phiên trong máy còn dùng được không
  //   null      = chưa đăng nhập
  //   object    = đã đăng nhập
  // Gộp "đang hỏi" vào "chưa đăng nhập" sẽ nháy màn đăng nhập một cái mỗi lần tải lại trang,
  // kể cả khi phiên còn tốt.
  const [nguoiDung, setNguoiDung] = useState(undefined)
  const [{ pageId, projectId }, setDiaChi] = useState(docDiaChi)
  const [nhap, setNhap] = useState(projectId || pageId)
  const [project, setProject] = useState(null)
  const [canhBao, setCanhBao] = useState(null)
  const [chatLuongChapter, setChatLuongChapter] = useState(null)
  const [chatLuongTrang, setChatLuongTrang] = useState(null)
  const [chiTiet, setChiTiet] = useState(null)
  const [dangChon, setDangChon] = useState(null)
  const [hienCanhBaoAnh, setHienCanhBaoAnh] = useState(true)
  // E14: mặc định TẮT. Lớp phủ hình học là công cụ soi lỗi bố cục, không phải thứ cần thấy
  // mỗi lần mở trang — bật lên khi nghi chữ đặt lệch trong bong bóng.
  const [hienVungAnToan, setHienVungAnToan] = useState(false)
  const [vungAnToan, setVungAnToan] = useState({})
  // E15 — hướng chữ. `huongChu[regionId] === null` nghĩa là CHƯA kiểm (backend trả 404),
  // khác hẳn `{orientation:'unknown'}` nghĩa là đã kiểm mà không đủ bằng chứng.
  const [huongChu, setHuongChu] = useState({})
  const [tomTatHuong, setTomTatHuong] = useState(null)
  const [locHuong, setLocHuong] = useState('tat_ca')
  const [hienLuoiCot, setHienLuoiCot] = useState(false)
  const [dangBan, setDangBan] = useState(false)
  const [loi, setLoi] = useState(null)
  const [thongBao, setThongBao] = useState(null)
  // Đổi mỗi lần vẽ lại preview để trình duyệt không dùng ảnh cũ trong bộ nhớ đệm.
  const [phienBanAnh, setPhienBanAnh] = useState(0)
  // Ảnh trang phải tự tải bằng `fetch` (có mã phiên) rồi dựng `blob:` URL — `<img src>` không
  // gắn được header `Authorization`, nên từ slice B nó nhận 401 và màn sửa tay trắng trơn.
  const [anhBlob, setAnhBlob] = useState(null)
  const [loiAnh, setLoiAnh] = useState(null)
  const [ganDay, setGanDay] = useState(docChapterDaLuu)
  // E13 — thuật ngữ & rà soát nhất quán
  const [thuatNgu, setThuatNgu] = useState([])
  const [hoSoGiong, setHoSoGiong] = useState([])
  const [tomTatNQ, setTomTatNQ] = useState(null)
  const [viecNQ, setViecNQ] = useState([])
  const [dangQuet, setDangQuet] = useState(false)
  const [moHangDoi, setMoHangDoi] = useState(false)

  useEffect(() => {
    const doi = () => setDiaChi(docDiaChi())
    window.addEventListener('hashchange', doi)
    return () => window.removeEventListener('hashchange', doi)
  }, [])

  const napTrang = useCallback(async (id) => {
    setLoi(null)
    try {
      const data = await api.layChiTietTrang(id)
      setChiTiet(data)
      // Chấm chất lượng chạy sau bước căn chữ; trang chưa tới đó thì chưa có gì để hiện.
      api.layChatLuongTrang(id).then(setChatLuongTrang).catch(() => setChatLuongTrang(null))
      setPhienBanAnh((v) => v + 1)
      setDangChon((cu) => (data.regions.some((r) => r.id === cu) ? cu : data.regions[0]?.id ?? null))
    } catch (e) {
      setLoi(e.message)
    }
  }, [])

  useEffect(() => {
    if (pageId) napTrang(pageId)
    else setChiTiet(null)
  }, [pageId, napTrang])

  /** Nạp dữ liệu E13. Lỗi ở đây KHÔNG được chặn cả màn hình — rà soát nhất quán là lớp thêm,
   *  thiếu nó thì các bước dịch/căn chữ/xuất vẫn phải dùng được bình thường. */
  const napNhatQuan = useCallback(async (id) => {
    try {
      const [tn, hs, tt, vc] = await Promise.all([
        api.layThuatNgu(id),
        api.layHoSoGiong(id),
        api.tomTatNhatQuan(id),
        api.layViecNhatQuan(id, '?status=open'),
      ])
      setThuatNgu(tn)
      setHoSoGiong(hs)
      setTomTatNQ(tt)
      setViecNQ(vc.items || [])
    } catch { /* chưa có gì thì thôi */ }
  }, [])

  const napProject = useCallback(async (id) => {
    const p = await api.layProject(id)
    setProject(p)
    luuChapter(p.id, p.name)
    setGanDay(docChapterDaLuu())
    try {
      setCanhBao(await api.layCanhBaoXuat(id))
      setChatLuongChapter(await api.layTomTatChatLuong(id))
    } catch { /* chapter chưa có gì để cảnh báo thì thôi, không phải lỗi chặn */ }
    await napNhatQuan(id)
    return p
  }, [napNhatQuan])

  // Trang chi tiết cũng cần biết mình thuộc chapter nào (để có breadcrumb + điều hướng trang).
  const idChapter = projectId || chiTiet?.page?.project_id || ''
  useEffect(() => {
    if (!idChapter) return setProject(null)
    napProject(idChapter).catch((e) => setLoi(e.message))
  }, [idChapter, napProject])

  // ---------- E13: thao tác thuật ngữ & rà soát ----------

  /** Bọc một thao tác E13: khoá giao diện, nạp lại, và ĐỂ LỖI HIỆN RA thay vì nuốt.
   *  Ném lại lỗi để form trong hộp thoại hiện được lỗi ngay tại chỗ nhập. */
  const chayNQ = async (viec, thongBaoXong) => {
    setDangBan(true)
    setLoi(null)
    try {
      const kq = await viec()
      await napNhatQuan(idChapter)
      if (thongBaoXong) setThongBao(thongBaoXong)
      return kq
    } catch (e) {
      setLoi(e.message)
      throw e
    } finally {
      setDangBan(false)
    }
  }

  const quetNhatQuan = async () => {
    setDangQuet(true)
    setLoi(null)
    setThongBao('Đang rà soát nhất quán…')
    try {
      const { job_id } = await api.quetNhatQuan(idChapter)
      await api.choJobXong(job_id)
      await napNhatQuan(idChapter)
      setThongBao('Đã rà soát xong.')
    } catch (e) {
      setLoi(e.message)
    } finally {
      setDangQuet(false)
    }
  }

  /** Áp một đề xuất. Sau khi áp, vùng đó được căn chữ lại — phải CHỜ việc đó xong rồi mới
   *  nạp lại, nếu không người dùng thấy trạng thái cũ và tưởng chưa ăn. */
  const apViec = async (taskId, ban) => {
    setDangBan(true)
    setLoi(null)
    setThongBao('Đang áp dụng và căn chữ lại…')
    try {
      const kq = await api.apViecNhatQuan(taskId, ban)
      if (kq.refit_job_id) await api.choJobXong(kq.refit_job_id)
      await napNhatQuan(idChapter)
      if (pageId) await napTrang(pageId)
      setThongBao('Đã áp dụng và căn chữ lại vùng đó.')
    } catch (e) {
      setLoi(e.message)
    } finally {
      setDangBan(false)
    }
  }

  const mo = () => {
    const id = nhap.trim()
    if (!id) return
    // Đoán: mở như một chapter trước; không phải thì thử mở như một trang.
    api.layProject(id)
      .then(() => { window.location.hash = `project=${id}` })
      .catch(() => { window.location.hash = `page=${id}` })
  }

  /** Chạy một thao tác nền rồi nạp lại dữ liệu — khoá giao diện trong lúc chạy.
   *
   * Nói rõ đang CHỜ TỚI LƯỢT hay ĐANG CHẠY: worker xử lý từng việc một, nên lúc bận thì việc
   * nằm trong hàng đợi cả phút. Chỉ hiện "Đang…" đứng im khiến người dùng tưởng máy treo.
   */
  const chay = async (moTa, viec) => {
    setDangBan(true)
    setLoi(null)
    setThongBao(`Đang ${moTa}…`)
    try {
      const { job_id } = await viec()
      await api.choJobXong(job_id, {
        onTien: (job) => setThongBao(
          job.status === 'queued'
            ? `Đang chờ tới lượt (${moTa}) — máy chủ đang bận việc khác…`
            : `Đang ${moTa}…`,
        ),
      })
      await napTrang(pageId)
      setThongBao(`Xong: ${moTa}.`)
    } catch (e) {
      setLoi(e.message)
      setThongBao(null)
    } finally {
      setDangBan(false)
    }
  }

  /** Ghi quyết định của người cho một vùng (E12). Không đụng tới dữ liệu dịch. */
  const quyetDinhVung = async (regionId, quyetDinh) => {
    setDangBan(true)
    setLoi(null)
    try {
      await api.ghiQuyetDinhVung(regionId, quyetDinh)
      setChatLuongTrang(await api.layChatLuongTrang(pageId))
      setThongBao(quyetDinh === 'skip'
        ? 'Đã ghi: bỏ qua vùng này. Dữ liệu vẫn được giữ nguyên.'
        : 'Đã ghi: giữ vùng này để dịch.')
    } catch (e) {
      setLoi(e.message)
    } finally {
      setDangBan(false)
    }
  }

  const luuVung = (regionId, thayDoi) =>
    chay('lưu và căn lại chữ', async () => {
      const kq = await api.suaVung(regionId, thayDoi)
      return { job_id: kq.refit_job_id }
    })

  const luuBbox = (regionId, bbox) =>
    chay('lưu khung chữ', async () => {
      const kq = await api.suaVung(regionId, {
        bbox: {
          x: Math.round(bbox.x), y: Math.round(bbox.y),
          w: Math.round(bbox.w), h: Math.round(bbox.h),
        },
      })
      return { job_id: kq.refit_job_id }
    })

  // Nạp cho cả trang khi mở, không đợi bật lớp phủ: "hình bong bóng" là một dữ kiện RIÊNG mà
  // người sửa cần thấy ngay ở bảng bên phải, còn công tắc chỉ để bật/tắt phần vẽ đè lên ảnh.
  useEffect(() => {
    if (!chiTiet?.regions?.length) return
    let huy = false
    api.layVungAnToan(chiTiet.regions.map((r) => r.id))
      .then((d) => { if (!huy) setVungAnToan(d) })
      .catch(() => { if (!huy) setVungAnToan({}) })
    return () => { huy = true }
  }, [chiTiet?.page?.id, phienBanAnh])

  // Nạp hướng chữ cho cả trang cùng lúc với vùng an toàn: người sửa cần thấy ngay, không phải
  // bật công tắc mới có.
  useEffect(() => {
    if (!chiTiet?.regions?.length) return
    let huy = false
    api.layHuongChu(chiTiet.regions.map((r) => r.id))
      .then((d) => { if (!huy) setHuongChu(d) })
      .catch(() => { if (!huy) setHuongChu({}) })
    api.tomTatHuongChu(chiTiet.page.id)
      .then((d) => { if (!huy) setTomTatHuong(d) })
      .catch(() => { if (!huy) setTomTatHuong(null) })
    return () => { huy = true }
  }, [chiTiet?.page?.id, phienBanAnh])

  const vungDangChon = chiTiet?.regions.find((r) => r.id === dangChon) ?? null
  const soTran = chiTiet?.regions.filter((r) => r.fit_status === 'overflow_warning').length ?? 0
  const soCanXem = chiTiet?.regions.filter(
    (r) => r.ocr_status === 'needs_manual' || r.status === 'low_confidence',
  ).length ?? 0
  const dsTrang = project?.pages ?? []
  const tienDo = tinhTienDoChapter(dsTrang, {
    soTran: canhBao?.overflow_warning_count, soCanDocLai: canhBao?.needs_manual_count,
    soThieuFont: canhBao?.font_missing_count,
  })
  useEffect(() => {
    let huy = false
    if (!api.docMaPhien()) { setNguoiDung(null); return undefined }
    api.toiLaAi()
      .then((n) => { if (!huy) setNguoiDung(n) })
      // Mã phiên còn trong máy nhưng máy chủ không nhận (hết hạn, bị thu hồi, đổi máy chủ) —
      // dọn luôn, để lần sau không phải chờ một lượt gọi thất bại nữa.
      .catch(() => { if (!huy) { api.xoaMaPhien(); setNguoiDung(null) } })
    return () => { huy = true }
  }, [])

  // Nạp ảnh preview mỗi khi đổi trang hoặc sau khi căn lại chữ. Thu hồi blob cũ để không rò
  // bộ nhớ: mỗi ảnh là 2MB, xem 30 trang là 60MB nằm lại trong tab.
  const duongDanAnh = chiTiet?.preview_url
  useEffect(() => {
    if (!duongDanAnh) { setAnhBlob(null); return undefined }
    let huy = false
    let url = null
    setLoiAnh(null)
    api.taiVeBlobUrl(`${api.API_BASE}${duongDanAnh}?v=${phienBanAnh}`)
      .then((u) => {
        if (huy) { URL.revokeObjectURL(u); return }
        url = u
        setAnhBlob(u)
      })
      .catch((e) => { if (!huy) setLoiAnh(e.message) })
    return () => {
      huy = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [duongDanAnh, phienBanAnh])

  const oTrangChu = !projectId && !pageId

  if (nguoiDung === undefined) {
    return <div className="app"><main className="than-trang"><p>Đang kiểm phiên đăng nhập…</p></main></div>
  }
  if (nguoiDung === null) {
    return (
      <div className="app">
        <main className="than-trang">
          <ManDangNhap onXong={setNguoiDung} />
        </main>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="dau-trang">
        <a className="hieu" href="#">
          <span className="hieu-dau">T</span>
          <span>
            <b>Translation</b>
            <small>Dịch truyện tranh sang tiếng Việt</small>
          </span>
        </a>

        <nav aria-label="Điều hướng chính" className="dieu-huong">
          <a href="#" className={oTrangChu ? 'dang-o' : ''}>Chapter</a>
          <a href="#" className="nut nut-phu" onClick={() => {
            document.getElementById('nut-tao')?.scrollIntoView({ block: 'center' })
          }}>Tạo chapter</a>
          <span className="tai-khoan">
            <span title={nguoiDung.email}>{nguoiDung.ten_hien || nguoiDung.email}</span>
            <button type="button" className="nut-chu" onClick={async () => {
              await api.dangXuat()
              setNguoiDung(null)
            }}>Đăng xuất</button>
          </span>
        </nav>

        <div className="o-tim">
          <label className="an-di" htmlFor="o-ma">Mã chapter hoặc mã trang</label>
          <input
            id="o-ma" value={nhap} onChange={(e) => setNhap(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && mo()}
            placeholder="Dán mã chapter hoặc mã trang…"
          />
          <Button kieu="phu" onClick={mo}>Mở</Button>
        </div>
      </header>

      <main className="than-trang">
        {/* Sau slice B, 401 ở đây nghĩa là PHIÊN HẾT HẠN giữa chừng, không phải thiếu khoá
            chung nữa. Hiện ô nhập khoá lúc này là chỉ sai đường cho người dùng. */}
        {loi && api.laLoiChuaDangNhap(loi)
          ? <Alert sac="canh" tieuDe="Phiên đăng nhập đã hết hạn">
              <p>Đăng nhập lại để tiếp tục. Việc đang làm dở không mất — nó nằm trên máy chủ.</p>
              <Button kieu="chinh" onClick={() => { api.xoaMaPhien(); setNguoiDung(null) }}>
                Đăng nhập lại
              </Button>
            </Alert>
          : loi && <Alert sac="loi" tieuDe="Có lỗi" onDong={() => setLoi(null)}>{loi}</Alert>}
        {thongBao && <Alert sac="tin" onDong={() => setThongBao(null)}>{thongBao}</Alert>}

        {oTrangChu && (
          <>
            {/* Danh bạ tài khoản chỉ hiện với quản trị. Máy chủ cũng chặn (404 với người
                thường), nhưng hiện một mục chắc chắn báo lỗi là thiết kế tồi. */}
            {nguoiDung.la_quan_tri && <QuanTriNguoiDung toi={nguoiDung} />}

            <div className="tieu-de-man">
              <h1>Dịch truyện tranh</h1>
              <p>
                Tải ảnh PNG hoặc JPG. Hệ thống sẽ nhận diện chữ, dịch sang tiếng Việt và tự căn
                vào bong bóng — rồi bạn rà soát lại trước khi xuất.
              </p>
            </div>
            <div className="luoi-2-cot">
              <ChapterCreateForm onXong={(id) => { window.location.hash = `project=${id}` }} />
              <ChapterRecentList
                danhSach={ganDay}
                onTaoMoi={() => document.getElementById('nut-tao')?.scrollIntoView({ block: 'center' })}
              />
            </div>
          </>
        )}

        {project && !pageId && (
          <>
            <BangChuaCoChu
              project={project}
              onNhanXong={(moi) => setProject((cu) => ({ ...cu, ...moi }))}
            />

            <div className="tieu-de-man">
              <h1>{project.name}</h1>
              <p>
                Mục đích đã khai: <b>{MUC_DICH[project.intended_use] ?? project.intended_use}</b>
                {' '}· không sửa được sau khi tạo
              </p>
            </div>

            <ChapterSummary
              tienDo={tienDo} canhBao={canhBao} trangDau={dsTrang[0]?.id}
              onXuat={() => document.getElementById('bang-xuat')?.scrollIntoView({ block: 'start' })}
            />

            {moHangDoi && (
              <ConsistencyReviewQueue
                viec={viecNQ}
                hoSoGiong={hoSoGiong}
                dangBan={dangBan}
                onAp={apViec}
                onGiuNguyen={(id) =>
                  chayNQ(() => api.boQuaViecNhatQuan(id, 'keep_current'), 'Đã giữ bản hiện tại.')}
                onBoQua={(id) =>
                  chayNQ(() => api.boQuaViecNhatQuan(id, 'not_applicable'), 'Đã bỏ qua gợi ý này.')}
              />
            )}

            <GlossaryManager
              danhSach={thuatNgu}
              dangBan={dangBan}
              onThem={(d) => chayNQ(() => api.themThuatNgu(project.id, d), 'Đã thêm thuật ngữ (đang ở nháp).')}
              onSua={(id, d) => chayNQ(() => api.suaThuatNgu(id, d), 'Đã lưu thuật ngữ.')}
              onDuyet={(id) => chayNQ(() => api.duyetThuatNgu(id), 'Đã duyệt — thuật ngữ này sẽ tham gia rà soát.')}
              onCat={(id) => chayNQ(() => api.catThuatNgu(id), 'Đã cất thuật ngữ đi.')}
              onTimUngVien={() => api.layUngVienThuatNgu(project.id)}
              onXinGoiY={(ten) => api.xinGoiYTheoTenTruyen(project.id, ten)}
              onDoiChieuTen={(ten) => api.doiChieuTenChinhThuc(project.id, ten)}
              onDocGoiY={(runId) => api.layKetQuaGoiY(runId)}
            />

            <VoiceProfileManager
              danhSach={hoSoGiong}
              dangBan={dangBan}
              onThem={(d) => chayNQ(() => api.themHoSoGiong(project.id, d), 'Đã thêm hồ sơ nhân vật.')}
              onBat={(id) => chayNQ(() => api.batHoSoGiong(id), 'Đã bật hồ sơ.')}
              onCat={(id) => chayNQ(() => api.catHoSoGiong(id), 'Đã cất hồ sơ đi.')}
              onTimTinHieu={() => api.layTinHieuXungHo(project.id)}
            />

            <div className="luoi-2-cot">
              <ChapterProgress
                project={project} canhBao={canhBao}
                onNapLai={() => napProject(project.id).catch((e) => setLoi(e.message))}
              />
              <div className="cot-phai">
                <QualityPanel tomTat={chatLuongChapter} trangDau={dsTrang[0]?.id} />
                <ConsistencyPanel
                  tomTat={tomTatNQ}
                  dangQuet={dangQuet}
                  onQuet={quetNhatQuan}
                  onMoHangDoi={() => {
                    setMoHangDoi(true)
                    setTimeout(
                      () => document.getElementById('tieu-de-hang-doi')
                        ?.scrollIntoView({ block: 'start' }),
                      0,
                    )
                  }}
                />
                <BatchPanel projectId={project.id} soTrang={dsTrang.length} />
                <ExportPanel
                  projectId={project.id} tenProject={project.name}
                  nhatQuan={tomTatNQ}
                  onRaSoat={() => {
                    setMoHangDoi(true)
                    setTimeout(
                      () => document.getElementById('tieu-de-hang-doi')
                        ?.scrollIntoView({ block: 'start' }),
                      0,
                    )
                  }}
                />
              </div>
            </div>
          </>
        )}

        {chiTiet && (
          <>
            <ReviewToolbar
              tenChapter={project?.name} projectId={chiTiet.page?.project_id}
              trang={chiTiet.page} danhSachTrang={dsTrang} soCanXem={soCanXem}
            />

            <div className="bo-cuc">
              <section className="cot-anh">
                <div className="hang-cong-cu">
                  <label className="o-tick nho">
                    <input
                      type="checkbox" checked={hienCanhBaoAnh}
                      onChange={(e) => setHienCanhBaoAnh(e.target.checked)}
                    />
                    <span>Hiện cảnh báo trên ảnh</span>
                  </label>
                  <label className="o-tick nho">
                    <input
                      type="checkbox" checked={hienVungAnToan}
                      onChange={(e) => setHienVungAnToan(e.target.checked)}
                    />
                    <span>Hiện vùng an toàn của bong bóng</span>
                  </label>
                  <span className="ghi-chu">
                    {soTran} vùng tràn khung · {soCanXem} vùng cần xem lại ·{' '}
                    {chiTiet.regions.length} vùng
                  </span>
                </div>

                {loiAnh && (
                  <Alert sac="loi" tieuDe="Không tải được ảnh trang">
                    {loiAnh}
                  </Alert>
                )}
                {chiTiet.preview_url && anhBlob ? (
                  <BboxOverlay
                    src={anhBlob}
                    regions={chiTiet.regions}
                    dangChon={dangChon}
                    onChon={setDangChon}
                    onLuuBbox={luuBbox}
                    hienCanhBao={hienCanhBaoAnh}
                    vungAnToan={vungAnToan}
                    hienVungAnToan={hienVungAnToan}
                  />
                ) : chiTiet.preview_url && !loiAnh ? (
                  // "Đang tải" KHÁC "chưa có": ảnh 2MB tải mất một nhịp, và báo "chưa có ảnh"
                  // lúc đó là nói sai — người dùng sẽ đi chạy lại một bước vốn đã xong.
                  <p className="ghi-chu">Đang tải ảnh trang…</p>
                ) : !chiTiet.preview_url ? (
                  <Alert sac="tin" tieuDe="Chưa có ảnh xem thử">
                    Trang này cần chạy xong bước căn chữ mới có ảnh để xem.
                  </Alert>
                ) : null}
              </section>

              <aside className="cot-sua">
                <OrientationSummaryCard
                  tomTat={tomTatHuong}
                  dangBan={dangBan}
                  onChayLai={() => chay('chạy lại nhận biết hướng chữ',
                    () => api.chayLaiHuongChu(chiTiet.page.id))}
                />

                <div className="loc-huong-chu" role="group" aria-label="Lọc vùng theo hướng chữ">
                  {LOC_HUONG_CHU.map((l) => {
                    const so = chiTiet.regions.filter((r) => l.hop(huongChu[r.id])).length
                    return (
                      <button
                        key={l.ma}
                        type="button"
                        className={`the-loc ${locHuong === l.ma ? 'dang-chon' : ''}`}
                        aria-pressed={locHuong === l.ma}
                        onClick={() => setLocHuong(l.ma)}
                      >
                        {l.nhan} <span className="so">{so}</span>
                      </button>
                    )
                  })}
                </div>

                <div className="danh-sach-vung">
                  {(() => {
                    const loc = LOC_HUONG_CHU.find((l) => l.ma === locHuong) ?? LOC_HUONG_CHU[0]
                    const ds = chiTiet.regions.filter((r) => loc.hop(huongChu[r.id]))
                    if (!ds.length) {
                      return (
                        <p className="ghi-chu">
                          Không có vùng nào khớp bộ lọc &ldquo;{loc.nhan}&rdquo;.
                        </p>
                      )
                    }
                    return ds.map((r) => {
                      const h = huongChu[r.id]
                      return (
                        <button
                          key={r.id}
                          className={`the-vung ${dangChon === r.id ? 'dang-chon' : ''}`}
                          onClick={() => setDangChon(r.id)}
                        >
                          <b>{r.reading_order ?? '?'}</b>
                          <span className="tom-tat">
                            {r.translated_text || <i>chưa có bản dịch</i>}
                          </span>
                          <span className="nhom-nhan">
                            <StatusBadge loai="canh_chu" trangThai={r.fit_status} />
                            {/* Huy hiệu hướng chữ đứng RIÊNG, không gộp vào huy hiệu căn chữ. */}
                            {h && (
                              <StatusBadge
                                dienGiai={nhanHuongChu(h.orientation, h.status, h.reason_codes)}
                              />
                            )}
                          </span>
                        </button>
                      )
                    })
                  })()}
                </div>

                {vungDangChon && (
                  <RegionQualityBox
                    danhGia={(chatLuongTrang?.regions ?? [])
                      .find((d) => d.region_id === vungDangChon.id)}
                    dangBan={dangBan}
                    onQuyetDinh={(qd) => quyetDinhVung(vungDangChon.id, qd)}
                  />
                )}

                {vungDangChon && (
                  <OrientationBox
                    huongChu={huongChu[vungDangChon.id]}
                    hienLuoi={hienLuoiCot}
                    onDoiLuoi={setHienLuoiCot}
                  />
                )}

                {vungDangChon && (
                  <RegionPanel
                    key={vungDangChon.id}
                    region={vungDangChon}
                    vungAnToan={vungAnToan[vungDangChon.id]}
                    fontFamilies={chiTiet.font_families}
                    coMin={chiTiet.min_font_size}
                    coMax={chiTiet.max_font_size}
                    dangBan={dangBan}
                    onLuu={luuVung}
                    onCanhLai={(id) => chay('căn lại chữ', () => api.canhLaiVung(id))}
                    onDocLai={(id) => chay('đọc lại chữ gốc', () => api.docLaiVung(id))}
                    onDichLai={(id) => chay('dịch lại', () => api.dichLaiVung(id))}
                  />
                )}
              </aside>
            </div>
          </>
        )}
      </main>
    </div>
  )
}


