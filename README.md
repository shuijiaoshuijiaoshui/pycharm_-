# pycharm-code-focus

> **PyCharm 高亮搜索相关代码** —— 输入一个关键词，项目里跟它相关的**整个代码块**全部挑出来高亮，其余部分变暗；点一下就跳回 PyCharm 对应行。

[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](#)

---

## 它解决什么问题

代码读多了会乱：一个功能散在十几个文件里，`Ctrl+Shift+F` 搜出来的是一堆孤零零的行，上下文全丢了。

这个工具换个思路：**你只说要了解哪个方面，它把相关代码整块端出来给你看。**

```
你想了解「缓存」  →  它找出：cache_manager.py 里的 CacheManager 类（41-204 行）
                            memory_manager.py 里的 ConversationMemory（16-261 行）
                            ……
```

打开网页，**命中的函数/类整块亮着，无关代码全部变暗**，左边目录点一下就能跳过去。

---

## 效果长这样

网页左侧是目录，右侧是代码：

```
┌──────────────────────────┬────────────────────────────────────────────┐
│ ① core\cache_manager.py  │  # core/cache_manager.py        [在 PyCharm 打开] │
│    CacheManager 41-204   │  ─────────────────────────────────────────  │
│ ② core\memory_manager.py │  41 │ class CacheManager:                   │
│    ConversationMemory    │  42 │     """LLM 响应双层缓存"""            │  ← 整块亮着
│    16-261                │  43 │     def __init__(self, ttl=3600):     │
│ ③ api\chat.py            │  ...│                                       │
│    chat 88-140           │  ─────────────────────────────────────────  │
│                          │  # api/chat.py                            │
│                          │  ...（无关的文件整体变暗）...              │
└──────────────────────────┴────────────────────────────────────────────┘
```

黑窗口里同时列出所有命中，直接输编号就能跳：

```
想看哪部分代码？(关键词 / 编号跳PyCharm / p 换项目 / q 退出) > 缓存

  #   文件                          代码块                 行范围     命中词
  ------------------------------------------------------------------
  1   core\cache_manager.py        CacheManager          41-204    缓存、cache
  2   core\memory_manager.py       ConversationMemory    16-261    扩: memo
  ------------------------------------------------------------------
  ★ 网页里点代码块标题右边的「在 PyCharm 打开」→ PyCharm 直接跳过去。
```

---

## 快速开始

需要 **Python 3.8+**（唯一依赖是 `pygments`，脚本会自动装）。

**Windows**

1. 下载本仓库（`Code → Download ZIP`），解压到任意目录
2. 双击 **`code-focus.bat`**
3. 第一次运行会让你粘一个项目路径，粘进去回车 —— 之后它记住了
4. 输入关键词，比如 `缓存`，回车

**macOS / Linux**

```bash
pip install pygments
python ask.py
```

> 第一次运行会问你项目路径；也可以直接 `python code_focus.py 缓存 -p /path/to/project`。

---

## 中文也能搜（自动翻译成代码里的写法）

你输中文，它自动去找代码里对应的英文写法：

| 你输入 | 自动一起搜 |
|---|---|
| `缓存` | 缓存 / cache / lru_cache / memo / functools |
| `标签` | 标签 / label / tag / target |
| `分词` | 分词 / tokeniz / jieba / encode / split |
| `内存` | 内存 / memory / cache / lru |
| `cache` | cache / 缓存（反向：英文 → 中文注释） |

结果分两档，**原词命中的排最前**，只命中扩展词的会单独标出来：

```
  1   core\cache_manager.py   CacheManager   41-204   缓存、cache
  ------------------------------------------------------------------
  下面这些没写原词，只是命中了自动扩展出来的英文写法：
  26  core\memory_manager.py  ConversationMemory  16-261  扩: memo
```

**如果整个项目里根本没出现你输的那个词**，它会直接告诉你，而不是硬凑一个结果给你：

```
注意：这个项目里根本没出现「情感」这个词。
      下面只是英文近似写法（情感 / sentiment / polarity）的结果，可能不是你要的。
```

### 自己加同义词

打开 `同义词.txt`，一行一个：

```
会员 = vip, member, is_vip, level
优惠券 = coupon, discount, promo
```

改完直接生效，不用重启。

---

## 网页上有什么

**左侧目录**：点一下跳到对应代码块（可以反复点）。

**三个标签页**（随便切）：

| 标签页 | 看什么 |
|---|---|
| **只看相关代码块** | 只显示命中的函数/类，最清爽 |
| **看完整文件（无关部分变暗）** | 整个文件都在，但只有相关的行是亮的 |
| **项目结构（全部文件）** | 整个项目的目录框架，每个文件干什么用 |

---

## 项目结构：一眼看清整个项目

点第三个标签页「**项目结构（全部文件）**」：

```
📁 core         9 个文件   核心业务层 —— 认证、缓存、记忆、Prompt、工具注册
   PY  cache_manager.py   8.5 KB   LLM 响应双层缓存          【本次命中 74】 [跳]
   PY  auth.py            7.1 KB   Token 认证模块 —— 登录/校验  [跳]
📁 mcp_tools   10 个文件   工具实现层 —— 外部 API 封装
📁 static      13 个文件   前端 —— 页面
```

每行给你四样东西：

| 看到的东西 | 意思 |
|---|---|
| `PY` / `HTML` / `MD` 彩色小标签 | 文件类型 |
| 文件名 + 大小 | 比如 `cache_manager.py` `8.5 KB` |
| **中文说明** | 这文件干什么用（自动从文件开头的文档字符串读出来） |
| `[跳]` | 点一下在 PyCharm 打开这个文件 |

**中文说明是读出来的，不是猜的** —— 优先读 `.py` 的文档字符串，其次 `<title>`、Markdown 标题、文件首条注释，最后按文件名兜底。

**目录也带整体说明**，从上往下看一遍就知道项目分了哪几层。

顶部三个小工具：**分层按钮**（只看某一层的文件）、**过滤框**（实时筛文件名）、**全部展开/折叠**。

**黄色高亮的文件 = 本次搜索命中的文件**，旁边有橙色徽章「本次命中 N」—— 搜完一个词切到这页，就知道命中的东西在项目里处于什么位置。

---

## 点一下就跳 PyCharm

网页里每个代码块标题右边都有个蓝色按钮 **「在 PyCharm 打开」**，左侧目录每个条目下面也有。

**点一下 → PyCharm 直接跳到那个文件的对应行。**

- 成功：按钮变成 `✓ 已跳转，去看 PyCharm`
- 失败：变成 `✗ 桥接服务没开，请重新运行 code-focus.bat`

原理：程序运行时在 `127.0.0.1:8765` 上起了个很小的本地服务。浏览器出于安全不允许本地网页直接启动 PyCharm，所以由这个小服务代劳。

**PyCharm 装在哪儿？** 它会自动找（Program Files / JetBrains Toolbox / snap / macOS 常见位置）。找不到也不影响搜索，只是跳转按钮不可用。手动指定两种方式：

```bash
set PYCHARM_EXE=D:\JetBrains\PyCharm\bin\pycharm64.exe     # Windows
export PYCHARM_EXE=/opt/pycharm/bin/pycharm.sh             # macOS / Linux
```

或者在本目录建一个 `pycharm_path.txt`，里面写一行完整路径。

---

## 让 PyCharm 自己也高亮

PyCharm 没有「按概念高亮」的接口（那要写插件），但这两个是现成好用的：

1. **`Ctrl+Shift+F7`** —— 光标放在某个词上按它，**当前文件里所有这个词全亮**。配合 `F3` 逐个跳。
2. **挂成 PyCharm 右键菜单**（选中词 → 右键 → External Tools）：

   `File → Settings → Tools → External Tools → +`

   | 字段 | 填什么 |
   |---|---|
   | Name | `代码聚焦` |
   | Program | 你的 `python.exe` 完整路径 |
   | Arguments | `<本工具目录>\code_focus.py "$SelectedText$"` |
   | Working directory | `<本工具目录>` |

   以后在 PyCharm 里选中 `缓存` → 右键 → External Tools → 代码聚焦，浏览器直接出结果。

---

## 命令行用法

```bash
python code_focus.py 缓存                       # 搜记住的项目
python code_focus.py 缓存 -p "/path/to/project" # 指定项目
python code_focus.py 缓存 -f "src/app.py"       # 只搜一个文件
python code_focus.py "cache_.*" --regex         # 正则
python code_focus.py 缓存 -n 40 --per-file 8    # 最多 40 块，单文件最多 8 块
python code_focus.py 缓存 --extra 0             # 只要原词命中，不要扩展词
python code_focus.py 缓存 --md                  # 只生成可跳转清单
python code_focus.py 缓存 --no-open             # 不自动开浏览器
```

---

## 文件说明

| 文件 | 作用 |
|---|---|
| `code-focus.bat` | Windows 双击入口（自动找 Python、自动装依赖） |
| `ask.py` | 交互式主程序 + 本地跳转服务 |
| `code_focus.py` | 搜索 + 生成高亮网页 |
| `tree_view.py` | 生成「项目结构」页 |
| `同义词.txt` | 自己加「中文 = 英文写法」对照 |
| `requirements.txt` | 依赖（只有 pygments） |
| `output/` | 生成的结果（自动创建，已被 .gitignore 忽略） |

---

## 小提示

- **关键词越短越核心越好**：`缓存` 比 `实现一个缓存` 好得多。
- 网页文件名故意用英文（`focus_xxxx.html`），避免浏览器把 `file://` 地址认错跳成首页。
- 短英文词（`pos`/`tag`/`acc`）按**整个单词**匹配，不会再出现 `pos` 命中 `compose`、`tag` 命中 `stage` 这种噪声。
- `.venv`、`__pycache__`、`.git`、`node_modules` 这类目录自动跳过；超长数据文件（如 `merges.txt`）也不会刷屏。
- 关键词可以带空格搜多个（`缓存 过期` = 同时要含这两个词）。

---

## 常见问题

**Q：双击 bat 一闪就没了？**
没装 Python，或者装的时候没勾「Add python.exe to PATH」。重装 Python 时记得勾上。

**Q：跳转按钮点了没反应？**
先确认那个黑窗口还开着（跳转服务跟着它）。关了就重新双击 `code-focus.bat`。

**Q：中文搜不到？**
换个更短更核心的词，或者在 `同义词.txt` 里补一条对照。

**Q：能搜别的语言吗？**
能。Python 用 AST 精确切「类/函数」，其他语言（JS/Java/Go…）按大括号缩进切块，高亮照常。

---

## 许可

[MIT](LICENSE) —— 随便用，随便改。
