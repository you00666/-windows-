import ctypes
import sys
import os
import threading
import subprocess
import winreg
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

# ============================================================
# 👇 【1. 图标生成函数】
# ============================================================
def create_custom_icon():
    """动态生成高保真的‘开关切换’图标"""
    icon = tk.PhotoImage(width=64, height=64)
    
    # 1. 绘制浅蓝色圆角矩形背景
    bg_color = "#89cceb"
    for x in range(64):
        for y in range(64):
            # 模拟圆角效果 (圆角半径 8px)
            if (x < 8 or x >= 56) and (y < 8 or y >= 56):
                continue
            icon.put(bg_color, (x, y))

    # 2. 绘制“开启”状态（上：蓝色底 + 白色圆点）
    on_bg_color = "#2a79ff"
    on_knob_color = "#ffffff"
    for y in range(10, 31):
        for x in range(6, 58):
            icon.put(on_bg_color, (x, y))
    for x in range(64):
        for y in range(64):
            if 11 <= x <= 21 and 15 <= y <= 25:
                if (x-16)**2 + (y-20)**2 <= 36:
                    icon.put(on_knob_color, (x, y))

    # 3. 绘制“关闭”状态（下：红色底 + 白色圆点）
    off_bg_color = "#ff2a2a"
    off_knob_color = "#ffffff"
    for y in range(34, 55):
        for x in range(6, 58):
            icon.put(off_bg_color, (x, y))
    for x in range(64):
        for y in range(64):
            if 43 <= x <= 53 and 39 <= y <= 49:
                if (x-48)**2 + (y-44)**2 <= 36:
                    icon.put(off_knob_color, (x, y))

    return icon

# ============================================================
# 👇 【2. 主程序类】（这部分代码保持不变）
# ============================================================
class Win11UpdateGUI:
    """Windows 11 更新管理器 - 图形界面版"""
    UPDATE_SERVICES = ["wuauserv", "UsoSvc", "WaaSMedicSvc", "dosvc"]
    REG_PATH_AU = r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
    REG_PATH_WU = r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
    PAUSE_REG = r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Windows 10/11 更新管理工具V3.0")
        self.root.geometry("560x490")
        self.root.resizable(False, False)
        self.is_admin = self._check_admin()
        self._build_ui()
        if self.is_admin:
            self._log("✅ 程序已启动，就绪。", "success")
        else:
            self._log("❌ 未检测到管理员权限！请右键以管理员身份运行此程序。", "error")
            self.btn_disable.config(state="disabled")
            self.btn_enable.config(state="disabled")
            self.btn_refresh.config(state="disabled")

    def _build_ui(self):
        style = ttk.Style()
        style.configure("Action.TButton", padding=8, font=("Microsoft YaHei UI", 10))
        style.configure("Status.TLabel", font=("Microsoft YaHei UI", 9))

        # --- 按钮区域 ---
        btn_frame = ttk.Frame(self.root, padding=15)
        btn_frame.pack(fill="x")
        self.btn_disable = ttk.Button(btn_frame, text="🔴 关闭更新", style="Action.TButton", command=lambda: self._run_task(self.disable_updates))
        self.btn_disable.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.btn_enable = ttk.Button(btn_frame, text="🟢 恢复更新", style="Action.TButton", command=lambda: self._run_task(self.enable_updates))
        self.btn_enable.pack(side="left", expand=True, fill="x", padx=5)
        self.btn_refresh = ttk.Button(btn_frame, text="📊 刷新状态", style="Action.TButton", command=lambda: self._run_task(self.check_status))
        self.btn_refresh.pack(side="left", expand=True, fill="x", padx=(5, 0))

        # --- 状态栏 ---
        status_frame = ttk.Frame(self.root, padding=(15, 0))
        status_frame.pack(fill="x")
        self.status_label = ttk.Label(status_frame, text="状态: 未知", style="Status.TLabel")
        self.status_label.pack(anchor="w")

        # --- 日志区域 ---
        log_frame = ttk.Frame(self.root, padding=15)
        log_frame.pack(fill="both", expand=True)
        
        # 👇 【已修改】这里将背景色改为 Win10 终端经典蓝
        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap="word", font=("Consolas", 9),
            bg='navy',           # 修改1：背景色改为海军蓝
            fg='#CCCCCC',        # 修改2：默认字体颜色改为浅灰（保证对比度）
            insertbackground="white",
            relief="flat", borderwidth=1
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.config(state="disabled")

        # 日志颜色标签
        # 👇 【已修改】为了适应深蓝背景，调整了部分日志的高亮颜色
        self.log_text.tag_configure("success", foreground="#6ec96e")  # 绿色保持，深蓝底色下很清晰
        self.log_text.tag_configure("warning", foreground="#FFFF00")  # 修改3：警告色改为纯黄 (原色在深蓝下易偏绿)
        self.log_text.tag_configure("error", foreground="#FF6666")    # 修改4：错误色改为浅红 (原色太暗)
        self.log_text.tag_configure("info", foreground="#66B2FF")     # 修改5：信息色改为亮蓝

    def _log(self, message: str, level: str = "info"):
        def _append():
            self.log_text.config(state="normal")
            self.log_text.insert("end", message + "\n", level)
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.root.after(0, _append)

    def _set_status(self, text: str):
        self.root.after(0, lambda: self.status_label.config(text=f"状态: {text}"))

    def _set_buttons(self, state: str):
        for btn in (self.btn_disable, self.btn_enable, self.btn_refresh):
            self.root.after(0, lambda b=btn: b.config(state=state))

    def _run_task(self, func):
        if not self.is_admin and func != self.check_status:
            messagebox.showwarning("权限不足", "请以管理员身份运行此程序！")
            return
        confirm_map = {
            self.disable_updates: ("确认关闭", "确定要关闭 Windows 11 更新吗？\n\n关闭后系统将不再接收安全补丁。"),
            self.enable_updates: ("确认恢复", "确定要恢复 Windows 11 更新吗？"),
        }
        if func in confirm_map:
            title, msg = confirm_map[func]
            if not messagebox.askyesno(title, msg):
                return
        self._set_buttons("disabled")
        self._set_status("⏳ 执行中...")
        def worker():
            try:
                func()
            except Exception as e:
                self._log(f"❌ 发生异常: {e}", "error")
            finally:
                self._set_buttons("normal")
                self._set_status("✅ 就绪")
        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _check_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    @staticmethod
    def _run_cmd(cmd: str) -> tuple[bool, str]:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return r.returncode == 0, r.stdout + r.stderr
        except Exception as e:
            return False, str(e)

    def _set_reg_dword(self, path: str, name: str, value: int) -> bool:
        try:
            key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY)
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
            winreg.CloseKey(key)
            return True
        except Exception as e:
            self._log(f"   ⚠️ 注册表写入失败 [{name}]: {e}", "warning")
            return False

    def _delete_reg_key(self, path: str) -> bool:
        try:
            winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE, path, winreg.KEY_WOW64_64KEY, 0)
            return True
        except FileNotFoundError:
            return True
        except Exception as e:
            self._log(f"   ⚠️ 注册表删除失败: {e}", "warning")
            return False

    def disable_updates(self):
        self._log("\n🔧 开始关闭 Windows 11 更新...", "info")
        self._log("📌 [1/3] 禁用更新相关服务...")
        for svc in self.UPDATE_SERVICES:
            self._run_cmd(f"net stop {svc} /y 2>nul")
            ok, _ = self._run_cmd(f"sc config {svc} start= disabled")
            self._log(f"   {'✅' if ok else '⚠️'} {svc}", "success" if ok else "warning")
        self._log("📌 [2/3] 配置组策略注册表...")
        for name, val in {"NoAutoUpdate": 1, "AUOptions": 1, "UseWUServer": 1}.items():
            ok = self._set_reg_dword(self.REG_PATH_AU, name, val)
            self._log(f"   {'✅' if ok else '❌'} {name} = {val}", "success" if ok else "error")
        self._log("📌 [3/3] 阻止更新访问 & 设置暂停...")
        ok = self._set_reg_dword(self.REG_PATH_WU, "DisableWindowsUpdateAccess", 1)
        self._log(f"   {'✅' if ok else '❌'} DisableWindowsUpdateAccess", "success" if ok else "error")
        pause_cmds = [
            f'reg add "HKLM\\{self.PAUSE_REG}" /v PauseUpdatesStartTime /t REG_SZ /d "2099-01-01T00:00:00Z" /f 2>nul',
            f'reg add "HKLM\\{self.PAUSE_REG}" /v PauseUpdatesExpiryTime /t REG_SZ /d "2099-01-01T00:00:00Z" /f 2>nul',
        ]
        for cmd in pause_cmds:
            self._run_cmd(cmd)
        self._log("   ✅ 暂停更新时间已设为 2099 年", "success")
        self._log("\n✅ Windows 11 更新已成功关闭！建议重启电脑。", "success")

    def enable_updates(self):
        self._log("\n🔧 开始恢复 Windows 11 更新...", "info")
        self._log("📌 [1/3] 清除组策略注册表...")
        self._delete_reg_key(self.REG_PATH_AU)
        self._delete_reg_key(self.REG_PATH_WU)
        self._log("   ✅ 组策略注册表已清除", "success")
        self._log("📌 [2/3] 恢复更新相关服务...")
        for svc in self.UPDATE_SERVICES:
            self._run_cmd(f"sc config {svc} start= demand")
            ok, _ = self._run_cmd(f"net start {svc} 2>nul")
            self._log(f"   {'✅' if ok else '⚠️'} {svc}", "success" if ok else "warning")
        self._log("📌 [3/3] 清除暂停更新设置...")
        for v in ("PauseUpdatesStartTime", "PauseUpdatesExpiryTime"):
            self._run_cmd(f'reg delete "HKLM\\{self.PAUSE_REG}" /v {v} /f 2>nul')
        self._log("   ✅ 暂停更新设置已清除", "success")
        self._log("\n✅ Windows 11 更新已恢复！建议重启后手动检查更新。", "success")

    def check_status(self):
        self._log("\n📊 正在检查更新状态...", "info")
        running_count = 0
        self._log("📌 服务状态:")
        for svc in self.UPDATE_SERVICES:
            ok, out = self._run_cmd(f"sc query {svc}")
            state = "未知"
            if ok:
                for line in out.splitlines():
                    if "STATE" in line:
                        state = line.split(":")[-1].strip()
                        break
            is_running = "RUNNING" in state.upper()
            if is_running:
                running_count += 1
            icon = "🟢" if is_running else "🔴"
            self._log(f"   {icon} {svc}: {state}", "success" if is_running else "warning")
        self._log("📌 组策略状态:")
        try:
            key = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, self.REG_PATH_AU, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            no_auto, _ = winreg.QueryValueEx(key, "NoAutoUpdate")
            winreg.CloseKey(key)
            disabled = no_auto == 1
            self._log(f"   {'🔴 已禁用' if disabled else '🟢 未禁用'} 自动更新", "warning" if disabled else "success")
        except FileNotFoundError:
            self._log("   🟢 未配置组策略 (更新正常)", "success")
        except Exception:
            self._log("   ❓ 无法读取注册表", "error")
        summary = "🔴 更新已关闭" if running_count == 0 else f"🟡 {running_count}/{len(self.UPDATE_SERVICES)} 个服务运行中"
        self._log(f"\n📋 总结: {summary}", "info")
        self._set_status(summary)

# ============================================================
# 👇 【3. 主程序入口】
# ============================================================
def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    
    # 👇 【关键：在这里加载自定义生成的开关图标】
    custom_icon = create_custom_icon()
    root.iconphoto(True, custom_icon)

    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20,
            ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
        )
    except Exception:
        pass

    app = Win11UpdateGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
