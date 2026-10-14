# -*- coding: utf-8 -*-
"""
code_focus.py —— 代码聚焦器
让"我想看 XX 相关的代码"变成一件一秒的事：搜索关键词 -> 把相关代码块挑出来 -> 高亮显示，
其余部分全部变暗（真正意义上的"高清显示"）。

用法:
  python code_focus.py 缓存                       # 在默认项目里搜索
  python code_focus.py 缓存 -p "E:/你的项目"       # 指定项目目录
  python code_focus.py 缓存 -f "app.py"            # 只搜一个文件
  python code_focus.py "cache_.*" --regex          # 用正则搜
  python code_focus.py 缓存 --no-open              # 不自动开浏览器
  python code_focus.py 缓存 --md                   # 只生成 PyCharm 可跳转清单
"""
import argparse
import ast
import hashlib
import html as html_mod
import json
import os
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from pygments import highlight as pyg_highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import TextLexer, get_lexer_for_filename
    from pygments.styles import get_style_by_name
    PYGMENTS = True
except ImportError:
    PYGMENTS = False

HERE = Path(__file__).resolve().parent
OUTDIR = HERE / "output"

# 由 ask.py 通过环境变量传进来：本地桥接服务地址（网页点"在 PyCharm 打开"用它）
BRIDGE = os.environ.get("CODEFOCUS_BRIDGE", "").strip()
try:
    import tree_view          # 项目结构树（同目录）
except Exception:
    tree_view = None

SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", "node_modules", ".idea",
             "dist", "build", ".mypy_cache", ".pytest_cache", ".ipynb_checkpoints",
             "site-packages", ".ruff_cache", ".tox", ".eggs"}
TEXT_EXT = {".py", ".md", ".txt", ".yaml", ".yml", ".json", ".ini", ".cfg", ".toml",
            ".js", ".ts", ".html", ".css", ".bat", ".sh", ".sql", ".env"}
MAX_FILE_BYTES = 2_000_000
MAX_BLOCK_LINES = 140      # 单个代码块最多展示行数
CTX = 8                    # 非 Python 文件 / 模块级代码的上下文行数
DATA_EXT = {".txt", ".json", ".csv"}          # 数据类文件：行数太多就不当代码看
DATA_MAX_LINES = 3000
DATA_NAMES = {"merges.txt", "vocab.txt", "vocab.json", "tokenizer.json",
              "special_tokens_map.json", "added_tokens.json", "tokenizer_config.json",
              "config.json", "package-lock.json", "poetry.lock"}

# 中文概念 -> 代码里可能出现的写法。用户输入中文时自动一起搜这些英文写法。
SYNONYMS = {
    "缓存": ["cache", "lru_cache", "memo", "functools"],
    "分词": ["tokeniz", "jieba", "encode", "split"],
    "训练": ["train", "fit", "epoch", "backward", "Trainer"],
    "评估": ["evaluat", "metric", "accuracy", "f1", "report"],
    "预测": ["predict", "infer", "classify"],
    "推理": ["infer", "predict", "generate", "no_grad"],
    "标签": ["label", "tag", "target"],
    "数据": ["data", "dataset", "read_csv"],
    "读取": ["read_csv", "read_excel", "open(", "read_text", "load"],
    "保存": ["save", "dump", "to_csv", "joblib", "write"],
    "加载": ["load", "from_pretrained", "load_model"],
    "模型": ["model", "nn.Module", "net"],
    "配置": ["config", "settings", "argparse", "add_argument"],
    "超参": ["config", "param", "learning_rate", "batch_size", "epoch"],
    "日志": ["log", "logger", "logging"],
    "绘图": ["plot", "plt", "figure", "matplotlib", "seaborn"],
    "图表": ["plot", "chart", "figure", "plt"],
    "清洗": ["clean", "preprocess", "strip", "dropna", "process"],
    "去重": ["drop_duplicates", "unique"],
    "异常": ["except", "raise", "Exception", "try:"],
    "报错": ["except", "raise", "error", "traceback"],
    "阈值": ["threshold", "thres"],
    "学习率": ["learning_rate", "lr", "scheduler"],
    "损失": ["loss", "criterion", "CrossEntropy", "FocalLoss"],
    "优化器": ["optimizer", "AdamW", "Adam", "SGD"],
    "准确率": ["accuracy", "acc", "correct"],
    "召回": ["recall"],
    "精确率": ["precision"],
    "混淆矩阵": ["confusion_matrix", "confusion"],
    "词表": ["vocab", "vocabulary"],
    "权重": ["weight", "state_dict", "checkpoint"],
    "接口": ["route", "endpoint", "api", "app.route", "app.post", "app.get"],
    "上传": ["upload", "request.files", "FileStorage"],
    "导出": ["export", "download", "to_csv", "save"],
    "前端": ["streamlit", "st.", "render_template", "html"],
    "页面": ["streamlit", "render_template", "template", "html"],
    "路径": ["path", "dir", "os.path", "Path(", "BASE_DIR"],
    "目录": ["path", "dir", "mkdir", "Path("],
    "批量": ["batch", "for "],
    "批大小": ["batch_size", "bs"],
    "训练集": ["train", "X_train", "y_train"],
    "测试集": ["test", "X_test", "eval", "val"],
    "验证": ["val", "valid", "eval", "dev"],
    "随机": ["random", "shuffle", "sample"],
    "种子": ["seed", "manual_seed", "random_state"],
    "监控": ["monitor", "watch", "alert"],
    "情感": ["sentiment", "polarity", "pos", "neg"],
    "评论": ["comment", "review", "content", "text"],
    "多标签": ["MultiLabel", "multilabel", "BCEWithLogits"],
    "弱监督": ["weak", "rule", "keyword", "规则"],
    "数据库": ["sqlite", "sql", "db", "connect", "mysql"],
    "连接": ["connect", "session", "client", "request"],
    "网络请求": ["requests", "http", "url", "session"],
    "下载": ["download", "requests.get", "urlretrieve", "hf_hub", "snapshot"],
    "环境": ["venv", "requirements", "conda", "env"],
    "入口": ["__main__", "app.run", "def main"],
    "参数": ["argparse", "args", "add_argument", "param"],
    "命令行": ["argparse", "sys.argv", "add_argument"],
    "装饰器": ["@wraps", "decorator", "functools.wraps"],
    "异常处理": ["try:", "except", "finally"],
    "排序": ["sort", "sorted", "argsort"],
    "分组": ["groupby", "group", "agg"],
    "统计": ["value_counts", "describe", "mean", "count"],
    "合并": ["merge", "join", "concat", "append"],
    "计时": ["time", "perf_counter", "elapsed"],
    "进度条": ["tqdm", "progress"],
    "显存": ["cuda", "device", "memory", "OOM"],
    "显卡": ["cuda", "device", "gpu"],
    "设备": ["device", "cuda", "cpu", ".to("],
    "半精度": ["fp16", "half", "autocast", "amp"],
    "量化": ["quantiz", "int8", "qat"],
    "蒸馏": ["distill", "teacher", "student"],
    "剪枝": ["prune", "sparsity"],
    "测试": ["test", "assert", "pytest", "unittest"],
    "健康检查": ["health", "ping", "status"],
    "单例": ["_instance", "singleton", "instance"],
    "线程": ["thread", "Thread", "concurrent"],
    "异步": ["async", "await", "asyncio"],
    "队列": ["queue", "Queue", "deque"],
    "重试": ["retry", "attempt", "backoff"],
    "超时": ["timeout", "deadline"],
    "正则": ["re.compile", "regex", "re.sub", "re.findall"],
    "替换": ["replace", "sub(", "strip"],
    "编码": ["encode", "decode", "utf-8", "charset"],
    "格式": ["format", "json", "strftime", "f\""],
    "校验": ["valid", "check", "verify", "assert"],
    "性能": ["perf", "time", "speed", "fast", "optimi"],
    "内存": ["memory", "cache", "lru"],
    "调试": ["print(", "log", "debug"],
    "温度": ["temperature", "top_p"],
    "提示词": ["prompt", "system", "messages"],
    "大模型": ["llm", "openai", "chat", "gpt"],
    "中文": ["chinese", "zh", "cn", "中文"],
    "英文": ["english", "en", "英文"],
    "长度": ["len(", "length", "max_len", "max_length"],
    "截断": ["truncat", "max_length", "cut"],
    "填充": ["pad", "padding"],
    "注意力": ["attention", "attn"],
    "卷积": ["conv", "Conv2d", "kernel"],
    "池化": ["pool", "maxpool", "avgpool"],
    "激活": ["relu", "sigmoid", "tanh", "gelu", "activation"],
    "归一化": ["norm", "BatchNorm", "LayerNorm", "normalize"],
    "dropout": ["dropout", "Dropout"],
    "早停": ["early_stop", "patience", "earlystop"],
    "交叉验证": ["cross_val", "KFold", "kfold"],
    "网格搜索": ["GridSearch", "grid_search"],
    "特征": ["feature", "vector", "vectoriz"],
    "向量": ["vector", "embedding", "tfidf", "TF-IDF"],
    "相似度": ["similarity", "cosine", "distance"],
    "聚类": ["cluster", "kmeans", "KMeans"],
    "分类": ["classif", "class", "label"],
    "回归": ["regress"],
    "序列": ["sequence", "seq", "list"],
    "字典": ["dict", "{}", "json"],
    "列表": ["list", "[", "append"],
    "字符串": ["str", "string", "strip", "split"],
    "时间戳": ["timestamp", "time.time", "datetime"],
    "文件": ["file", "open(", "path", "fp"],
    "文件夹": ["dir", "mkdir", "glob", "os.walk"],
    "遍历": ["for ", "iter", "enumerate", "os.walk"],
    "过滤": ["filter", "if ", "query"],
    "计数": ["count", "len(", "value_counts"],
    "求和": ["sum(", "add", "total"],
    "平均": ["mean", "avg", "average"],
    "最大": ["max(", "argmax", "topk"],
    "最小": ["min(", "argmin"],
    "转换": ["convert", "astype", "to(", "cast"],
    "类型": ["type", "dtype", "astype"],
    "空值": ["nan", "None", "null", "dropna", "isna"],
    "重复": ["duplicat", "unique", "set("],
    "启动": ["app.run", "start", "main(", "uvicorn"],
    "端口": ["port", "host", "8000", "5000"],
    "返回": ["return", "response", "jsonify"],
    "请求": ["request", "post", "get", "body"],
    "响应": ["response", "jsonify", "return"],
    "状态码": ["status_code", "200", "400", "500"],
    "错误处理": ["try:", "except", "errorhandler"],
    "打印": ["print(", "log"],
    "导入": ["import", "from "],
    "常量": ["CONST", "UPPER", "="],
    "全局变量": ["global", "GLOBAL"],
    "类方法": ["@classmethod", "cls"],
    "静态方法": ["@staticmethod"],
    "属性": ["@property", "self."],
    "初始化": ["__init__", "init"],
    "主流程": ["def main", "__main__"],
    "结果": ["result", "output", "out"],
    "报告": ["report", "summary", "metrics"],
    "分数": ["score", "prob", "logit"],
    "概率": ["prob", "softmax", "logit", "sigmoid"],
    "样本": ["sample", "example", "instance", "row"],
    "标签映射": ["label2id", "id2label", "map"],
    "编码器": ["Encoder", "encoder"],
    "池化层": ["pooler", "pooling"],
    "分类头": ["classifier", "head", "fc"],
    "微调": ["fine", "finetune", "Trainer", "training_args"],
    "预训练": ["pretrain", "from_pretrained", "bert", "roberta"],
    "数据集": ["dataset", "DataLoader", "Dataset"],
    "采样": ["sample", "shuffle", "weights"],
    "类别": ["class", "category", "label", "type"],
    "权重衰减": ["weight_decay", "wd"],
    "梯度": ["grad", "backward", "zero_grad", "clip"],
    "梯度裁剪": ["clip_grad", "grad_clip"],
    "混合精度": ["amp", "autocast", "GradScaler"],
    "分布式": ["distributed", "DDP", "rank"],
    "检查点": ["checkpoint", "ckpt", "state_dict"],
    "恢复": ["resume", "load_state_dict", "restore"],
    "超时重试": ["retry", "timeout", "backoff"],
    "缓存目录": ["cache_dir", "hf_home", "CACHE"],
}
USER_SYN_FILE = "同义词.txt"


def load_user_synonyms():
    """同义词.txt 里一行一个：中文 = 英文1, 英文2"""
    f = HERE / USER_SYN_FILE
    extra = {}
    if not f.exists():
        f.write_text(
            "# 自己加同义词，一行一个，格式：中文 = 代码里可能出现的写法, 用逗号隔开\n"
            "# 例如：\n"
            "# 会员 = vip, member, is_vip, level\n"
            "# 优惠券 = coupon, discount, promo\n", encoding="utf-8")
        return extra
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        words = [w.strip() for w in v.replace("，", ",").split(",") if w.strip()]
        if k and words:
            extra[k] = words
    return extra


def expand_terms(kw: str):
    """把关键词扩展成一组同义词：中文 -> 英文写法；英文 -> 对应中文（注释里是中文）。"""
    syn = dict(SYNONYMS)
    syn.update(load_user_synonyms())
    terms = [kw]
    low = kw.lower().strip()
    if kw in syn:
        terms += syn[kw]
    else:
        for cn, lst in syn.items():
            if any(low == t.lower() or low in t.lower() or t.lower() in low for t in lst):
                terms.append(cn)
                break
    seen, out = set(), []
    for t in terms:
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def bigrams(s):
    s = "".join(ch for ch in s if not ch.isspace())
    return [s[i:i + 2] for i in range(len(s) - 1)]


# ---------------------------------------------------------------- 搜索
def iter_files(root: Path, only_file: str = None):
    if only_file:
        p = Path(only_file)
        if not p.is_absolute():
            p = (root / p) if (root / p).exists() else Path.cwd() / p
        yield p
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() not in TEXT_EXT:
                continue
            try:
                if p.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield p


def _short_ascii_re(t):
    """短的英文词（<=3 个字母）按"整个单词"匹配：
    否则 pos 会命中 compose、tag 会命中 stage，结果全是噪声。"""
    if t.isascii() and t.isalpha() and len(t) <= 3:
        return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(t) + r"(?![A-Za-z0-9_])",
                          re.IGNORECASE)
    return None


def _compile_terms(terms, case_sensitive):
    out = []
    for t in terms:
        rx = _short_ascii_re(t)
        if rx is not None:
            out.append((t, rx))
        else:
            out.append((t, t if case_sensitive else t.lower()))
    return out


def make_matcher(terms, use_regex: bool, case_sensitive: bool):
    """terms: 一组同义词。命中任意一个就算命中。"""
    if use_regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        rx = re.compile(terms[0], flags)
        return lambda line: rx.search(line) is not None
    comp = _compile_terms(terms, case_sensitive)

    def match(line):
        low = line if case_sensitive else line.lower()
        for t, c in comp:
            if isinstance(c, str):
                if c in low:
                    return True
            elif c.search(line):
                return True
        return False

    return match


def term_in_text(text, term):
    rx = _short_ascii_re(term)
    if rx is not None:
        return rx.search(text) is not None
    return term.lower() in text.lower()


def terms_in_line(line, terms, case_sensitive=False):
    low = line if case_sensitive else line.lower()
    hit = []
    for t in terms:
        rx = _short_ascii_re(t)
        if rx is not None:
            if rx.search(line):
                hit.append(t)
        elif (t if case_sensitive else t.lower()) in low:
            hit.append(t)
    return hit


# ---------------------------------------------------------------- 代码块提取
def py_blocks(src: str, lines):
    """返回 [(start, end, name, kind)]，start/end 为 1-based 行号。"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []

    def walk(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                end = getattr(child, "end_lineno", child.lineno) or child.lineno
                kind = "class" if isinstance(child, ast.ClassDef) else "func"
                out.append((start, end, (prefix + child.name) if prefix else child.name, kind))
                walk(child, prefix + child.name + ".")
            else:
                walk(child, prefix)

    walk(tree)
    return out


def group_line_windows(hit_lines, total, ctx=CTX):
    """把散落的命中行合并成 [start,end] 窗口（1-based，闭区间）。"""
    if not hit_lines:
        return []
    spans = []
    for ln in sorted(set(hit_lines)):
        s, e = max(1, ln - ctx), min(total, ln + ctx)
        if spans and s <= spans[-1][1] + 3:
            spans[-1][1] = max(spans[-1][1], e)
        else:
            spans.append([s, e])
    return [(s, e) for s, e in spans]


def is_minified_data(path: Path, lines) -> bool:
    """排除 tokenizer.json / vocab.json / merges.txt 这类数据文件，避免刷屏。"""
    if path.name.lower() in DATA_NAMES:
        return True
    if path.suffix.lower() in DATA_EXT and len(lines) > DATA_MAX_LINES:
        return True
    if len(lines) > 40:
        return False
    return any(len(l) > 500 for l in lines)


def build_blocks(path: Path, root: Path, match, terms, kw, max_blocks_per_file=12):
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = src.splitlines()
    if not lines:
        return []
    hits = [i + 1 for i, l in enumerate(lines) if match(l)]
    if not hits:
        return []
    if is_minified_data(path, lines):
        return []

    blocks = []
    if path.suffix.lower() == ".py":
        defs = py_blocks(src, lines)
        for ln in hits:
            cands = [d for d in defs if d[0] <= ln <= d[1]]
            if cands:
                cands.sort(key=lambda d: d[1] - d[0])
                s, e, name, kind = cands[0]
                blocks.append((s, e, name, kind))
            else:
                blocks.append((ln, ln, "(模块级代码)", "module"))
        # 合并同名/同区间
        merged = {}
        for s, e, name, kind in blocks:
            key = (s, e)
            merged.setdefault(key, (s, e, name, kind))
        blocks = list(merged.values())
        # 模块级代码用窗口合并
        mod = [b for b in blocks if b[3] == "module"]
        others = [b for b in blocks if b[3] != "module"]
        for s, e in group_line_windows([b[0] for b in mod], len(lines)):
            others.append((s, e, "(模块级代码)", "module"))
        blocks = others
    else:
        for s, e in group_line_windows(hits, len(lines)):
            blocks.append((s, e, path.name, "file"))

    results = []
    for s, e, name, kind in blocks:
        inner = [l for l in hits if s <= l <= e]
        if not inner:
            continue
        body = lines[s - 1:e]
        # 打分：块名命中 > docstring 命中 > 命中词种类多 > 命中行多
        hit_terms, name_terms = set(), set()
        for t in terms:
            if t.lower() in name.lower():
                name_terms.add(t)
        for l in inner:
            for t in terms_in_line(lines[l - 1], terms):
                hit_terms.add(t)
        head = " ".join(lines[s - 1:min(e, s + 2)])
        doc_hit = any(term_in_text(head, t) for t in terms)
        kw_hit = term_in_text(name, kw) or any(term_in_text(lines[l - 1], kw) for l in inner)
        score = 0
        if kw_hit:
            score += 400
        if term_in_text(name, kw):
            score += 60
        score += 25 * len(name_terms)
        if doc_hit:
            score += 15
        score += 6 * len(hit_terms)
        score += min(len(inner), 10)
        for l in inner:
            stripped = lines[l - 1].strip()
            if stripped.startswith("#") or '"""' in stripped or "'''" in stripped:
                score += 3
        results.append({
            "file": path, "start": s, "end": e, "name": name, "kind": kind,
            "hits": inner, "score": score, "lines": body, "total": len(lines),
            "terms": sorted(hit_terms | name_terms), "kw_hit": kw_hit,
        })
    results.sort(key=lambda b: -b["score"])
    return results[:max_blocks_per_file]


# ---------------------------------------------------------------- HTML 渲染
CSS = """
* { box-sizing: border-box; }
body { margin:0; background:#14161a; color:#e6e6e6;
  font-family: "Microsoft YaHei","Segoe UI",system-ui,sans-serif; }
header { position:sticky; top:0; z-index:10; background:#1b1e24;
  border-bottom:1px solid #2c313a; padding:12px 18px; }
h1 { margin:0 0 6px; font-size:16px; font-weight:600; }
h1 b { color:#ffd479; }
.meta { font-size:12px; color:#8b93a1; }
.tabs { margin-top:10px; display:flex; gap:8px; }
.tab { padding:5px 14px; border-radius:6px; cursor:pointer; font-size:13px;
  border:1px solid #333a45; color:#aab3c0; user-select:none; }
.tab.on { background:#2b6cb0; border-color:#2b6cb0; color:#fff; }
.tab:hover { border-color:#4a5464; color:#e6e6e6; }
.tab.on:hover { background:#2b6cb0; border-color:#2b6cb0; color:#fff; }
::-webkit-scrollbar { width:10px; height:10px; }
::-webkit-scrollbar-track { background:#14161a; }
::-webkit-scrollbar-thumb { background:#333a45; border-radius:5px; }
::-webkit-scrollbar-thumb:hover { background:#4a5464; }
section.blk:hover { border-color:#3a4150; }
.wrap { display:flex; align-items:flex-start; }
nav { width:280px; flex:0 0 280px; position:sticky; top:0; max-height:100vh;
  overflow:auto; padding:14px; border-right:1px solid #262b33; }
nav .nitem { display:block; padding:7px 9px; margin-bottom:6px; border-radius:6px;
  font-size:12px; color:#c3cad6; text-decoration:none; border-left:3px solid #3a4150;
  background:#1a1d23; }
nav .nitem:hover { background:#232833; }
nav .nitem .f { color:#7fd1ff; word-break:break-all; }
nav .nitem .n { color:#ffd479; }
nav .nwrap { position:relative; }
a.jump { display:inline-block; margin-left:10px; padding:2px 10px; border-radius:5px;
  background:#1f6feb; color:#fff; font-size:12px; text-decoration:none; white-space:nowrap;
  font-family:inherit; }
a.jump:hover { background:#3b82f6; }
a.jump.done { background:#238636; }
a.jump.bad { background:#8b1a1a; }
span.jump.off { display:inline-block; margin-left:10px; padding:2px 8px; border-radius:5px;
  background:#2a2f3a; color:#8b93a1; font-size:11px; font-family:Consolas,monospace; }
nav a.jump { display:block; margin:0 0 8px 0; padding:1px 4px; text-align:center;
  font-size:11px; background:#1c3f6e; }
nav a.jump:hover { background:#1f6feb; }
main { flex:1; padding:16px 20px 60px; min-width:0; }
section.blk { margin-bottom:22px; border:1px solid #262b33; border-radius:8px;
  overflow:hidden; background:#181b21; }
.bh { display:flex; gap:12px; align-items:center; flex-wrap:wrap;
  padding:9px 14px; background:#1e222a; border-bottom:1px solid #262b33;
  font-size:12.5px; font-family:Consolas,monospace; }
.bh .rank { color:#fff; background:#2b6cb0; border-radius:4px; padding:1px 7px; }
.bh .loc { color:#7fd1ff; }
.bh .name { color:#ffd479; font-weight:600; }
.bh .hits { color:#8b93a1; }
.bh .terms { color:#7ee787; background:#17301c; border:1px solid #24502f;
  border-radius:4px; padding:1px 7px; }
.bh .terms.exp { color:#ffb86c; background:#2a2113; border-color:#5a4321; }
.st { color:#ffb86c; background:#2a2113; border:1px solid #5a4321;
  border-radius:3px; padding:0 5px; font-size:11px; margin-left:6px; }
.expand { margin-top:7px; font-size:12px; color:#7ee787;
  background:#16241a; border:1px solid #24502f; border-radius:6px;
  padding:5px 10px; display:inline-block; }
.expand.fuzzy { color:#ffb86c; background:#2a2113; border-color:#5a4321; margin-left:8px; }
pre.code { margin:0; font-family:Consolas,"Cascadia Mono",monospace;
  font-size:13.5px; line-height:1.55; overflow-x:auto; padding:8px 0; }
.ln { display:flex; }
.ln .no { flex:0 0 58px; text-align:right; padding-right:14px; color:#4d5666;
  user-select:none; }
.ln .tx { white-space:pre; flex:1; padding-right:20px; }
.ln.hit { background:#3d3418; box-shadow:inset 3px 0 0 #ffd479; }
.ln.hit .no { color:#ffd479; font-weight:700; }
.ln.dim { opacity:.28; }
.ln.ellipsis .tx { color:#6b7484; }
.ellipsis { color:#6b7484; font-style:italic; }
.full h3 { font-size:14px; color:#7fd1ff; margin:18px 0 6px;
  font-family:Consolas,monospace; border-left:3px solid #2b6cb0; padding-left:9px; }
.hidden { display:none; }
/* ---------- 项目结构树 ---------- */
body.treeon nav { display:none; }
.treehead { padding:2px 0 12px; border-bottom:1px solid #262b33; margin-bottom:12px; }
.ttitle { font-size:17px; color:#e6e6e6; font-weight:600; }
.ttitle b { color:#7fd1ff; }
.tmeta { font-size:12px; color:#8b93a1; margin-top:5px; }
.tmeta .hi { color:#ffd479; }
.tbar { margin-top:11px; display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.tbar input { flex:1; max-width:360px; background:#1a1d23; border:1px solid #333a45;
  color:#e6e6e6; padding:7px 11px; border-radius:6px; font-size:13px; font-family:inherit; }
.tbar input:focus { outline:none; border-color:#1f6feb; }
.tbar button { background:#1a1d23; border:1px solid #333a45; color:#aab3c0;
  padding:7px 13px; border-radius:6px; font-size:12px; cursor:pointer; font-family:inherit; }
.tbar button:hover { background:#232833; color:#fff; }
.chipbar { margin-top:12px; display:flex; gap:7px; flex-wrap:wrap; }
.chip { background:#1a1d23; border:1px solid #333a45; color:#aab3c0; padding:4px 12px;
  border-radius:20px; font-size:12px; cursor:pointer; font-family:Consolas,monospace; }
.chip i { color:#5c6370; font-style:normal; margin-left:6px; font-size:10.5px; }
.chip:hover { border-color:#4a5464; color:#e6e6e6; }
.chip.on { background:#1c3f6e; border-color:#2b6cb0; color:#fff; }
.chip.on i { color:#9ec5ff; }
.tree { font-size:13px; }
.tree details { margin:0; }
.tree details > summary { cursor:pointer; padding:6px 9px; border-radius:6px;
  list-style:none; display:flex; gap:9px; align-items:center; }
.tree details > summary::-webkit-details-marker { display:none; }
.tree details > summary:hover { background:#1c2027; }
.tree .dico { color:#5c6370; font-size:9px; flex:0 0 9px; transition:transform .15s; }
.tree details[open] > summary .dico { transform:rotate(90deg); }
.tree .dname { color:#7fd1ff; font-weight:600; font-family:Consolas,monospace; }
.tree .dcnt { color:#5c6370; font-size:11px; }
.tree .ddesc { color:#8b93a1; font-size:11.5px; }
.tree .kids { margin-left:14px; border-left:1px dashed #2a2f3a; padding-left:7px; }
.frow { display:flex; gap:10px; align-items:center; padding:4px 9px; border-radius:5px; }
.frow:hover { background:#1c2027; }
.frow.hit { background:#2a2113; box-shadow:inset 3px 0 0 #d29922; }
.frow.hide { display:none; }
.badge { flex:0 0 44px; text-align:center; font-size:9.5px; font-weight:700; color:#fff;
  border-radius:3px; padding:2px 0; letter-spacing:.4px; font-family:Consolas,monospace; }
.fname { flex:0 0 290px; color:#e6e6e6; font-family:Consolas,monospace;
  font-size:12.5px; word-break:break-all; }
.fsize { flex:0 0 66px; color:#5c6370; font-size:11px; text-align:right; }
.fdesc { flex:1 1 auto; color:#8b93a1; font-size:12px; min-width:0; }
.frow.hit .fdesc { color:#c9d1d9; }
.fhit { flex:0 0 auto; background:#d29922; color:#241a00; font-size:10.5px;
  font-weight:700; padding:1px 8px; border-radius:9px; }
.frow a.jump { margin-left:0; padding:1px 9px; font-size:11px; }
.frow span.jump.off { margin-left:0; font-size:10px; }
@media (max-width:1100px) { .fname { flex:0 0 170px; } .fdesc { display:none; } }
footer { color:#5d6675; font-size:11.5px; padding:20px; text-align:center; }
"""


def esc(s):
    return html_mod.escape(s)


def split_highlighted_lines(html_text):
    """把 pygments 的高亮 HTML 按行切开，且每行 span 自行闭合。"""
    lines, cur, stack = [], [], []
    pos = 0
    tag_rx = re.compile(r"<(/?)(\w+)([^>]*)>")
    for m in tag_rx.finditer(html_text):
        chunk = html_text[pos:m.start()]
        parts = chunk.split("\n")
        for i, part in enumerate(parts):
            cur.append(part)
            if i != len(parts) - 1:
                cur.append("</span>" * len(stack))
                lines.append("".join(cur))
                cur = ["".join('<span%s>' % a for _, _, a in stack)]
        closing, tag, attrs = m.group(1), m.group(2), m.group(3)
        if tag.lower() == "span":
            if closing:
                if stack:
                    stack.pop()
                cur.append("</span>")
            else:
                stack.append((tag, attrs, attrs))
                cur.append(m.group(0))
        else:
            cur.append(m.group(0))
        pos = m.end()
    cur.append(html_text[pos:])
    cur.append("</span>" * len(stack))
    lines.append("".join(cur))
    return lines


def hl_lines(code_text, filename):
    if not PYGMENTS:
        return [esc(l) for l in code_text.split("\n")]
    try:
        lexer = get_lexer_for_filename(filename, stripnl=False)
    except Exception:
        lexer = TextLexer(stripnl=False)
    fmt = HtmlFormatter(nowrap=True, style="monokai")
    return split_highlighted_lines(pyg_highlight(code_text, lexer, fmt))


def jump_html(path, line, label="在 PyCharm 打开"):
    """网页里那个"点一下就跳 PyCharm"的链接。没有桥接服务时只显示路径。"""
    if not BRIDGE:
        return ('<span class="jump off" title="%s:%d">%s:%d</span>'
                % (esc(str(path)), line, esc(Path(path).name), line))
    href = "%s/open?p=%s&l=%d" % (BRIDGE, quote(str(path)), line)
    return ('<a class="jump" href="%s" title="在 PyCharm 里打开 %s 第 %d 行" data-t="%s">%s</a>'
            % (esc(href), esc(str(path)), line, esc(label), esc(label)))


def render_block(b, idx, match):
    s, e = b["start"], b["end"]
    shown_s, shown_e = s, e
    note_top = note_bot = ""
    if e - s + 1 > MAX_BLOCK_LINES:
        first_hit = min(b["hits"])
        shown_s = max(s, first_hit - 30)
        shown_e = min(e, shown_s + MAX_BLOCK_LINES - 1)
        if shown_s > s:
            note_top = '<div class="ln ellipsis"><span class="no">…</span><span class="tx">（上面省略 %d 行）</span></div>' % (shown_s - s)
        if shown_e < e:
            note_bot = '<div class="ln ellipsis"><span class="no">…</span><span class="tx">（下面省略 %d 行）</span></div>' % (e - shown_e)
    code_text = "\n".join(b["lines"][shown_s - s:shown_e - s + 1])
    hl = hl_lines(code_text, b["file"].name)
    children = sorted([c for c in b.get("children", []) if c["start"] >= shown_s],
                      key=lambda c: c["start"])
    skip = {}
    for c in children:
        skip.setdefault(c["start"], c)
    rows = [note_top]
    i = 0
    while i < len(hl):
        ln = shown_s + i
        if ln in skip:
            c = skip[ln]
            end = min(c["end"], shown_e)
            refs = "、".join("#%d" % r for r in c.get("in_parents", []))
            rows.append('<div class="ln ellipsis"><span class="no">…</span>'
                        '<span class="tx">（%s 已单独展示，此处折叠 %d 行）</span></div>'
                        % (refs, end - ln + 1))
            i = end - shown_s + 1
            continue
        h = hl[i]
        raw = b["lines"][ln - s] if ln - s < len(b["lines"]) else ""
        cls = "ln hit" if (match(raw) or ln in b["hits"]) else "ln"
        rows.append('<div class="%s"><span class="no">%d</span><span class="tx">%s</span></div>'
                    % (cls, ln, h))
        i += 1
    rows.append(note_bot)
    try:
        rel = b["rel"]
    except Exception:
        rel = b["file"]
    return ('<section class="blk" id="b%d">'
            '<div class="bh"><span class="rank">#%d</span>'
            '<span class="loc">%s:%d-%d</span>'
            '<span class="name">%s</span>'
            '<span class="hits">整个代码块 %d 行 · 命中 %d 行</span>'
            '<span class="terms%s">%s</span>%s</div>'
            '<pre class="code">%s</pre></section>'
            % (idx, idx, esc(str(b["rel"])), s, e, esc(b["name"]),
               e - s + 1, len(b["hits"]),
               "" if b.get("stage") == "原词" else " exp",
               esc(("命中词：" if b.get("stage") == "原词" else "只命中扩展词：")
                   + "、".join(b.get("terms", [])[:6])) if b.get("terms") else "",
               jump_html(b.get("path") or str(b["file"]), s),
               "".join(rows)))


def render_full_file(path, rel, match, hits_set):
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if len(lines) > 4000:
        return ""
    hl = hl_lines("\n".join(lines), path.name)
    rows = []
    for i, h in enumerate(hl):
        ln = i + 1
        cls = "ln hit" if (ln in hits_set or match(lines[i])) else "ln dim"
        rows.append('<div class="%s"><span class="no">%d</span><span class="tx">%s</span></div>'
                    % (cls, ln, h))
    return '<h3>%s</h3><pre class="code">%s</pre>' % (esc(str(rel)), "".join(rows))


def render_html(kw, root, blocks, full_files, elapsed, terms=None, fuzzy=False):
    style_defs = ""
    if PYGMENTS:
        style_defs = HtmlFormatter(style="monokai").get_style_defs(".code")
    nav, secs = [], []
    for i, b in enumerate(blocks, 1):
        nav.append('<div class="nwrap"><a class="nitem" href="#b%d"><span class="f">%s:%d</span>%s<br>'
                   '<span class="n">%s</span> · %d处</a>%s</div>'
                   % (i, esc(b["file"].name), b["start"],
                      "" if b.get("stage") == "原词" else
                      '<span class="st">%s</span>' % esc(b.get("stage", "")),
                      esc(b["name"]), len(b["hits"]),
                      jump_html(b.get("path") or str(b["file"]), b["start"], "在 PyCharm 打开")))
        secs.append(render_block(b, i, b["_match"]))
    full_secs = [render_full_file(p, rel, m, hs) for p, rel, m, hs in full_files]
    expand = ""
    if terms and len(terms) > 1:
        expand = ("<div class=\"expand\">自动扩展成这些写法一起搜：%s</div>"
                  % esc(" / ".join(terms)))
    if blocks and not any(b.get("kw_hit") for b in blocks) and not fuzzy:
        expand += ("<div class=\"expand fuzzy\">这个项目里根本没出现原词，"
                   "下面只是英文近似写法的结果</div>")
    if fuzzy:
        expand += ("<div class=\"expand fuzzy\">没搜到原词，下面是【模糊匹配】的结果（按相邻两个字拆开找）</div>")
    # ---- 项目结构树 ----
    hit_map = {}
    for b in blocks:
        try:
            k = os.path.normcase(os.path.abspath(str(b.get("path") or b["file"])))
        except Exception:
            continue
        hit_map[k] = hit_map.get(k, 0) + len(b.get("hits") or [])
    tree_html = ""
    if tree_view is not None:
        try:
            nodes = tree_view.build_tree(root)
            tree_html = tree_view.render_panel(root, nodes, hit_map, jump_html)
        except Exception as e:
            tree_html = ("<div class=\"expand fuzzy\">项目结构生成失败：%s</div>"
                         % esc("%s: %s" % (type(e).__name__, e)))
    else:
        tree_html = "<div class=\"expand fuzzy\">tree_view.py 没找到，项目结构不可用</div>"
    body = ("<header><h1>代码聚焦：<b>%s</b></h1>"
            "<div class=\"meta\">项目 %s · 挑出 %d 个完整代码块 · %s · 耗时 %.2fs</div>"
            "%s"
            "<div class=\"tabs\"><div class=\"tab on\" data-v=\"blocks\">只看相关代码块（%d 个）</div>"
            "<div class=\"tab\" data-v=\"full\">看完整文件（无关部分变暗）</div>"
            "<div class=\"tab\" data-v=\"tree\">项目结构（全部文件）</div></div></header>"
            "<div class=\"wrap\"><nav>%s</nav><main>"
            "<div class=\"view-blocks\">%s</div>"
            "<div class=\"view-full hidden\">%s</div>"
            "<div class=\"view-tree hidden\">%s</div>"
            "</main></div>"
            "<footer>由 code_focus.py 生成 · 换个关键词重新搜一次即可</footer>"
            % (esc(kw), esc(str(root)), len(blocks), datetime.now().strftime("%Y-%m-%d %H:%M"),
               elapsed, expand, len(blocks), "".join(nav), "".join(secs), "".join(full_secs),
               tree_html))
    js = ("<script>document.querySelectorAll('.tab').forEach(function(t){t.onclick=function(){"
          "document.querySelectorAll('.tab').forEach(function(x){x.classList.remove('on')});"
          "t.classList.add('on');var v=t.dataset.v;"
          "['blocks','full','tree'].forEach(function(k){"
          "var el=document.querySelector('.view-'+k); if(el){el.classList.toggle('hidden',k!==v);}});"
          "document.body.classList.toggle('treeon',v==='tree');"
          "window.scrollTo(0,0);};});"
          "document.querySelectorAll('a.jump').forEach(function(a){"
          "a.addEventListener('click',function(e){e.preventDefault();"
          "var t=a.getAttribute('data-t')||'在 PyCharm 打开';"
          "a.classList.add('done');a.textContent='…正在打开';"
          "fetch(a.href,{mode:'no-cors'}).then(function(){"
          "a.textContent='✓ 已跳转，去看 PyCharm';}).catch(function(){"
          "a.textContent='✗ 桥接服务没开，重新运行 code-focus.bat';a.classList.add('bad');});"
          "setTimeout(function(){a.classList.remove('done');a.classList.remove('bad');"
          "a.textContent=t;},3000);});});"
          "</script>")
    return ("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<title>代码聚焦 - %s</title><style>%s%s</style></head><body>%s%s</body></html>"
            % (esc(kw), CSS, style_defs, body, js))


def render_md(kw, root, blocks, terms=None, fuzzy=False):
    out = ["# 代码聚焦清单：%s" % kw, "",
           "在 PyCharm 里 **Ctrl+鼠标左键** 点下面的 `路径:行号` 就能直接跳到那段代码。", ""]
    if terms and len(terms) > 1:
        out += ["> 自动扩展成这些写法一起搜：%s" % " / ".join(terms), ""]
    if fuzzy:
        out += ["> 没搜到原词，下面是【模糊匹配】的结果。", ""]
    for i, b in enumerate(blocks, 1):
        out.append("## #%d %s  （%s，命中 %d 处）%s"
                   % (i, b["name"], b["kind"], len(b["hits"]),
                      "" if b.get("stage") == "原词" else "  ← 只命中扩展词"))
        out.append("")
        if b.get("terms"):
            out.append("- 命中的词：%s" % "、".join(b["terms"]))
        out.append("- 代码块：%s:%d-%d" % (b["file"].as_posix(), b["start"], b["end"]))
        for ln in b["hits"][:20]:
            out.append("- 命中行：%s:%d" % (b["file"].as_posix(), ln))
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------- 主流程
def scan_project(root, only_file, match, terms, kw):
    blocks, full_files, files_scanned = [], [], 0
    for p in iter_files(root, only_file):
        files_scanned += 1
        res = build_blocks(p, root, match, terms, kw)
        if not res:
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:
            rel = p
        for b in res:
            b["rel"] = rel
            b["_match"] = match
        blocks.extend(res)
        hs = set()
        for b in res:
            hs.update(b["hits"])
        full_files.append((p, rel, match, hs))
    return blocks, full_files, files_scanned


def open_in_browser(path: Path):
    """用系统默认浏览器打开本地文件。优先用原生路径（比 file:// URI 稳）。"""
    try:
        if os.name == "nt":
            os.startfile(str(path))
            return True
    except Exception:
        pass
    try:
        return webbrowser.open(path.as_uri())
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("keyword")
    ap.add_argument("-p", "--project", default=None)
    ap.add_argument("-f", "--file", default=None)
    ap.add_argument("-n", "--top", type=int, default=25)
    ap.add_argument("--extra", type=int, default=8,
                    help="最多再显示几个「只命中扩展词」的块（默认 8）")
    ap.add_argument("--per-file", type=int, default=5, help="同一个文件最多显示几个块")
    ap.add_argument("--regex", action="store_true")
    ap.add_argument("--case", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--md", action="store_true", help="只生成 PyCharm 可跳转清单")
    args = ap.parse_args()

    if args.project:
        root = Path(args.project).expanduser().resolve()
    elif args.file:
        root = Path(args.file).expanduser().resolve().parent
    else:
        cfg = HERE / "default_project.txt"
        root = Path(cfg.read_text(encoding="utf-8").strip()).resolve() if cfg.exists() else Path.cwd()
    if not root.exists():
        print("[X] 项目目录不存在：%s" % root)
        return 1

    kw = args.keyword
    terms = [kw] if args.regex else expand_terms(kw)
    match = make_matcher(terms, args.regex, args.case)

    t0 = datetime.now()
    blocks, full_files, files_scanned = scan_project(root, args.file, match, terms, kw)

    # 兜底：一个都没搜到时，用"相邻两个字"的模糊匹配（中文输入时很管用）
    fuzzy = False
    if not blocks and not args.regex and len(kw.strip()) >= 2:
        grams = bigrams(kw)
        if grams:
            fuzzy = True
            terms = grams
            match = make_matcher(terms, False, args.case)
            blocks, full_files, files_scanned = scan_project(root, args.file, match, terms, kw)

    # 去掉重复：如果一个大代码块（比如整个类）里的命中行，已经被它内部的小块（各个方法）全覆盖，
    # 就丢掉大块，只留更聚焦的小块。
    by_file = {}
    for b in blocks:
        by_file.setdefault(str(b["file"]), []).append(b)
    keep = []
    for f, bs in by_file.items():
        for a in bs:
            a_hits = set(a["hits"])
            covered = set()
            for c in bs:
                if c is a:
                    continue
                if c["start"] >= a["start"] and c["end"] <= a["end"]:
                    covered |= set(c["hits"])
            if a_hits and a_hits <= covered:
                continue
            keep.append(a)
    blocks = keep

    # 单个文件最多留 N 个块，免得一个文件把榜单刷满
    per_file, capped = {}, []
    for b in sorted(blocks, key=lambda x: -x["score"]):
        k = str(b["file"])
        if per_file.get(k, 0) >= args.per_file:
            continue
        per_file[k] = per_file.get(k, 0) + 1
        capped.append(b)
    blocks = capped

    # 排序：命中原词的排最前；只命中"自动扩展词"的放后面，并且限量
    blocks.sort(key=lambda b: (0 if b.get("kw_hit") else 1, -b["score"]))
    if not args.regex:
        head = [b for b in blocks if b.get("kw_hit")][:args.top]
        tail = [b for b in blocks if not b.get("kw_hit")][:args.extra]
        blocks = head + tail
    else:
        blocks = blocks[:args.top]
    for b in blocks:
        b["stage"] = "原词" if b.get("kw_hit") else ("模糊" if fuzzy else "扩展词")

    # 给块编号；标出"被大块包住的小块"，渲染大块时把它们折叠成一行提示
    for i, b in enumerate(blocks, 1):
        b["rank"] = i
    for b in blocks:
        b["children"] = [c for c in blocks
                         if c is not b and c["start"] >= b["start"] and c["end"] <= b["end"]]
        for c in b["children"]:
            c.setdefault("in_parents", []).append(b["rank"])

    elapsed = (datetime.now() - t0).total_seconds()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|]', "_", kw)[:40] or "result"

    md_path = OUTDIR / ("%s.md" % safe)
    md_path.write_text(render_md(kw, root, blocks, terms, fuzzy), encoding="utf-8")

    if args.md:
        print("已生成清单：%s" % md_path)
        return 0

    # 网页文件名只允许 ASCII，否则某些浏览器会把 file:// 地址认错、跳成首页
    if re.fullmatch(r"[A-Za-z0-9_.\-]+", safe):
        html_name = "focus_%s.html" % safe
    else:
        html_name = "focus_%s.html" % hashlib.md5(kw.encode("utf-8")).hexdigest()[:8]
    html_path = OUTDIR / html_name
    html_path.write_text(render_html(kw, root, blocks, full_files, elapsed, terms, fuzzy),
                         encoding="utf-8")

    json_path = OUTDIR / ("%s.json" % safe)
    json_path.write_text(json.dumps(
        [{"rank": b["rank"], "file": str(b["rel"]), "path": b["file"].as_posix(),
          "start": b["start"], "end": b["end"], "name": b["name"], "kind": b["kind"],
          "hits": b["hits"], "terms": b.get("terms", []),
          "stage": b.get("stage", ""), "kw_hit": bool(b.get("kw_hit"))} for b in blocks],
        ensure_ascii=False, indent=1), encoding="utf-8")

    print("=" * 62)
    print("关键词「%s」  ·  扫描 %d 个文件  ·  挑出 %d 个完整代码块  ·  %.2fs"
          % (kw, files_scanned, len(blocks), elapsed))
    if not args.regex and len(terms) > 1:
        print("自动扩展成这些写法一起搜：%s" % " / ".join(terms))
    if fuzzy:
        print("（没搜到原词，上面是【模糊匹配】的结果：%s）" % " / ".join(terms))
    print("=" * 62)
    if not blocks:
        print("没有找到。换个词试试，比如更短的核心词。")
    kw_hit_n = sum(1 for b in blocks if b.get("kw_hit"))
    if blocks and not args.regex and not kw_hit_n:
        print("注意：这个项目里根本没出现「%s」这个词。" % kw)
        print("      下面只是英文近似写法（%s）的结果，可能不是你要的。" % " / ".join(terms[:6]))
        print("-" * 62)
    for i, b in enumerate(blocks[:14], 1):
        if i > 1 and b.get("stage") == "扩展词" and blocks[i - 2].get("stage") != "扩展词":
            print("-" * 62)
            print("  下面这些没写「%s」这个词，只是命中了自动扩展出来的英文写法：" % kw)
        print("#%-2d  %-44s %-28s 行 %d-%d  [%s]"
              % (i, str(b["rel"])[:44], b["name"][:28], b["start"], b["end"],
                 "、".join(b.get("terms", [])[:4])))
    print("-" * 62)
    print("网页版（推荐看这个）：%s" % html_path)
    print("PyCharm 跳转清单：    %s" % md_path)
    print("JSON: %s" % json_path)
    if not args.no_open:
        open_in_browser(html_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
