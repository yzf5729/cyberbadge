# CyberBadge 项目规则（给未来的自己/协作 agent）

本文件优先级高于一般约定。改动前先读 `docs/decisions.md`，不要推翻已记录的决策；要推翻，先写新决策并说明原因。

## 定位
- CyberBadge 是 **agent 宿主 + 切换器 + 借屏 UI**，不是又一个通用 agent。
- builtin agent 只做"最小兜底"（对话 + 工具 + 技能），不加通用 agent 的重功能。

## 架构
- 业务层（`device/`）保持系统无关：只用 Python 标准库 + pip 包，不写死路径（走 `AGENT_WORKDIR`）。
- 硬件/系统相关调用必须收进 `platform/` 适配层，x86 上给空实现。
- 前端是 PWA（`web/`），不依赖原生 UI；M1 形态也用同一套 PWA（Chromium kiosk）。

## 安全
- 不引入"最高权限"式设计；权限按 L0–L3 分级，高危操作需确认与审计。
- 不把密钥写进代码/文档/提交；`.env` 不进仓库。
- 未鉴权的端口不长期暴露在局域网；优先 Tailscale/白名单。

## 内容
- 不生成对儿童体型角色的性化内容（含受缚/捆绑题材）；不调用明显成人向的 LoRA。

## 流程
- 先改文档（决策/能力契约）再改代码；提交信息用 `type: summary`（feat/fix/docs/chore/refactor/ui）。
- 每次功能变更：本地跑 `python3 -m compileall device/`、`node --check web/app.js`，必要时 TestClient 冒烟；推 GitHub 前确认 CI 绿。
- 部署到台式机：打包 zip → scp → Expand-Archive 覆盖 `C:\AI\cyberbadge\device|web` → 重启 `cyberbadge` 计划任务 → 验证 `/api/health`。

## 不做（见 D11）
不自研手机 OS、不在胸牌跑本地大模型、不造通用 agent 运行时、不为"接 100 个 agent"堆功能、不追新硬件。
