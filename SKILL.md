---
name: huoban-user-manual
description: >
  用浏览器实测伙伴云系统并截图，生成图文手册（Markdown + 图片目录），一次一本：
  使用手册（面向业务操作者）或配置手册（面向管理员，讲配置在哪、为什么、改了影响什么）。
  用户要带截图的使用/操作手册、配置/搭建手册、实测手册或帮助文档时触发。
metadata:
  requires:
    bins: ["hac", "python3"]
---

# 伙伴云图文手册生成 Skill

## 核心原则

1. **一次任务只出一本**：使用手册或配置手册，二选一，不并出。术语口径见 [CONTEXT.md](CONTEXT.md)。检验句：使用手册回答"我该做什么、系统会给我什么"，配置手册回答"系统为什么会这样、在哪改、改了影响什么"。
2. **双轨采集**：hac 管逻辑真相（字段配置、自动化逻辑、审批流），浏览器管界面真相（真实截图、交互细节、提示文案）。二者冲突时以界面实测为准，并在实测笔记里标记。外部平台和纯平台功能没有 hac 兜底，**事实来源**以用户提供加界面实测为准，拿不准标 `[待确认]`；这条只约束事实从哪来，不限制截图由谁截。
3. **浏览器里能打开的都自己截，且一律走 `scripts/browser.py`**：不分伙伴云还是外部平台（阿里云、企业微信、飞书等控制台），走查和截图都由自己完成，不要让用户代截。唯一的例外是**输入账号密码**：登录动作在 browser.py 的窗口里交给用户，登完继续代劳。**不要去接管用户日常用的浏览器**：那类工具截的图落不到指定路径，也没有脱敏和标框能力，做不成手册产物。
4. **标注与脱敏只有一份标准**：截图怎么画标注框、怎么脱敏，全按 [references/walkthrough-guide.md](references/walkthrough-guide.md) 第五节执行，其他文件不另立规则：业务数据零打码，只有 API key、密钥、账号密码类凭证要模糊。
5. **按需采集，省 token**：能用一条命令批量落盘的不逐表查；只对写进文档的内容深查配置，不拿全量配置层。
6. **分阶段交互**：范围和骨架让用户确认后再动手；生成后交用户审阅。
7. **写作规范分轨**：使用手册按 [references/writing-guide.md](references/writing-guide.md)，配置手册按 [references/config-writing-guide.md](references/config-writing-guide.md)；走查规范两轨共用 walkthrough-guide。

---

## 工作流程

### 阶段〇：环境准备

1. 涉及伙伴云工作区时验证 hac 可用：`hac table list-tables --space-id <space_id>` 试跑，401/403 停止任务让用户检查认证。

2. 启动走查浏览器：

   ```bash
   python3 scripts/browser.py start          # 默认打开 https://app.huoban.com
   ```

   首次使用（或会话失效）让用户在弹出的浏览器窗口里自行登录；登录态存在持久化 profile（`~/.hb-manual-profile`），之后免登录。涉及外部平台控制台时同理：`start --url <控制台地址>` 打开，让用户在**这个窗口**里登录。

3. **切到目标工作区并核对**：先用 hac 按 space_id 查出工作区名（`hac space` 域命令现查），再在浏览器里切到该工作区（左上角工作区切换器，或直达工作区 URL）。`python3 scripts/browser.py snapshot` 核对页面上的工作区名与 space_id 对得上；对不上就是进错了区，切对再继续。账号有多个工作区时这一步不能省。

### 阶段一：需求对齐 + 现状盘点 + 定骨架

1. **需求对齐**，跟用户问清：

   - **写哪本**：使用手册还是配置手册。用户措辞能判断就不问（"给业务人员的操作手册"→使用手册；"交付给管理员的配置文档"→配置手册），判断不了就明确问一句。
   - 写什么范围（模块 / 场景清单）、给谁看、**演示环境**在哪个工作区/账号。演示环境由用户提供搭好的，本 skill 不负责搭建；场景和流程也只能来自用户，不替用户发明。

2. **现状盘点，表和页面都要盘，起点固定是工作区首页**：先停在目标工作区首页，把左侧导航从头滚到底看全（分组、表、工作台、看板、报表页逐个记下），不要拿到表清单就直接跳进某张表。`hac table list-tables --space-id <space_id>` 拉表清单；工作台、看板、报表页这类**页面不在表清单里**，以导航实看为准（或用 hac 页面命令现查），把非表入口一并列出。两份清单一起展示给用户确认哪些纳入、哪些排除；确认后 `hac table +resolve-id --table <表名>` 解析成纯数字 table_id 列对照表。不落在任何工作区的内容（纯平台功能、外部平台）记下来，没有元数据可盘。

3. **定文档骨架，写进 `<产出目录>/outline.md`**。outline.md 记三样：纳入的表、纳入的页面、章节清单，它是阶段三的写作依据，也是骨架环节确实做过的凭证。两轨骨架不同：

   **使用手册**（形态唯一：成册，单场景就是只有一章的册子）：

   - 判定模块类型（基础资料 / 业务流程），标出主单据、明细表、资料表，划业务闭环，给一版章节清单。
   - 册末固定含「典型业务场景」章；业务流程模块册头固定配一张全流程图（`scripts/flow.py`）；基础资料模块固定含「基础资料导入说明」章。

   **配置手册**（结构见 config-writing-guide）：

   - 第一章固定是**成果展示**；之后按**搭建顺序**分章：建表与字段（依赖序）→ 自动化 → 审批流 → 权限与角色 → 页面/工作台 → 数据仓库。**涉及到的层才列，不涉及的不出现在骨架里**。
   - 骨架里列清每章覆盖哪些表/自动化/流程，让用户确认。

4. **阶段一的交付物就是 outline.md 本身**：把章节清单展示给用户，本次任务到此**正常完成**。用户回复确认后，在 outline.md 末尾加一行 `<!-- 用户已确认 -->`，续写任务才进入阶段二（digest.py 会校验这个标记，没有就拒绝运行）。

### 阶段二：轻采集（全部落盘，不进上下文）

只跑清单级命令，输出全部重定向到采集目录，AI 不读原始 JSON：

```bash
hac table er-diagram-collect --space <space_id> --output <采集目录>/facts.json   # 全区表、字段、关系、记录数
# 对范围内每张表（工作区级 automation 搜索会漏快捷按钮和旧版 workflow，必须按表逐个查）：
hac automation list --table-id <tid> --space-id <space_id> > <采集目录>/automation-<tid>.json
hac table form-layout get --table-id <tid> > <采集目录>/layout-<tid>.json
hac procedures list-procedures --space-id <space_id> > <采集目录>/procedures.json
# 落盘后核一眼，0 字节的是采失败了（hac 把错误写 stderr，重定向只留空文件）
wc -c <采集目录>/*.json
```

**采多少由骨架决定，不一律跑全套**：

- 使用手册：只核对演示环境的跑 `er-diagram-collect` 加涉及表的 `automation list`；要细讲表单填写才补 `form-layout`，讲审批才补 `procedures`。
- 配置手册：骨架里有哪层就采哪层，范围内的表通常全跑（配置手册的主体就是配置本身）。
- 内容不落在任何工作区的，记一句"无可采集的工作区"，直接进阶段三。

然后逐章跑摘要脚本，拿紧凑摘要包（一张 40 字段的表约 1.5k token）：

```bash
python3 scripts/digest.py --dir <采集目录> --tables "本章的表,逗号分隔" --outline <产出目录>/outline.md
```

把摘要要点展示给用户确认后进循环。

### 阶段三：逐章循环（深查 → 走查 → 写作）

业务流程模块动笔前先出册头总览流程图（仅使用手册）：从骨架写 flow.json，`python3 scripts/flow.py flow.json images/0-全流程总览.svg`，放模块介绍后面。然后按阶段一确认的骨架推进，每章一个闭环：

1. **读本章摘要包**（digest.py 输出；无可采集工作区的单元跳过）。
2. **按需深查**，只查本章要写的内容：
   - 重点自动化（会点的按钮、改状态/金额的触发、发通知起审批的）：
     `hac --output-mode purpose automation get --automation-id <id>`（流程/分支/写哪张表的业务投影）；要具体写入值才用 `--output-mode full`。看不懂节点含义用 `hac automation docs` 按 key 切片取。
   - 审批流（procedures.json 里绑定到本章表的启用流程）：`hac procedures get-procedure --procedure-id <id>` 拿版本 → `hac procedures get-procedure-version` 直读流程图环节。
   - 零散配置（计算公式、自动编号规则、字段显示条件、打印模板）：仅对需要向读者解释的字段跑 `hac --output-mode full table get-table --table-id <id>` / `hac table list-print-templates --table-id <id>` 提取。
   - 字段类型名以 `hac table field-config list-types` 为准，不凭印象写。
   - **配置手册专用**：写"改动会影响什么"时查引用关系：字段被哪些自动化、公式、关联引用（子命令用 `hac table --help` 现查，不凭印象）；权限角色、页面配置 hac 覆盖不到的部分以界面实测为准。
3. **浏览器走查 + 截图**，全按 [references/walkthrough-guide.md](references/walkthrough-guide.md) 执行：先从摘要包推导本章的截图点位清单（配置手册的点位是配置入口和编辑界面，密度低于使用手册），再按「看 → 动 → 看 → 截」循环走查。截图存 `<产出目录>/images/`，界面观察记 `notes.md`，落的演示数据登记 `demo-data.md`。
4. **写本章 Markdown**：使用手册按 writing-guide，配置手册按 config-writing-guide，含配图规范。图放进它对应的步骤条目里（列表项下缩进 4 空格），用相对路径引用。**本章写完的标准**：每个操作序列配齐入口图、过程图、结果图（能合并的合并），每张图挂在它对应的步骤下、框对准该步骤的控件，步骤点名的按钮和字段都能在图里找到；对照 notes.md 登记的截图逐步骤核对，缺图现在回走查补截，不欠到自检。
5. **渲染 HTML 预览**：`python3 scripts/render.py <文档.md>`，同目录出同名 .html。md 是源文件，人工修改改 md，改完重跑一次；html 只当预览不手改。

一章写完再进下一章；上一章的深查 JSON 和走查细节不带进下一章上下文。

### 阶段四：自检 + 交付

对照 [references/self-check.md](references/self-check.md) 逐项过，全部通过才交用户审阅；`[待确认]` `[待补充]` 处需用户校正。

---

## 内置脚本

各脚本的参数细节和示例以**脚本头注释**为准（`head <脚本>` 即可查），此处只记分工：

- **digest.py**：读采集目录落盘文件，输出章节摘要包 Markdown。AI 只读它的输出，不读原始 JSON。`--outline` 必传：outline.md 缺失或没有用户确认标记就拒绝运行（阶段一门闩）。
- **flow.py**：册头全流程图（一册一张），flow.json → SVG。分组横排、步骤竖排，副行标表名，系统自动环节置灰虚线。
- **render.py**：Markdown → HTML 预览（Linear 浅色皮肤，零依赖零 token）。md 写法约定见脚本头注释。
- **annotate.py**：按百分比坐标给截图画标注框、模糊、裁剪。browser.py 的 CSS 选择器在控制台类 SPA 匹配不上时用它；没先 `--grid` 量过就画会直接报错。多个 `--box` 自动按传入顺序标序号角标。
- **browser.py**：浏览器走查驱动，每个子命令独立执行、窗口跨命令常驻。子命令清单（start / status / page / goto / snapshot / click / type / fill / press / scroll / wait / shot / eval / stop）和参数见脚本头注释；`shot` 的 `--highlight` 多框自动标序号，`--blur` 做模糊脱敏。

## CLI 铁律

1. `table_id` / `space_id` 必须纯数字，需要 ID 先 `hac table +resolve-id`。
2. 执行 hac 禁止 `2>&1`：stdout 是数据，stderr 是 token 统计。
3. 认证失败（401/403）→ 停止任务，告知用户检查认证配置。
4. 浏览器操作报"连不上浏览器"时重新 `start`；页面内容和预期对不上时先 `snapshot` 看清现状再决定，不盲点。

## 输出规范

一个需求一个目录，一次只出一本手册：

```
<模块名或主题>/
├── <模块名>.md            # 使用手册（写使用手册时）；源文件，人工修改改这份
├── <模块名>-配置手册.md    # 配置手册（写配置手册时）
├── <同名>.html            # 预览产物，scripts/render.py 从 md 渲染，改完 md 重跑
├── images/                # 截图与流程图，<章节号>-<序号>-<短说明>.png/.svg
├── outline.md             # 骨架清单（表、页面、章节），用户确认的凭证
├── notes.md               # 实测笔记（交付时可删）
└── demo-data.md           # 演示数据登记（清理完可删）
```

- 使用手册标题只写模块名，不追加"使用手册"；配置手册标题写"<模块名>配置手册"。
- 短流程用文本箭头 `→`，册头全流程图用 flow.py 出图。
