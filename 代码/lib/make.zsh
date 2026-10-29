# 各片共用的全流程。每条片子的 make.sh 只有两行：记下自己的文件夹 HERE，再 source 这个文件。命令说明见 ../README.md
# 新片子用 代码/new.sh <规格> <标题> 从 模板/ 起步；它写的 片子.json 给 lib 当默认值（音色、语气、配乐套、门禁按规格）
# 在片子的文件夹里跑：
#   ./make.sh export              稿子 → build/cues.json（配音的待办清单）
#   python3 script.py sheet       给审稿人看的稿子（带稿子哈希）；审稿结论写进 审稿.md，配音前会查
#   ./make.sh try h1,b3,c4,g5     试音（Gemini）：同几句按两种语气指示各念一遍，拼成 build/试音/试音.wav 给作者盲听，答案在 答案.txt
#   ./make.sh voice               逐句配音：默认 IndexTTS（每批 12 句自动重启）；voice.txt 写 gemini:<音色> 走 Gemini TTS，
#                                 写 volc:<音色> 走火山豆包语音（2.0 预置音色或复刻的 S_xxx）。已有的跳过
#   ./make.sh waitvoice [HHMM]    Gemini 额度用完时：每 10 分钟重试 voice，配完自动 align（默认试到 23:00）
#   ./make.sh align               FunASR 回读：逐字时间 + 拼音差错率，列出要重做的句子；接着跑 recheck
#   ./make.sh recheck [词,词]     读音孤立复认：say= 的词和回读对不上的词前后各 0.3 秒切出来单独再认，跟别句里的同一个词比；
#                                 对不上的写进 build/复认.txt，listen 会带上。可以点名几个词，每处都查
#   ./make.sh listen              抽听：钉了拼音的句子和回读有出入的句子拼成 build/抽听.wav，附清单，给作者一次听完
#   ./make.sh timeline            按配音生成时间轴、字幕、停顿
#   ./make.sh stills 12.5,30      出几帧静帧检查（build/still_*.png）
#   ./make.sh check               渲染前查画面（只要时间轴，一分钟左右）。先查 render.js 里按词触发的词还在不在稿子里（lib/wordcheck.py）、字幕让开（subskip）的键
#                                 对不对得上字幕的分段（script.py subcheck，timeline 也提醒），再跑崩溃扫描。静帧：小于 36px 的字、字压着字、字压进平台界面区，
#                                 每句念到一半和快念完各一帧，每个转场过了四分之一、一半、四分之三各一帧。
#                                 时间上：章节名可读够不够 1.5 秒、转场里透出场景的字、旁白在讲画面却 6 秒没变化、字没停够读完
#                                 人：字幕压着画面里的人、人被画面边缘切掉（person()、chibi() 自动登记，片子自己画的人调 subject()）
#   ./make.sh dense [秒]          全片密查字：每 0.5 秒一帧（要更密写 0.2），只查字压字、字压进平台界面区、小于 36px 的字，连着的几帧
#                                 写成一段。check 只查取样的时刻，转场里一闪而过的叠字落在两帧之间会漏（运动片又找出四处）。渲染前跑
#   ./make.sh crash               崩溃扫描：每个转场的每一帧、每场和每句开头几帧、每秒一帧、全片首尾，只算不存，列出会崩的帧（check 和 render 前都跑）
#   ./make.sh render [进程数] [时间]  逐帧渲染（默认 8 个进程），每 10 秒一段。带时间（12.5,95-101）只重渲这些时间所在的段，再拼回去
#   ./make.sh music               Lyria 3.5 生成配乐候选（music/make_music.py 里的提示词，已有的跳过），再用 HDemucs 查每首混没混进人声；选中的那套写进 music/选用.txt
#   ./make.sh cover               出封面候选（cover.js）→ build/cover_<n>.png，选中的复制成 cover.png
#   ./make.sh events              render.js 用 EV.build 定下的事件表（lib/events.js）→ build/events.json，带时间轴的哈希；mix 里的
#                                 fx_from_events 按它放音效，时间轴改过就不肯混（方法/声音.md「声音上的贴」）。没有事件的片子写一张空表
#   ./make.sh mix                 配乐、音效、人声混音 → build/audio.wav
#   ./make.sh mixcheck            混音后回读：每句从混好的音轨里再认一遍，比干声多错 2 个音节以上的列出来（配乐或音效盖住了人声）
#   ./make.sh mux [文件名]        两遍响度标准化，合成成片放进 $OUT_DIR（默认 ~/Documents/notes）；超过 50 MB 自动接着跑 fit
#   ./make.sh fit [成片]          成片超过 49 MB（对话里发不全）就两遍编码压到 45 MB，高码率原片留在 build/成片_高码率.mp4
#   ./make.sh teaser [check]      预告片：照 预告.txt 按句从成片里剪（交叉淡化，最后一帧停住、配成片自己的结尾，一行引流字），
#                                 30–60 秒，放进 $OUT_DIR（默认 ~/Documents/notes）。check 只排表、查切点
#   ./make.sh qc [成片]           成片后第二道审的材料：check 的两样、手机尺寸联系表（每张 20 格）和格子索引、前后响度跳变、
#                                 转场和首尾以外的黑屏和静音、混音后回读。都写进 build/qc_*.txt；另出四张原尺寸静帧看质感。
#                                 有 build/events.json 的再跑 qcsync
#   ./make.sh qcsync [成片]       画面落没落在声音上：每个带探测框的事件，画面亮起的那一帧对声音开始的那一帧（lib/qcsync.py）。
#                                 同一帧至少 90%、没有差过 ±1 帧的才算过；音效轨和成片里的起音只报不判
#   ./make.sh all                 export → voice → align → listen → timeline → check → dense → render → events → mix → mixcheck → mux
# 换声音：REF=/path/to/ref.wav ./make.sh voice
ROOT=${HERE:h:h}; ENG=$ROOT/engines; LIB=$ROOT/lib
REF=${REF:-$ROOT/voices/SSB0407/ref.wav}
TITLE=${${HERE:t}#[0-9][0-9][0-9][0-9]-[0-9][0-9]-}
cd $HERE
# 配音、回读、配乐要的 engines/（Gemini、火山、IndexTTS、FunASR 的封装）不在这个仓库里，key 自己在环境变量里设，脚本不读、不打印。
# 本机设置：代码/local.env（照 local.env.example 抄一份，不进仓库），在这里读进来。可以设 CHROME、PATH、OUT_DIR、VENC。
[[ -f $ROOT/local.env ]] && source $ROOT/local.env
# 成片放哪：OUT_DIR，默认 ~/Documents/notes。浏览器：CHROME 指一个 chrome-headless-shell，没设就用 Playwright 自己下载的那个。
export OUT_DIR=${OUT_DIR:-$HOME/Documents/notes}; mkdir -p $OUT_DIR
[[ -n $CHROME && ! -x $CHROME ]] && { print "CHROME 指的文件不能执行：$CHROME（改 local.env，或者 unset CHROME 用 Playwright 自己的）"; unset CHROME; }
# 编码器：有 libx264 用它；没有（比如只带 VideoToolbox 的 ffmpeg）就用 h264_videotoolbox
[[ -z $VENC ]] && ! ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libx264 && export VENC=videotoolbox

step() {
  case $1 in
    export)   python3 script.py export ;;
    try)      python3 script.py try $2 ;;
    musictry) python3 script.py musictry ${@:2} ;;   # open.h0-o4c,L4.d1-d5 [A B]: each music set mixed under the voice, the same stretches cut for a blind listen
    voice)    python3 script.py gate || return 1
              local src=${VOICE:-$(cat voice.txt 2>/dev/null)}
              [[ -z $src && -f 片子.json ]] && src=$(python3 -c "import json; print(json.load(open('片子.json')).get('音色', ''))")   # the series' voice (new.sh)
              if [[ $src == gemini:* ]]; then          # a Gemini preset voice: cloud TTS, no GPU, no batches
                VOICE=$src python3 $ENG/gemini.py tts $HERE/build/cues.json && return 0
                print "Gemini 没配完。额度用完的话：nohup ./make.sh waitvoice 等额度；或者整条换成火山的声音（voice.txt 改成 volc:<音色>，从 export 重跑）。一条片子只用一个声音，不混配。"
                return 1
              fi
              if [[ $src == volc:* ]]; then            # Doubao Speech: a 2.0 preset voice or a cloned voice S_xxx
                python3 $ENG/volc.py tts $HERE/build/cues.json; return $?
              fi
              local free; free=$(memory_pressure 2>/dev/null | awk -F': ' '/free percentage/ {print $2+0}')
              if [[ -n $free ]] && (( free < 40 )); then
                print "提醒：内存只剩 ${free}% 空闲，交换区已用 $(sysctl -n vm.swapusage | awk '{print $6}')。IndexTTS 会慢好几倍（四版有一句拖到 3 分半），先关掉占内存的应用再配。"
              fi
              ( cd $ENG/index-tts; code=10
                while (( code == 10 )); do
                  PYTHONPATH=. caffeinate -i uv run python gen_itts.py $HERE/build/cues.json $REF --max 12; code=$?
                done; exit $code ) ;;
    waitvoice) local until=${2:-2300}           # the Gemini limit is 100 calls in a rolling 24 hours: keep trying every 10 minutes
              until caffeinate -i ./make.sh voice; do
                (( $(date +%H%M) >= until )) && { print "waitvoice: gave up at $(date +%H:%M)"; return 1; }
                print "waitvoice: try again at $(date -v+10M +%H:%M)"; sleep 600
              done
              step align ;;
    align)    $ENG/asr-venv/bin/python $ENG/align_itts.py $HERE/build/cues.json ${2:-} | tee build/align.txt
              step recheck ;;
    recheck)  # say= words and words the read-back got wrong, cut out alone (0.3 s each side) and recognised again, compared
              # with the same word in the other lines (大理: 吐蕃 came out right in its sentence, wrong alone); flags go to listen
              $ENG/asr-venv/bin/python $ENG/word_recheck.py $HERE/build/cues.json ${2:-} 2>/dev/null | tee build/recheck.txt ;;
    listen)   python3 script.py listen ;;
    timeline) ENGINE=itts python3 script.py tts ;;
    stills)   node $LIB/capture.mjs stills $2 ;;
    check)    python3 $LIB/wordcheck.py; local wc=$?   # then the subskip keys: both text checks print before either stops it
              python3 script.py subcheck && (( wc == 0 )) && node $LIB/capture.mjs crash && node $LIB/capture.mjs audit $(python3 $LIB/qcpoints.py) 36 && node $LIB/timecheck.mjs ;;
    dense)    node $LIB/capture.mjs dense ${2:-0.5} 36 ;;   # the text checks on a frame every 0.5 s: an overlap inside a transition falls between check's frames
    crash)    node $LIB/capture.mjs crash ;;
    render)   node $LIB/capture.mjs crash && node $LIB/capture.mjs render ${2:-8} ${3:-} ;;
    music)    python3 music/make_music.py || return 1   # Lyria 3.5: every candidate in music/make_music.py that is not there yet
              # then every candidate not checked yet (subfolders too) is checked for leaked vocals (HDemucs; FunASR invents
              # words on pure music); the results pile up in music/人声检查.txt
              local tracks=(music/**/*.mp3(N)) todo=() t
              for t in $tracks; do grep -qF "$t " music/人声检查.txt 2>/dev/null || todo+=($t); done
              (( $#todo )) && $ENG/asr-venv/bin/python $ENG/vocal_check.py $todo | tee -a music/人声检查.txt ;;
    cover)    node $LIB/cover.mjs ;;                       # designed covers (cover.js) -> build/cover_<n>.png; copy the chosen one to cover.png
    events)   node $LIB/capture.mjs events ;;
    mix)      python3 script.py mix ;;
    mixcheck) $ENG/asr-venv/bin/python $ENG/mix_readback.py 2>/dev/null ;;
    mux)      local m ii out
              m=$(ffmpeg -hide_banner -i build/audio.wav -af loudnorm=I=-16:TP=-1.5:LRA=20:print_format=json -f null - 2>&1 | sed -n '/^{/,/^}/p')
              ii=$(print -r -- $m | python3 -c "import json,sys;d=json.load(sys.stdin);print(f\"measured_I={d['input_i']}:measured_TP={d['input_tp']}:measured_LRA={d['input_lra']}:measured_thresh={d['input_thresh']}:offset={d['target_offset']}\")")
              out=$OUT_DIR/$(date +%Y%m%dT%H%M%S)--${2:-$TITLE}__video.mp4
              ffmpeg -y -loglevel error -f concat -safe 0 -i build/segs.txt -i build/audio.wav -map 0:v -map 1:a -c:v copy \
                -c:a aac -b:a 192k -af "loudnorm=I=-16:TP=-1.5:LRA=20:${ii}:linear=true" -ar 48000 -shortest -movflags +faststart $out \
                && step fit $out && print -- $out ;;
    fit)      # a film over 50 MB is cut off when it is sent in the chat (等于没说: 112 MB, nothing after 1:10): squeeze it to 45 MB
              # (counted in decimal megabytes, to be safe) with a two-pass encode at the bitrate that fits; the full-rate file stays in build/成片_高码率.mp4
              local f=${2:-$(ls -t $OUT_DIR/*--${TITLE}__video.mp4 | head -1)} sz dur vb
              sz=$(stat -f %z $f); print "成片体积 $(( sz / 1000000 )) MB"
              (( sz <= 49000000 )) && return 0
              dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 $f)
              vb=$(python3 -c "print(int(45e6 * 8 / $dur - 200000))")
              ffmpeg -y -loglevel error -i $f -c:v libx264 -preset slow -b:v $vb -pass 1 -passlogfile build/x264pass -an -f null /dev/null \
                && ffmpeg -y -loglevel error -i $f -c:v libx264 -preset slow -b:v $vb -pass 2 -passlogfile build/x264pass -c:a copy -movflags +faststart build/fit.mp4 \
                && mv $f build/成片_高码率.mp4 && mv build/fit.mp4 $f && rm -f build/x264pass* \
                && print "超过 49 MB（从对话里发不全），压到 $(( $(stat -f %z $f) / 1000000 )) MB（视频 $(( vb / 1000 )) kbps）；原来的高码率版在 build/成片_高码率.mp4" ;;
    qc)       local qf=${2:-$(ls -t $OUT_DIR/*--${TITLE}__video.mp4 | head -1)}
              python3 $LIB/qcmoves.py $qf   # where the camera moves: frames there too (they can fall between two lines)
              python3 $LIB/qcpoints.py json moves > build/qc_points.json; local T; T=$(python3 $LIB/qcpoints.py moves)
              node $LIB/capture.mjs audit $T 36 > build/qc_text.txt; cat build/qc_text.txt
              node $LIB/timecheck.mjs | tee build/qc_time.txt
              find build -maxdepth 1 -name 'qc_sheet_*' -delete
              node $LIB/capture.mjs stills $T > /dev/null && python3 $LIB/qcsheet.py build/qc_points.json
              # for the 质感 question (方法/两道审.md, E): four full-size frames, picked the way 大理's blind review picked them
              local P; P=$(python3 -c "import json; d = json.load(open('timeline.json'))['duration']; print(f'0,3,{d * .3:.1f},{d * .6:.1f}')")
              node $LIB/capture.mjs stills $P > /dev/null && print "质感：四张原尺寸静帧 build/still_<秒>.png（$P 秒：第一帧、第 3 秒、三成处、六成处）"
              python3 script.py loudness ${2:-} | tee build/qc_loudness.txt
              python3 $LIB/qc_av.py ${2:-} | tee build/qc_av.txt
              step mixcheck | tee build/qc_mix.txt
              [[ -s build/events.json ]] && python3 $LIB/qcsync.py $qf | tee build/qc_sync.txt   # event-driven sound only
              print "成片体积 $(( $(stat -f %z $qf) / 1000000 )) MB（超过 49 MB 从对话里发不全，make.sh fit 压一下）" | tee build/qc_size.txt ;;
    teaser)   python3 $LIB/teaser.py ${2:-} ;;
    qcsync)   python3 $LIB/qcsync.py ${2:-} ;;
    all)      for s in export voice align listen timeline check dense render events mix mixcheck mux; do print "== $s"; step $s || return 1; done ;;
    *)        sed -n '1,/^ROOT=/p' $LIB/make.zsh | sed '$d'; return 1 ;;
  esac
}
step "$@"
