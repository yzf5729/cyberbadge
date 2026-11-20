# 可移植性与演进顺序

> 结论：**先在 x86（服务器/台式机）上把业务跑通，保持内核与平台无关；硬件相关的部分做成适配层，最后再移植到 ARM 板子。** 系统和板子是最容易换的，业务逻辑才是最贵的。

## 1. 分层

```
┌─────────────────────────────────────┐
│  web/（PWA，纯浏览器）                │  ← 与系统无关
├─────────────────────────────────────┤
│  device/ 业务层                      │  ← Python 标准库 + pip，跨架构
│   main.py / agent.py / tools.py      │
│   skills.py / store.py / registry.py │
├─────────────────────────────────────┤
│  platform/ 适配层（按需实现）          │  ← 唯一与硬件/系统耦合的地方
│   power.py  wifi.py  modem.py        │
│   display.py  watchdog.py  ota.py    │
├─────────────────────────────────────┤
│  OS：Debian 系（Armbian/DietPi/…)    │  ← 可替换
└─────────────────────────────────────┘
```

- 业务层**不 import** 任何系统命令、不写死路径；路径一律走 `AGENT_WORKDIR`、`DSH_HOME` 之类的环境变量；
- 适配层用**接口 + 空实现**：x86 开发时全部是 no-op，ARM 上再填真实实现；
- 系统服务用 systemd 单元模板，**不写死用户名/路径**（用 `%h`、`Environment=`）。

## 2. 什么会阻碍移植（以及现在怎么规避）

| 风险 | 规避方式 |
|---|---|
| 硬编码 `/home/pi`、`/srv/hermes` | 全部走环境变量，默认值相对仓库根目录 |
| 依赖某个发行版才有的包 | 依赖声明分两层：`requirements.txt`（pip 可装）+ `bootstrap.sh`（apt 包，按 Debian 系写，注明其他系需替换） |
| 直接调 `iw`/`nmcli`/`gpio` | 收进 `platform/`，接口不变、实现按板子换 |
| systemd 专属逻辑 | 保留 systemd 作为首选；文档里给出"无 systemd 时的替代"（supervisord/rc.local） |
| 交叉编译 | 业务层是纯 Python，ARM 上直接 `pip install`；只有原生依赖（tesseract/LibreOffice）需要目标系统装 |
| TF 卡写入/掉电 | 日志走内存（log2ram 可选）、SQLite 开 WAL、提供只读模式开关 |

## 3. 演进顺序（推荐）

1. **x86 先行**（现在）：服务器/台式机跑 `uvicorn`，验证会话、工具、技能、ACP；
2. **容器化**：`Dockerfile` 固化依赖，保证"换机器即跑"；
3. **ARM 板子联调**：同一份代码，`platform/` 里填 Wi-Fi 省电、电源状态、看门狗；
4. **系统替换**：Armbian ↔ DietPi ↔ Raspberry Pi OS 之间切换，只改 `bootstrap.sh` 和适配实现；
5. **产品化**：OTA、回滚、只读根文件系统、断电保护。

## 4. 关于"未来再移植"

- **先开发、后移植是正确顺序**，因为业务需求会变，板子/系统只是载体；
- 但有一个例外：**电源与散热的行为**（待机功耗、掉电恢复、温度降频）在 x86 上验证不了，必须在真机上早测——建议 M0 板子到手后**先跑 72 小时稳定性**，再决定是否加 4G/屏幕；
- 另一例外是**性能上限**：如果以后要在本地跑模型，x86 上的体验不能代表 ARM，需按目标 SoC 单独评估。

## 5. 当前代码的移植债

- `device/main.py` 直接用了 `AGENT_WORKDIR`，但 `web/` 是静态目录，已相对路径 —— ✅ 基本可移植；
- `device/office_convert.py` 调 `soffice`，靠 PATH 查找 —— 可移植，但需目标系统装 LibreOffice；
- `device/tools.py` 的 OCR 依赖 `tesseract` 与语言包 —— 需 `bootstrap.sh` 声明；
- `start_agent.bat` 是 Windows 专用 —— ARM 上改用 systemd 单元（文档已给模板）；
- 暂无 `platform/` 包 —— 下一步先加空实现，把 Wi-Fi/电源相关调用收口。
