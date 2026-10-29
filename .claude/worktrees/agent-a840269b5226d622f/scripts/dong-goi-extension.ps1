<#
.SYNOPSIS
    Đóng gói tiện ích mở rộng trình duyệt (Chrome Web Store / Edge Add-ons) chuẩn Manifest V3.
    Chỉ đưa vào gói `manifest.json` và thư mục `src/` (loại bỏ hoàn toàn `node_modules`, `tests`, `package.json`).

.PARAMETER DiaChiMayChu
    (Tuỳ chọn) URL máy chủ chạy thật (vd: "https://dich.tenmien.vn") để nhúng thẳng vào `DIA_CHI_MAC_DINH`
    trong gói phát hành — giúp người dùng cài từ Chrome Web Store là bấm dịch ngay không cần cấu hình.
#>
param(
    [string]$DiaChiMayChu = ""
)

$ErrorActionPreference = "Stop"
$Goc = Split-Path -Parent $PSScriptRoot
$ThuMucExt = Join-Path $Goc "extension-doc-truyen"
$ThuMucDist = Join-Path $Goc "dist"
$ThuMucTam = Join-Path $ThuMucDist "_build_ext_tmp"

if (-not (Test-Path $ThuMucDist)) {
    New-Item -ItemType Directory -Path $ThuMucDist | Out-Null
}
if (Test-Path $ThuMucTam) {
    Remove-Item -Recurse -Force $ThuMucTam
}
New-Item -ItemType Directory -Path $ThuMucTam | Out-Null

Copy-Item (Join-Path $ThuMucExt "manifest.json") -Destination $ThuMucTam
Copy-Item (Join-Path $ThuMucExt "src") -Destination (Join-Path $ThuMucTam "src") -Recurse

if ($DiaChiMayChu -ne "") {
    $ApiFile = Join-Path $ThuMucTam "src\lib\api.js"
    $NoiDung = Get-Content -Raw -Encoding UTF8 $ApiFile
    $NoiDung = $NoiDung -replace "export const DIA_CHI_MAC_DINH = ''", "export const DIA_CHI_MAC_DINH = '$DiaChiMayChu'"
    Set-Content -Path $ApiFile -Value $NoiDung -Encoding UTF8
}

$Manifest = Get-Content -Raw (Join-Path $ThuMucTam "manifest.json") | ConvertFrom-Json
$PhienBan = $Manifest.version
$TepZip = Join-Path $ThuMucDist "extension-doc-truyen-v$PhienBan.zip"
if (Test-Path $TepZip) {
    Remove-Item -Force $TepZip
}

Compress-Archive -Path (Join-Path $ThuMucTam "*") -DestinationPath $TepZip -Force
Copy-Item -Path $TepZip -Destination (Join-Path $ThuMucExt "dich-truyen-dang-doc.zip") -Force
Copy-Item -Path $TepZip -Destination (Join-Path $Goc "dich-truyen-dang-doc.zip") -Force
Remove-Item -Recurse -Force $ThuMucTam

Write-Host "✅ Đã đóng gói Chrome Web Store thành công: $TepZip"
