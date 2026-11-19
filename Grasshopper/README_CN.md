# FacadeAI：80组自动化模拟代码整理包（CSV Index 80–159）

本包整理了原始 `script.zip` 中与后80组（Index 80–159）自动化模拟有关的代码、Grasshopper模型、输入参数、结果文件和运行说明。**原始核心脚本保留，没有把流程改写成未经验证的新代码。**

## 1. 自动化范围与数据边界

- 自动化范围：`CSV Index 80–159`，共80组。
- Index 0–79：原始项目记录为队友提供的数据，不属于本自动化脚本独立运行并验证的80组。
- 本包 `config.example.json` 已将 `start_index` / `end_index` 设为 `80` / `159`。
- 输入CSV仍包含完整160组，因为Grasshopper的Case Index与输入行号对应，不能把后80行单独截出来后仍沿用原索引。

## 2. 文件结构

```text
FacadeAI_80_Case_Automation_Code/
├─ README.md                         # 原项目说明
├─ README_CN.md                      # 中文运行说明（本文件）
├─ SIMULATION_METHOD.md              # 原项目方法、验证标准和局限
├─ config.example.json               # 示例配置，默认只运行80–159
├─ requirements.txt                  # Python依赖
├─ model/
│  ├─ FacadeAI_Final_Model_v1.gh     # Grasshopper原模型
│  └─ FacadeAI_Final_Model_v1.ghx    # 自动化脚本打开的GHX副本
├─ data/
│  ├─ input/FacadeAI_Input_Cases.csv # 160组参数输入
│  └─ results/                       # 原始/汇总结果及Excel模板
└─ scripts/
   ├─ run_facadeai_rhino.py          # Rhino 8 / Grasshopper批量控制入口
   ├─ facadeai_case.py               # 单组任务、断点续跑、CSV/Excel checkpoint
   ├─ facadeai_pipeline.py           # OpenStudio运行、SQL/EUI提取和结果验证
   ├─ assemble_results.py            # 合并来源结果，生成带来源标记的总表
   └─ validate_package.py            # 文件、依赖、索引和结果一致性检查
```

## 3. 五个脚本分别做什么

| 脚本 | 作用 | 关键内容 |
|---|---|---|
| `run_facadeai_rhino.py` | 批量入口 | 打开GHX；设置CSV路径、Case Index和输出路径；触发ModelToOSM导出；按80–159循环 |
| `facadeai_case.py` | 单案例控制 | 检查是否已有验证成功的结果；执行单组模拟；写CSV；同步Excel |
| `facadeai_pipeline.py` | 核心计算/验证 | 检查HBJSON身份、OSW引用；调用OpenStudio；检查EnergyPlus日志和SQL；计算EUI |
| `assemble_results.py` | 结果整理 | 将0–79队友记录与80–159自动化记录合并，并保留provenance |
| `validate_package.py` | 运行前检查 | 检查文件、Python依赖、160行输入CSV、索引范围和CSV/Excel一致性 |

## 4. 自动化流程

```text
FacadeAI_Input_Cases.csv（160行）
             │
             ▼
Rhino 8 打开 FacadeAI_Final_Model_v1.ghx
             │
             ▼
逐一选择 CSV Index 80–159
             │
             ▼
设置 Case Index + 输出目录
             │
             ▼
Grasshopper Recompute
             │
             ▼
核对 design_id / WWR / glazing / shading 参数
             │
             ▼
ModelToOSM 导出 HBJSON + workflow.osw
             │
             ▼
检查文件新鲜度、HBJSON身份、OSW模型引用
             │
             ▼
OpenStudio 3.7.0 → EnergyPlus
             │
             ▼
检查 eplusout.end / eplusout.err / eplusout.sql
             │
             ▼
提取 Total Site Energy + Building Area
             │
             ▼
EUI = Annual Site Energy / Total Building Area
             │
             ▼
CSV checkpoint → Excel同步 → 下一个case
```

### 断点续跑与停止规则

- 已存在且通过验证的结果会被跳过（Resume）。
- 每组成功后先写CSV，再尝试同步Excel（Checkpoint）。
- 如果导出、模拟或验证失败，批处理会记录错误并在该组停止，不会静默跳过失败项。
- Excel被占用时，CSV/SQL验证结果仍保留；脚本会尝试生成同步副本或在批次结束时再次同步。
- EnergyPlus出现Severe/Fatal错误、没有成功结束标记、SQL过期或无法提取面积/能耗时，该组不会标记为成功。

## 5. Windows环境要求

原项目README注明的运行环境：

- Windows 10/11
- Rhino 8 + Grasshopper
- 与该GHX兼容的 Ladybug Tools / Honeybee（原项目注明1.8.0）
- OpenStudio 3.7.0（含EnergyPlus）
- Python 3.8或更新版本，安装`openpyxl`
- Rhino内置脚本运行环境需兼容该驱动使用的IronPython 2.7语法

> 注意：Rhino驱动使用Rhino/Grasshopper .NET API；单组处理器则由配置中的外部Python解释器执行。两者不是同一个Python运行环境。

## 6. 首次运行步骤

### A. 解压与配置

1. 将整个文件夹解压到本机固定路径，路径尽量不要包含特殊字符。
2. 在项目根目录复制配置文件：

```powershell
Copy-Item config.example.json config.json
```

3. 编辑`config.json`中的：
   - `python_exe`：本机可用且已安装`openpyxl`的Python解释器路径；
   - `openstudio_exe`：本机`openstudio.exe`完整路径；
   - 如有需要，调整`simulation_root`等输出目录。
4. 本包默认`start_index=80`、`end_index=159`，运行前再次确认。

### B. 安装依赖并预检查

```powershell
python -m pip install -r requirements.txt
python scripts/validate_package.py --dry-run
```

`--dry-run`只检查配置和已有结果，不启动EnergyPlus。

### C. 在Rhino 8中启动

1. 启动Rhino 8。
2. 打开Grasshopper（脚本会自行打开配置指定的GHX副本）。
3. 在Rhino命令行执行：

```text
_RunPythonScript "D:\你的解压路径\FacadeAI_80_Case_Automation_Code\scripts\run_facadeai_rhino.py"
```

4. 查看Rhino命令行及`data/simulation/.facadeai_logs/rhino_batch.log`。
5. 结果写入配置指定的CSV与XLSX；模拟输出按design_id分目录保存。

## 7. 重要：如何避免“旧结果被跳过”

`facadeai_case.py`会跳过已验证成功的案例，这是为了断点续跑。如果你要在新电脑上**重新跑全部80组**，应先备份现有结果文件，并确认旧SQL/HBJSON/OSW路径不可用或不应复用；再按项目规则清理/另设`results_csv`和`simulation_root`。不要直接删除唯一结果副本。

## 8. 结果与公式

- SQL提取：优先`Total Building Area`，缺失时尝试`Net Conditioned Building Area`。
- 年总场地能耗：`Total Site Energy`。
- 单位换算后：

  `EUI (kWh/m²·year) = Annual Total Site Energy (kWh) / Total Building Area (m²)`

- 成功记录同时保存HBJSON、OSW、SQL路径、运行状态、更新时间及provenance。

## 9. 可复现性与限制

- 历史模拟文件夹、SQL数据库、EnergyPlus日志、天气文件等大体积运行产物未包含在原始ZIP中。
- 原始项目文档说明：80–159的既有结果在打包时已针对HBJSON、OSW、EnergyPlus完成标记、错误日志、SQL和EUI进行过验证；这不代表本次对话环境重新运行了Rhino或EnergyPlus。
- 0–79的队友数据被明确标记为未由该自动化流程独立验证。
- 本整理包没有在当前环境执行Rhino/Grasshopper/OpenStudio模拟；运行成功仍取决于目标Windows电脑上的软件版本、插件、路径和天气/模型依赖。

## 10. 运行日志与排错

优先检查：

1. `data/simulation/.facadeai_logs/rhino_batch.log`
2. 每组OpenStudio运行目录中的`openstudio_batch.log`
3. `eplusout.err`与`eplusout.end`
4. 对应的`eplusout.sql`
5. `data/results/FacadeAI_Results_160.csv`中的`status`、`error`和`provenance`

不要只看Excel里是否有EUI数值；应同时确认状态和来源标记。
