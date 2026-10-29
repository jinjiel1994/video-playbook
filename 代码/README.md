# 代码：一套能跑的最小工具

![一条片子是怎么算出来的：稿子、配音、时间轴、每一帧、截帧、成片](../docs/img/pipeline.png)

车间做片子用的底座，删到能带走的那部分：画面底座、逐帧渲染、时间轴、检查、合成音效、混音、出片。配音、回读、生成配乐的引擎没带（要 key、要大模型），示例片用「估计时间轴 + 合成音」把整条流程走通。

## 要什么环境

在一台 Apple Silicon Mac 上验证过（Linux 也能跑，编码器换成 libx264）：

| 东西 | 版本 | 干什么 |
|---|---|---|
| Node | 20 以上（验证用的 v26.8.1） | 跑渲染脚本 |
| playwright-core | 1.62.1（`npm install` 装） | 驱动无头浏览器 |
| 浏览器 | 一个 chrome-headless-shell，或 Playwright 自己下载的 chromium | 一帧帧画、截图 |
| ffmpeg | 验证用的 8.1 | 编码、拼段、响度 |
| Python | 3，加 numpy、scipy | 时间轴、合成音效、混音 |
| 字体 | Noto Sans CJK SC、Noto Serif CJK SC（装在系统里，仓库不带字体文件） | 中文字 |
| zsh | macOS 自带 | `make.sh`、`跑一遍.sh` |

## 本机设置：local.env

每台机器的浏览器、Python 放的地方不一样。把 `local.env.example` 复制成 `local.env`（同一个文件夹，不进仓库），按自己的机器改；`make.sh` 和 `跑一遍.sh` 开头会读它。

| 变量 | 管什么 | 不设时 |
|---|---|---|
| `CHROME` | chrome-headless-shell 的路径 | 用 Playwright 自己下载的 chromium（`npx playwright-core install chromium`） |
| `PATH` | 把带 numpy、scipy 的 Python（比如一个 venv 的 bin）放到最前面 | 用系统的 `python3` |
| `OUT_DIR` | 成片放哪 | `~/Documents/notes`；示例片放自己的 `build/out/` |
| `VENC` | `videotoolbox` 用苹果的硬件编码 | ffmpeg 没带 libx264 时自动设上 |

另外，`ENGINE=est` 表示不配音，按每字 0.24 秒估时间轴，画面、检查、渲染都能先跑。（`fit` 那一步压文件大小用的是 libx264 两遍编码，没有 libx264 就跑不了，示例片用不到。）

## 跑示例片

```zsh
cd video-playbook/代码
npm install
cp local.env.example local.env     # 按需改；什么都不改也行
cd 片子/示例-一帧一帧
./跑一遍.sh            # WORKERS=8 ./跑一遍.sh 开更多渲染进程
```

它依次跑：

1. `python3 script.py sheet`：给审稿人看的稿子（带稿子哈希）。
2. `ENGINE=est python3 script.py tts`：估时间轴（每个字几秒念到）。
3. `./make.sh check`：渲染前查画面（崩溃扫描、小字、字压字、界面区、停太久、字没停够读完）。
4. `./make.sh render 4`：4 个进程逐帧渲染，每 10 秒一段。
5. `python3 script.py mix`：合成配乐垫底和音效（`lib/sound.py`），混音。
6. `./make.sh mux 示例-一帧一帧`：响度标准化，合成成片，放进 `build/out/`。

![示例片的三帧](../docs/img/demo.png)

示例片 15 秒：开头一句大字，「算出来」三个字念到时红圈升起，「动」那一下画面跳一下，结尾卡。因为没配音，听到的只有垫底和音效，字幕照估的时间走。

## 开一条新片子

```zsh
cd video-playbook/代码
./new.sh 抖音信息流 为什么冬天晒太阳
cd 片子/2026-10-为什么冬天晒太阳
python3 script.py sheet && ENGINE=est python3 script.py tts && ./make.sh check
```

`new.sh` 从 `模板/共用` 和 `模板/讲解短片` 起步，写好 `片子.json`。**不复制上一条片子**：复制会把上一条的画面和习惯一起带过来。

每条片子文件夹里：

| 文件 | 写什么 |
|---|---|
| `口播稿.md` | 先写稿子，写给耳朵听（`../方法/稿子写给耳朵听.md`） |
| `分镜单.md` | 每一句话配什么画面、哪个词触发什么 |
| `script.py` | 稿子切成场景和句子：`C('h1', '一句话', hl='要强调的词')`；`HOOK` 是开头那句 |
| `render.js` | 每个场景一个函数，`renderFrame(t)` 按时间算出这一帧；`Q(sc).w('h1', '词')` 拿到那个词念到的时刻 |
| `index.html` | 载入 `lib/film.js`、`lib/events.js` 和 `render.js` 的页面 |
| `片子.json` | 规格、平台、标题、音色这些默认值 |

## lib 里有什么

| 文件 | 干什么 |
|---|---|
| `film.js` | 画面底座：文字、面板、小签、大标题、人、圆圈，缓动，按词取时间，检查登记；片子可以给一条贯穿的锚（`drawAnchor(t)`） |
| `events.js` | 事件表：画面和混音读同一张（`EV.build`、`pattern`、`onWord`），命中画在声音那一帧（`snapT`、`hitEnv`、`progHit`）；`make.sh events` 导出，`film.py` 的 `fx_from_events` 按它放音效（`../方法/声音.md`「声音上的贴」） |
| `film.py` | 稿子 → 时间轴 → 字幕 → 门禁（开头、名句、稿子哈希）→ 混音 |
| `sound.py` | 合成音效：垫底、铃、哔、呼的一声、落地、音符 |
| `capture.mjs` | 起浏览器：崩溃扫描、静帧、检查、密查、逐帧渲染、导出事件表 |
| `timecheck.mjs` | 时间上的检查：章节名停够没有、字停够读完没有、画面停太久 |
| `make.zsh` | 每条片子 `./make.sh <命令>` 的全部命令，不带参数列出来 |
| `wordcheck.py` | render.js 里按词触发的词还在不在稿子里 |
| `qc*.py`、`sheet.py`、`qc_av.py` | 成片审的材料：手机尺寸联系表、响度跳变、黑屏静音 |
| `qcsync.py` | 画声同步：成片里每个事件的画面亮起那一帧对声音开始那一帧，90% 同一帧、没有差过 ±1 帧才过（`make.sh qcsync`） |
| `cover.mjs` | 出封面候选 |
| `pixel.js`、`chibi.js`、`mocap.py` | 像素小人、Q 版小人、动作数据（mocap 要的 CMU 数据没带） |
| `teaser.py` | 从成片剪预告（默认不做） |

## 没带的、要自己接的

- `engines/`：Gemini TTS、火山豆包语音、IndexTTS、FunASR 回读、Lyria 配乐、HDemucs 查人声。`make.sh voice`、`align`、`music`、`mixcheck` 这些命令要它们，不接就跑不了。key 自己放环境变量，脚本不读文件、不打印 key。
- `voices/`：参考音色。
- 别的模板（纪录长片等）和各系列自己的样式。
