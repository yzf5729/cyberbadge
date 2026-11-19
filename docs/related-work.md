# 相关项目与差异化

> 结论先行：部件都有成熟开源，**"胸牌形态 + agent 常驻 + 借屏 + 文件/浏览器工具"的组合**在开源里很少见，重叠度约 20–30%。

| 类别 | 代表项目 | 重合点 | 不重合 |
|---|---|---|---|
| 语音 AI 硬件 | [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) | 小硬件、语音、云端 LLM、MCP 工具 | 跑不了 agent 任务队列/文件/浏览器 |
| AI 胸牌 | [atopile/ai-pin](https://github.com/atopile/ai-pin) | 可穿戴形态、语音 | 偏硬件设计，无 agent 工具链 |
| 语言模型计算机 | [01](https://github.com/PrimeDeviation/01) | 设备 + 服务端 + 语音 | 无文件/浏览器工具，已停更 |
| 软件 agent | Open Interpreter / Leon / Open WebUI | 文件、浏览器、记忆 | 跑在 PC/服务器，不随身 |
| 手机自动化 | Mobile-Agent / droidrun | 浏览器/App 操作 | 寄生安卓手机，非硬件 |

## 我们的三条差异

1. **agent 常驻 + 系统级工具权限**，不是语音助手；
2. **借屏架构**：设备可无屏，手机浏览器即显示器（PWA）；
3. **可复现的 BOM + 真实功耗/成本数据**，而不是概念。

## 风险

- Humane AI Pin 已停服、Rabbit R1 是安卓壳：品类商业化难，Demo 定位要诚实；
- 门槛低：语音前端已有成熟方案，护城河在 agent 能力与形态。
