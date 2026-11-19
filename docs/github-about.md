# GitHub 门面文案（复制粘贴用）

## About

点仓库首页右侧 **About** 的齿轮，粘贴：

- **Description**：
  ```
  随身 AI agent 宿主：借手机屏当显示器，7×24 常驻，管理家里/办公室/云上的设备
  ```
- **Website**：留空，或以后填文档站
- **Topics**（一个一个加）：
  ```
  ai-agent
  llm
  linux
  wearable
  pwa
  self-hosted
  edge-computing
  fastapi
  ```

英文版 Description（如果想让国际用户看懂）：
```
A pocket AI-agent host: borrows your phone as the screen, stays online 24/7, and orchestrates your devices at home and in the office
```

## 第一个 Issue 正文（建议 pinned）

**标题**：`MVP 范围讨论：四类设备 × 三件事`

**正文**：
```markdown
## 目标

用最小范围验证「随身 agent 管家」是否好用。

## 设备（四类）

- [ ] Linux / macOS：SSH，L0–L2
- [ ] Windows：OpenSSH，先只做 L0 只读 + 文件
- [ ] NAS：官方 API 优先，SSH 兜底
- [ ] 路由器：SSH/HTTP，L0 + 重启/改网络

## 动作（三件）

- [ ] 看状态：在线、磁盘、负载、服务
- [ ] 取放文件：授权目录内
- [ ] 跑一条命令：白名单 + 二次确认 + 输出回传

## 非目标（v1 不做）

- 提权操作（Windows 管理员）
- GUI 自动化
- 公网直连（走覆盖网络）
- 计费与多租户
```

## Release 说明（v0.1.0）

```markdown
## 首个可运行版本

- 设备端 agent（对话 + 文件 + 网页抓取）
- 手机 PWA 借屏（无需设备屏幕）
- 薄网关（设备鉴权 + 上游 Key 隔离）
- 中英双语文档、架构图、BOM、路线图

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env   # 填 LLM_API_KEY
uvicorn device.main:app --port 8000
```

零硬件即可运行；硬件形态见 `docs/modes.md`。
```
