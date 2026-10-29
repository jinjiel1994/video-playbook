#!/bin/zsh
# 新片子从模板起步，不复制上一条（复制会把上一条的习惯和画面一起带过来）：
#   ./new.sh <规格> <标题>        比如 ./new.sh 抖音信息流 为什么冬天晒太阳
# 规格：抖音信息流、讲解长片（这个仓库只带了「讲解短片」这一套模板）
# 建出 片子/<年-月>-<标题>/：先放 模板/共用，再盖 模板/讲解短片，写好 片子.json，把文件里的 {{标题}} 这些换掉。
set -e
ROOT=${0:A:h}
spec=$1 title=$2
if [[ -z $title ]]; then sed -n '2,5p' $0; exit 1; fi
case $spec in
  抖音信息流|讲解长片) tpl=讲解短片 ;;
  *) print "这个仓库只带了抖音信息流、讲解长片的模板。其他规格见 ../规格/各规格.md。"; exit 1 ;;
esac
dir=$ROOT/片子/$(date +%Y-%m)-$title
[[ -e $dir ]] && { print "已经有了：$dir"; exit 1; }
mkdir -p $dir/build
cp -R $ROOT/模板/共用/ $dir/
cp -R $ROOT/模板/$tpl/ $dir/
chmod +x $dir/make.sh
python3 - $dir $spec $title $tpl <<'PY'
import json, os, sys, time
d, spec, title, tpl = sys.argv[1:]
LEN = {'抖音信息流': 150, '讲解长片': 480}   # 秒，只做参考（片长跟着内容走）
film = {'系列': '单片', '规格': spec, '平台': ['抖音'], '标题': title, '音色': '', '语气': '严格逐字',
        '配乐套': 'A', '片长参考': LEN[spec], '模板': tpl, '建立': time.strftime('%Y-%m-%d')}
json.dump(film, open(os.path.join(d, '片子.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
sub = {'{{系列}}': '单片', '{{标题}}': title, '{{规格}}': spec, '{{日期}}': time.strftime('%Y-%m-%d')}
for dp, _, fs in os.walk(d):
    for f in fs:
        if f.endswith(('.py', '.js', '.html', '.md', '.txt')):
            p = os.path.join(dp, f); s = open(p, encoding='utf-8').read(); t = s
            for a, b in sub.items():
                t = t.replace(a, b)
            if t != s:
                open(p, 'w', encoding='utf-8').write(t)
print(json.dumps(film, ensure_ascii=False))
PY
print "建好了：${dir#$ROOT/}"
print "开工前读：../方法/README.md、../规格/各规格.md。任务书先过选题门，再写 口播稿.md、分镜单.md、script.py、render.js。"
print "先跑通：cd ${dir#$ROOT/} && python3 script.py sheet && ENGINE=est python3 script.py tts && ./make.sh check"
