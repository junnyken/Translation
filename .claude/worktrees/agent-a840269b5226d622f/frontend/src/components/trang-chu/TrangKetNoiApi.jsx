import { useState } from 'react'
import * as api from '../../api'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui'
import ChanTrangManga from './ChanTrangManga'

export default function TrangKetNoiApi({ onQuayLai, onMoTaiKhoan }) {
  const { laEn } = useNgonNguUI()
  const [tabCode, setTabCode] = useState('python')
  const [daSaoChep, setDaSaoChep] = useState(false)
  const apiOrigin = api.API_BASE || 'https://translation-api.vibe1.tinhgon.xyz'

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
        "engine": "llm_context",  # llm_context (Gemini AI) | google_fast
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
  "rendered_image_url": "${apiOrigin}/api/v1/developer/pages/6f9c2a10-.../rendered-image?api_key=tr_live_...",
  "inpainted_image_url": "${apiOrigin}/api/v1/developer/pages/6f9c2a10-.../inpainted-image?api_key=tr_live_...",
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
    "daily_remaining": 18,
    "purchased_remaining": 6500,
    "total_usable_pages": 6518
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
                    ? 'Translate 1 comic page (send file, image_url, or image_base64). Supports wait=true (sync) or wait=false (async) + 0.15s SHA-256 Community Cache.'
                    : 'Dịch 1 trang truyện (gửi file, image_url hoặc image_base64). Hỗ trợ wait=true (chờ lấy ngay link ảnh đã ghép chữ) hoặc wait=false (chạy nền) + Cache Cộng đồng 0.15s.',
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
                    ? 'Get status, rendered_image_url, inpainted_image_url, and speech bubble JSON of a single page.'
                    : 'Lấy trạng thái, link tải ảnh đã ghép chữ (rendered-image), ảnh đã xoá chữ (inpainted-image) và JSON bóng thoại của 1 trang.',
                },
                {
                  method: 'POST',
                  mau: '#f59e0b',
                  path: '/api/v1/developer/translate-text',
                  moTa: laEn
                    ? 'Batch-translate an array of paragraphs for Web Novels / Light Novels using Gemini AI or Google Fast.'
                    : 'Dịch hàng loạt mảng các đoạn văn bản Truyện Chữ (Web Novel / Light Novel) chuẩn mạch ngữ cảnh bằng Gemini AI hoặc Google Nhanh.',
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
