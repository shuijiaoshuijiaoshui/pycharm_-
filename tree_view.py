# -*- coding: utf-8 -*-
"""
项目结构树 + 文件中文说明
给 code_focus.py 生成的网页用：画出整个项目的目录框架，
每个文件标出"在哪、多大、干什么用"。

中文说明的来源（按优先级）：
  1. .py 文件开头的文档字符串（docstring）第一句有意义的话
  2. .html 的 <title>
  3. .md 的第一个标题
  4. 文件里的第一条注释
  5. 按文件名/扩展名兜底（requirements.txt → Python 依赖清单 之类）
"""
import html as html_mod
import io
import os
import re
from pathlib import Path

SKIP_DIRS = {".git", ".idea", "__pycache__", ".venv", "venv", "env", "node_modules",
             "dist", "build", ".mypy_cache", ".pytest_cache", ".ipynb_checkpoints",
             "log", "logs", ".git-rewrite", ".vscode"}

TEXT_EXT = {".py", ".html", ".htm", ".js", ".css", ".yaml", ".yml", ".md", ".toml",
            ".txt", ".json", ".csv", ".sh", ".conf", ".ini", ".cfg", ".sql",
            ".bat", ".ps1", ".env", ".properties"}

BADGE = {
    ".py": ("PY", "#3572A5"), ".html": ("HTML", "#c9510c"), ".htm": ("HTML", "#c9510c"),
    ".js": ("JS", "#a89100"), ".css": ("CSS", "#563d7c"),
    ".yaml": ("YML", "#a01f24"), ".yml": ("YML", "#a01f24"),
    ".md": ("MD", "#3d7ea6"), ".toml": ("TOML", "#8a5a2b"),
    ".txt": ("TXT", "#5c6370"), ".json": ("JSON", "#6b7484"), ".csv": ("CSV", "#6b7484"),
    ".sh": ("SH", "#4c8b2b"), ".conf": ("CONF", "#5c6370"), ".ini": ("INI", "#5c6370"),
    ".bat": ("BAT", "#4c8b2b"), ".ps1": ("PS1", "#2b5f9e"), ".sql": ("SQL", "#b5761f"),
}

# 目录作用（手工整理，这才是"项目框架"真正有价值的部分）
DIR_DESC = {
    "a2a_server": "A2A 协议服务层 —— 把能力包装成 A2A agent 对外提供",
    "a2a_server/a2a_weather.py": "",
    "mcp_server": "MCP 协议服务层 —— 把工具包装成 MCP server（streamable HTTP）",
    "mcp_tools": "工具实现层 —— 高德/博查/飞常准/和风天气等外部 API 的具体封装",
    "core": "核心业务层 —— 认证、缓存、记忆、Prompt、工具注册中心",
    "utils": "基础设施层 —— 配置、日志、MySQL/Milvus 连接封装",
    "data_init": "数据初始化 —— 建库建表、灌测试数据、一键清空",
    "deploy": "部署 —— Docker、Nginx、依赖清单",
    "static": "前端 —— 项目导览站页面",
    "static/assets": "前端静态资源 —— JS 脚本",
    "static/modules": "导览站的分模块说明页",
    "test": "测试 —— 系统集成、业务、压测",
    "test/压力测试": "压力测试 —— 脚本、报告、样本数据",
    "scripts": "辅助脚本",
    "前置知识": "学习笔记 —— uv / Function Call / 异步编程",
    "前置知识/1-uv环境管理工具": "uv 环境管理命令备忘",
    "前置知识/2-Function Call": "Function Call 的三种写法示例",
    "前置知识/3-异步编程": "asyncio 异步编程示例",
}

# 文件名兜底说明
NAME_FALLBACK = [
    ("requirements_all_packages", "全部依赖的完整清单（含间接依赖）"),
    ("requirements", "Python 依赖清单（pip install -r 用）"),
    ("pyproject.toml", "项目配置 —— 依赖与构建声明"),
    ("dockerfile", "Docker 镜像构建脚本"),
    ("docker-compose", "Docker 编排 —— 一条命令启动多个服务"),
    ("nginx.conf", "Nginx 反向代理配置"),
    ("__init__.py", "Python 包标识文件（让这个目录可以被 import）"),
    (".gitignore", "Git 忽略规则 —— 哪些文件不进版本库"),
    ("location_id.csv", "和风天气城市编码对照表"),
    ("renderflow.js", "导览站的流程动画脚本（画请求流转图）"),
    ("test_samples.json", "压测用的测试样本数据"),
    ("压力测试提示词", "压测用的提示词素材"),
]

EXT_FALLBACK = {
    ".py": "Python 源码", ".html": "网页页面", ".js": "前端脚本", ".css": "样式表",
    ".md": "Markdown 文档", ".yaml": "YAML 配置", ".yml": "YAML 配置",
    ".toml": "TOML 配置", ".txt": "文本文件", ".json": "JSON 数据",
    ".csv": "CSV 数据表", ".sh": "Shell 脚本", ".conf": "配置文件",
    ".bat": "Windows 批处理脚本", ".ps1": "PowerShell 脚本",
    ".sql": "SQL 语句", ".ini": "INI 配置",
}

_DECOR = re.compile(r"^[\s=\-*#/_~\.\+]+$")
_DOC_RE = re.compile(r'\A(?:[ \t]*#[^\n]*\n|[ \t]*\n)*[ \t]*(?:"""(?P<a>.*?)"""|\'\'\'(?P<b>.*?)\'\'\')', re.S)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)


def _clean(s):
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(todo|TODO|Todo)\s*[:：]?\s*", "", s)
    s = re.sub(r"^(需求|目标|项目目标|备注|说明|注|本文件|该文件|本模块|该模块)\s*[:：]\s*", "", s)
    s = s.strip(" -—=*#")
    return s[:88]


def _first_meaningful(text):
    for line in text.splitlines():
        s = line.strip()
        if not s or _DECOR.match(s):
            continue
        return _clean(s)
    return ""


def describe_file(path: Path):
    """抽这个文件的中文说明。"""
    try:
        text = io.open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""
    ext = path.suffix.lower()
    head = text[:6000]

    if ext == ".py":
        m = _DOC_RE.match(head)
        if m:
            d = m.group("a") or m.group("b") or ""
            got = _first_meaningful(d)
            if got:
                return got
    elif ext in (".html", ".htm"):
        m = _TITLE_RE.search(head)
        if m:
            t = _clean(re.sub(r"<[^>]+>", "", m.group(1)))
            if t and t.lower() not in ("document", "untitled"):
                return t

    if ext == ".md":
        for line in head.splitlines():
            if line.strip().startswith("#"):
                got = _clean(line.strip().lstrip("#"))
                if got:
                    return got

    # 通用：第一条注释
    for line in head.splitlines()[:50]:
        s = line.strip()
        if s.startswith("<!--"):
            got = _clean(re.sub(r"<!--|-->", "", s))
            if got and not _DECOR.match(got):
                return got
        if (s.startswith("#") or s.startswith("//")) and not _DECOR.match(s):
            got = _clean(s.lstrip("#/"))
            if got:
                return got
    return ""


def fallback_desc(path: Path):
    low = path.name.lower()
    # 和风天气的三个接口测试脚本，按名字分别说明
    if low.startswith("test_和风天气_"):
        what = path.stem.replace("test_和风天气_", "")
        return "和风天气接口测试：%s" % what
    for key, d in NAME_FALLBACK:
        if key in low:
            return d
    return EXT_FALLBACK.get(path.suffix.lower(), "项目文件")


def human_size(n):
    if n < 1024:
        return "%d B" % n
    if n < 1024 * 1024:
        return "%.1f KB" % (n / 1024.0)
    return "%.1f MB" % (n / 1024.0 / 1024.0)


def _rel(p, root):
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except Exception:
        return p.name


def build_tree(root, skip_dirs=None):
    """把项目目录扫成一棵树。"""
    root = Path(root)
    skip = set(SKIP_DIRS) | set(skip_dirs or ())

    def walk(d):
        try:
            entries = sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except Exception:
            return []
        out = []
        for p in entries:
            if p.is_dir():
                if p.name in skip or p.name.startswith("."):
                    continue
                kids = walk(p)
                if not kids:
                    continue
                desc = DIR_DESC.get(_rel(p, root), "")
                if not desc and p.parent.name == "前置知识":
                    m = re.match(r"^\d+\s*[-_]\s*(.+)$", p.name)
                    if m:
                        desc = "示例代码 —— %s" % m.group(1)
                out.append({"t": "d", "name": p.name, "rel": _rel(p, root),
                            "kids": kids, "n": count_files(kids),
                            "desc": desc})
            else:
                if p.suffix.lower() not in TEXT_EXT and p.name != ".gitignore":
                    continue
                try:
                    size = p.stat().st_size
                except Exception:
                    size = 0
                out.append({"t": "f", "name": p.name, "rel": _rel(p, root),
                            "path": str(p), "size": size,
                            "desc": describe_file(p) or fallback_desc(p)})
        return out

    return walk(root)


def count_files(nodes):
    n = 0
    for x in nodes:
        n += count_files(x["kids"]) if x["t"] == "d" else 1
    return n


def count_dirs(nodes):
    n = 0
    for x in nodes:
        if x["t"] == "d":
            n += 1 + count_dirs(x["kids"])
    return n


def _k(p):
    """路径统一成小写绝对形式，方便和搜索结果的路径对上。"""
    try:
        return os.path.normcase(os.path.abspath(str(p)))
    except Exception:
        return str(p)


def _esc(s):
    return html_mod.escape(str(s), quote=True)


def render_tree(root, nodes, hit_map=None, jump_fn=None):
    """生成项目结构树的 HTML。hit_map: {绝对路径: 命中次数}"""
    hit_map = hit_map or {}
    total = count_files(nodes)
    hitfiles = sum(1 for x in _iter_files(nodes) if hit_map.get(_k(x["path"])))

    rows = []
    for x in nodes:
        if x["t"] == "d":
            desc = ('<span class="ddesc">%s</span>' % _esc(x["desc"])) if x["desc"] else ""
            rows.append('<details class="dir" open><summary>'
                        '<span class="dico">▸</span>'
                        '<span class="dname">%s</span>'
                        '<span class="dcnt">%d 个文件</span>%s</summary>'
                        '<div class="kids">%s</div></details>'
                        % (_esc(x["name"]), x["n"], desc,
                           render_tree(root, x["kids"], hit_map, jump_fn)))
        else:
            b, color = BADGE.get(Path(x["name"]).suffix.lower(), ("FILE", "#5c6370"))
            hits = hit_map.get(_k(x["path"]), 0)
            hitbadge = ('<span class="fhit">本次命中 %d</span>' % hits) if hits else ""
            jump = jump_fn(x["path"], 1, "跳") if jump_fn else ""
            sdata = ("%s %s %s %s" % (x["name"], x["rel"], x["desc"], x["path"])).lower()
            drel = x["rel"].rsplit("/", 1)[0] if "/" in x["rel"] else ""
            rows.append('<div class="frow%s" data-s="%s" data-d="%s" title="%s">'
                        '<span class="badge" style="background:%s">%s</span>'
                        '<span class="fname">%s</span>'
                        '<span class="fsize">%s</span>'
                        '<span class="fdesc">%s</span>%s%s</div>'
                        % (" hit" if hits else "", _esc(sdata), _esc(drel), _esc(x["path"]),
                           color, _esc(b), _esc(x["name"]), human_size(x["size"]),
                           _esc(x["desc"]), hitbadge, jump))

    return "".join(rows)


def _iter_files(nodes):
    for x in nodes:
        if x["t"] == "d":
            for y in _iter_files(x["kids"]):
                yield y
        else:
            yield x


def render_panel(root, nodes, hit_map=None, jump_fn=None):
    """带标题栏、过滤框、展开/折叠按钮的完整面板。"""
    hit_map = hit_map or {}
    total = count_files(nodes)
    ndir = count_dirs(nodes)
    nfile = list(_iter_files(nodes))
    hitfiles = sum(1 for x in nfile if hit_map.get(x["path"]))
    rootname = Path(root).name

    chips = ['<button class="chip on" data-f="" type="button">全部</button>']
    for x in nodes:
        if x["t"] == "d":
            chips.append('<button class="chip" data-f="%s" type="button">%s<i>%d</i></button>'
                         % (_esc(x["rel"]), _esc(x["name"]), x["n"]))
    head = (
        '<div class="treehead">'
        '<div class="ttitle">项目结构：<b>%s</b></div>'
        '<div class="tmeta">共 %d 个文件 · %d 个目录%s</div>'
        '<div class="chipbar">%s</div>'
        '<div class="tbar">'
        '<input id="treefilt" type="text" placeholder="输入文件名 / 说明 过滤…">'
        '<button data-expand="1" type="button">全部展开</button>'
        '<button data-expand="0" type="button">全部折叠</button>'
        '</div></div>'
        % (_esc(rootname), total, ndir,
           (" · <b class=\"hi\">本次搜索命中 %d 个文件</b>" % hitfiles) if hitfiles else "",
           "".join(chips))
    )
    body = ('<div class="tree">%s</div>' % render_tree(root, nodes, hit_map, jump_fn))
    js = ("<script>(function(){"
          "var f=document.getElementById('treefilt');"
          "var chips=document.querySelectorAll('.chip');"
          "function applyChip(dir){"
          "var rs=document.querySelectorAll('.tree .frow');"
          "for(var i=0;i<rs.length;i++){"
          "var d=rs[i].getAttribute('data-d')||'';"
          "var ok=!dir||d===dir||d.indexOf(dir+'/')===0;"
          "rs[i].classList.toggle('hide',!ok);}"
          "var ds=document.querySelectorAll('.tree details');"
          "for(var j=0;j<ds.length;j++){ds[j].open=true;}}"
          "chips.forEach(function(c){c.addEventListener('click',function(){"
          "chips.forEach(function(x){x.classList.remove('on')});c.classList.add('on');"
          "if(f){f.value='';}applyChip(c.getAttribute('data-f')||'');});});"
          "if(f){f.addEventListener('input',function(){"
          "var q=f.value.trim().toLowerCase();"
          "if(q){chips.forEach(function(x){x.classList.remove('on')});}"
          "var ds=document.querySelectorAll('.tree details');"
          "if(q){for(var i=0;i<ds.length;i++){ds[i].open=true;}}"
          "var rs=document.querySelectorAll('.tree .frow');"
          "for(var j=0;j<rs.length;j++){"
          "var hit=!q||(rs[j].getAttribute('data-s')||'').indexOf(q)>=0;"
          "rs[j].classList.toggle('hide',!hit);}});}"
          "document.querySelectorAll('[data-expand]').forEach(function(b){"
          "b.addEventListener('click',function(){"
          "var op=b.getAttribute('data-expand')==='1';"
          "document.querySelectorAll('.tree details').forEach(function(d){d.open=op;});"
          "});});})();</script>")
    return head + body + js
