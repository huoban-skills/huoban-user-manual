---
name: huoban-user-manual
description: >
  用浏览器实测伙伴云系统并截图，生成图文手册（Markdown + 图片目录），一次一本：
  使用手册（面向业务操作者）或配置手册（面向管理员，讲配置在哪、为什么、改了影响什么）。
  用户要带截图的使用/操作手册、配置/搭建手册或帮助文档时触发。
metadata:
  requires:
    bins: ["hac", "python3"]
    pips: ["pillow", "playwright"]   # pillow 缺了标注框机检会整项跑不了；playwright 缺了走查开不了浏览器
---

# 伙伴云图文手册生成

**目标**：对着搭好的演示环境逐屏实测，产出带截图的图文手册。一次一本，二选一：

- **使用手册**：面向业务操作者，回答"我该做什么、系统会给我什么"
- **配置手册**：面向管理员，回答"系统为什么会这样、在哪改、改了影响什么"

**输入**：

1. **工作区 ID（必填）**：演示环境的 `space_id`，缺了先问
2. **写哪本（必填）**：用户措辞能判断就不问（"给业务人员的操作手册"→使用手册；"交付给管理员的配置文档"→配置手册），判断不了就问一句
3. **范围（必填）**：写哪些模块、给谁看；在阶段一盘点后与用户确认定稿
4. **场景清单（可选）**：用户提供的真实业务流程，没有就按盘点结果推导

**输出**：`<模块名>/` 一个目录，结构见「输出物结构」。读者是**一线操作者或管理员**，对着手册就能照做。

**边界**：

- 一次只出一本，两轨不并出
- 不搭演示环境：环境由用户提供，场景和流程也只能来自用户，不替用户发明
- 不接管用户日常浏览器：走查一律走 `scripts/browser.py`，那类工具截的图落不到指定路径，也没有脱敏和标框能力
- 账号密码不代输：登录在 browser.py 窗口里交给用户，登完继续代劳

## 依赖关系

| 要做的事 | 去哪 |
| --- | --- |
| 使用手册怎么写 | [writing-guide.md](references/writing-guide.md) |
| 配置手册怎么写 | [config-writing-guide.md](references/config-writing-guide.md) |
| 措辞、口吻、用词（两轨共用，表述层唯一事实源） | [user-manual-humanize.md](references/user-manual-humanize.md) |
| 走查、截图、标注框、脱敏（两轨共用，唯一事实源） | [walkthrough-guide.md](references/walkthrough-guide.md) |
| 交付前逐项过 | [self-check.md](references/self-check.md) |
| 轻采集落盘 | `python3 scripts/collect.py --space-id <sid> --dir <采集目录> --tables "表A,表B"` |
| 章节摘要包（AI 只读它，不读原始 JSON） | `python3 scripts/digest.py --dir <采集目录> --tables "本章的表" --outline <产出目录>/outline.md` |
| 系统原词表（供机检核对界面名词） | `python3 scripts/vocab.py --dir <采集目录>` |
| 册头全流程图（业务流程模块，一册一张） | `python3 scripts/flow.py flow.json images/0-全流程总览.svg` |
| 渲染预览 + 格式机检 | `python3 scripts/render.py <文档.md> --vocab <采集目录>/vocab.json` |
| 浏览器走查驱动 | `scripts/browser.py`，子命令和参数见脚本头注释 |
| 控制台类 SPA 画框（CSS 选择器匹配不上时） | `scripts/annotate.py`，没先 `--grid` 量过就画会报错 |

**双轨采集**：hac 管逻辑真相（字段配置、自动化逻辑、审批流），浏览器管界面真相（截图、交互细节、提示文案）。二者冲突以界面实测为准，并在 notes.md 标记差异。外部平台和纯平台功能没有 hac 兜底，事实来源以用户提供加界面实测为准，拿不准标 `[待确认]`。

**事实来源分级（硬规则）**：正文里的菜单、按钮、页签、提示语只能用**浏览器实测到的界面原词**；hac 里的表名、字段名、自动化名称是内部配置名，不得当界面词写进正文（配置叫「收款核销」，界面按钮可能是「核销应收」）。界面原词的凭证是 `browser.py shot` 自动落盘的 `.png.meta.json`（URL + 被框元素原文 + 页面可见按钮原文），render.py 语义审计逐图核对：正文点名的按钮没有截图证据、或用了 hac 内部名，机检直接不通过。没有证据的说法宁可标 `[待确认]`，不许按常见页面模式脑补（"列表右侧还能查看详情/审批"这类没亲眼见过的不写）。

## 执行流程

```
环境准备 → 盘点定骨架 → 确认点一（骨架） → 轻采集 → 逐章循环（深查 → 走查 → 写作 → 机检） → 自检 → 交付
```

## 执行步骤

### 阶段〇：环境准备

1. 验证 hac 可用：`hac table list-tables --space-id <space_id>` 试跑。
2. 启动走查浏览器：`python3 scripts/browser.py start`。首次使用或会话失效，让用户在弹出窗口里自行登录；登录态存在持久化 profile（`~/.hb-manual-profile`）。涉及外部平台控制台同理，`start --url <控制台地址>` 后让用户在**这个窗口**里登录。
3. 切到目标工作区并核对：先用 `hac space` 域命令按 space_id 查出工作区名，再在浏览器里切过去，`browser.py snapshot` 核对页面上的工作区名对得上。对不上就是进错了区，切对再继续。

### 阶段一：盘点定骨架

1. **盘点，起点固定是工作区首页**：先停在首页把左侧导航从头滚到底看全（分组、表、工作台、看板、报表页逐个记下），不要拿到表清单就跳进某张表。
2. `hac table list-tables --space-id <space_id>` 拉表清单；工作台、看板、报表页**不在表清单里**，以导航实看为准。
3. 盘点范围取**表清单和导航的并集**（导航没入口的表也算，从「全部表格」能进），展示给用户确认哪些纳入。
4. 确认后 `hac table +resolve-id --table <表名>` 解析成纯数字 table_id 列对照表。
5. **写 `<产出目录>/outline.md`**，记三样：纳入的表、纳入的页面、章节清单。两轨骨架不同：
   - **使用手册**：判定模块类型（基础资料 / 业务流程），标出主单据、明细表、资料表，划业务闭环。业务流程模块册头固定配一张全流程图；基础资料模块固定含「基础资料导入说明」章。
   - **配置手册**：第一章固定成果展示，之后按搭建顺序分章（建表与字段 → 自动化 → 审批流 → 权限与角色 → 页面/工作台 → 数据仓库），涉及到的层才列。
6. **确认点一**：把章节清单展示给用户，本次任务到此**正常完成**。用户回复确认后，在 outline.md 末尾加一行 `<!-- 用户已确认 -->`，续写任务才进阶段二。

### 阶段二：轻采集

输出全部落盘，AI 不读原始 JSON。

```bash
python3 scripts/collect.py --space-id <space_id> --dir <采集目录> --tables "表A,表B,表C"
hac procedures list-procedures --space-id <space_id> > <采集目录>/procedures.json   # 讲审批才补
python3 scripts/vocab.py --dir <采集目录>
wc -c <采集目录>/*.json    # 0 字节的是采失败了（hac 把错误写 stderr，重定向只留空文件）
```

- 采多少由骨架决定：使用手册只传骨架里纳入的表；配置手册骨架里有哪层就采哪层。
- 工作区级 automation 搜索会漏快捷按钮和旧版 workflow，collect.py 按表逐个查，不要绕开它自己拼。
- 内容不落在任何工作区的（纯平台功能、外部平台），记一句"无可采集的工作区"，直接进阶段三。
- 逐章跑 `digest.py` 拿摘要包，把要点展示给用户确认后进循环。

### 阶段三：逐章循环

业务流程模块动笔前先出册头总览流程图（仅使用手册）：从骨架写 flow.json，`flow.py` 渲染，放模块介绍后面。然后按骨架推进，每章一个闭环：

1. **读本章摘要包**（digest.py 输出；无可采集工作区的单元跳过）。
2. **按需深查**，只查本章要写的内容：
   - 重点自动化（会点的按钮、改状态/金额的触发、发通知起审批的）：`hac --output-mode purpose automation get --automation-id <id>`；要具体写入值才用 `--output-mode full`。看不懂节点含义用 `hac automation docs` 按 key 切片取。
   - 审批流：`hac procedures get-procedure --procedure-id <id>` 拿版本 → `hac procedures get-procedure-version` 直读环节。
   - 零散配置（计算公式、自动编号规则、字段显示条件、打印模板）：仅对要向读者解释的字段跑 `hac --output-mode full table get-table --table-id <id>` / `hac table list-print-templates --table-id <id>`。
   - 字段类型名以 `hac table field-config list-types` 为准，不凭印象写。
   - **配置手册专用**：写"改动会影响什么"时查引用关系（子命令用 `hac table --help` 现查）；权限角色、页面配置 hac 覆盖不到的部分以界面实测为准。
3. **走查截图**，全按 walkthrough-guide 执行：先从摘要包推导本章点位清单**落盘 notes.md**，再按「看 → 动 → 看 → 截」循环。截图存 `<产出目录>/images/`，落的演示数据登记 `demo-data.md`。
4. **写本章 Markdown**：使用手册按 writing-guide，配置手册按 config-writing-guide，措辞两轨都按 user-manual-humanize。写作中拿不准按钮、页签的原词，先 `grep <关键词> images/*.meta.json` 查截图证据——原文都在里面，不用回浏览器再走一趟。图挂进它对应的步骤条目（列表项下缩进 4 空格），相对路径引用。**本章写完的标准**：每张图挂在对应步骤下、框对准该步骤讲的内容，步骤点名的按钮和字段都能在图里找到；对照 notes.md 逐步骤核对，缺图现在回走查补截，不欠到自检。
5. **渲染 + 机检**：`render.py <文档.md> --vocab <采集目录>/vocab.json`，同目录出同名 .html。md 是源文件，人工改 md 后重跑；html 只当预览不手改。机检含格式检查和截图证据语义审计（界面原词、框↔正文、角标顺序、notes 点位），退出码非 0 就不算写完，不许口头宣布完成。`--vocab` 不传，正文里「」引的字段名是否生造就没人核对。

一章写完再进下一章；上一章的深查 JSON 和走查细节不带进下一章上下文。

### 阶段四：自检交付

对照 [self-check.md](references/self-check.md) 逐项过，全部通过才交用户审阅；`[待确认]` `[待补充]` 处需用户校正。

## 输出物结构

```
<模块名或主题>/
├── <模块名>.md            # 使用手册；源文件，人工修改改这份
├── <模块名>-配置手册.md    # 配置手册
├── <同名>.html            # 预览产物，render.py 渲染，改完 md 重跑
├── images/                # 截图与流程图，<章节号>-<序号>-<短说明>.png/.svg
│                          # 每张 png 配 shot 自动落盘的同名 .png.meta.json 证据，交付保留不清理
├── outline.md             # 骨架清单，用户确认的凭证
├── notes.md               # 实测笔记与点位清单（机检核它，交付前不删）
└── demo-data.md           # 演示数据登记（清理完可删）
```

- 使用手册标题只写模块名，不追加"使用手册"；配置手册标题写"<模块名>配置手册"。
- 短流程用文本箭头 `→`，册头全流程图用 flow.py 出图。

## CLI 铁律

1. `table_id` / `space_id` 必须纯数字，需要 ID 先 `hac table +resolve-id`。
2. 执行 hac 禁止 `2>&1`：stdout 是数据，stderr 是 token 统计。
3. 认证失败（401/403）→ 停止任务，告知用户检查认证配置。
4. 浏览器报"连不上浏览器"时重新 `start`；页面内容和预期对不上时先 `snapshot` 看清现状，不盲点。
