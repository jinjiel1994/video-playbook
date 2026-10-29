#!/bin/zsh
# 一条视频的全流程，命令都在 ../../lib/make.zsh（各片共用）。./make.sh 不带参数，列出全部命令
HERE=${0:A:h}; source ${HERE:h:h}/lib/make.zsh "$@"
