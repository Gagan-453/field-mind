# Campaign watch, night of 2026-10-03 / 04

Campaign launched by the human at 23:07:35 (tmux session `campaign`, `~/campaign_loop.sh`). Wi-Fi on: not the offline
proof. Watched by Claude under the human's written rules (relaunch only after exit 2 or a board drop; at most 2 runner
fixes; never after exit 3; nothing under results/ edited; no other board use). All times are laptop time.

## Checks
| time | running | stage | model | episodes done | lane RSS / MemAvailable (latest episode) | peak CPU / NPU C (latest episode) | notes |
|---|---|---|---|---|---|---|---|
| 23:12 | wrapper in its 10-min wait (campaign starts ~23:17:35) | - | - | 0 | - | - | board connected, no llama-server; results/board not created yet |
| 23:43 | yes (1 campaign, started 23:37:59) | A | gemma3-1b-qat | 2 of 4 screenings | - (stage A has no episode yet) | - | ODD: the wrapper's first start at 23:17:35 found 0 adb devices and exited 2; kernel log shows the board off USB and back at 23:27:58 (unexplained, before any campaign call); the wrapper relaunched by itself. idle 33.3 C, no failed attempt, no guard restart |
| 23:45 (addendum) | | | | | | | kernel log: USB disconnect 23:17:33 -> back 23:17:34 (same second as the wrapper's `adb shell svc power stayon usb`), then disconnect 23:25:24 -> back 23:27:58 (2.5 min, reboot-like). Both before the campaign's first call. Cause unexplained |
| 00:14 | yes | B (round 1) | qwen25-0.5b | A 4/4, B 1 of 6 | 489 MB / 6,240 MB (before B/round1/llama32-3b) | 68.2 / 65.2 | 3B finished dev_A01: 59 calls, 1 cache hit, no failed attempt (past the 31-call point where the aborted launch 1 died); thermal gate waited 30 s; no guard restart |
| 00:44 | yes | B (round 2) | llama32-3b | A 4/4, B 2 of 6 | 216 MB / 8,580 MB (before B/round1/qwen25-0.5b) | 57.0 / 51.7 (qwen25 ep); max over all episodes 68.2 CPU | the job that died 3 times (round2/llama32-3b/dev_B01) is at 95 live calls with no stall (old stall: call 37); decode 15-17 tok/s first to last; CPU 66 C; longest call 19.2 s; thermal gate waited 195 s before the qwen25 episode; no guard restart |
