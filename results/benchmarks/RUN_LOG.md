# Benchmark run log

One line per event, laptop time. Written by `scripts/benchmark.sh`; never rewritten.

| time | test | event | details |
|---|---|---|---|
| 2026-10-19 13:59:55 | bevideas_shadow | batch_start | command=scripts/benchmark.sh bevideas_shadow dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal --overlay configs/bev_ideas.yaml --bev explain=shadow,first=shadow,actions=shadow,unknown=shadow,verifier=shadow,notes=shadow,clear_skip=shadow; git={"commit": "41e2bd0", "branch": "bev-ideas", "uncommitted_changes": false}; episodes=10; params={"arch": "multi", "mode": "lockstep", "tick_s": null, "overlay": "configs/bev_ideas.yaml", "overlay_sha256": "194387069d0771ef", "merge_rule": "hybrid", "backend": "llamaserver", "models": {"npu": "Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf", "cpu": "gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf", "bev": "bev-decider-0.4B-backbone-Q8_0.gguf"}, "prompts_saved": true, "bev": "explain=shadow,first=shadow,actions=shadow,unknown=shadow,verifier=shadow,notes=shadow,clear_skip=shadow", "bev_device": "npu"} |
| 2026-10-19 14:00:13 | bevideas_shadow | episode_start | episode=dev_A01_fcv_seize; run=1; stem=dev_A01_fcv_seize_multi; chip_c=36.0 |
| 2026-10-19 14:02:42 | bevideas_shadow | episode_done | episode=dev_A01_fcv_seize; run=1; wall_s=141.6; group_top1=0.561; calls=31; unusable=0; bev_ideas={"actions": {"calls": 14, "failed": 0, "rejected": 0, "used": 0}, "explain": {"calls": 31, "failed": 0, "rejected": 0, "used": 0}, "first": {"calls": 23, "failed": 0, "rejected": 0, "used": 0}, "notes": {"calls": 1, "failed": 0, "rejected": 0, "used": 0}, "unknown": {"calls": 57, "failed": 0, "rejected": 0, "used": 0}} |
| 2026-10-19 14:06:05 | bevideas_shadow | episode_start | episode=dev_A02_fcv_seize_fast; run=1; stem=dev_A02_fcv_seize_fast_multi; chip_c=39.7 |
| 2026-10-19 14:09:35 | bevideas_shadow | episode_done | episode=dev_A02_fcv_seize_fast; run=1; wall_s=201.1; group_top1=0.625; calls=51; unusable=0; bev_ideas={"actions": {"calls": 14, "failed": 0, "rejected": 0, "used": 0}, "clear_skip": {"calls": 0, "failed": 0, "rejected": 0, "used": 0}, "explain": {"calls": 40, "failed": 0, "rejected": 0, "used": 0}, "first": {"calls": 18, "failed": 0, "rejected": 0, "used": 0}, "unknown": {"calls": 64, "failed": 0, "rejected": 0, "used": 0}, "verifier": {"calls": 22, "failed": 0, "rejected": 0, "used": 0}} |
| 2026-10-19 14:14:15 | bevideas_shadow | episode_start | episode=dev_B01_tube_leak; run=1; stem=dev_B01_tube_leak_multi; chip_c=39.7 |
| 2026-10-19 14:18:43 | bevideas_shadow | episode_done | episode=dev_B01_tube_leak; run=1; wall_s=259.1; group_top1=0.953; calls=65; unusable=0; bev_ideas={"actions": {"calls": 2, "failed": 0, "rejected": 0, "used": 0}, "clear_skip": {"calls": 0, "failed": 0, "rejected": 0, "used": 0}, "explain": {"calls": 58, "failed": 0, "rejected": 0, "used": 0}, "first": {"calls": 39, "failed": 0, "rejected": 0, "used": 0}, "notes": {"calls": 1, "failed": 0, "rejected": 0, "used": 0}, "unknown": {"calls": 128, "failed": 0, "rejected": 0, "used": 0}, "verifier": {"calls": 7, "failed": 0, "rejected": 0, "used": 0}} |
| 2026-10-19 14:24:21 | bevideas_shadow | episode_start | episode=dev_B02_tube_leak_fast; run=1; stem=dev_B02_tube_leak_fast_multi; chip_c=39.3 |
| 2026-10-19 14:25:57 | bevideas_shadow | episode_done | episode=dev_B02_tube_leak_fast; run=1; wall_s=88.0; group_top1=1.0; calls=24; unusable=0; bev_ideas={"clear_skip": {"calls": 0, "failed": 0, "rejected": 0, "used": 0}, "explain": {"calls": 23, "failed": 0, "rejected": 0, "used": 0}, "first": {"calls": 2, "failed": 0, "rejected": 0, "used": 0}, "unknown": {"calls": 51, "failed": 0, "rejected": 0, "used": 0}} |
| 2026-10-19 14:29:40 | bevideas_shadow | episode_start | episode=dev_C01_wet_coal; run=1; stem=dev_C01_wet_coal_multi; chip_c=39.3 |
| 2026-10-19 14:32:08 | bevideas_shadow | episode_done | episode=dev_C01_wet_coal; run=1; wall_s=140.1; group_top1=0.529; calls=27; unusable=0; bev_ideas={"actions": {"calls": 17, "failed": 0, "rejected": 0, "used": 0}, "clear_skip": {"calls": 0, "failed": 0, "rejected": 0, "used": 0}, "explain": {"calls": 27, "failed": 0, "rejected": 0, "used": 0}, "first": {"calls": 20, "failed": 0, "rejected": 0, "used": 0}, "notes": {"calls": 1, "failed": 0, "rejected": 0, "used": 0}, "unknown": {"calls": 52, "failed": 0, "rejected": 0, "used": 0}} |
| 2026-10-19 14:37:27 | bevideas_shadow | episode_start | episode=dev_C02_feeder_trip; run=1; stem=dev_C02_feeder_trip_multi; chip_c=39.7 |
| 2026-10-19 14:41:44 | bevideas_shadow | episode_done | episode=dev_C02_feeder_trip; run=1; wall_s=249.6; group_top1=0.429; calls=58; unusable=0; bev_ideas={"actions": {"calls": 34, "failed": 0, "rejected": 0, "used": 0}, "explain": {"calls": 42, "failed": 0, "rejected": 0, "used": 0}, "first": {"calls": 41, "failed": 0, "rejected": 0, "used": 0}, "unknown": {"calls": 77, "failed": 0, "rejected": 0, "used": 0}, "verifier": {"calls": 28, "failed": 0, "rejected": 0, "used": 0}} |
| 2026-10-19 14:48:21 | bevideas_shadow | episode_start | episode=dev_D01_high_cv_coal; run=1; stem=dev_D01_high_cv_coal_multi; chip_c=39.7 |
| 2026-10-19 15:01:02 | bevideas_shadow | episode_done | episode=dev_D01_high_cv_coal; run=1; wall_s=753.4; group_top1=0.804; calls=134; unusable=0; bev_ideas={"actions": {"calls": 241, "failed": 0, "rejected": 0, "used": 0}, "clear_skip": {"calls": 0, "failed": 0, "rejected": 0, "used": 0}, "explain": {"calls": 127, "failed": 0, "rejected": 0, "used": 0}, "first": {"calls": 8, "failed": 0, "rejected": 0, "used": 0}, "notes": {"calls": 1, "failed": 0, "rejected": 0, "used": 0}, "unknown": {"calls": 250, "failed": 0, "rejected": 0, "used": 0}, "verifier": {"calls": 9, "failed": 0, "rejected": 0, "used": 0}} |
| 2026-10-19 15:07:58 | bevideas_shadow | episode_start | episode=dev_D03_high_cv_severe; run=1; stem=dev_D03_high_cv_severe_multi; chip_c=39.7 |
| 2026-10-19 15:13:23 | bevideas_shadow | episode_done | episode=dev_D03_high_cv_severe; run=1; wall_s=317.2; group_top1=0.939; calls=56; unusable=0; bev_ideas={"actions": {"calls": 132, "failed": 0, "rejected": 0, "used": 0}, "clear_skip": {"calls": 0, "failed": 0, "rejected": 0, "used": 0}, "explain": {"calls": 56, "failed": 0, "rejected": 0, "used": 0}, "first": {"calls": 11, "failed": 0, "rejected": 0, "used": 0}, "notes": {"calls": 1, "failed": 0, "rejected": 0, "used": 0}, "unknown": {"calls": 132, "failed": 0, "rejected": 0, "used": 0}} |
| 2026-10-19 15:19:59 | bevideas_shadow | episode_start | episode=dev_N01_normal; run=1; stem=dev_N01_normal_multi; chip_c=39.7 |
| 2026-10-19 15:20:14 | bevideas_shadow | episode_done | episode=dev_N01_normal; run=1; wall_s=6.5; calls=0; unusable=0 |
| 2026-10-19 15:20:45 | bevideas_shadow | episode_start | episode=dev_N02_normal; run=1; stem=dev_N02_normal_multi; chip_c=39.7 |
| 2026-10-19 15:21:03 | bevideas_shadow | episode_done | episode=dev_N02_normal; run=1; wall_s=10.5; calls=1; unusable=0; bev_ideas={"actions": {"calls": 1, "failed": 0, "rejected": 0, "used": 0}, "explain": {"calls": 1, "failed": 0, "rejected": 0, "used": 0}, "unknown": {"calls": 1, "failed": 0, "rejected": 0, "used": 0}} |
| 2026-10-19 15:21:04 | bevideas_shadow | batch_end | status=all episodes done |
| 2026-10-19 15:26:24 | bevideas_A1 | batch_start | command=scripts/benchmark.sh bevideas_A1 dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal --overlay configs/bev_ideas.yaml; git={"commit": "41e2bd0", "branch": "bev-ideas", "uncommitted_changes": false}; episodes=10; params={"arch": "multi", "mode": "lockstep", "tick_s": null, "overlay": "configs/bev_ideas.yaml", "overlay_sha256": "194387069d0771ef", "merge_rule": "hybrid", "backend": "llamaserver", "models": {"npu": "Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf", "cpu": "gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf", "bev": "bev-decider-0.4B-backbone-Q8_0.gguf"}, "prompts_saved": true, "bev_device": "npu"} |
| 2026-10-19 15:26:44 | bevideas_A1 | episode_start | episode=dev_A01_fcv_seize; run=1; stem=dev_A01_fcv_seize_multi; chip_c=38.6 |
| 2026-10-19 15:28:30 | bevideas_A1 | episode_done | episode=dev_A01_fcv_seize; run=1; wall_s=98.6; group_top1=0.561; calls=31; unusable=0 |
| 2026-10-19 15:30:18 | bevideas_A1 | episode_start | episode=dev_A02_fcv_seize_fast; run=1; stem=dev_A02_fcv_seize_fast_multi; chip_c=42.0 |
| 2026-10-19 15:32:45 | bevideas_A1 | episode_done | episode=dev_A02_fcv_seize_fast; run=1; wall_s=138.6; group_top1=0.625; calls=51; unusable=0 |
| 2026-10-19 15:35:49 | bevideas_A1 | episode_start | episode=dev_B01_tube_leak; run=1; stem=dev_B01_tube_leak_multi; chip_c=42.0 |
| 2026-10-19 15:39:03 | bevideas_A1 | episode_done | episode=dev_B01_tube_leak; run=1; wall_s=186.1; group_top1=0.953; calls=65; unusable=0 |
| 2026-10-19 15:42:28 | bevideas_A1 | episode_start | episode=dev_B02_tube_leak_fast; run=1; stem=dev_B02_tube_leak_fast_multi; chip_c=42.0 |
| 2026-10-19 15:43:44 | bevideas_A1 | episode_done | episode=dev_B02_tube_leak_fast; run=1; wall_s=68.5; group_top1=1.0; calls=24; unusable=0 |
| 2026-10-19 15:45:51 | bevideas_A1 | episode_start | episode=dev_C01_wet_coal; run=1; stem=dev_C01_wet_coal_multi; chip_c=42.0 |
| 2026-10-19 15:47:35 | bevideas_A1 | episode_done | episode=dev_C01_wet_coal; run=1; wall_s=96.0; group_top1=0.451; calls=27; unusable=0 |
| 2026-10-19 15:50:02 | bevideas_A1 | episode_start | episode=dev_C02_feeder_trip; run=1; stem=dev_C02_feeder_trip_multi; chip_c=42.0 |
| 2026-10-19 15:53:02 | bevideas_A1 | episode_done | episode=dev_C02_feeder_trip; run=1; wall_s=171.6; group_top1=0.429; calls=58; unusable=0 |
| 2026-10-19 15:56:07 | bevideas_A1 | episode_start | episode=dev_D01_high_cv_coal; run=1; stem=dev_D01_high_cv_coal_multi; chip_c=41.8 |
| 2026-10-19 16:03:59 | bevideas_A1 | episode_done | episode=dev_D01_high_cv_coal; run=1; wall_s=464.3; group_top1=0.804; calls=134; unusable=0 |
| 2026-10-19 16:07:42 | bevideas_A1 | episode_start | episode=dev_D03_high_cv_severe; run=1; stem=dev_D03_high_cv_severe_multi; chip_c=42.0 |
| 2026-10-19 16:10:41 | bevideas_A1 | episode_done | episode=dev_D03_high_cv_severe; run=1; wall_s=171.6; group_top1=0.939; calls=56; unusable=0 |
| 2026-10-19 16:14:05 | bevideas_A1 | episode_start | episode=dev_N01_normal; run=1; stem=dev_N01_normal_multi; chip_c=42.0 |
| 2026-10-19 16:14:20 | bevideas_A1 | episode_done | episode=dev_N01_normal; run=1; wall_s=7.0; calls=0; unusable=0 |
| 2026-10-19 16:14:51 | bevideas_A1 | episode_start | episode=dev_N02_normal; run=1; stem=dev_N02_normal_multi; chip_c=41.7 |
| 2026-10-19 16:15:10 | bevideas_A1 | episode_done | episode=dev_N02_normal; run=1; wall_s=10.5; calls=1; unusable=0 |
| 2026-10-19 16:15:11 | bevideas_A1 | batch_end | status=all episodes done |
| 2026-10-19 16:15:11 | bevideas_B_explain | batch_start | command=scripts/benchmark.sh bevideas_B_explain dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal --overlay configs/bev_ideas.yaml --bev explain=on; git={"commit": "41e2bd0", "branch": "bev-ideas", "uncommitted_changes": false}; episodes=10; params={"arch": "multi", "mode": "lockstep", "tick_s": null, "overlay": "configs/bev_ideas.yaml", "overlay_sha256": "194387069d0771ef", "merge_rule": "hybrid", "backend": "llamaserver", "models": {"npu": "Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf", "cpu": "gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf", "bev": "bev-decider-0.4B-backbone-Q8_0.gguf"}, "prompts_saved": true, "bev": "explain=on", "bev_device": "npu"} |
| 2026-10-19 16:15:29 | bevideas_B_explain | episode_start | episode=dev_A01_fcv_seize; run=1; stem=dev_A01_fcv_seize_multi; chip_c=43.4 |
| 2026-10-19 16:16:43 | bevideas_B_explain | episode_done | episode=dev_A01_fcv_seize; run=1; wall_s=65.5; group_top1=0.509; calls=62; unusable=0; bev_ideas={"explain": {"calls": 31, "failed": 0, "rejected": 0, "used": 31}} |
| 2026-10-19 16:17:13 | bevideas_B_explain | episode_start | episode=dev_A02_fcv_seize_fast; run=1; stem=dev_A02_fcv_seize_fast_multi; chip_c=46.7 |
| 2026-10-19 16:19:05 | bevideas_B_explain | episode_done | episode=dev_A02_fcv_seize_fast; run=1; wall_s=103.0; group_top1=0.625; calls=91; unusable=0; bev_ideas={"explain": {"calls": 40, "failed": 0, "rejected": 0, "used": 40}} |
| 2026-10-19 16:20:14 | bevideas_B_explain | episode_start | episode=dev_B01_tube_leak; run=1; stem=dev_B01_tube_leak_multi; chip_c=46.7 |
| 2026-10-19 16:22:29 | bevideas_B_explain | episode_done | episode=dev_B01_tube_leak; run=1; wall_s=128.1; group_top1=0.953; calls=123; unusable=0; bev_ideas={"explain": {"calls": 58, "failed": 0, "rejected": 0, "used": 58}} |
| 2026-10-19 16:23:39 | bevideas_B_explain | episode_start | episode=dev_B02_tube_leak_fast; run=1; stem=dev_B02_tube_leak_fast_multi; chip_c=48.2 |
| 2026-10-19 16:24:30 | bevideas_B_explain | episode_done | episode=dev_B02_tube_leak_fast; run=1; wall_s=43.5; group_top1=1.0; calls=47; unusable=0; bev_ideas={"explain": {"calls": 23, "failed": 0, "rejected": 0, "used": 23}} |
| 2026-10-19 16:25:20 | bevideas_B_explain | episode_start | episode=dev_C01_wet_coal; run=1; stem=dev_C01_wet_coal_multi; chip_c=47.5 |
| 2026-10-19 16:26:32 | bevideas_B_explain | episode_done | episode=dev_C01_wet_coal; run=1; wall_s=64.0; group_top1=0.549; calls=54; unusable=0; bev_ideas={"explain": {"calls": 27, "failed": 0, "rejected": 0, "used": 27}} |
| 2026-10-19 16:27:22 | bevideas_B_explain | episode_start | episode=dev_C02_feeder_trip; run=1; stem=dev_C02_feeder_trip_multi; chip_c=47.5 |
| 2026-10-19 16:29:21 | bevideas_B_explain | episode_done | episode=dev_C02_feeder_trip; run=1; wall_s=111.6; group_top1=0.571; calls=98; unusable=0; bev_ideas={"explain": {"calls": 42, "failed": 0, "rejected": 0, "used": 42}} |
| 2026-10-19 16:30:52 | bevideas_B_explain | episode_start | episode=dev_D01_high_cv_coal; run=1; stem=dev_D01_high_cv_coal_multi; chip_c=46.7 |
| 2026-10-19 16:36:19 | bevideas_B_explain | episode_done | episode=dev_D01_high_cv_coal; run=1; wall_s=318.7; group_top1=0.804; calls=261; unusable=0; bev_ideas={"explain": {"calls": 127, "failed": 0, "rejected": 0, "used": 127}} |
| 2026-10-19 16:38:06 | bevideas_B_explain | episode_start | episode=dev_D03_high_cv_severe; run=1; stem=dev_D03_high_cv_severe_multi; chip_c=47.1 |
| 2026-10-19 16:40:21 | bevideas_B_explain | episode_done | episode=dev_D03_high_cv_severe; run=1; wall_s=126.6; group_top1=0.939; calls=112; unusable=0; bev_ideas={"explain": {"calls": 56, "failed": 0, "rejected": 0, "used": 56}} |
| 2026-10-19 16:41:50 | bevideas_B_explain | episode_start | episode=dev_N01_normal; run=1; stem=dev_N01_normal_multi; chip_c=46.7 |
| 2026-10-19 16:42:05 | bevideas_B_explain | episode_done | episode=dev_N01_normal; run=1; wall_s=7.0; calls=0; unusable=0 |
| 2026-10-19 16:42:16 | bevideas_B_explain | episode_start | episode=dev_N02_normal; run=1; stem=dev_N02_normal_multi; chip_c=47.1 |
| 2026-10-19 16:42:34 | bevideas_B_explain | episode_done | episode=dev_N02_normal; run=1; wall_s=9.0; calls=2; unusable=0; bev_ideas={"explain": {"calls": 1, "failed": 0, "rejected": 0, "used": 1}} |
| 2026-10-19 16:42:35 | bevideas_B_explain | batch_end | status=all episodes done |
| 2026-10-19 16:42:35 | bevideas_B_actions | batch_start | command=scripts/benchmark.sh bevideas_B_actions dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal --overlay configs/bev_ideas.yaml --bev actions=on; git={"commit": "41e2bd0", "branch": "bev-ideas", "uncommitted_changes": false}; episodes=10; params={"arch": "multi", "mode": "lockstep", "tick_s": null, "overlay": "configs/bev_ideas.yaml", "overlay_sha256": "194387069d0771ef", "merge_rule": "hybrid", "backend": "llamaserver", "models": {"npu": "Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf", "cpu": "gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf", "bev": "bev-decider-0.4B-backbone-Q8_0.gguf"}, "prompts_saved": true, "bev": "actions=on", "bev_device": "npu"} |
| 2026-10-19 16:42:53 | bevideas_B_actions | episode_start | episode=dev_A01_fcv_seize; run=1; stem=dev_A01_fcv_seize_multi; chip_c=47.3 |
| 2026-10-19 16:44:47 | bevideas_B_actions | episode_done | episode=dev_A01_fcv_seize; run=1; wall_s=106.2; group_top1=0.561; calls=45; unusable=0; bev_ideas={"actions": {"calls": 14, "failed": 0, "rejected": 0, "used": 14}} |
| 2026-10-19 16:45:18 | bevideas_B_actions | episode_start | episode=dev_A02_fcv_seize_fast; run=1; stem=dev_A02_fcv_seize_fast_multi; chip_c=51.7 |
| 2026-10-19 16:47:57 | bevideas_B_actions | episode_done | episode=dev_A02_fcv_seize_fast; run=1; wall_s=150.6; group_top1=0.625; calls=65; unusable=0; bev_ideas={"actions": {"calls": 14, "failed": 0, "rejected": 0, "used": 14}} |
| 2026-10-19 16:48:47 | bevideas_B_actions | episode_start | episode=dev_B01_tube_leak; run=1; stem=dev_B01_tube_leak_multi; chip_c=51.3 |
| 2026-10-19 16:52:12 | bevideas_B_actions | episode_done | episode=dev_B01_tube_leak; run=1; wall_s=197.1; group_top1=0.953; calls=67; unusable=0; bev_ideas={"actions": {"calls": 2, "failed": 0, "rejected": 0, "used": 2}} |
| 2026-10-19 16:53:21 | bevideas_B_actions | episode_start | episode=dev_B02_tube_leak_fast; run=1; stem=dev_B02_tube_leak_fast_multi; chip_c=50.2 |
| 2026-10-19 16:54:44 | bevideas_B_actions | episode_done | episode=dev_B02_tube_leak_fast; run=1; wall_s=75.0; group_top1=1.0; calls=24; unusable=0 |
| 2026-10-19 16:55:15 | bevideas_B_actions | episode_start | episode=dev_C01_wet_coal; run=1; stem=dev_C01_wet_coal_multi; chip_c=51.7 |
| 2026-10-19 16:57:08 | bevideas_B_actions | episode_done | episode=dev_C01_wet_coal; run=1; wall_s=105.1; group_top1=0.549; calls=44; unusable=0; bev_ideas={"actions": {"calls": 17, "failed": 0, "rejected": 0, "used": 17}} |
| 2026-10-19 16:58:00 | bevideas_B_actions | episode_start | episode=dev_C02_feeder_trip; run=1; stem=dev_C02_feeder_trip_multi; chip_c=49.8 |
| 2026-10-19 17:01:20 | bevideas_B_actions | episode_done | episode=dev_C02_feeder_trip; run=1; wall_s=191.6; group_top1=0.429; calls=92; unusable=0; bev_ideas={"actions": {"calls": 34, "failed": 0, "rejected": 0, "used": 34}} |
| 2026-10-19 17:02:12 | bevideas_B_actions | episode_start | episode=dev_D01_high_cv_coal; run=1; stem=dev_D01_high_cv_coal_multi; chip_c=51.3 |
| 2026-10-19 17:12:08 | bevideas_B_actions | episode_done | episode=dev_D01_high_cv_coal; run=1; wall_s=587.4; group_top1=0.804; calls=375; unusable=0; bev_ideas={"actions": {"calls": 241, "failed": 0, "rejected": 0, "used": 241}} |
| 2026-10-19 17:13:36 | bevideas_B_actions | episode_start | episode=dev_D03_high_cv_severe; run=1; stem=dev_D03_high_cv_severe_multi; chip_c=50.2 |
| 2026-10-19 17:17:46 | bevideas_B_actions | episode_done | episode=dev_D03_high_cv_severe; run=1; wall_s=242.1; group_top1=0.939; calls=188; unusable=0; bev_ideas={"actions": {"calls": 132, "failed": 0, "rejected": 0, "used": 132}} |
| 2026-10-19 17:18:56 | bevideas_B_actions | episode_start | episode=dev_N01_normal; run=1; stem=dev_N01_normal_multi; chip_c=50.9 |
| 2026-10-19 17:19:11 | bevideas_B_actions | episode_done | episode=dev_N01_normal; run=1; wall_s=7.0; calls=0; unusable=0 |
| 2026-10-19 17:19:22 | bevideas_B_actions | episode_start | episode=dev_N02_normal; run=1; stem=dev_N02_normal_multi; chip_c=50.5 |
| 2026-10-19 17:19:40 | bevideas_B_actions | episode_done | episode=dev_N02_normal; run=1; wall_s=10.0; calls=2; unusable=0; bev_ideas={"actions": {"calls": 1, "failed": 0, "rejected": 0, "used": 1}} |
| 2026-10-19 17:19:41 | bevideas_B_actions | batch_end | status=all episodes done |
| 2026-10-19 17:19:42 | bevideas_B_unknown | batch_start | command=scripts/benchmark.sh bevideas_B_unknown dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal --overlay configs/bev_ideas.yaml --bev unknown=on; git={"commit": "41e2bd0", "branch": "bev-ideas", "uncommitted_changes": false}; episodes=10; params={"arch": "multi", "mode": "lockstep", "tick_s": null, "overlay": "configs/bev_ideas.yaml", "overlay_sha256": "194387069d0771ef", "merge_rule": "hybrid", "backend": "llamaserver", "models": {"npu": "Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf", "cpu": "gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf", "bev": "bev-decider-0.4B-backbone-Q8_0.gguf"}, "prompts_saved": true, "bev": "unknown=on", "bev_device": "npu"} |
| 2026-10-19 17:20:18 | bevideas_B_unknown | episode_start | episode=dev_A01_fcv_seize; run=1; stem=dev_A01_fcv_seize_multi; chip_c=51.3 |
| 2026-10-19 17:22:30 | bevideas_B_unknown | episode_done | episode=dev_A01_fcv_seize; run=1; wall_s=124.1; group_top1=0.614; calls=88; unusable=0; bev_ideas={"unknown": {"calls": 57, "failed": 0, "rejected": 0, "used": 57}} |
| 2026-10-19 17:23:01 | bevideas_B_unknown | episode_start | episode=dev_A02_fcv_seize_fast; run=1; stem=dev_A02_fcv_seize_fast_multi; chip_c=53.6 |
| 2026-10-19 17:25:59 | bevideas_B_unknown | episode_done | episode=dev_A02_fcv_seize_fast; run=1; wall_s=169.6; group_top1=0.625; calls=115; unusable=0; bev_ideas={"unknown": {"calls": 64, "failed": 0, "rejected": 0, "used": 64}} |
| 2026-10-19 17:26:31 | bevideas_B_unknown | episode_start | episode=dev_B01_tube_leak; run=1; stem=dev_B01_tube_leak_multi; chip_c=54.4 |
| 2026-10-19 17:30:39 | bevideas_B_unknown | episode_done | episode=dev_B01_tube_leak; run=1; wall_s=239.1; group_top1=0.953; calls=193; unusable=0; bev_ideas={"unknown": {"calls": 128, "failed": 0, "rejected": 0, "used": 128}} |
| 2026-10-19 17:31:31 | bevideas_B_unknown | episode_start | episode=dev_B02_tube_leak_fast; run=1; stem=dev_B02_tube_leak_fast_multi; chip_c=52.9 |
| 2026-10-19 17:33:09 | bevideas_B_unknown | episode_done | episode=dev_B02_tube_leak_fast; run=1; wall_s=90.0; group_top1=1.0; calls=75; unusable=0; bev_ideas={"unknown": {"calls": 51, "failed": 0, "rejected": 0, "used": 51}} |
| 2026-10-19 17:33:42 | bevideas_B_unknown | episode_start | episode=dev_C01_wet_coal; run=1; stem=dev_C01_wet_coal_multi; chip_c=54.0 |
| 2026-10-19 17:35:47 | bevideas_B_unknown | episode_done | episode=dev_C01_wet_coal; run=1; wall_s=117.1; group_top1=0.451; calls=79; unusable=0; bev_ideas={"unknown": {"calls": 52, "failed": 0, "rejected": 0, "used": 52}} |
| 2026-10-19 17:36:20 | bevideas_B_unknown | episode_start | episode=dev_C02_feeder_trip; run=1; stem=dev_C02_feeder_trip_multi; chip_c=54.8 |
| 2026-10-19 17:39:56 | bevideas_B_unknown | episode_done | episode=dev_C02_feeder_trip; run=1; wall_s=208.6; group_top1=0.455; calls=135; unusable=0; bev_ideas={"unknown": {"calls": 77, "failed": 0, "rejected": 0, "used": 77}} |
| 2026-10-19 17:40:48 | bevideas_B_unknown | episode_start | episode=dev_D01_high_cv_coal; run=1; stem=dev_D01_high_cv_coal_multi; chip_c=53.2 |
| 2026-10-19 17:50:31 | bevideas_B_unknown | episode_done | episode=dev_D01_high_cv_coal; run=1; wall_s=574.9; group_top1=0.804; calls=384; unusable=0; bev_ideas={"unknown": {"calls": 250, "failed": 0, "rejected": 0, "used": 250}} |
| 2026-10-19 17:51:23 | bevideas_B_unknown | episode_start | episode=dev_D03_high_cv_severe; run=1; stem=dev_D03_high_cv_severe_multi; chip_c=54.4 |
| 2026-10-19 17:55:23 | bevideas_B_unknown | episode_done | episode=dev_D03_high_cv_severe; run=1; wall_s=231.7; group_top1=0.939; calls=188; unusable=0; bev_ideas={"unknown": {"calls": 132, "failed": 0, "rejected": 0, "used": 132}} |
| 2026-10-19 17:56:15 | bevideas_B_unknown | episode_start | episode=dev_N01_normal; run=1; stem=dev_N01_normal_multi; chip_c=53.2 |
| 2026-10-19 17:56:30 | bevideas_B_unknown | episode_done | episode=dev_N01_normal; run=1; wall_s=7.0; calls=0; unusable=0 |
| 2026-10-19 17:56:42 | bevideas_B_unknown | episode_start | episode=dev_N02_normal; run=1; stem=dev_N02_normal_multi; chip_c=52.9 |
| 2026-10-19 17:57:00 | bevideas_B_unknown | episode_done | episode=dev_N02_normal; run=1; wall_s=10.5; calls=2; unusable=0; bev_ideas={"unknown": {"calls": 1, "failed": 0, "rejected": 0, "used": 1}} |
| 2026-10-19 17:57:01 | bevideas_B_unknown | batch_end | status=all episodes done |
| 2026-10-19 17:57:02 | bevideas_B_verifier | batch_start | command=scripts/benchmark.sh bevideas_B_verifier dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal --overlay configs/bev_ideas.yaml --bev verifier=on; git={"commit": "41e2bd0", "branch": "bev-ideas", "uncommitted_changes": false}; episodes=10; params={"arch": "multi", "mode": "lockstep", "tick_s": null, "overlay": "configs/bev_ideas.yaml", "overlay_sha256": "194387069d0771ef", "merge_rule": "hybrid", "backend": "llamaserver", "models": {"npu": "Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf", "cpu": "gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf", "bev": "bev-decider-0.4B-backbone-Q8_0.gguf"}, "prompts_saved": true, "bev": "verifier=on", "bev_device": "npu"} |
| 2026-10-19 17:57:20 | bevideas_B_verifier | episode_start | episode=dev_A01_fcv_seize; run=1; stem=dev_A01_fcv_seize_multi; chip_c=52.9 |
| 2026-10-19 17:59:17 | bevideas_B_verifier | episode_done | episode=dev_A01_fcv_seize; run=1; wall_s=109.1; group_top1=0.561; calls=31; unusable=0 |
| 2026-10-19 17:59:47 | bevideas_B_verifier | episode_start | episode=dev_A02_fcv_seize_fast; run=1; stem=dev_A02_fcv_seize_fast_multi; chip_c=54.0 |
| 2026-10-19 18:02:09 | bevideas_B_verifier | episode_done | episode=dev_A02_fcv_seize_fast; run=1; wall_s=135.1; group_top1=0.625; calls=73; unusable=0; bev_ideas={"verifier": {"calls": 22, "failed": 0, "rejected": 0, "used": 11}} |
| 2026-10-19 18:02:42 | bevideas_B_verifier | episode_start | episode=dev_B01_tube_leak; run=1; stem=dev_B01_tube_leak_multi; chip_c=55.6 |
| 2026-10-19 18:06:02 | bevideas_B_verifier | episode_done | episode=dev_B01_tube_leak; run=1; wall_s=191.6; group_top1=0.953; calls=72; unusable=0; bev_ideas={"verifier": {"calls": 7, "failed": 0, "rejected": 0, "used": 7}} |
| 2026-10-19 18:06:35 | bevideas_B_verifier | episode_start | episode=dev_B02_tube_leak_fast; run=1; stem=dev_B02_tube_leak_fast_multi; chip_c=56.7 |
| 2026-10-19 18:07:58 | bevideas_B_verifier | episode_done | episode=dev_B02_tube_leak_fast; run=1; wall_s=75.5; group_top1=1.0; calls=24; unusable=0 |
| 2026-10-19 18:08:31 | bevideas_B_verifier | episode_start | episode=dev_C01_wet_coal; run=1; stem=dev_C01_wet_coal_multi; chip_c=55.6 |
| 2026-10-19 18:10:23 | bevideas_B_verifier | episode_done | episode=dev_C01_wet_coal; run=1; wall_s=103.6; group_top1=0.451; calls=27; unusable=0 |
| 2026-10-19 18:10:55 | bevideas_B_verifier | episode_start | episode=dev_C02_feeder_trip; run=1; stem=dev_C02_feeder_trip_multi; chip_c=55.2 |
| 2026-10-19 18:13:45 | bevideas_B_verifier | episode_done | episode=dev_C02_feeder_trip; run=1; wall_s=161.6; group_top1=0.429; calls=87; unusable=0; bev_ideas={"verifier": {"calls": 29, "failed": 0, "rejected": 0, "used": 16}} |
| 2026-10-19 18:14:18 | bevideas_B_verifier | episode_start | episode=dev_D01_high_cv_coal; run=1; stem=dev_D01_high_cv_coal_multi; chip_c=55.6 |
| 2026-10-19 18:22:31 | bevideas_B_verifier | episode_done | episode=dev_D01_high_cv_coal; run=1; wall_s=484.9; group_top1=0.804; calls=143; unusable=0; bev_ideas={"verifier": {"calls": 9, "failed": 0, "rejected": 0, "used": 7}} |
| 2026-10-19 18:23:04 | bevideas_B_verifier | episode_start | episode=dev_D03_high_cv_severe; run=1; stem=dev_D03_high_cv_severe_multi; chip_c=56.7 |
| 2026-10-19 18:26:23 | bevideas_B_verifier | episode_done | episode=dev_D03_high_cv_severe; run=1; wall_s=191.6; group_top1=0.939; calls=56; unusable=0 |
| 2026-10-19 18:26:56 | bevideas_B_verifier | episode_start | episode=dev_N01_normal; run=1; stem=dev_N01_normal_multi; chip_c=56.3 |
| 2026-10-19 18:27:11 | bevideas_B_verifier | episode_done | episode=dev_N01_normal; run=1; wall_s=6.5; calls=0; unusable=0 |
| 2026-10-19 18:27:24 | bevideas_B_verifier | episode_start | episode=dev_N02_normal; run=1; stem=dev_N02_normal_multi; chip_c=53.6 |
| 2026-10-19 18:27:42 | bevideas_B_verifier | episode_done | episode=dev_N02_normal; run=1; wall_s=10.0; calls=1; unusable=0 |
| 2026-10-19 18:27:43 | bevideas_B_verifier | batch_end | status=all episodes done |
| 2026-10-19 18:27:44 | bevideas_B_notes | batch_start | command=scripts/benchmark.sh bevideas_B_notes dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal --overlay configs/bev_ideas.yaml --bev notes=on; git={"commit": "41e2bd0", "branch": "bev-ideas", "uncommitted_changes": false}; episodes=10; params={"arch": "multi", "mode": "lockstep", "tick_s": null, "overlay": "configs/bev_ideas.yaml", "overlay_sha256": "194387069d0771ef", "merge_rule": "hybrid", "backend": "llamaserver", "models": {"npu": "Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf", "cpu": "gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf", "bev": "bev-decider-0.4B-backbone-Q8_0.gguf"}, "prompts_saved": true, "bev": "notes=on", "bev_device": "npu"} |
| 2026-10-19 18:28:02 | bevideas_B_notes | episode_start | episode=dev_A01_fcv_seize; run=1; stem=dev_A01_fcv_seize_multi; chip_c=53.1 |
| 2026-10-19 18:29:49 | bevideas_B_notes | episode_done | episode=dev_A01_fcv_seize; run=1; wall_s=99.5; group_top1=0.561; calls=32; unusable=0; bev_ideas={"notes": {"calls": 1, "failed": 0, "rejected": 0, "used": 1}} |
| 2026-10-19 18:30:22 | bevideas_B_notes | episode_start | episode=dev_A02_fcv_seize_fast; run=1; stem=dev_A02_fcv_seize_fast_multi; chip_c=53.2 |
| 2026-10-19 18:33:01 | bevideas_B_notes | episode_done | episode=dev_A02_fcv_seize_fast; run=1; wall_s=151.6; group_top1=0.625; calls=51; unusable=0 |
| 2026-10-19 18:33:34 | bevideas_B_notes | episode_start | episode=dev_B01_tube_leak; run=1; stem=dev_B01_tube_leak_multi; chip_c=54.8 |
| 2026-10-19 18:36:59 | bevideas_B_notes | episode_done | episode=dev_B01_tube_leak; run=1; wall_s=196.6; group_top1=0.953; calls=66; unusable=0; bev_ideas={"notes": {"calls": 1, "failed": 0, "rejected": 0, "used": 1}} |
| 2026-10-19 18:37:32 | bevideas_B_notes | episode_start | episode=dev_B02_tube_leak_fast; run=1; stem=dev_B02_tube_leak_fast_multi; chip_c=56.0 |
| 2026-10-19 18:38:54 | bevideas_B_notes | episode_done | episode=dev_B02_tube_leak_fast; run=1; wall_s=74.5; group_top1=1.0; calls=24; unusable=0 |
| 2026-10-19 18:39:27 | bevideas_B_notes | episode_start | episode=dev_C01_wet_coal; run=1; stem=dev_C01_wet_coal_multi; chip_c=54.0 |
| 2026-10-19 18:41:14 | bevideas_B_notes | episode_done | episode=dev_C01_wet_coal; run=1; wall_s=99.6; group_top1=0.451; calls=28; unusable=0; bev_ideas={"notes": {"calls": 1, "failed": 0, "rejected": 0, "used": 1}} |
| 2026-10-19 18:41:47 | bevideas_B_notes | episode_start | episode=dev_C02_feeder_trip; run=1; stem=dev_C02_feeder_trip_multi; chip_c=54.4 |
| 2026-10-19 18:44:58 | bevideas_B_notes | episode_done | episode=dev_C02_feeder_trip; run=1; wall_s=182.6; group_top1=0.429; calls=58; unusable=0 |
| 2026-10-19 18:45:31 | bevideas_B_notes | episode_start | episode=dev_D01_high_cv_coal; run=1; stem=dev_D01_high_cv_coal_multi; chip_c=56.7 |
| 2026-10-19 18:53:54 | bevideas_B_notes | episode_done | episode=dev_D01_high_cv_coal; run=1; wall_s=494.8; group_top1=0.804; calls=135; unusable=0; bev_ideas={"notes": {"calls": 1, "failed": 0, "rejected": 0, "used": 1}} |
| 2026-10-19 18:54:27 | bevideas_B_notes | episode_start | episode=dev_D03_high_cv_severe; run=1; stem=dev_D03_high_cv_severe_multi; chip_c=57.1 |
| 2026-10-19 18:57:45 | bevideas_B_notes | episode_done | episode=dev_D03_high_cv_severe; run=1; wall_s=190.6; group_top1=0.939; calls=56; unusable=0; bev_ideas={"notes": {"calls": 1, "failed": 0, "rejected": 0, "used": 1}} |
| 2026-10-19 18:58:18 | bevideas_B_notes | episode_start | episode=dev_N01_normal; run=1; stem=dev_N01_normal_multi; chip_c=56.7 |
| 2026-10-19 18:58:33 | bevideas_B_notes | episode_done | episode=dev_N01_normal; run=1; wall_s=7.0; calls=0; unusable=0 |
| 2026-10-19 18:58:46 | bevideas_B_notes | episode_start | episode=dev_N02_normal; run=1; stem=dev_N02_normal_multi; chip_c=54.4 |
| 2026-10-19 18:59:04 | bevideas_B_notes | episode_done | episode=dev_N02_normal; run=1; wall_s=10.0; calls=1; unusable=0 |
| 2026-10-19 18:59:05 | bevideas_B_notes | batch_end | status=all episodes done |
| 2026-10-19 18:59:06 | bevideas_B_skip | batch_start | command=scripts/benchmark.sh bevideas_B_skip dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal --overlay configs/bev_ideas.yaml --bev clear_skip=on; git={"commit": "41e2bd0", "branch": "bev-ideas", "uncommitted_changes": false}; episodes=10; params={"arch": "multi", "mode": "lockstep", "tick_s": null, "overlay": "configs/bev_ideas.yaml", "overlay_sha256": "194387069d0771ef", "merge_rule": "hybrid", "backend": "llamaserver", "models": {"npu": "Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf", "cpu": "gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf", "bev": "bev-decider-0.4B-backbone-Q8_0.gguf"}, "prompts_saved": true, "bev": "clear_skip=on", "bev_device": "npu"} |
| 2026-10-19 18:59:24 | bevideas_B_skip | episode_start | episode=dev_A01_fcv_seize; run=1; stem=dev_A01_fcv_seize_multi; chip_c=53.5 |
| 2026-10-19 19:01:22 | bevideas_B_skip | episode_done | episode=dev_A01_fcv_seize; run=1; wall_s=110.6; group_top1=0.614; calls=31; unusable=0 |
| 2026-10-19 19:01:55 | bevideas_B_skip | episode_start | episode=dev_A02_fcv_seize_fast; run=1; stem=dev_A02_fcv_seize_fast_multi; chip_c=54.0 |
| 2026-10-19 19:04:19 | bevideas_B_skip | episode_done | episode=dev_A02_fcv_seize_fast; run=1; wall_s=136.1; group_top1=0.625; calls=46; unusable=0; bev_ideas={"clear_skip": {"calls": 0, "failed": 0, "rejected": 0, "used": 7}} |
| 2026-10-19 19:04:52 | bevideas_B_skip | episode_start | episode=dev_B01_tube_leak; run=1; stem=dev_B01_tube_leak_multi; chip_c=55.2 |
| 2026-10-19 19:08:08 | bevideas_B_skip | episode_done | episode=dev_B01_tube_leak; run=1; wall_s=188.1; group_top1=0.953; calls=60; unusable=0; bev_ideas={"clear_skip": {"calls": 0, "failed": 0, "rejected": 0, "used": 11}} |
| 2026-10-19 19:08:41 | bevideas_B_skip | episode_start | episode=dev_B02_tube_leak_fast; run=1; stem=dev_B02_tube_leak_fast_multi; chip_c=56.3 |
| 2026-10-19 19:09:49 | bevideas_B_skip | episode_done | episode=dev_B02_tube_leak_fast; run=1; wall_s=60.5; group_top1=1.0; calls=19; unusable=0; bev_ideas={"clear_skip": {"calls": 0, "failed": 0, "rejected": 0, "used": 16}} |
| 2026-10-19 19:10:22 | bevideas_B_skip | episode_start | episode=dev_C01_wet_coal; run=1; stem=dev_C01_wet_coal_multi; chip_c=54.8 |
| 2026-10-19 19:12:06 | bevideas_B_skip | episode_done | episode=dev_C01_wet_coal; run=1; wall_s=95.5; group_top1=0.471; calls=25; unusable=0; bev_ideas={"clear_skip": {"calls": 0, "failed": 0, "rejected": 0, "used": 2}} |
| 2026-10-19 19:12:39 | bevideas_B_skip | episode_start | episode=dev_C02_feeder_trip; run=1; stem=dev_C02_feeder_trip_multi; chip_c=54.4 |
| 2026-10-19 19:15:51 | bevideas_B_skip | episode_done | episode=dev_C02_feeder_trip; run=1; wall_s=184.6; group_top1=0.429; calls=58; unusable=0 |
| 2026-10-19 19:16:24 | bevideas_B_skip | episode_start | episode=dev_D01_high_cv_coal; run=1; stem=dev_D01_high_cv_coal_multi; chip_c=56.3 |
| 2026-10-19 19:22:35 | bevideas_B_skip | episode_done | episode=dev_D01_high_cv_coal; run=1; wall_s=362.8; group_top1=0.804; calls=99; unusable=0; bev_ideas={"clear_skip": {"calls": 0, "failed": 0, "rejected": 0, "used": 52}} |
| 2026-10-19 19:23:08 | bevideas_B_skip | episode_start | episode=dev_D03_high_cv_severe; run=1; stem=dev_D03_high_cv_severe_multi; chip_c=56.7 |
| 2026-10-19 19:25:51 | bevideas_B_skip | episode_done | episode=dev_D03_high_cv_severe; run=1; wall_s=156.1; group_top1=0.939; calls=45; unusable=0; bev_ideas={"clear_skip": {"calls": 0, "failed": 0, "rejected": 0, "used": 30}} |
| 2026-10-19 19:26:24 | bevideas_B_skip | episode_start | episode=dev_N01_normal; run=1; stem=dev_N01_normal_multi; chip_c=56.7 |
| 2026-10-19 19:26:39 | bevideas_B_skip | episode_done | episode=dev_N01_normal; run=1; wall_s=6.5; calls=0; unusable=0 |
| 2026-10-19 19:26:52 | bevideas_B_skip | episode_start | episode=dev_N02_normal; run=1; stem=dev_N02_normal_multi; chip_c=54.3 |
| 2026-10-19 19:27:10 | bevideas_B_skip | episode_done | episode=dev_N02_normal; run=1; wall_s=10.0; calls=1; unusable=0 |
| 2026-10-19 19:27:11 | bevideas_B_skip | batch_end | status=all episodes done |
| 2026-10-19 19:27:12 | bevideas_A2 | batch_start | command=scripts/benchmark.sh bevideas_A2 dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal --overlay configs/bev_ideas.yaml; git={"commit": "41e2bd0", "branch": "bev-ideas", "uncommitted_changes": false}; episodes=10; params={"arch": "multi", "mode": "lockstep", "tick_s": null, "overlay": "configs/bev_ideas.yaml", "overlay_sha256": "194387069d0771ef", "merge_rule": "hybrid", "backend": "llamaserver", "models": {"npu": "Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf", "cpu": "gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf", "bev": "bev-decider-0.4B-backbone-Q8_0.gguf"}, "prompts_saved": true, "bev_device": "npu"} |
| 2026-10-19 19:27:29 | bevideas_A2 | episode_start | episode=dev_A01_fcv_seize; run=1; stem=dev_A01_fcv_seize_multi; chip_c=53.6 |
| 2026-10-19 19:29:24 | bevideas_A2 | episode_done | episode=dev_A01_fcv_seize; run=1; wall_s=106.6; group_top1=0.561; calls=31; unusable=0 |
| 2026-10-19 19:29:54 | bevideas_A2 | episode_start | episode=dev_A02_fcv_seize_fast; run=1; stem=dev_A02_fcv_seize_fast_multi; chip_c=55.2 |
| 2026-10-19 19:32:35 | bevideas_A2 | episode_done | episode=dev_A02_fcv_seize_fast; run=1; wall_s=152.6; group_top1=0.625; calls=51; unusable=0 |
| 2026-10-19 19:33:07 | bevideas_A2 | episode_start | episode=dev_B01_tube_leak; run=1; stem=dev_B01_tube_leak_multi; chip_c=57.4 |
| 2026-10-19 19:36:40 | bevideas_A2 | episode_done | episode=dev_B01_tube_leak; run=1; wall_s=205.6; group_top1=0.953; calls=65; unusable=0 |
| 2026-10-19 19:37:13 | bevideas_A2 | episode_start | episode=dev_B02_tube_leak_fast; run=1; stem=dev_B02_tube_leak_fast_multi; chip_c=57.5 |
| 2026-10-19 19:38:38 | bevideas_A2 | episode_done | episode=dev_B02_tube_leak_fast; run=1; wall_s=77.0; group_top1=1.0; calls=24; unusable=0 |
| 2026-10-19 19:39:11 | bevideas_A2 | episode_start | episode=dev_C01_wet_coal; run=1; stem=dev_C01_wet_coal_multi; chip_c=56.0 |
| 2026-10-19 19:41:05 | bevideas_A2 | episode_done | episode=dev_C01_wet_coal; run=1; wall_s=105.5; group_top1=0.51; calls=27; unusable=0 |
| 2026-10-19 19:41:38 | bevideas_A2 | episode_start | episode=dev_C02_feeder_trip; run=1; stem=dev_C02_feeder_trip_multi; chip_c=56.7 |
| 2026-10-19 19:44:54 | bevideas_A2 | episode_done | episode=dev_C02_feeder_trip; run=1; wall_s=189.1; group_top1=0.429; calls=58; unusable=0 |
| 2026-10-19 19:45:27 | bevideas_A2 | episode_start | episode=dev_D01_high_cv_coal; run=1; stem=dev_D01_high_cv_coal_multi; chip_c=57.9 |
| 2026-10-19 19:54:09 | bevideas_A2 | episode_done | episode=dev_D01_high_cv_coal; run=1; wall_s=513.3; group_top1=0.804; calls=134; unusable=0 |
| 2026-10-19 19:55:01 | bevideas_A2 | episode_start | episode=dev_D03_high_cv_severe; run=1; stem=dev_D03_high_cv_severe_multi; chip_c=56.3 |
| 2026-10-19 19:58:25 | bevideas_A2 | episode_done | episode=dev_D03_high_cv_severe; run=1; wall_s=196.1; group_top1=0.939; calls=56; unusable=0 |
| 2026-10-19 19:58:58 | bevideas_A2 | episode_start | episode=dev_N01_normal; run=1; stem=dev_N01_normal_multi; chip_c=58.3 |
| 2026-10-19 19:59:13 | bevideas_A2 | episode_done | episode=dev_N01_normal; run=1; wall_s=7.0; calls=0; unusable=0 |
| 2026-10-19 19:59:27 | bevideas_A2 | episode_start | episode=dev_N02_normal; run=1; stem=dev_N02_normal_multi; chip_c=56.0 |
| 2026-10-19 19:59:44 | bevideas_A2 | episode_done | episode=dev_N02_normal; run=1; wall_s=10.0; calls=1; unusable=0 |
| 2026-10-19 19:59:46 | bevideas_A2 | batch_end | status=all episodes done |
