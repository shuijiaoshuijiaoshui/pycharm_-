# -*- coding: utf-8 -*-
"""
代码聚焦器 —— 交互版
输入一个关键词（比如"缓存"、"tokenizer"、"predict"），
它会把项目里跟这个词相关的代码块全部挑出来，高亮显示，其余部分变暗。

用法：双击 code-focus.bat（或直接 python ask.py）
"""
import glob
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = HERE / "default_project.txt"
OUT = HERE / "output"

# ------------------------------------------------------------------ 找 PyCharm
# 按顺序试：
#   1. 环境变量 PYCHARM_EXE
#   2. 工具目录下的 pycharm_path.txt（里面写一行 pycharm64.exe 的完整路径）
#   3. 自动搜索常见安装位置（JetBrains Toolbox / Program Files / snap / macOS）
# 找不到也不影响搜索，只是"跳转 PyCharm"按钮不可用。
PYCHARM_ENV = "PYCHARM_EXE"
PYCHARM_CFG = HERE / "pycharm_path.txt"
PYCHARM_GLOBS = [
    r"C:\Program Files\JetBrains\PyCharm*\bin\pycharm64.exe",
    r"C:\Program Files (x86)\JetBrains\PyCharm*\bin\pycharm64.exe",
    r"C:\Users\*\AppData\Local\Programs\PyCharm*\bin\pycharm64.exe",
    r"C:\Users\*\AppData\Local\JetBrains\Toolbox\apps\PyCharm*\*\*\bin\pycharm64.exe",
    r"C:\Users\*\AppData\Local\JetBrains\Toolbox\scripts\pycharm64.exe",
    r"D:\*\PyCharm*\bin\pycharm64.exe",
    r"E:\*\PyCharm*\bin\pycharm64.exe",
    r"F:\*\PyCharm*\bin\pycharm64.exe",
    r"C:\*\*\PyCharm*\bin\pycharm64.exe",
    r"D:\*\*\PyCharm*\bin\pycharm64.exe",
    r"E:\*\*\PyCharm*\bin\pycharm64.exe",
    r"F:\*\*\PyCharm*\bin\pycharm64.exe",

    "/opt/pycharm*/bin/pycharm.sh",
    "/snap/pycharm-*/current/bin/pycharm.sh",
    "/usr/local/bin/pycharm*",
    "/Applications/PyCharm*.app/Contents/MacOS/pycharm",
    "~/Applications/PyCharm*.app/Contents/MacOS/pycharm",
    "~/pycharm*/bin/pycharm.sh",
]


def _scan_pycharm(max_depth=4, budget=3.0):
    """实在找不到时，在盘里翻一遍（限制深度和时间，免得卡住）。"""
    import string
    import time
    t0 = time.time()
    skip = {"windows", "$recycle.bin", "system volume information", "recovery",
            "perflogs", "programdata", "node_modules", ".git", "__pycache__",
            ".venv", "venv", "env", "temp", "tmp", "site-packages", "lib",
            "libs", "cache", "logs", "anaconda3", "miniconda3", "miniforge3"}
    roots = []
    if os.name == "nt":
        for ch in string.ascii_uppercase:
            d = ch + ":\\"
            if os.path.exists(d):
                roots.append(d)
    else:
        roots = ["/opt", "/usr/local", os.path.expanduser("~")]

    def hit(base):
        for name in ("pycharm64.exe", "pycharm.sh", "pycharm"):
            f = os.path.join(base, "bin", name)
            if os.path.isfile(f):
                return f
        return None

    def walk(base, depth):
        if depth > max_depth or time.time() - t0 > budget:
            return None
        try:
            ents = [e for e in os.scandir(base) if e.is_dir(follow_symlinks=False)]
        except Exception:
            return None
        for e in ents:
            if e.name.lower().startswith("pycharm"):
                r = hit(e.path)
                if r:
                    return r
        for e in ents:
            n = e.name.lower()
            if n in skip or n.startswith("$") or n.startswith("."):
                continue
            r = walk(e.path, depth + 1)
            if r:
                return r
        return None

    for root in roots:
        r = walk(root, 0)
        if r:
            return r
    return None


_PYCHARM_MEMO = []


def pycharm_exe(remember=True):
    """返回 PyCharm 可执行文件路径；找不到返回 None。找到会记进 pycharm_path.txt。"""
    if _PYCHARM_MEMO:
        return _PYCHARM_MEMO[0]
    found = None
    p = os.environ.get(PYCHARM_ENV, "").strip().strip('"')
    if p and Path(p).exists():
        found = p
    if not found:
        try:
            if PYCHARM_CFG.exists():
                p = PYCHARM_CFG.read_text(encoding="utf-8").strip().strip('"')
                if p and Path(p).exists():
                    found = p
        except Exception:
            pass
    if not found:
        for pat in PYCHARM_GLOBS:
            try:
                hits = sorted(glob.glob(os.path.expanduser(pat)), reverse=True)
            except Exception:
                continue
            for h in hits:
                if Path(h).exists():
                    found = h
                    break
            if found:
                break
    if not found:
        found = _scan_pycharm()
    _PYCHARM_MEMO.append(found)
    if found and remember:
        try:
            PYCHARM_CFG.write_text(found, encoding="utf-8")
        except Exception:
            pass
    return found


BRIDGE_PORT = 8765
BRIDGE_URL = None


def open_in_pycharm(path, line):
    exe = pycharm_exe()
    if not exe or not Path(path).exists():
        return False
    subprocess.Popen([exe, "--line", str(line), str(path)])
    return True


class _Bridge(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        if u.path != "/open":
            self.send_response(204)
            self.end_headers()
            return
        p = qs.get("p", [""])[0]
        try:
            line = int(qs.get("l", ["1"])[0])
        except ValueError:
            line = 1
        ok = open_in_pycharm(p, line)
        if ok:
            msg, color = ("✓ 已经在 PyCharm 打开 %s 第 %d 行" % (Path(p).name, line)), "#7ee787"
        else:
            msg, color = "✗ 打开失败，路径可能不对", "#ff6b6b"
        body = ("<html><head><meta charset='utf-8'><title>已跳转</title></head>"
                "<body style='background:#14161a;color:%s;font-family:Microsoft YaHei;"
                "padding:40px'><h2>%s</h2>"
                "<p style='color:#8b949e'>这个标签页可以关掉，回去看高亮页面就行。</p>"
                "</body></html>" % (color, msg)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class _Server(socketserver.TCPServer):
    allow_reuse_address = True


def start_bridge():
    global BRIDGE_URL
    if BRIDGE_URL:
        return BRIDGE_URL
    try:
        srv = _Server(("127.0.0.1", BRIDGE_PORT), _Bridge)
    except OSError:
        return None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    BRIDGE_URL = "http://127.0.0.1:%d" % BRIDGE_PORT
    return BRIDGE_URL


def load_project():
    if CFG.exists():
        try:
            t = CFG.read_text(encoding="utf-8").strip().strip('"')
        except Exception:
            t = ""
        if t and Path(t).exists():
            return t
    return None


def save_project(p):
    CFG.write_text(p, encoding="utf-8")


def safe_name(kw):
    return (re.sub(r'[\\/:*?"<>|]', "_", kw)[:40] or "result")


def run_search(kw, project):
    env = dict(os.environ)
    if BRIDGE_URL:
        env["CODEFOCUS_BRIDGE"] = BRIDGE_URL
    r = subprocess.run([sys.executable, str(HERE / "code_focus.py"), kw, "-p", project],
                       cwd=str(HERE), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    out = (r.stdout or "") + (r.stderr or "")
    jpath = None
    for line in out.splitlines():
        if line.startswith("JSON: "):
            jpath = line[6:].strip()
    blocks = []
    if jpath and Path(jpath).exists():
        try:
            blocks = json.loads(Path(jpath).read_text(encoding="utf-8"))
        except Exception:
            blocks = []
    return blocks, out


def banner(project):
    print()
    print("=" * 66)
    print("  代码聚焦器  —— 输入关键词，直接看相关代码（其余变暗）")
    print("=" * 66)
    print("  当前项目：%s" % project)
    print("  p = 换项目    q = 退出")
    print("-" * 66)


def show_blocks(blocks):
    print()
    print("  #   文件                                 代码块                     行范围     命中词")
    print("  " + "-" * 92)
    prev_exp = False
    for b in blocks:
        exp = not (b.get("stage") == "原词" or b.get("kw_hit"))
        if exp and not prev_exp:
            print("  " + "-" * 92)
            print("  下面这些没写原词，只是命中了自动扩展出来的英文写法：")
        prev_exp = exp
        print("  %-3d %-34s %-25s %-10s %s%s"
              % (b["rank"], str(b["file"])[:34], str(b["name"])[:25],
                 "%d-%d" % (b["start"], b["end"]),
                 "扩: " if exp else "",
                 "、".join(b.get("terms", [])[:3])))
    print("  " + "-" * 92)


def jump_to(block):
    exe = pycharm_exe()
    if exe:
        subprocess.Popen([exe, "--line", str(block["start"]), block["path"]])
        print("[OK] 已在 PyCharm 打开 %s 第 %d 行" % (block["file"], block["start"]))
    else:
        print("[!] 没找到 pycharm64.exe，手动打开：%s:%d" % (block["path"], block["start"]))


def ask_project_first_time():
    """第一次使用：让用户粘一个项目路径，并记住它。"""
    print()
    print("=" * 66)
    print("  代码聚焦器 —— 第一次使用，先告诉我你要看哪个项目")
    print("=" * 66)
    print("  把项目文件夹的完整路径粘进来，例如：")
    print(r"     C:\code\my-project            （Windows）")
    print("     /home/me/code/my-project      （Mac / Linux）")
    print("  小技巧：在文件管理器里进到项目文件夹，点一下地址栏就能复制路径。")
    print("-" * 66)
    while True:
        try:
            p = input("项目路径 > ").strip().strip('"').strip("'")
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not p:
            continue
        if Path(p).exists():
            save_project(p)
            print("[OK] 记住了，下次打开直接就是这个项目。")
            return p
        print("[X] 这个路径不存在，再试一次（Ctrl+C 退出）")


def main():
    project = load_project()
    if not project:
        project = ask_project_first_time()
    if not project:
        return
    start_bridge()
    banner(project)
    last = []
    while True:
        try:
            sel = input("\n想看哪部分代码？(关键词 / 编号跳PyCharm / p 换项目 / q 退出) > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not sel:
            continue
        low = sel.lower()
        if low in ("q", "quit", "exit"):
            break
        if low == "p":
            newp = input("把项目路径粘进来 > ").strip().strip('"')
            if newp and Path(newp).exists():
                project = newp
                save_project(newp)
                print("[OK] 项目已切换：%s" % project)
            else:
                print("[X] 路径不存在，保持原项目")
            continue
        if sel.isdigit():
            hit = next((b for b in last if b["rank"] == int(sel)), None)
            if hit:
                jump_to(hit)
            else:
                print("[X] 还没有编号 %s，先搜一个关键词吧" % sel)
            continue

        print("\n正在搜索「%s」……（浏览器会自动弹出高亮页面）" % sel)
        blocks, out = run_search(sel, project)
        last = blocks
        if not blocks:
            print("[!] 没找到「%s」。" % sel)
            for line in out.strip().splitlines():
                if "没有找到" in line or "模糊匹配" in line:
                    print("    " + line.strip())
            print("    换个更短、更核心的词试试（中文英文都行，比如 缓存 / cache / 分词 / 标签）。")
            continue
        show_blocks(blocks)
        print("  浏览器里已经打开高亮页面（黄色 = 命中的行，整块就是完整函数/类）。")
        print("  ★ 网页里点代码块标题右边的「在 PyCharm 打开」→ PyCharm 直接跳过去。")
        print("  输入上面任意编号 → 也能跳 PyCharm；再输个关键词 → 继续搜；q → 退出。")
    print("\n再见。")


if __name__ == "__main__":
    main()
