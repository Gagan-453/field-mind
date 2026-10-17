#!/system/bin/sh
# FieldMind board resource sampler (reports/bev_ideas.md, commit 11).
# Runs ON THE BOARD, pushed by bench/board_sampler.py (sha256-checked).
#
#   sh board_sampler.sh OUT STOP [PERIOD_S]
#
# Appends one block per PERIOD_S (default 1) to OUT until the file STOP exists
# (the laptop creates a NEW stop file per episode; nothing is ever deleted):
#   T <uptime s> <idle s>                         /proc/uptime
#   C <cpu line of /proc/stat>                    aggregate jiffies
#   P <name> <pid> <port> <utime> <stime> <rss kB>   per server process
#   S <pid> <utime> <stime> <cutime> <cstime>     this sampler (its own cost)
#   F <policy> <kHz>                              cpufreq per cluster
#   Z <type> <temp>                               thermal zones
#   W <supply> <current_now> <voltage_now>        only if readable
OUT="$1"
STOP="$2"
PERIOD="${3:-1}"
while [ ! -e "$STOP" ]; do
  {
    echo "T $(cat /proc/uptime)"
    echo "C $(head -1 /proc/stat)"
    for name in llama-server bev-decide; do
      for pid in $(pidof "$name"); do
        port=$(tr '\0' ' ' < /proc/$pid/cmdline | sed -n 's/.*--port \([0-9]*\).*/\1/p')
        st=$(cut -d' ' -f14,15 /proc/$pid/stat)
        rss=$(grep VmRSS /proc/$pid/status | tr -s ' ' | cut -d' ' -f2)
        echo "P $name $pid ${port:-?} $st ${rss:-0}"
      done
    done
    echo "S $$ $(cut -d' ' -f14,15,16,17 /proc/$$/stat)"
    for f in /sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq; do
      [ -r "$f" ] && echo "F $(basename $(dirname $f)) $(cat $f)"
    done
    for z in /sys/class/thermal/thermal_zone*; do
      [ -r "$z/temp" ] && echo "Z $(cat $z/type) $(cat $z/temp)"
    done
    for p in /sys/class/power_supply/*; do
      [ -r "$p/current_now" ] && [ -r "$p/voltage_now" ] && \
        echo "W $(basename $p) $(cat $p/current_now) $(cat $p/voltage_now)"
    done
  } 2>/dev/null >> "$OUT"
  sleep "$PERIOD"
done
