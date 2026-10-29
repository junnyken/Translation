"""Build a separate candidate ZIP; never replace existing public download bundles."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["Chay-App-Dich-Truyen-Windows.bat", "app_dich_truyen_windows.py", "production.py",
         "sources.py", "review_delivery.py", "Ra-Soat-Ban-Giao.bat",
         "HUONG-DAN-SU-DUNG.txt", "HUONG-DAN-PRODUCTION.md", "HUONG-DAN-RA-SOAT.md",
         "Cai-Dich-Offline.bat"]


def package(destination):
    hashes = {}
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            data = (ROOT / "windows-app" / name).read_bytes()
            hashes[name] = hashlib.sha256(data).hexdigest()
            archive.writestr(name, data)
        archive.writestr("MANIFEST.sha256.json", json.dumps(hashes, indent=2))
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        for name, digest in hashes.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    print(f"Candidate (chưa UAT Windows): {destination}")


if __name__ == "__main__":
    package(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/Translation-Windows-production-candidate.zip"))
