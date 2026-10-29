import { useState } from 'react'
import * as api from '../../api'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui'
import ChanTrangManga from './ChanTrangManga'

export default function TrangKetNoiApi({ onQuayLai, onMoTaiKhoan }) {
  const { laEn } = useNgonNguUI()
  const [tabCode, setTabCode] = useState('python')
  const [daSaoChep, setDaSaoChep] = useState(false)
  const [khoaThuNghiem, setKhoaThuNghiem] = useState('')
  const [dangTestApi, setDangTestApi] = useState(false)
  const [ketQuaTest, setKetQuaTest] = useState(null)
  const [loiTest, setLoiTest] = useState('')
  const apiOrigin = api.API_BASE || 'https://translation-api.vibe1.tinhgon.xyz'

  async function kiemTraKetNoiApiTrucTiep(e) {
    if (e) e.preventDefault()
    setDangTestApi(true)
    setLoiTest('')
    setKetQuaTest(null)
    const t0 = performance.now()
    try {
      const keySach = (khoaThuNghiem || '').trim()
      const headers = {}
      if (keySach) {
        headers['X-Customer-Api-Key'] = keySach
        headers['Authorization'] = `Bearer ${keySach}`
      } else {
        const tokenWeb = api.layTokenXacThuc?.()
        if (tokenWeb) {
          headers['Authorization'] = `Bearer ${tokenWeb}`
        }
      }
      if (!headers['X-Customer-Api-Key'] && !headers['Authorization']) {
        throw new Error(
          laEn
            ? 'Please paste your tr_live_... API Key (or sign in first) to test connection.'
            : 'Vui lòng dán mã tr_live_... (hoặc đăng nhập tài khoản trên Web) để kiểm tra kết nối.'
        )
      }
      const res = await fetch(`${apiOrigin}/api/v1/developer/quota`, {
        method: 'GET',
        headers,
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(data?.detail || `HTTP ${res.status}`)
      }
      const latencyMs = Math.round(performance.now() - t0)
      setKetQuaTest({ ...data, latencyMs })
    } catch (err) {
      setLoiTest(err.message || (laEn ? 'Connection test failed.' : 'Không thể kết nối tới API.'))
    } finally {
      setDangTestApi(false)
    }
  }

  const CODE_MAU = {
    python: `import requests

API_KEY = "tr_live_YOUR_API_KEY"  # Lấy trong mục Tài khoản trên https://comic.io.vn
BASE_URL = "${apiOrigin}/api/v1/developer"

# 1. Kiểm tra số dư lượt khả dụng
quota = requests.get(
    f"{BASE_URL}/quota",
    headers={"X-Customer-Api-Key": API_KEY}
).json()
print("Tổng số trang khả dụng:", quota["total_usable_pages"])

# 2. Dịch 1 trang truyện từ URL ảnh (hệ thống tự vượt chống Hotlink)
res = requests.post(
    f"{BASE_URL}/translate-image",
    headers={"X-Customer-Api-Key": API_KEY},
    data={
        "image_url": "https://uploads.mangadex.org/data/.../page01.jpg",
        "source_lang": "ja",      # ja (Nhật) | ko (Hàn) | zh (Trung) | en (Anh)
        "target_lang": "vi",      # vi (Tiếng Việt) | en (Tiếng Anh Quốc tế)
        "engine": "llm_context",  # llm_context (AI Ngữ Cảnh) | google_fast
        "mode": "day_du",         # day_du = ghép sẵn chữ vào ảnh | chi_chu = chỉ lấy JSON
        "font_style": "bangers",  # bangers | romance | historical | comic
        "wait": "true"
    }
).json()

# Kéo ảnh đã ghép chữ hoàn chỉnh về server của bạn:
if res.get("rendered_image_url"):
    img_bytes = requests.get(res["rendered_image_url"]).content
    with open("trang_01_da_dich.png", "wb") as f:
        f.write(img_bytes)

# 3. Đẩy nguyên 1 Chapter (danh sách nhiều URL ảnh) chỉ với 1 lệnh:
chap = requests.post(
    f"{BASE_URL}/translate-chapter",
    headers={"X-Customer-Api-Key": API_KEY},
    json={
        "chapter_name": "Solo Leveling - Chap 150",
        "image_urls": [
            "https://cdn.example.com/chap150/001.jpg",
            "https://cdn.example.com/chap150/002.jpg"
        ],
        "source_lang": "ko",
        "target_lang": "vi",
        "engine": "llm_context",
        "mode": "day_du"
    }
).json()
print("Link theo dõi & kéo trọn bộ Chapter:", chap["poll_chapter_url"])`,

    nodejs: `// Node.js 18+ / Next.js / Discord Bot / Telegram Bot
const API_KEY = "tr_live_YOUR_API_KEY";
const BASE_URL = "${apiOrigin}/api/v1/developer";

async function dichTrangTruyen(imageUrl) {
  const form = new FormData();
  form.append("image_url", imageUrl);
  form.append("source_lang", "ko");
  form.append("target_lang", "vi");
  form.append("engine", "llm_context");
  form.append("mode", "day_du");
  form.append("wait", "true");

  const res = await fetch(\`\${BASE_URL}/translate-image\`, {
    method: "POST",
    headers: { "X-Customer-Api-Key": API_KEY },
    body: form,
  });

  const data = await res.json();
  console.log("✅ Link ảnh đã ghép chữ:", data.rendered_image_url);
  console.log("💬 Danh sách bóng thoại:", data.regions);
  return data;
}

dichTrangTruyen("https://example.com/raw-chapter/01.jpg");`,

    php: `<?php
// Tích hợp vào Website PHP / WordPress (Theme Madara / MangaReader)
$apiKey = "tr_live_YOUR_API_KEY";
$endpoint = "${apiOrigin}/api/v1/developer/translate-image";

$ch = curl_init($endpoint);
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 180,
    CURLOPT_HTTPHEADER => [
        "X-Customer-Api-Key: " . $apiKey
    ],
    CURLOPT_POSTFIELDS => [
        "image_url" => "https://example.com/raw/chap-1/01.jpg",
        "source_lang" => "zh",
        "target_lang" => "vi",
        "engine" => "llm_context",
        "mode" => "day_du",
        "wait" => "true"
    ]
]);

$response = json_decode(curl_exec($ch), true);
curl_close($ch);

if (!empty($response["rendered_image_url"])) {
    // Lưu ảnh đã dịch về thư mục wp-content/uploads của bạn
    $imgData = file_get_contents($response["rendered_image_url"]);
    file_put_contents(__DIR__ . "/chap1-01-vi.png", $imgData);
    echo "Đã lưu trang truyện dịch thành công!";
}
?>`,

    curl: `# 1. Kiểm tra hạn mức & số dư trang của API Key:
curl -X GET "${apiOrigin}/api/v1/developer/quota" \\
  -H "X-Customer-Api-Key: tr_live_YOUR_API_KEY"

# 2. Gửi file ảnh trực tiếp từ máy chủ khách hàng lên dịch & lấy ảnh ghép chữ:
curl -X POST "${apiOrigin}/api/v1/developer/translate-image" \\
  -H "X-Customer-Api-Key: tr_live_YOUR_API_KEY" \\
  -F "file=@./page01.jpg" \\
  -F "source_lang=ja" \\
  -F "target_lang=vi" \\
  -F "engine=llm_context" \\
  -F "mode=day_du" \\
  -F "wait=true"

# 3. Dịch chương Truyện Chữ (Web Novel / Light Novel):
curl -X POST "${apiOrigin}/api/v1/developer/translate-text" \\
  -H "X-Customer-Api-Key: tr_live_YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "texts": ["第1話：始まり", "彼は静かに立ち上がった。"],
    "source_lang": "ja",
    "target_lang": "vi",
    "engine": "llm_context"
  }'`,

    json: `{
  "status": "completed",
  "completed": true,
  "cached": false,
  "page_id": "6f9c2a10-81e4-4c92-b012-9a8b7c6d5e4f",
  "source_lang": "ja",
  "target_lang": "vi",
  "mode": "day_du",
  "rendered_image_url": "${apiOrigin}/api/v1/developer/pages/6f9c2a10-.../rendered-image?sig=a8f92c...&exp=1793294000",
  "inpainted_image_url": "${apiOrigin}/api/v1/developer/pages/6f9c2a10-.../inpainted-image?sig=a8f92c...&exp=1793294000",
  "regions_count": 2,
  "regions": [
    {
      "order": 1,
      "bbox": { "x": 118.0, "y": 42.0, "w": 164.0, "h": 210.0 },
      "source_text": "いくぞ！",
      "translated_text": "Lên đường thôi!",
      "font_size": 24.0,
      "text_color": "#111827",
      "stroke_color": "#FFFFFF"
    }
  ],
  "quota": {
    "daily_remaining": 10,
    "purchased_remaining": 6500,
    "total_usable_pages": 6510
  }
}`,
  }

  function saoChepCode() {
    navigator.clipboard?.writeText(CODE_MAU[tabCode] || '')
    setDaSaoChep(true)
    setTimeout(() => setDaSaoChep(false), 2000)
  }

  return (
    <main className="than-trang" style={{ maxWidth: 1120, margin: '0 auto', padding: '24px 16px 48px' }}>
      {/* Hero Banner */}
      <div style={{
        padding: '28px 24px',
        marginBottom: 26,
        borderRadius: 20,
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(12, 74, 110, 0.92))',
        border: '1px solid rgba(56, 189, 248, 0.45)',
        color: '#f8fafc',
        boxShadow: '0 20px 45px rgba(2, 6, 23, 0.35)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
          <span style={{
            display: 'inline-block',
            background: 'rgba(56, 189, 248, 0.2)',
            color: '#38bdf8',
            border: '1px solid rgba(56, 189, 248, 0.45)',
            padding: '5px 14px',
            borderRadius: 999,
            fontSize: 12.5,
            fontWeight: 700,
          }}>
            ⚡ {laEn ? 'DEVELOPER REST API · API KEY (tr_live_...)' : 'CỔNG DEVELOPER REST API · KHOÁ API RIÊNG (tr_live_...)'}
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
            ? 'API Integration Guide for Customer Tools, Comic Websites & Bots'
            : 'Hướng Dẫn Kết Nối API Cho Tool Khách Hàng, Web Truyện & Bot Tự Động'}
        </h1>
        <p style={{ fontSize: 15.5, color: '#cbd5e1', lineHeight: 1.65, maxWidth: 880, margin: '0 0 18px' }}>
          {laEn
            ? 'Have your own comic reader website, WordPress/Madara theme, auto-leech tool, or Discord/Telegram bot? Generate a personal API Key (tr_live_...) in your Account menu and pull translated images + speech bubble JSON automatically.'
            : 'Bạn có website đọc truyện riêng, plugin WordPress/Madara, tool auto-leech hoặc bot Discord/Telegram? Chỉ cần tạo mã API Key (tr_live_...) trong mục Tài khoản để tool của bạn tự động đẩy ảnh/link lên dịch và kéo ảnh đã ghép chữ hoàn chỉnh về!'}
        </p>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {onMoTaiKhoan && (
            <button
              type="button"
              className="nut-manga nut-manga-chinh"
              onClick={onMoTaiKhoan}
            >
              🔑 {laEn ? 'Open Account to Get API Key (tr_live_...)' : 'Mở Tài Khoản Lấy Mã API Key (tr_live_...)'}
            </button>
          )}
          <a
            href="#tien-ich"
            className="nut-manga nut-manga-phu"
          >
            🧩 {laEn ? 'Download Extension & Windows App' : 'Tải Tiện Ích Chrome & App Windows'}
          </a>
        </div>
      </div>

      {/* 3 bước đấu nối nhanh */}
      <section style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: 18,
        marginBottom: 26,
      }}>
        {[
          {
            buoc: '01',
            tieuDe: laEn ? 'Generate Personal API Key' : 'Tạo Khoá API Cố Định (tr_live_...)',
            moTa: laEn
              ? 'Sign in at comic.io.vn → Click your account name on the top bar → In the Developer API Key box, click Generate to get your tr_live_... key (never expires after 14 days).'
              : 'Đăng nhập trên comic.io.vn → Bấm vào tên tài khoản trên thanh menu → Tại mục Khoá API Developer, bấm "Tạo khoá API" để nhận mã tr_live_... (không bị hết hạn sau 14 ngày).',
            mau: '#38bdf8',
          },
          {
            buoc: '02',
            tieuDe: laEn ? 'Attach Authentication Header' : 'Gắn Header Xác Thực Vào Tool',
            moTa: laEn
              ? 'Pass your API key in the HTTP header X-Customer-Api-Key: tr_live_... or Authorization: Bearer tr_live_... with every request.'
              : 'Gắn khoá vào Header HTTP: X-Customer-Api-Key: tr_live_... (hoặc Authorization: Bearer tr_live_...). Mọi lượt dịch sẽ trừ trực tiếp vào số dư trang của bạn.',
            mau: '#a855f7',
          },
          {
            buoc: '03',
            tieuDe: laEn ? 'Push Raw Images & Pull Translated PNG' : 'Đẩy Ảnh / Link Lên & Kéo Ảnh Đã Dịch Về',
            moTa: laEn
              ? 'Send a file, image_url, or chapter URL list. Receive rendered_image_url (typeset PNG), inpainted_image_url, and speech bubble coordinates JSON.'
              : 'Gửi file ảnh, image_url hoặc danh sách link cả Chapter. Nhận về ngay link tải Ảnh đã ghép chữ hoàn chỉnh (rendered_image_url), Ảnh đã xoá chữ và JSON toạ độ.',
            mau: '#10b981',
          },
        ].map((item) => (
          <div
            key={item.buoc}
            style={{
              background: 'rgba(15, 23, 42, 0.94)',
              border: '1px solid rgba(148, 163, 184, 0.28)',
              borderTop: `4px solid ${item.mau}`,
              borderRadius: 16,
              padding: '20px 18px',
              color: '#f8fafc',
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 800, color: item.mau, marginBottom: 6 }}>
              {laEn ? `STEP ${item.buoc}` : `BƯỚC ${item.buoc}`}
            </div>
            <h2 style={{ fontSize: 18, margin: '0 0 8px', color: '#ffffff' }}>{item.tieuDe}</h2>
            <p style={{ margin: 0, fontSize: 14, color: '#cbd5e1', lineHeight: 1.6 }}>{item.moTa}</p>
          </div>
        ))}
      </section>

      {/* Trạm kiểm tra kết nối API & số dư trực tiếp */}
      <section style={{
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(6, 78, 59, 0.28))',
        border: '1px solid rgba(16, 185, 129, 0.45)',
        borderRadius: 18,
        padding: '22px',
        color: '#f8fafc',
        marginBottom: 26,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 10 }}>
          <h2 style={{ margin: 0, fontSize: 20, color: '#6ee7b7' }}>
            🩺 {laEn ? 'Live API Connection & Quota Tester' : 'Trạm Kiểm Tra Kết Nối API & Đồng Bộ Số Dư Trực Tiếp'}
          </h2>
          <span style={{ fontSize: 12.5, color: '#a7f3d0', fontWeight: 700 }}>
            GET /api/v1/developer/quota
          </span>
        </div>
        <p style={{ margin: '0 0 14px', fontSize: 13.8, color: '#cbd5e1', lineHeight: 1.6 }}>
          {laEn
            ? 'Paste your tr_live_... API Key (or leave blank to test with your current Web login session) to verify connection speed, account linkage, daily free quota (10 pages/day), and cumulative VIP purchased pages.'
            : 'Dán mã tr_live_... của bạn vào ô bên dưới (hoặc để trống nếu bạn đang đăng nhập trên Web) rồi bấm Kiểm tra ngay để xác nhận API thông suốt, kiểm tra độ trễ (ms) và xem số dư trang đồng bộ thời gian thực.'}
        </p>

        <form onSubmit={kiemTraKetNoiApiTrucTiep} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            type="text"
            value={khoaThuNghiem}
            onChange={(e) => setKhoaThuNghiem(e.target.value)}
            placeholder={laEn ? 'Paste tr_live_... API Key (or leave empty if signed in on Web)' : 'Dán mã tr_live_... vào đây (hoặc để trống nếu đã đăng nhập trên Web)'}
            style={{
              flex: '1 1 320px',
              padding: '10px 14px',
              borderRadius: 10,
              border: '1px solid rgba(56, 189, 248, 0.45)',
              background: '#020617',
              color: '#38bdf8',
              fontFamily: 'monospace',
              fontSize: 13.5,
            }}
          />
          <button
            type="submit"
            disabled={dangTestApi}
            className="nut-manga nut-manga-chinh"
            style={{ padding: '10px 18px', fontSize: 13.5 }}
          >
            {dangTestApi
              ? (laEn ? '⏳ Testing...' : '⏳ Đang kiểm tra...')
              : (laEn ? '⚡ Test Connection & Quota Now' : '⚡ Kiểm Tra Kết Nối & Số Dư Ngay')}
          </button>
        </form>

        {loiTest && (
          <div style={{
            marginTop: 12,
            padding: '10px 14px',
            borderRadius: 10,
            background: 'rgba(239, 68, 68, 0.16)',
            border: '1px solid rgba(248, 113, 113, 0.45)',
            color: '#fca5a5',
            fontSize: 13.5,
          }}>
            ❌ {loiTest}
          </div>
        )}

        {ketQuaTest && (
          <div style={{
            marginTop: 14,
            padding: '14px 16px',
            borderRadius: 12,
            background: 'rgba(2, 6, 23, 0.85)',
            border: '1px solid rgba(16, 185, 129, 0.5)',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(185px, 1fr))',
            gap: 12,
            fontSize: 13.5,
          }}>
            <div>
              <div style={{ color: '#94a3b8', fontSize: 12 }}>{laEn ? 'Connection Status' : 'Trạng thái kết nối'}</div>
              <div style={{ color: '#34d399', fontWeight: 800, marginTop: 2 }}>
                ✅ ONLINE ({ketQuaTest.latencyMs} ms)
              </div>
            </div>
            <div>
              <div style={{ color: '#94a3b8', fontSize: 12 }}>{laEn ? 'Linked Account' : 'Tài khoản liên kết'}</div>
              <div style={{ color: '#f8fafc', fontWeight: 700, marginTop: 2 }}>
                {ketQuaTest.user?.email || '—'}
              </div>
            </div>
            <div>
              <div style={{ color: '#94a3b8', fontSize: 12 }}>{laEn ? 'Daily Free Quota' : 'Miễn phí trong ngày'}</div>
              <div style={{ color: '#38bdf8', fontWeight: 800, marginTop: 2 }}>
                {ketQuaTest.daily_free_remaining ?? 0} / {ketQuaTest.daily_free_limit ?? 10} {laEn ? 'pages' : 'trang'}
              </div>
            </div>
            <div>
              <div style={{ color: '#94a3b8', fontSize: 12 }}>{laEn ? 'VIP Purchased Wallet' : 'Ví mua thêm (cộng dồn)'}</div>
              <div style={{ color: '#fbbf24', fontWeight: 800, marginTop: 2 }}>
                +{ketQuaTest.purchased_pages_remaining ?? 0} {laEn ? 'pages' : 'trang'}
              </div>
            </div>
            <div>
              <div style={{ color: '#94a3b8', fontSize: 12 }}>{laEn ? 'Total Usable Pages' : 'Tổng khả dụng ngay'}</div>
              <div style={{ color: '#6ee7b7', fontWeight: 900, fontSize: 15, marginTop: 2 }}>
                {ketQuaTest.total_usable_pages ?? 0} {laEn ? 'pages' : 'trang'}
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Checklist 5 điều kiện cần thiết để kết nối API & đồng bộ đa nền tảng ổn định 100% */}
      <section style={{
        background: 'rgba(15, 23, 42, 0.95)',
        border: '1px solid rgba(56, 189, 248, 0.35)',
        borderRadius: 18,
        padding: '24px 22px',
        color: '#f8fafc',
        marginBottom: 26,
      }}>
        <h2 style={{ margin: '0 0 8px', fontSize: 21, color: '#ffffff' }}>
          🛠️ {laEn
            ? '5 Essential Requirements for Rock-Solid API Connection & Cross-Platform Sync'
            : 'Khách Dùng API Cần Chuẩn Bị Gì Để Kết Nối Ổn Định 100% & Đồng Bộ Đa Nền Tảng?'}
        </h2>
        <p style={{ margin: '0 0 18px', fontSize: 14, color: '#cbd5e1', lineHeight: 1.6 }}>
          {laEn
            ? 'Follow these 5 technical guidelines so your Website, Auto-Leech Tool, Chrome Extension, and Windows App run continuously without timeout, hotlink block, or quota desync:'
            : 'Chỉ cần cấu hình đúng 5 mục dưới đây, tool/website của bạn sẽ chạy tự động 24/7 mượt mà, không lo đứt kết nối, không bị chặn ảnh gốc và đồng bộ chung 1 ví trang với Tiện ích Chrome & App Windows:'}
        </p>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))',
          gap: 14,
        }}>
          {[
            {
              icon: '🔑',
              mau: '#38bdf8',
              tieuDe: laEn
                ? '1. Use Fixed API Key (tr_live_...) & Cumulative Wallet'
                : '1. Dùng Khoá API Cố Định (tr_live_...) & Ví Cộng Dồn Vĩnh Viễn',
              noiDung: laEn
                ? 'Unlike Web login cookies (which expire after 14 days), your tr_live_... key never expires until you rotate it. Every package you buy (including the 20,000đ / 40-page Starter Pack or larger bonus packs) automatically stacks into one shared balance.'
                : 'Khác với phiên đăng nhập Web (hết hạn sau 14 ngày), mã tr_live_... hoạt động vĩnh viễn cho tới khi bạn bấm Đổi khoá. Khi bạn mua bất kỳ gói nào (kể cả mua nhiều lần Gói Mồi 20.000đ = 40 trang hay gói lớn +5% → +40%), toàn bộ số trang đều cộng dồn vào chung 1 ví duy nhất.',
            },
            {
              icon: '⏱️',
              mau: '#f59e0b',
              tieuDe: laEn
                ? '2. Set HTTP Timeout >= 120s (Sync vs Async Chapter Queue)'
                : '2. Đặt Timeout HTTP >= 120 Giây & Chọn Đúng Chế Độ Chờ (wait)',
              noiDung: laEn
                ? 'Smart OCR + Background Reconstruction + Typesetting takes ~4–12s per new page (or 0.15s on high-speed cache hit). When calling /translate-image with wait=true, set your HTTP client timeout to 120–180s. When translating a full chapter (10–150 pages), call /translate-chapter or set wait=false and poll /projects/{project_id} every 3 seconds.'
                : 'Quá trình Nhận diện chữ + Tái tạo nền + Dịch ngữ cảnh + Ghép chữ tốn khoảng 4–12 giây/trang mới (hoặc chỉ 0.15 giây nếu trúng Bộ nhớ đệm tốc độ cao). Khi gọi /translate-image với wait=true, hãy đặt CURLOPT_TIMEOUT / timeout >= 120–180 giây. Nếu đẩy nguyên chương (10–150 ảnh), hãy gọi /translate-chapter hoặc đặt wait=false rồi poll tiến độ mỗi 3 giây.',
            },
            {
              icon: '🛡️',
              mau: '#10b981',
              tieuDe: laEn
                ? '3. Pass Anti-Hotlink Referer & Image Format Rules'
                : '3. Truyền Tham Số Referer Chống Chặn Ảnh (Anti-Hotlink) & Quy Chuẩn File',
              noiDung: laEn
                ? 'Supported formats: JPG, PNG, WEBP up to 20MB/page. If you pass image_url from a site protected by Cloudflare/Hotlink (e.g. MangaDex, Rawkuma, Baozimh), pass the referer field (e.g. referer="https://mangadex.org/") so our server fetches the raw image cleanly.'
                : 'Hỗ trợ ảnh JPG, PNG, WEBP tối đa 20MB/trang. Nếu bạn gửi image_url lấy từ các trang gốc chặn leech ảnh (MangaDex, Rawkuma, Baozimh...), hãy truyền thêm tham số referer (ví dụ referer="https://mangadex.org/") để server tự động giả lập trình duyệt vượt chặn Hotlink.',
            },
            {
              icon: '🔒',
              mau: '#a855f7',
              tieuDe: laEn
                ? '4. Secure HMAC Signed Image URLs (?sig=...&exp=...)'
                : '4. Bảo Mật Chữ Ký Số HMAC (?sig=...&exp=...) Khi Tải Ảnh Đã Dịch',
              noiDung: laEn
                ? 'The returned rendered_image_url and inpainted_image_url are signed with a page-scoped HMAC-SHA256 signature (?sig=...&exp=..., valid for 24h). Your API Key is NEVER exposed in image URLs, and tr_live_... keys cannot be abused to change your password or rotate keys.'
                : 'Link ảnh trả về (rendered_image_url, inpainted_image_url) được đính kèm chữ ký HMAC-SHA256 riêng cho từng trang (?sig=...&exp=..., hiệu lực 24h) giúp bạn tải ảnh trực tiếp mà KHÔNG bao giờ lộ mã tr_live_... trên trình duyệt. Ngoài ra, mã tr_live_... bị khoá quyền đổi mật khẩu để bảo vệ tài khoản tuyệt đối.',
            },
            {
              icon: '🔗',
              mau: '#ec4899',
              tieuDe: laEn
                ? '5. 1-Click Account Sync Across Web, Chrome Extension & Windows App'
                : '5. Đồng Bộ Chung 1 Tài Khoản Giữa Web ↔ Tiện Ích Chrome ↔ App Windows',
              noiDung: laEn
                ? 'You can sign in to the Chrome Extension and Windows Desktop App using: (A) Email + Password, (B) your tr_live_... API Key, or (C) clicking "Copy Session Token" in your Web Account modal and pasting it into the Extension/App. All platforms share the exact same 10 free daily pages + VIP wallet.'
                : 'Trên Tiện ích Chrome và App Windows, bạn có thể liên kết cùng 1 tài khoản theo 3 cách: (A) Nhập Email + Mật khẩu, (B) Dán trực tiếp mã tr_live_... vào ô kết nối, hoặc (C) Bấm nút "🔗 Copy Mã Phiên" trong mục Tài khoản trên Web rồi dán vào Tiện ích/App. Cả 4 nơi đều dùng chung 10 trang miễn phí/ngày + Ví trang mua thêm.',
            },
            {
              icon: '♻️',
              mau: '#34d399',
              tieuDe: laEn
                ? '6. Auto-Refund on Error & Free High-Speed Cache'
                : '6. Tự Động Hoàn Lượt Khi Lỗi Ảnh & Miễn Phí Khi Trúng Bộ Nhớ Đệm',
              noiDung: laEn
                ? 'If a raw image URL is broken or fails during processing, the ledger automatically refunds +1 page back to your wallet. If a page matches our High-Speed Cache, it returns in 0.15s with cached=true and costs 0 pages!'
                : 'Nếu link ảnh gốc bị lỗi hoặc quá trình xử lý gặp sự cố, sổ cái tự động hoàn trả lại đúng +1 trang vào ví của bạn. Đặc biệt, nếu trang truyện đã có trong Bộ nhớ đệm tốc độ cao, API trả kết quả ngay trong 0.15 giây (cached=true) và hoàn toàn KHÔNG trừ lượt!',
            },
          ].map((muc) => (
            <div
              key={muc.tieuDe}
              style={{
                background: 'rgba(2, 6, 23, 0.72)',
                border: '1px solid rgba(148, 163, 184, 0.24)',
                borderLeft: `4px solid ${muc.mau}`,
                borderRadius: 14,
                padding: '16px',
              }}
            >
              <div style={{ fontWeight: 800, fontSize: 15, color: '#ffffff', marginBottom: 6 }}>
                {muc.icon} {muc.tieuDe}
              </div>
              <p style={{ margin: 0, fontSize: 13.4, color: '#cbd5e1', lineHeight: 1.6 }}>
                {muc.noiDung}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Bảng danh sách 6 Endpoint */}
      <section style={{
        background: 'rgba(15, 23, 42, 0.95)',
        border: '1px solid rgba(148, 163, 184, 0.28)',
        borderRadius: 18,
        padding: '24px 22px',
        color: '#f8fafc',
        marginBottom: 26,
      }}>
        <h2 style={{ margin: '0 0 6px', fontSize: 21, color: '#ffffff' }}>
          📡 {laEn ? 'REST API Endpoints Reference' : 'Danh Sách Các Endpoint Đấu Nối Trực Tiếp'}
        </h2>
        <p style={{ margin: '0 0 16px', fontSize: 14, color: '#94a3b8' }}>
          Base URL: <code style={{ color: '#38bdf8', fontWeight: 700 }}>{apiOrigin}</code> (hoặc <code style={{ color: '#38bdf8' }}>https://comic.io.vn</code>)
        </p>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13.8, color: '#e2e8f0' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #334155', textAlign: 'left', color: '#94a3b8' }}>
                <th style={{ padding: '10px 12px' }}>Method</th>
                <th style={{ padding: '10px 12px' }}>Endpoint</th>
                <th style={{ padding: '10px 12px' }}>{laEn ? 'Description & Parameters' : 'Chức năng & Tham số truyền vào'}</th>
              </tr>
            </thead>
            <tbody>
              {[
                {
                  method: 'GET',
                  mau: '#10b981',
                  path: '/api/v1/developer/quota',
                  moTa: laEn
                    ? 'Check account info, daily free pages remaining, VIP purchased pages, and total usable quota.'
                    : 'Kiểm tra thông tin tài khoản, số lượt miễn phí trong ngày, số lượt VIP tích luỹ và tổng số trang khả dụng.',
                },
                {
                  method: 'POST',
                  mau: '#38bdf8',
                  path: '/api/v1/developer/translate-image',
                  moTa: laEn
                    ? 'Translate 1 comic page (send file, image_url, or image_base64). Supports wait=true (sync) or wait=false (async) + 0.15s High-Speed Cache.'
                    : 'Dịch 1 trang truyện (gửi file, image_url hoặc image_base64). Hỗ trợ wait=true (chờ lấy ngay link ảnh đã ghép chữ) hoặc wait=false (chạy nền) + Bộ nhớ đệm 0.15s.',
                },
                {
                  method: 'POST',
                  mau: '#38bdf8',
                  path: '/api/v1/developer/translate-chapter',
                  moTa: laEn
                    ? 'Submit a full chapter (array of image_urls) in 1 call. Server auto-fetches with Anti-Hotlink headers and queues all pages.'
                    : 'Đẩy nguyên 1 Chapter (mảng image_urls tối đa 150 ảnh/lệnh). Máy chủ tự tải ảnh vượt chặn Hotlink và xếp hàng dịch toàn bộ chương.',
                },
                {
                  method: 'GET',
                  mau: '#10b981',
                  path: '/api/v1/developer/projects/{project_id}',
                  moTa: laEn
                    ? 'Poll full chapter progress and retrieve rendered_image_url + regions for all pages in the chapter.'
                    : 'Theo dõi tiến độ dịch của cả Chapter và kéo một lượt toàn bộ danh sách link ảnh đã dịch + toạ độ của tất cả các trang.',
                },
                {
                  method: 'GET',
                  mau: '#10b981',
                  path: '/api/v1/developer/pages/{page_id}',
                  moTa: laEn
                    ? 'Get status, rendered_image_url, inpainted_image_url, and dialog coordinates JSON of a single page.'
                    : 'Lấy trạng thái, link tải ảnh đã ghép chữ (rendered-image), ảnh nền sạch (inpainted-image) và JSON vùng chữ của 1 trang.',
                },
                {
                  method: 'POST',
                  mau: '#f59e0b',
                  path: '/api/v1/developer/translate-text',
                  moTa: laEn
                    ? 'Batch-translate an array of paragraphs for Web Novels / Light Novels using Cloud Context AI.'
                    : 'Dịch hàng loạt mảng các đoạn văn bản Truyện Chữ (Web Novel / Light Novel) chuẩn mạch ngữ cảnh bằng AI Đám Mây.',
                },
              ].map((ep) => (
                <tr key={ep.path} style={{ borderBottom: '1px solid rgba(51, 65, 85, 0.65)' }}>
                  <td style={{ padding: '12px' }}>
                    <span style={{
                      display: 'inline-block',
                      padding: '3px 8px',
                      borderRadius: 6,
                      fontWeight: 800,
                      fontSize: 11.5,
                      background: `${ep.mau}22`,
                      color: ep.mau,
                      border: `1px solid ${ep.mau}66`,
                    }}>
                      {ep.method}
                    </span>
                  </td>
                  <td style={{ padding: '12px', fontFamily: 'monospace', fontWeight: 700, color: '#f8fafc' }}>
                    {ep.path}
                  </td>
                  <td style={{ padding: '12px', color: '#cbd5e1', lineHeight: 1.5 }}>
                    {ep.moTa}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Bộ Code mẫu đấu nối */}
      <section style={{
        background: '#090d16',
        border: '1px solid #334155',
        borderRadius: 18,
        padding: '22px',
        color: '#e2e8f0',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
          <h2 style={{ margin: 0, fontSize: 20, color: '#ffffff' }}>
            💻 {laEn ? 'Ready-to-Use Integration Code Examples' : 'Code Mẫu Đấu Nối Sẵn Sàng Chạy Ngay'}
          </h2>
          <button
            type="button"
            onClick={saoChepCode}
            style={{
              padding: '7px 14px',
              borderRadius: 8,
              border: '1px solid #38bdf8',
              background: daSaoChep ? '#059669' : 'rgba(56, 189, 248, 0.15)',
              color: '#ffffff',
              fontWeight: 700,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            {daSaoChep
              ? (laEn ? '✅ Copied!' : '✅ Đã sao chép!')
              : (laEn ? '📋 Copy Code Snippet' : '📋 Sao chép đoạn Code này')}
          </button>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
          {[
            { id: 'python', label: '🐍 Python (Tool / Crawler)' },
            { id: 'nodejs', label: '🟢 Node.js / JS (Web / Bot)' },
            { id: 'php', label: '🐘 PHP (WordPress / Madara)' },
            { id: 'curl', label: '💻 cURL / Terminal' },
            { id: 'json', label: laEn ? '📦 Sample JSON Response' : '📦 Mẫu JSON Kết quả trả về' },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTabCode(t.id)}
              style={{
                padding: '8px 14px',
                borderRadius: 9,
                border: tabCode === t.id ? '1px solid #38bdf8' : '1px solid #334155',
                background: tabCode === t.id ? 'rgba(56, 189, 248, 0.22)' : '#1e293b',
                color: '#f8fafc',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: 13,
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <pre style={{
          margin: 0,
          padding: 16,
          background: '#020617',
          borderRadius: 12,
          border: '1px solid #1e293b',
          overflowX: 'auto',
          fontSize: 13,
          lineHeight: 1.6,
          color: '#e2e8f0',
        }}>
          {CODE_MAU[tabCode]}
        </pre>
      </section>

      <div style={{ marginTop: 36 }}>
        <ChanTrangManga />
      </div>
    </main>
  )
}
