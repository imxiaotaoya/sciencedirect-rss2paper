# SDRSS — ScienceDirect RSS 全文爬取

从 ScienceDirect 期刊的 RSS 订阅中不仅获取标题，还能拉取文章摘要与全文，并保存为本地 JSON。

## 功能

- **RSS 解析**：支持多个期刊 RSS，自动从文章链接中提取 DOI/PII
- **全文获取**：优先使用 [Elsevier Article Retrieval API](https://dev.elsevier.com/) 获取全文（需 API Key 与机构权限）；可选通过请求文章页 HTML 并携带 Cookie 作为备选
- **正文提取**：从 API 返回的 XML 或文章页 HTML 中解析摘要与正文
- **结果保存**：统一输出为 `output/articles.json`，每篇包含标题、链接、摘要、全文等字段

## 环境要求

- Python 3.10+
- 有 ScienceDirect 期刊的 RSS 地址
- 获取全文需满足其一：**Elsevier API Key**（[在此注册](https://dev.elsevier.com/)）或 **机构订阅 + 登录 Cookie**

## 安装

```bash
cd sdrss
pip install -r requirements.txt
```

### 使用 Anaconda 的 Python（Windows）

把 `python` 加入 PATH
不确定路径时，在 **Anaconda Prompt** 里输入 `where python` 即可看到当前使用的 `python.exe` 完整路径。
比如我的路径是这样：
where python
E:\Anaconda\python.exe

那么就在PATH里面加
E:\Anaconda
E:\Anaconda\Scripts


## 配置

1. 复制环境变量示例并编辑：

   ```bash
   copy .env.example .env
   ```

2. 在 `.env` 中填写（至少填 API Key 才能拉全文）：

   | 变量 | 说明 | 必填 |
   |------|------|------|
   | `ELSEVIER_API_KEY` | Elsevier 开发者 API Key | 推荐（获取全文） |
   | `SCIENCE_DIRECT_COOKIE` | 机构登录后从浏览器复制的 Cookie | 可选（API 不可用时用爬取） |
   | `REQUEST_TIMEOUT` | 请求超时秒数，默认 30 | 可选 |
   | `RSS_FEEDS` | 多行 RSS URL，每行一个 | 可选（也可用命令行传） |

**注意**：`.env` 不要提交到 Git，已写在 `.gitignore` 中。

## 使用

以下命令中的 `python` 若无法识别，请先按上文「使用 Anaconda 的 Python」激活 conda 环境，或改用 Anaconda 的 `python.exe` 完整路径。

### 命令行传入 RSS 地址

```bash
python main.py "https://你的期刊RSS地址1" "https://你的期刊RSS地址2"
```

### 使用环境变量中的 RSS 列表

在 `.env` 中设置 `RSS_FEEDS`（多行 URL），然后：

```bash
python main.py
```

### 常用参数

| 参数 | 说明 |
|------|------|
| `-o`, `--output DIR` | 输出目录，默认 `output` |
| `-n`, `--limit N` | 最多处理 N 篇文章（便于试跑） |
| `--no-api` | 不使用 API，仅通过爬取文章页获取（需配置 Cookie） |

示例：

```bash
# 只处理前 5 篇，结果写到 output 目录
python main.py "https://example.com/journal/rss" -n 5

# 指定输出目录
python main.py "https://example.com/journal/rss" -o ./data

# 不用 API，只用 Cookie 爬文章页
python main.py "https://example.com/journal/rss" --no-api
```

## 输出说明

运行成功后，在输出目录（默认 `output/`）下会生成 `articles.json`，结构大致如下：

```json
[
  {
    "title": "文章标题",
    "link": "https://www.sciencedirect.com/science/article/pii/...",
    "doi": "10.1016/j.xxx.2024.xxxxx",
    "pii": "S0123456789012345",
    "abstract": "摘要内容",
    "full_text": "正文内容（段落拼接）",
    "source": "api 或 crawl"
  }
]
```

- `source` 为 `api` 表示来自 Elsevier API，为 `crawl` 表示来自文章页 HTML。
- 若某篇无法获取或未解析到正文，对应条目中 `abstract`/`full_text` 可能为空，并可能有 `error` 字段说明原因。

## 项目结构

```
sdrss/
├── .env.example      # 环境变量示例（复制为 .env 后填写）
├── config.py         # 读取 .env 与配置项
├── rss_parser.py     # RSS 解析与 DOI/PII 提取
├── article_fetcher.py # API 与文章页拉取
├── content_extractor.py # 从 XML/HTML 提取摘要与正文
├── main.py           # 命令行入口
├── requirements.txt
├── README.md
└── output/           # 默认输出目录（自动创建）
    └── articles.json
```

## 常见问题

**1. 只有标题没有正文？**  
- 确认已配置 `ELSEVIER_API_KEY` 且机构有该期刊权限；或配置 `SCIENCE_DIRECT_COOKIE` 并用 `--no-api` 试爬文章页。  
- 部分文章仅开放摘要，无全文权限时无法拿到正文。

**2. 如何获取 API Key？**  
在 [Elsevier Developer](https://dev.elsevier.com/) 注册账号，在控制台创建 API Key，将 Key 填入 `.env` 的 `ELSEVIER_API_KEY`。

**3. Cookie 怎么填？**  
在已登录机构账号的前提下，用浏览器打开 ScienceDirect 文章页，按 F12 打开开发者工具，在 Network 里找到该页请求，复制请求头中的 `Cookie` 整段，粘贴到 `.env` 的 `SCIENCE_DIRECT_COOKIE`（注意不要有多余换行）。

**4. RSS 地址从哪来？**  
部分 ScienceDirect 期刊页面或检索结果页会提供 RSS 链接；也可通过第三方 RSS 生成工具为期刊/检索生成 Feed，只要最终文章链接是 `sciencedirect.com/science/article/pii/...` 格式即可被本工具解析并拉取。

## 合规说明

请仅在您拥有访问权限的范围内使用（机构订阅或 API 条款允许）。不要用于绕过付费墙或违反 Elsevier 使用条款与版权规定。
