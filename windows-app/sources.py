"""Input discovery only; no translation, authentication or browser automation."""
from __future__ import annotations

import json
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlsplit

from production import NeedsAttention, natural_key

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
UNSUPPORTED_IMAGES = {".gif", ".svg", ".bmp", ".tif", ".tiff", ".avif", ".heic"}
MAX_PAGES = 200
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_PAGE_BYTES = 20 * 1024 * 1024


class _Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []
        self.links = []
        self.active = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img":
            # Prefer the real lazy image to src=placeholder, irrespective of attribute order.
            source = next((attrs[k] for k in ("data-src", "data-original", "data-lazy-src", "data-url")
                           if attrs.get(k) and not attrs[k].startswith("data:")), None)
            if not source:
                srcset = attrs.get("data-srcset") or attrs.get("srcset")
                if srcset:
                    candidates = [item.strip().split() for item in srcset.split(",") if item.strip()]
                    if candidates:
                        source = candidates[-1][0]
            self.images.append(source or attrs.get("src", ""))
        if tag == "a":
            self.active = [attrs.get("href", ""), ""]

    def handle_data(self, data):
        if self.active is not None:
            self.active[1] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.active is not None:
            self.links.append(tuple(self.active))
            self.active = None


def chapter_links(html: str, page_url: str):
    parser = _Document()
    parser.feed(html)
    found, seen = [], set()
    pattern = re.compile(r"(?<![a-z0-9])(?:chapter|chap|chuong|chương|episode|ep)[-_/\s.]*(\d+(?:\.\d+)?)(?![a-z0-9])", re.I)
    # A reader page usually links to the previous and next chapters. Those links
    # must not replace the chapter the operator actually supplied.
    current_matches = list(pattern.finditer(urlsplit(page_url).path))
    if current_matches:
        current = current_matches[-1]
        number = float(current.group(1))
        name = f"Chapter-{int(number):03d}" if number.is_integer() else f"Chapter-{number}"
        return [{"so": number, "ten": name, "url": page_url, "nhan": name}]
    for href, label in parser.links:
        url = urljoin(page_url, href)
        parts = urlsplit(url)
        match = pattern.search(f"{parts.path} {label}")
        if parts.scheme not in ("http", "https") or parts.netloc != urlsplit(page_url).netloc:
            continue
        if not match or url in seen:
            continue
        seen.add(url)
        number = float(match.group(1))
        name = f"Chapter-{int(number):03d}" if number.is_integer() else f"Chapter-{number}"
        found.append({"so": number, "ten": name, "url": url, "nhan": label.strip() or name})
    if not found:
        raise NeedsAttention("Chưa nhận diện được mục lục hoặc chapter. Dùng link chapter có số "
                             "hoặc tải file; website này cần bộ lấy nội dung riêng.")
    return sorted(found, key=lambda chapter: chapter["so"])


def image_links(html: str, page_url: str):
    parser = _Document()
    parser.feed(html)
    result, seen = [], set()
    for raw in parser.images:
        url = urljoin(page_url, raw)
        parts = urlsplit(url)
        if not raw or parts.scheme not in ("http", "https"):
            continue
        if any(word in parts.path.lower() for word in ("logo", "avatar", "banner", "icon", "placeholder")):
            continue
        # An image CDN may use /image/123 or a signed endpoint with no extension.
        # Keep it; the downloaded bytes, not the URL suffix, decide if it is an image.
        if Path(parts.path).suffix.lower() in UNSUPPORTED_IMAGES:
            raise NeedsAttention("Trang có định dạng ảnh chưa hỗ trợ; tải file và kiểm tra đủ trang trước.")
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def local_image_sources(folder: Path):
    files = []
    total = 0
    for file in sorted(folder.iterdir(), key=lambda p: natural_key(p.name)):
        if not file.is_file():
            continue
        if file.suffix.lower() in UNSUPPORTED_IMAGES:
            raise NeedsAttention(f"Ảnh {file.name} chưa được hỗ trợ; chuyển sang JPG/PNG/WEBP trước khi dịch.")
        if file.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        size = file.stat().st_size
        total += size
        if size > MAX_PAGE_BYTES or total > MAX_TOTAL_BYTES:
            raise NeedsAttention("Dung lượng ảnh vượt giới hạn 20 MB/trang hoặc 50 MB/chapter.")
        files.append(f"local_file::{file.as_posix()}")
        if len(files) > MAX_PAGES:
            raise NeedsAttention("Thư mục vượt giới hạn 200 trang.")
    if not files:
        raise NeedsAttention("Thư mục không chứa ảnh JPG/PNG/WEBP được hỗ trợ.")
    return files


def archive_sources(path: Path):
    """Validate the complete ZIP directory first. Never extract arbitrary paths."""
    if path.stat().st_size > MAX_TOTAL_BYTES:
        raise NeedsAttention("Gói vượt giới hạn 50 MB.")
    try:
        with zipfile.ZipFile(path) as archive:
            selected = []
            names = set()
            total = 0
            for entry in archive.infolist():
                name = entry.filename.replace("\\", "/")
                parts = PurePosixPath(name)
                if parts.is_absolute() or ".." in parts.parts or ":" in name or "\x00" in name:
                    raise NeedsAttention("Gói chứa đường dẫn không an toàn.")
                if entry.is_dir() or "__MACOSX" in parts.parts:
                    continue
                if parts.suffix.lower() in UNSUPPORTED_IMAGES:
                    raise NeedsAttention(f"Ảnh {parts.name} chưa được hỗ trợ; chuyển sang JPG/PNG/WEBP trước khi dịch.")
                if parts.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                if name in names or entry.flag_bits & 1:
                    raise NeedsAttention("Gói có tên ảnh trùng hoặc ảnh mã hoá.")
                names.add(name)
                total += entry.file_size
                if entry.file_size > MAX_PAGE_BYTES or total > MAX_TOTAL_BYTES:
                    raise NeedsAttention("Dung lượng ảnh giải nén vượt giới hạn an toàn.")
                selected.append(entry.filename)
                if len(selected) > MAX_PAGES:
                    raise NeedsAttention("Gói vượt giới hạn 200 trang.")
    except (zipfile.BadZipFile, OSError) as exc:
        raise NeedsAttention("Không mở được gói ZIP/CBZ.") from exc
    if not selected:
        raise NeedsAttention("Gói không chứa ảnh JPG/PNG/WEBP được hỗ trợ.")
    return ["archive_file::" + json.dumps([str(path.resolve()), name], ensure_ascii=False)
            for name in sorted(selected, key=natural_key)]


def read_local_source(source: str):
    if source.startswith("local_file::"):
        path = Path(source.removeprefix("local_file::"))
        if path.stat().st_size > MAX_PAGE_BYTES:
            raise NeedsAttention("Ảnh vượt giới hạn 20 MB.")
        return path.read_bytes()
    if source.startswith("archive_file::"):
        path, name = json.loads(source.removeprefix("archive_file::"))
        with zipfile.ZipFile(path) as archive:
            with archive.open(name) as file:
                data = file.read(MAX_PAGE_BYTES + 1)
        if len(data) > MAX_PAGE_BYTES:
            raise NeedsAttention("Ảnh trong gói vượt giới hạn 20 MB.")
        return data
    raise ValueError("Không phải nguồn ảnh cục bộ.")
