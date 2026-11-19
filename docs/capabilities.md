# 能力清单（v1）· Capabilities

> 胸牌上的轻量 agent 不靠"本地跑大模型"，而靠"一套可靠的工具"。模型调云端，板子负责动手。
> 本文件是 v1 的能力契约：做什么、不做什么、失败时退到哪。

## 1. 分层原则

| 层 | 跑在哪 | 特征 |
|---|---|---|
| 内容级操作 | 胸牌本地 | 毫秒级、离线可用 |
| 格式转换（LibreOffice） | 胸牌本地，受内存闸门约束 | 秒级、单并发、忙时转远端 |
| 重排版 / 精细编辑 | 远端（台式机/服务器）或手机 WPS | 保证保真 |
| 生图 / 改图 | 远端 API（OpenAI 兼容） | 板子只发请求、存结果 |

## 2. 工具与权限

| 工具 | 能力 | 权限 | 依赖 |
|---|---|---|---|
| `read_docx` / `read_xlsx` / `read_pptx` | 抽取正文、表格、幻灯片文字 | L0 只读 | python-docx / openpyxl / python-pptx |
| `edit_docx` / `write_xlsx` / `edit_pptx` | 文本替换、追加、表格写值、图片替换 | L1 | 同上 |
| `read_pdf` / `pdf_to_images` / `merge_pdf` / `split_pdf` | 文本、表格、渲染、合并拆分 | L0/L1 | pypdf / pdfplumber / PyMuPDF |
| `ocr_image` / `ocr_pdf` | 中英文印刷体识别 | L0 | tesseract + chi_sim/eng |
| `image_resize` / `crop` / `watermark` / `convert` | 本地图像处理 | L1 | Pillow |
| `image_generate` / `image_edit` | 调远端生图 API（改图、生图） | L2 | OpenAI 兼容 API |
| `office_convert` | docx/xlsx/pptx ⇄ pdf 等格式转换 | L1 | LibreOffice headless |
| `list_files` / `read_file` / `write_file` / `delete_file` | 工作区文件读写 | L0/L1 | 标准库（限 AGENT_WORKDIR） |

**权限**：L0 只读直接执行；L1 记录审计；L2 需确认（Hub 弹窗/手机确认）。

## 3. LibreOffice 方案（本地保留）

### 安装（仅 headless 组件）

```bash
sudo apt install -y --no-install-recommends \
  libreoffice-core libreoffice-writer libreoffice-calc libreoffice-impress libreoffice-draw \
  fonts-noto-cjk
```

磁盘：约 500–700MB（含中文字体）。M0 的 32GB TF 卡足够。

### 运行约束（4GB 板子的关键）

- **单并发 + 排队**：同一时刻只允许一个 `soffice` 进程（文件锁 `~/.cache/cyberbadge/office.lock`）；
- **内存闸门**：启动前检查 `MemAvailable`，低于 700MB 直接拒绝，返回"忙，稍后再试或转远端"；
- **超时**：单任务 120s，超时杀进程组；
- **隔离 profile**：`-env:UserInstallation=file:///tmp/lo-profile`，避免首次运行向导和锁冲突；
- **冷启动代价**：5–15 秒（首次），之后 3–8 秒/个；不做常驻守护，用完即退，避免长期占 300–500MB；
- **输出校验**：转换后检查文件存在且 >1KB，否则报错。

### 支持的转换

| 输入 | 输出 | 说明 |
|---|---|---|
| docx / odt / rtf | pdf | 最常用 |
| xlsx / ods / csv | pdf | 表格宽页可能被缩放 |
| pptx / odp | pdf | 一页一页 |
| docx → docx | 格式规整 | 慎用，可能改变排版 |

**不做**：PDF → docx（LibreOffice 的转换质量差）、复杂排版保真、公式重排。

## 4. 失败退路

```
本地 LibreOffice 可用？
├─ 是 → 转换 → 校验 → 返回
└─ 否（内存不足/超时/未安装）→ 转 Hub 远端转换（台式机或服务器）
                                   └─ 仍失败 → 明确告知用户，附原因
```

## 5. 在线状态（QQ 式）

- 每个 agent 每 15–30 秒心跳一次（HTTP `POST /agents/{id}/heartbeat` 或 WS ping）；
- 状态：`online`（彩色头像）/ `busy`（转圈）/ `offline`（灰色 + "最后在线 x 分钟前"）；
- Hub 存 `last_seen`，PWA 顶部头像条实时变色；
- 远程 agent 掉线不影响本地 agent，UI 自动降级。

## 6. 实现状态（v1）

- ✅ `device/tools.py`：文件、docx/xlsx/pptx 读取、PDF 文本、OCR、图像操作、LibreOffice 转换、网页抓取
- ✅ `device/office_convert.py`：LibreOffice headless（单并发 + 内存闸门 + 超时 + 隔离 profile）
- ✅ `device/registry.py`：本地/远程 agent 注册表 + 心跳状态（online/busy/offline）
- ✅ `web/`：顶部头像条（彩色=在线，灰色=离线）
- ⏳ `image_generate` / `image_edit`：接口待接远端 API（v1.5）
- ⏳ Office "编辑"（edit_docx 等）：先做读取，写操作随 v1.1

依赖：`pip install -r requirements-tools.txt`；LibreOffice 见第 3 节。

## 7. 明确不做（v1）

- 本地跑生图模型（SDXL/Flux）——显存不够；
- 本地跑大语言模型——内存不够，走云端；
- 复杂排版保真编辑——交给远端或手机 WPS；
- 视频剪辑——超出轻量 agent 范围。
