using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Threading;
using System.Windows.Forms;

internal static class DesktopLauncher
{
    internal static readonly string Root = Directory.GetParent(AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar)).Parent.FullName;
    internal static readonly string LogPath = Path.Combine(Root, "data", "logs", "desktop-startup.log");

    internal static Process Start(bool openBrowser, StringBuilder output)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(LogPath));
        Process process = new Process();
        process.StartInfo = new ProcessStartInfo {
            FileName = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "WindowsPowerShell", "v1.0", "powershell.exe"),
            Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + Path.Combine(Root, "scripts", "start-local.ps1") + "\"" + (openBrowser ? " -OpenBrowser" : ""),
            WorkingDirectory = Root, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true, WindowStyle = ProcessWindowStyle.Hidden
        };
        DataReceivedEventHandler collect = delegate(object sender, DataReceivedEventArgs e) { if (e.Data != null) lock (output) output.AppendLine(e.Data); };
        process.OutputDataReceived += collect; process.ErrorDataReceived += collect;
        process.Start(); process.BeginOutputReadLine(); process.BeginErrorReadLine();
        return process;
    }

    [STAThread]
    private static int Main(string[] args)
    {
        bool acquired;
        using (Mutex mutex = new Mutex(true, "Local\\CreatorRadarDesktopStartup", out acquired)) {
            if (!acquired) return 0;
            try {
                if (args.Length == 1 && args[0] == "--check") {
                    StringBuilder output = new StringBuilder();
                    using (Process process = Start(false, output)) {
                        process.WaitForExit(); File.WriteAllText(LogPath, output.ToString(), Encoding.UTF8);
                        return process.ExitCode;
                    }
                }
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                if (args.Length == 1 && args[0] == "--render-preview") {
                    using (StartupWindow window = new StartupWindow(true)) {
                        window.Opacity = 0; window.ShowInTaskbar = false;
                        window.Show(); Application.DoEvents();
                        using (Bitmap preview = new Bitmap(window.Width, window.Height)) {
                            window.DrawToBitmap(preview, new Rectangle(0, 0, window.Width, window.Height));
                            preview.Save(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "preview.png"));
                        }
                    }
                    return 0;
                }
                Application.Run(new StartupWindow());
                return 0;
            } catch (Exception e) {
                MessageBox.Show("无法启动工作台。\n" + e.Message, "Creator Radar", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            } finally { mutex.ReleaseMutex(); }
        }
    }
}

internal sealed class StartupWindow : Form
{
    private Process process;
    private readonly StringBuilder output = new StringBuilder();
    private readonly System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer();
    private bool finished;

    internal StartupWindow(bool previewOnly = false)
    {
        Text = "Creator Radar 工作台"; StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false;
        ClientSize = new Size(440, 218); BackColor = Color.FromArgb(246, 249, 245);
        Font = new Font("Microsoft YaHei UI", 10); AutoScaleMode = AutoScaleMode.Dpi;
        Icon = new Icon(Path.Combine(DesktopLauncher.Root, "assets", "creator-radar.ico"));
        PictureBox logo = new PictureBox { Left = 28, Top = 30, Width = 56, Height = 56, SizeMode = PictureBoxSizeMode.Zoom };
        logo.Image = Image.FromFile(Path.Combine(DesktopLauncher.Root, "assets", "creator-radar.png"));
        Controls.Add(logo);
        Controls.Add(new Label { Left = 100, Top = 30, Width = 310, Height = 32, Text = "Creator Radar", Font = new Font("Segoe UI", 19, FontStyle.Bold), ForeColor = Color.FromArgb(25, 59, 53) });
        Controls.Add(new Label { Left = 102, Top = 69, Width = 310, Height = 28, Text = "正在准备你的本地工作台…", ForeColor = Color.FromArgb(92, 115, 101) });
        Controls.Add(new ProgressBar { Left = 30, Top = 122, Width = 380, Height = 5, Style = ProgressBarStyle.Marquee, MarqueeAnimationSpeed = 25 });
        Controls.Add(new Label { Left = 30, Top = 151, Width = 385, Height = 48, Text = "服务就绪后自动打开页面。\n关闭此窗口可隐藏启动进度。", ForeColor = Color.FromArgb(110, 129, 118), Font = new Font("Microsoft YaHei UI", 9) });
        timer.Interval = 200; timer.Tick += CheckCompletion;
        Shown += delegate { if (previewOnly) return; try { process = DesktopLauncher.Start(true, output); timer.Start(); } catch (Exception e) { Fail(e.Message); } };
        FormClosing += delegate(object sender, FormClosingEventArgs e) { if (!finished) { e.Cancel = true; Hide(); } };
    }

    private void CheckCompletion(object sender, EventArgs args)
    {
        if (!process.HasExited) return;
        timer.Stop(); process.WaitForExit();
        try { File.WriteAllText(DesktopLauncher.LogPath, output.ToString(), Encoding.UTF8); }
        catch (IOException) { }
        int code = process.ExitCode; process.Dispose();
        if (code != 0) { Fail("请先确认 Docker Desktop 已启动，再重新打开工作台。\n如果仍失败，请查看日志：\n" + DesktopLauncher.LogPath); return; }
        finished = true; Close();
    }

    private void Fail(string message)
    {
        timer.Stop(); finished = true;
        MessageBox.Show(message, "工作台未能启动", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        Close();
    }
}
