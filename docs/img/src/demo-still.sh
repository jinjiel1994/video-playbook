#!/bin/zsh
# 从示例片的成片里取三帧，拼成 ../demo.png。先跑一遍示例片（代码/片子/示例-一帧一帧/跑一遍.sh）。
set -e
HERE=${0:A:h}
f=$(ls -t $HERE/../../../代码/片子/示例-一帧一帧/build/out/*.mp4 | head -1)
ffmpeg -v error -y -i "$f" -vf "select='eq(n\,15)+eq(n\,200)+eq(n\,300)',scale=360:-1,tile=3x1:padding=40:margin=60:color=0xf5f5f7" -frames:v 1 -vsync 0 $HERE/../demo.png
print "demo.png ← $f"
