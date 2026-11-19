# Three form factors (SKUs)

Same agent core, split by "screen or not" and "4G or not".

| | **M1 Standalone** | **M2 Online** | **M3 Lite** |
|---|---|---|---|
| Screen | ✅ built-in 4–5" touch | ❌ borrowed phone (PWA) | ❌ borrowed phone (PWA) |
| Network | ✅ 4G + Wi-Fi | ✅ 4G (device hosts a hotspot for the phone) | ❌ phone hotspot / home Wi-Fi |
| Independence | Highest: no phone needed | High: online whenever powered | Low: offline when the phone is away |
| Weight | 180–220 g | 150–180 g | 80–110 g |
| Battery life | 6–8 h (screen on) / 3 days idle | 18–24 h active / 3–5 days idle | 2–3 days light use / 5–7 days idle |
| BOM | ¥600–700 | ¥420–500 | ¥250–320 |
| Software effort | Medium (UI layer) | Low (reuse PWA) | Lowest |
| Best for | People who don't want to pull out a phone; demos | Main product: an agent that never drops offline | Tinkerers, travel, privacy-first |

## M1 Standalone

- Hardware: 4 GB SoC (RK3566 / Orange Pi class) + 4–5" MIPI touchscreen + 4G Cat.4 + battery/UPS.
- OS: Buildroot/Armbian + lightweight Wayland + Chromium kiosk (reuse the PWA first), native LVGL UI later.
- Hard parts: thermals (2–3 W in a sealed badge), power budget, panel choice (MIPI costs more than SPI but feels much better).
- Not doing: a home-grown phone OS or an app store — that is a different war.

## M2 Online (recommended main product)

- Hardware: 4 GB SoC + 4G Cat.4 + battery; no screen — skips the most expensive and power-hungry part.
- Networking: the device runs a Wi-Fi hotspot with the 4G uplink (NAT); the phone joins the hotspot and opens `http://10.0.0.1`.
- Value: **the agent stays online** — even when the phone is off or has no signal, tasks still reach the device.
- Risks: 4G module drivers (EC200A/EC25 need quectel scripts), heat, data cost.

## M3 Lite

- Hardware: 2 GB SoC + battery, no cellular; Wi-Fi to the phone hotspot or home router.
- Position: **cheapest validation form**, and the "privacy-first" option (offline when away).
- Limitation: offline as soon as the phone leaves; best for home/office.

## Shared software

```
cyberbadge-core (all three)
├─ agent core (task queue / tools / memory)
├─ local web server + PWA
├─ self-check and mode switch (/etc/cyberbadge/mode = m1|m2|m3)
└─ network layer
   ├─ m1/m2: 4G dial-up + Wi-Fi AP + NAT
   └─ m3:    Wi-Fi client only
```

- **v0.1**: runs on any Linux machine (current repo).
- **v0.2**: M3 hardware (borrowed screen + hotspot).
- **v0.3**: M2 with 4G.
- **v0.4**: M1 with screen and kiosk UI.

## Recommendation

Build **M3 to validate the software** (cheapest), then **M2 as the product** (most value), then **M1 for the form factor** (most expensive and hardest).
