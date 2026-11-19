# 路线图

## v0.1 软件 demo（当前）

- [x] 对话 + 工具调用（文件/网页）
- [x] PWA 借屏
- [x] 后台任务 API
- [ ] 流式输出
- [ ] 本地记忆（SQLite）持久化

## M0 原型机（插电 + Wi-Fi + 4–5" 触屏）

- [ ] 采购：Orange Pi Zero 3 4GB、5" HDMI 触屏、32GB TF、5V/3A 电源
- [ ] 烧录 Armbian 并联网（Wi-Fi client）
- [ ] 装 Chromium + onboard 虚拟键盘，验证 kiosk 全屏
- [ ] 部署 `device/` 与 `cyberbadge.service`（systemd 自启）
- [ ] 开机自启 Chromium kiosk 指向 `http://127.0.0.1:8000`
- [ ] 真机体验记录：800×480 下的布局问题、触摸精度、发热
- [ ] 拍照 + BOM 实测价格回填文档

## v0.2 语音

- [ ] VAD + 云端流式 ASR
- [ ] TTS 播放
- [ ] 按住说话（PWA getUserMedia）

## v0.3 硬件

- [ ] Armbian 镜像脚本（Wi-Fi 热点 + 开机自启）
- [ ] 4G 模块联网
- [ ] 外壳 STL 与装配视频
- [ ] 功耗实测数据

## v0.4 网关与运营

- [ ] 设备注册与配额
- [ ] 多供应商切换与计费
- [ ] 审计日志
