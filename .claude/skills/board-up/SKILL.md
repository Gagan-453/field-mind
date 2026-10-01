---
name: board-up
description: Start the two persistent llama-server lanes (NPU and CPU) on the QIDK and forward their ports. Use when asked to run /board-up or before any run that calls the board's model lanes.
---

Bring up both model lanes on the QIDK. Model file to use: $ARGUMENTS (if empty, use the model named in
`configs/base.yaml`; if none is named there, ask).

1. `adb devices` must list exactly one device. Otherwise stop.
2. Find where the llama.cpp Android build lives on the board (`adb shell ls /data/local/tmp` and below). Do not assume
   a path; use what is actually there. Check the model file is present and is Q4_0 or Q8_0.
3. Stop any `llama-server` already running on the board (by process name only; never delete files).
4. Start the NPU lane in the background on port 8080: `--device HTP0 -ngl 99 -np 1`, the context size from
   `configs/base.yaml`, `--host 0.0.0.0`, with `LD_LIBRARY_PATH` and `ADSP_LIBRARY_PATH` set. Log to a file on the board.
5. Start the CPU lane in the background on port 8081: no GPU or NPU offload (`-ngl 0`), `-np 1`, same context size,
   a fixed thread count (start with 6 and record it). Log to a separate file.
6. `adb forward tcp:8080 tcp:8080` and `adb forward tcp:8081 tcp:8081`.
7. Wait until `curl -s http://localhost:8080/health` and `:8081/health` both report ready.
8. Read the NPU lane's startup log and confirm a nonzero HTP0 buffer size and that all layers were offloaded.
   Read the CPU lane's log and confirm no HTP buffer was allocated.
9. Send one short identical prompt to each lane and report: prompt tokens, prefill tok/s, decode tok/s and time to
   first token per lane, taken from the server's own timing fields. Also report chip temperature.
10. Report anything that did not match the expected state. Do not try workarounds without asking.
