"""
Build script đóng gói trọn bộ `Manga-Video-Review-Studio-Setup-v1.0.exe` (C# .NET Framework 4.x Self-Extracting GUI Installer)
và `Manga-Video-Review-Studio-v1.0.zip` đồng bộ lên `video-review-studio/`, `frontend/public/tai-ve/` và `dist/`.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO_DIR = ROOT / "video-review-studio"
ICON_PATH = ROOT / "windows-app" / "manga_studio.ico"
CSC_CANDIDATES = [
    Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
    Path(r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"),
]

PAYLOAD_FILES = [
    "Manga-Video-Review-Studio.exe",
    "Chay-Video-Review-Studio.bat",
    "app_video_review_studio.py",
    "prompt_kich_ban_review_chuan.py",
    "core_vision_character.py",
    "core_tts_voice.py",
    "core_video_renderer.py",
]

CSHARP_SETUP_SOURCE = r"""
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Reflection;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("Manga Video Review Studio v1.2 — Setup")]
[assembly: AssemblyDescription("Trình Cài Đặt Tự Động Biên Kịch AI, Lồng Tiếng & Dựng MP4 GPU (comic.io.vn)")]
[assembly: AssemblyCompany("comic.io.vn — Manga Translation Studio")]
[assembly: AssemblyProduct("Manga Video Review Studio")]
[assembly: AssemblyCopyright("Copyright © 2026 comic.io.vn")]
[assembly: AssemblyVersion("1.2.0.0")]
[assembly: AssemblyFileVersion("1.2.0.0")]

namespace MangaStudioLauncher
{
    public class SplashForm : Form
    {
        private Label lblTitle;
        private Label lblSub;
        private Label lblStatus;
        private ProgressBar progressBar;
        private CheckBox chkDesktopShortcut;
        private Button btnStartInstall;
        private bool isInstallerMode;
        private string targetDir;
        private string entryScript = "app_video_review_studio.py";
        private string pipPackages = "Pillow edge-tts imageio-ffmpeg rapidocr-onnxruntime";
        private string shortcutName = "Manga Video Review Studio";

        public SplashForm(bool installerMode)
        {
            this.isInstallerMode = installerMode;
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            this.targetDir = installerMode
                ? Path.Combine(localAppData, "MangaVideoReviewStudio")
                : AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\', '/');

            this.Text = "Manga Video Review Studio v1.2 — Setup (comic.io.vn)";
            this.Size = new Size(590, installerMode ? 315 : 235);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.StartPosition = FormStartPosition.CenterScreen;
            this.BackColor = Color.FromArgb(15, 23, 42);
            this.ForeColor = Color.FromArgb(248, 250, 252);

            try
            {
                Icon appIcon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
                if (appIcon != null) this.Icon = appIcon;
            }
            catch { }

            lblTitle = new Label();
            lblTitle.Text = "🎬 Manga Video Review Studio v1.2";
            lblTitle.Font = new Font("Segoe UI", 15f, FontStyle.Bold);
            lblTitle.ForeColor = Color.FromArgb(56, 189, 248);
            lblTitle.Location = new Point(24, 20);
            lblTitle.Size = new Size(530, 34);
            this.Controls.Add(lblTitle);

            lblSub = new Label();
            lblSub.Text = "Biên Kịch AI · Lồng Tiếng Đa Nhân Vật · Dựng MP4 GPU & -14 LUFS (https://comic.io.vn)";
            lblSub.Font = new Font("Segoe UI", 9.2f, FontStyle.Regular);
            lblSub.ForeColor = Color.FromArgb(203, 213, 225);
            lblSub.Location = new Point(26, 56);
            lblSub.Size = new Size(530, 24);
            this.Controls.Add(lblSub);

            lblStatus = new Label();
            lblStatus.Text = installerMode
                ? ("Thư mục cài đặt: " + this.targetDir)
                : "Đang kiểm tra môi trường vận hành...";
            lblStatus.Font = new Font("Segoe UI", 9f, FontStyle.Regular);
            lblStatus.ForeColor = Color.FromArgb(226, 232, 240);
            lblStatus.Location = new Point(26, 92);
            lblStatus.Size = new Size(530, 38);
            this.Controls.Add(lblStatus);

            progressBar = new ProgressBar();
            progressBar.Style = installerMode ? ProgressBarStyle.Blocks : ProgressBarStyle.Marquee;
            progressBar.Minimum = 0;
            progressBar.Maximum = 100;
            progressBar.Value = 0;
            progressBar.Location = new Point(26, 136);
            progressBar.Size = new Size(524, 22);
            this.Controls.Add(progressBar);

            if (installerMode)
            {
                chkDesktopShortcut = new CheckBox();
                chkDesktopShortcut.Text = "Tạo biểu tượng (Shortcut) ngoài màn hình Desktop";
                chkDesktopShortcut.Checked = true;
                chkDesktopShortcut.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);
                chkDesktopShortcut.ForeColor = Color.FromArgb(226, 232, 240);
                chkDesktopShortcut.Location = new Point(26, 170);
                chkDesktopShortcut.Size = new Size(460, 26);
                this.Controls.Add(chkDesktopShortcut);

                btnStartInstall = new Button();
                btnStartInstall.Text = "🚀 CÀI ĐẶT & MỞ NGAY MANGA VIDEO REVIEW STUDIO";
                btnStartInstall.Font = new Font("Segoe UI", 10.5f, FontStyle.Bold);
                btnStartInstall.BackColor = Color.FromArgb(219, 39, 119);
                btnStartInstall.ForeColor = Color.White;
                btnStartInstall.FlatStyle = FlatStyle.Flat;
                btnStartInstall.FlatAppearance.BorderSize = 0;
                btnStartInstall.Location = new Point(26, 208);
                btnStartInstall.Size = new Size(524, 46);
                btnStartInstall.Cursor = Cursors.Hand;
                btnStartInstall.Click += delegate
                {
                    btnStartInstall.Enabled = false;
                    chkDesktopShortcut.Enabled = false;
                    progressBar.Style = ProgressBarStyle.Marquee;
                    Thread worker = new Thread(RunSetupAndLaunch);
                    worker.IsBackground = true;
                    worker.Start();
                };
                this.Controls.Add(btnStartInstall);
            }
            else
            {
                this.Shown += delegate
                {
                    Thread worker = new Thread(RunSetupAndLaunch);
                    worker.IsBackground = true;
                    worker.Start();
                };
            }
        }

        private void UpdateStatus(string message)
        {
            if (this.IsDisposed) return;
            if (this.InvokeRequired)
            {
                try { this.BeginInvoke(new Action<string>(UpdateStatus), message); } catch { }
                return;
            }
            lblStatus.Text = message;
        }

        public static string FindPythonExe()
        {
            string localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string[] known = new string[]
            {
                Path.Combine(localApp, @"Programs\Python\Python312\python.exe"),
                Path.Combine(localApp, @"Programs\Python\Python311\python.exe"),
                Path.Combine(localApp, @"Programs\Python\Python310\python.exe"),
                @"C:\Python312\python.exe",
                @"C:\Python311\python.exe",
                @"C:\Python310\python.exe"
            };
            foreach (string candidate in known)
            {
                if (File.Exists(candidate) && RunHidden(candidate, "-c \"import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)\""))
                    return candidate;
            }

            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("where", "python");
                psi.CreateNoWindow = true;
                psi.UseShellExecute = false;
                psi.RedirectStandardOutput = true;
                using (Process p = Process.Start(psi))
                {
                    string output = p.StandardOutput.ReadToEnd();
                    p.WaitForExit(5000);
                    foreach (string rawLine in output.Split(new char[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries))
                    {
                        string line = rawLine.Trim();
                        if (line.ToLowerInvariant().Contains("windowsapps")) continue;
                        if (File.Exists(line) && RunHidden(line, "-c \"import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)\""))
                            return line;
                    }
                }
            }
            catch { }
            return null;
        }

        public static bool RunHidden(string fileName, string arguments)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo(fileName, arguments);
                psi.CreateNoWindow = true;
                psi.UseShellExecute = false;
                using (Process p = Process.Start(psi))
                {
                    p.WaitForExit(600000);
                    return p.ExitCode == 0;
                }
            }
            catch
            {
                return false;
            }
        }

        private void ExtractEmbeddedPayload()
        {
            Directory.CreateDirectory(this.targetDir);
            Assembly asm = Assembly.GetExecutingAssembly();
            using (Stream resStream = asm.GetManifestResourceStream("payload.zip"))
            {
                if (resStream == null)
                    throw new InvalidOperationException("Không tìm thấy gói dữ liệu nhúng payload.zip.");

                string tempZip = Path.Combine(Path.GetTempPath(), "_manga_video_review_payload_setup.zip");
                using (FileStream fs = new FileStream(tempZip, FileMode.Create, FileAccess.Write))
                {
                    resStream.CopyTo(fs);
                }

                try
                {
                    using (ZipArchive archive = ZipFile.OpenRead(tempZip))
                    {
                        foreach (ZipArchiveEntry entry in archive.Entries)
                        {
                            if (string.IsNullOrEmpty(entry.Name)) continue;
                            string destPath = Path.Combine(this.targetDir, entry.FullName);
                            string destParent = Path.GetDirectoryName(destPath);
                            if (!string.IsNullOrEmpty(destParent))
                                Directory.CreateDirectory(destParent);
                            entry.ExtractToFile(destPath, true);
                        }
                    }
                }
                finally
                {
                    try { File.Delete(tempZip); } catch { }
                }
            }
        }

        private void CreateShortcut()
        {
            try
            {
                string desktopDir = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                string lnkPath = Path.Combine(desktopDir, this.shortcutName + ".lnk");
                string launcherExe = Path.Combine(this.targetDir, "Manga-Video-Review-Studio.exe");
                if (!File.Exists(launcherExe))
                    launcherExe = Path.Combine(this.targetDir, "Chay-Video-Review-Studio.bat");

                Type shellType = Type.GetTypeFromProgID("WScript.Shell");
                if (shellType == null) return;
                dynamic shell = Activator.CreateInstance(shellType);
                dynamic shortcut = shell.CreateShortcut(lnkPath);
                shortcut.TargetPath = launcherExe;
                shortcut.WorkingDirectory = this.targetDir;
                shortcut.IconLocation = launcherExe + ",0";
                shortcut.Description = "Manga Video Review Studio (comic.io.vn)";
                shortcut.Save();
            }
            catch { }
        }

        private void RunSetupAndLaunch()
        {
            try
            {
                if (this.isInstallerMode)
                {
                    UpdateStatus("[1/4] Đang giải nén & cài đặt ứng dụng bản mới nhất vào máy tính...");
                    ExtractEmbeddedPayload();
                    if (this.chkDesktopShortcut != null && this.chkDesktopShortcut.Checked)
                        CreateShortcut();
                }

                UpdateStatus("[2/4] Đang kiểm tra môi trường Python 3.10+...");
                string pyExe = FindPythonExe();
                if (string.IsNullOrEmpty(pyExe))
                {
                    UpdateStatus("[2/4] Máy chưa cài Python. Đang tự động tải & cài đặt Python 3.11 chuẩn (25MB)...");
                    ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
                    string pySetup = Path.Combine(Path.GetTempPath(), "py311_manga_studio_setup.exe");
                    using (WebClient wc = new WebClient())
                    {
                        wc.DownloadFile("https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe", pySetup);
                    }
                    RunHidden(pySetup, "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_tcltk=1");
                    pyExe = FindPythonExe();
                    if (string.IsNullOrEmpty(pyExe))
                        throw new Exception("Không thể tự động tải Python 3.11. Vui lòng kiểm tra kết nối mạng và thử lại.");
                }

                if (!RunHidden(pyExe, "-c \"import PIL, rapidocr_onnxruntime, imageio_ffmpeg, edge_tts\""))
                {
                    UpdateStatus("[3/4] Đang cài đặt lõi Nhận Diện Đa Ngôn Ngữ, Giọng Đọc & Dựng MP4 GPU (chỉ chạy 1 lần đầu)...");
                    RunHidden(pyExe, "-m pip install --upgrade " + this.pipPackages + " --quiet");
                }

                UpdateStatus("[4/4] Đang mở giao diện Manga Video Review Studio...");
                Program.LaunchPythonGui(pyExe, this.targetDir, this.entryScript);
                this.BeginInvoke(new Action(delegate { this.Close(); }));
            }
            catch (Exception ex)
            {
                this.BeginInvoke(new Action(delegate
                {
                    progressBar.Style = ProgressBarStyle.Blocks;
                    lblStatus.Text = "Lỗi khởi tạo: " + ex.Message;
                    if (btnStartInstall != null) btnStartInstall.Enabled = true;
                    MessageBox.Show("Lỗi cài đặt: " + ex.Message, "Manga Video Review Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }));
            }
        }
    }

    public static class Program
    {
        public static void LaunchPythonGui(string pyExe, string workDir, string scriptName)
        {
            string pyDir = Path.GetDirectoryName(pyExe);
            string pyw = Path.Combine(pyDir, "pythonw.exe");
            string runner = File.Exists(pyw) ? pyw : pyExe;
            string scriptPath = Path.Combine(workDir, scriptName);

            ProcessStartInfo psi = new ProcessStartInfo(runner, "\"" + scriptPath + "\"");
            psi.WorkingDirectory = workDir;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            Process.Start(psi);
        }

        [STAThread]
        public static void Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            Assembly asm = Assembly.GetExecutingAssembly();
            bool hasEmbeddedPayload = false;
            foreach (string rn in asm.GetManifestResourceNames())
            {
                if (rn == "payload.zip") { hasEmbeddedPayload = true; break; }
            }

            string baseDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\', '/');
            string localScript = Path.Combine(baseDir, "app_video_review_studio.py");

            if (!hasEmbeddedPayload && File.Exists(localScript))
            {
                string pyExe = SplashForm.FindPythonExe();
                if (!string.IsNullOrEmpty(pyExe) && SplashForm.RunHidden(pyExe, "-c \"import PIL, rapidocr_onnxruntime, imageio_ffmpeg, edge_tts\""))
                {
                    LaunchPythonGui(pyExe, baseDir, "app_video_review_studio.py");
                    return;
                }
            }

            Application.Run(new SplashForm(hasEmbeddedPayload));
        }
    }
}
"""


def find_csc() -> Path:
    for p in CSC_CANDIDATES:
        if p.is_file():
            return p
    raise FileNotFoundError("Không tìm thấy trình biên dịch C# .NET Framework (csc.exe).")


def build_all() -> dict[str, str]:
    csc = find_csc()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        cs_file = tmp_dir / "SetupLauncher.cs"
        cs_file.write_text(CSHARP_SETUP_SOURCE, encoding="utf-8-sig")

        # 1. Biên dịch Launcher gọn nhẹ `Manga-Video-Review-Studio.exe` (không nhúng payload.zip)
        launcher_out = STUDIO_DIR / "Manga-Video-Review-Studio.exe"
        cmd_launcher = [
            str(csc),
            "/nologo",
            "/optimize+",
            "/target:winexe",
            f"/out:{launcher_out}",
            "/r:System.dll",
            "/r:System.Drawing.dll",
            "/r:System.Windows.Forms.dll",
            "/r:System.IO.Compression.dll",
            "/r:System.IO.Compression.FileSystem.dll",
            "/r:Microsoft.CSharp.dll",
        ]
        if ICON_PATH.is_file():
            cmd_launcher.append(f"/win32icon:{ICON_PATH}")
        cmd_launcher.append(str(cs_file))
        subprocess.run(cmd_launcher, check=True)

        # 2. Tạo `payload.zip` chứa toàn bộ mã nguồn Video Review Studio mới nhất + MANIFEST.sha256.json
        payload_zip = tmp_dir / "payload.zip"
        payload_hashes: dict[str, str] = {}
        with zipfile.ZipFile(payload_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for fn in PAYLOAD_FILES:
                raw = (STUDIO_DIR / fn).read_bytes()
                payload_hashes[fn] = hashlib.sha256(raw).hexdigest()
                zf.writestr(fn, raw)
            zf.writestr("MANIFEST.sha256.json", json.dumps(payload_hashes, indent=2))

        # 3. Biên dịch `Manga-Video-Review-Studio-Setup-v1.0.exe` có nhúng `payload.zip`
        setup_out = STUDIO_DIR / "Manga-Video-Review-Studio-Setup-v1.0.exe"
        cmd_setup = [
            str(csc),
            "/nologo",
            "/optimize+",
            "/target:winexe",
            f"/out:{setup_out}",
            f"/resource:{payload_zip},payload.zip",
            "/r:System.dll",
            "/r:System.Drawing.dll",
            "/r:System.Windows.Forms.dll",
            "/r:System.IO.Compression.dll",
            "/r:System.IO.Compression.FileSystem.dll",
            "/r:Microsoft.CSharp.dll",
        ]
        if ICON_PATH.is_file():
            cmd_setup.append(f"/win32icon:{ICON_PATH}")
        cmd_setup.append(str(cs_file))
        subprocess.run(cmd_setup, check=True)

        # 4. Sao chép `Setup.exe` đồng bộ sang `frontend/public/tai-ve/` và `dist/`
        pub_setup = ROOT / "frontend" / "public" / "tai-ve" / "Manga-Video-Review-Studio-Setup-v1.0.exe"
        dist_setup = ROOT / "dist" / "Manga-Video-Review-Studio-Setup-v1.0.exe"
        pub_setup.parent.mkdir(parents=True, exist_ok=True)
        dist_setup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(setup_out, pub_setup)
        shutil.copy2(setup_out, dist_setup)

        # 5. Đóng gói lại `Manga-Video-Review-Studio-v1.0.zip` chứa cả `Setup.exe` vừa biên dịch
        zip_files = PAYLOAD_FILES + ["Manga-Video-Review-Studio-Setup-v1.0.exe"]
        pub_zip = ROOT / "frontend" / "public" / "tai-ve" / "Manga-Video-Review-Studio-v1.0.zip"
        dist_zip = ROOT / "dist" / "Manga-Video-Review-Studio-v1.0.zip"
        zip_hashes: dict[str, str] = {}
        with zipfile.ZipFile(pub_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for fn in zip_files:
                raw = (STUDIO_DIR / fn).read_bytes()
                zip_hashes[fn] = hashlib.sha256(raw).hexdigest()
                zf.writestr(fn, raw)
            zf.writestr("MANIFEST.sha256.json", json.dumps(zip_hashes, indent=2))
        with zipfile.ZipFile(pub_zip, "r") as zf:
            assert zf.testzip() is None
        shutil.copy2(pub_zip, dist_zip)

        return {
            "launcher_exe": str(launcher_out),
            "launcher_bytes": str(launcher_out.stat().st_size),
            "setup_exe": str(pub_setup),
            "setup_bytes": str(pub_setup.stat().st_size),
            "setup_sha256": hashlib.sha256(pub_setup.read_bytes()).hexdigest(),
            "portable_zip": str(pub_zip),
            "portable_zip_bytes": str(pub_zip.stat().st_size),
            "portable_zip_sha256": hashlib.sha256(pub_zip.read_bytes()).hexdigest(),
        }


if __name__ == "__main__":
    info = build_all()
    print(json.dumps(info, indent=2, ensure_ascii=False))
