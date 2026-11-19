# M0 建造指南（插电 + Wi-Fi + 触屏）

[English](m0-build.en.md) | **简体中文**

> 这是最快能看到实物的一版：不装电池、不装 4G，插电即用。目标是把"胸牌形态 + 触屏 + agent"先跑通。

## 1. 采购清单

| 件 | 推荐 | 备注 |
|---|---|---|
| 主板 | Orange Pi Zero 3 4GB | 有 Wi-Fi；4GB 跑 Chromium 更稳 |
| 屏幕 | 5" HDMI 触屏 800×480（USB 触摸） | **别买 SPI 屏**，浏览器体验差 |
| 存储 | 32GB TF（A1/A2） | 8GB 太小 |
| 电源 | 5V/3A USB-C | 触屏也要供电，选带供电的 USB Hub 或双口电源 |
| 外壳 | 亚克力/3D 打印 | 先不用做外壳也能跑 |
| 线材 | HDMI 短排线、USB 线 | 短排线好看 |

## 2. 系统

1. 下载 Orange Pi Zero 3 的 Armbian（Debian bookworm）镜像，用 balenaEtcher 写卡；
2. 首次启动接 HDMI 显示器，按向导设 Wi-Fi、用户名、时区；
3. 换到 5" 触屏，确认触摸能用（`xinput list` 能看到设备）。

## 3. 软件

```bash
sudo apt update
sudo apt install -y chromium onboard git python3-venv
git clone https://github.com/yzf5729/cyberbadge.git
cd cyberbadge
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填 LLM_API_KEY
```

先手动跑一次：

```bash
uvicorn device.main:app --host 127.0.0.1 --port 8000
```

另开终端：

```bash
chromium --kiosk --noerrdialogs --disable-infobars http://127.0.0.1:8000
```

## 4. 开机自启

`/etc/systemd/system/cyberbadge.service`：

```ini
[Unit]
Description=CyberBadge agent
After=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/cyberbadge
ExecStart=/home/pi/cyberbadge/.venv/bin/uvicorn device.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cyberbadge
```

kiosk 自启（`~/.config/autostart/cyberbadge-kiosk.desktop`）：

```ini
[Desktop Entry]
Type=Application
Name=CyberBadge Kiosk
Exec=chromium --kiosk --noerrdialogs --disable-infobars http://127.0.0.1:8000
X-GNOME-Autostart-enabled=true
```

## 5. 验收清单

- [ ] 断电重启后，屏幕自动进入 agent 界面
- [ ] 触摸点按正常，虚拟键盘能弹出
- [ ] 说一句话能拿到回复（云端 LLM）
- [ ] 让它"列出 /home/pi 的文件"，工具调用成功
- [ ] 连续跑 2 小时，摸外壳不烫手（>60℃ 就要加散热片）

## 6. 已知问题

- 800×480 下界面字小：先用浏览器缩放 125%，或等小屏 UI 优化；
- Chromium 在 2GB 内存上会卡：优先 4GB；
- Wi-Fi 休眠断连：`sudo iw dev wlan0 set power_save off`，或 systemd 里加 `wifi.powersave = 2`。
