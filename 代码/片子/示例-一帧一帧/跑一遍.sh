#!/bin/zsh
# 示例片从头到尾跑一遍：估时间轴 → 检查 → 渲染 → 混音 → 出片。成片放在 build/out/，跑完删掉中间的分段。
set -e
HERE=${0:A:h}; cd $HERE
# 本机设置（CHROME、带 numpy/scipy 的 python 的 PATH……）：代码/local.env，没有就用系统默认
[[ -f ${HERE:h:h}/local.env ]] && source ${HERE:h:h}/local.env
export OUT_DIR=${OUT_DIR:-$HERE/build/out}
SECONDS=0
python3 script.py sheet | head -3
ENGINE=est python3 script.py tts
./make.sh check
./make.sh render ${WORKERS:-4}
python3 script.py mix
./make.sh mux 示例-一帧一帧
print "用时 ${SECONDS} 秒"
ls -la $OUT_DIR
