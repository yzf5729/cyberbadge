# M0 建造指南（8G 无屏移动服务器）

> 最低成本的实物验证：**8GB 内存、无屏、Wi-Fi、充电宝供电**。界面跑在手机浏览器里（PWA），设备只做服务器。目标是用最少的钱确认"随身服务器 + 借屏"这条路径成立。

## 1. 采购清单

| 件 | 推荐 | 参考价 | 备注 |
|---|---|---|---|
| 主板 | Radxa Zero 3W 8GB 或 Orange Pi Zero 3 8GB | 260–350 | 必须 8GB；Zero 3W 做工与散热更好 |
| 存储 | 32GB TF（A1/A2） | 30 | 8GB 太小，装完系统就没了 |
| 散热 | 铝散热片 20×20×10mm + 导热垫 | 20 | 被动散热，别用风扇 |
| 外壳 | 3D 打印/亚克力，带通风孔 | 40 | 先裸板也能跑 |
| 供电 | USB-C 线 + 10,000mAh 充电宝（5V/2A 常开输出） | 10 + 80 | 选不会因小电流自动断电的型号 |
| **合计** | | **约 440–530 元** | |

可选：USB 电流表（30 元，测真实功耗）、小 UPS/电源管理板（50–80 元，防掉电）。

## 2. 系统（Armbian，无桌面）

1. 下载对应板子的 **Armbian Bookworm minimal**（不要带桌面镜像），balenaEtcher 写卡；
2. 首次启动**临时接 HDMI** 完成向导：设用户名、密码、Wi-Fi（或先改 `/boot/armbian_first_run.txt` 免接屏）；
3. 之后不再需要屏幕，全部走 SSH。

## 3. 基础设置

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y avahi-daemon git python3-venv
sudo hostnamectl set-hostname cyberbadge
# 手机同 Wi-Fi 即可用 http://cyberbadge.local:8000 访问
```

关闭 Wi-Fi 省电（否则待机会断连）：

```bash
sudo iw dev wlan0 set power_save off
# 开机自动执行：写 /etc/systemd/system/wifi-powersave-off.service
```

## 4. 部署 CyberBadge

```bash
git clone https://github.com/yzf5729/cyberbadge.git ~/cyberbadge
cd ~/cyberbadge
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # 填 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
```

`/etc/systemd/system/cyberbadge.service`：

```ini
[Unit]
Description=CyberBadge agent
After=network-online.target
Wants=network-online.target

[Service]
User=你的用户名
WorkingDirectory=/home/你的用户名/cyberbadge
Environment=AGENT_WORKDIR=/home/你的用户名/cyberbadge/work
ExecStart=/home/你的用户名/cyberbadge/.venv/bin/uvicorn device.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now cyberbadge
curl -s http://127.0.0.1:8000/api/health
```

## 5. 手机当屏

- 手机连同一 Wi-Fi，浏览器打开 `http://cyberbadge.local:8000`；
- Chrome/Safari 菜单 → **添加到主屏幕**，之后像 App 一样打开；
- 外出：手机开热点，让设备连热点（或反过来），地址不变。

## 6. 验收清单

- [ ] 断电重启后，手机打开页面能自动连上（无人工干预）；
- [ ] 连续跑 24 小时，`uptime` 正常、温度 < 75℃（`cat /sys/class/thermal/thermal_zone0/temp`）；
- [ ] 充电宝供电下，12 小时耗电 < 60%；
- [ ] 手机端发一条消息、调用一次工具（如列目录）成功；
- [ ] 拔电再插电，会话历史还在（SQLite 落盘）。

## 7. 已知问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 充电宝几分钟后断电 | 负载电流低于充电宝阈值 | 换"常开/小电流模式"充电宝，或加假负载 |
| 手机打不开 `cyberbadge.local` | 路由器不支持 mDNS | 查路由器后台的设备 IP，直接用 IP |
| Wi-Fi 待机后失联 | 网卡省电 | 第 3 节的 power_save off |
| TF 卡文件系统损坏 | 突然断电写卡 | 尽量正常关机；或加小 UPS 板 |
| 温度过高降频 | 被动散热不足 | 加大散热片、外壳开孔、降 CPU governor |

## 8. 下一步

M0 验证通过（连续 3 天稳定）后，再决定：
- 加 4G（M2）：EC200A 类模组 + 天线，+130–170 元；
- 换自带屏（M1）：5" HDMI 触屏，+160 元；
- 都不急：先把 ACP 接真实 DSH/Hermes 跑通。
