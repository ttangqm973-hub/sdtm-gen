# SDTM GEN - SDTM SAS Code Generator

SDTM GEN 是一个自动化的 SDTM (Study Data Tabulation Model) SAS 代码生成工具，可以从 SPEC Excel/CSV 文件生成符合 CDISC SDTM 标准的 SAS 程序。

## 功能特性

- **SPEC 解析**: 支持 Excel (.xlsx) 和 CSV 格式的 SPEC 文件
- **智能 IR 构建**: 自动识别变量生成类型 (模板生成 vs AI 需要)
- **SAS 代码生成**: 基于模板生成标准 SDTM 域 SAS 程序
- **L1 语法检查**: 离线 SAS 代码语法检查和风格检查
- **CLI 工具**: 命令行界面支持批量处理

## 安装

```bash
cd sdtm_gen
pip install -r requirements.txt
pip install -e .
```

## 使用方法

### 生成 SAS 代码

```bash
# 从 SPEC 文件生成 SAS 代码
sdtm-gen generate spec.xlsx -o output_dir

# 生成并运行 L1 检查
sdtm-gen generate spec.xlsx -o output_dir --lint

# 详细输出
sdtm-gen generate spec.xlsx -o output_dir -v
```

### 分析 SPEC 文件

```bash
# 显示 SPEC 文件摘要
sdtm-gen analyze spec.xlsx

# 详细分析
sdtm-gen analyze spec.xlsx -v
```

### L1 语法检查

```bash
# 检查 SAS 文件
sdtm-gen lint code.sas

# JSON 格式输出
sdtm-gen lint code.sas --json
```

## 支持的 SDTM 域

- DM (Demographics)
- AE (Adverse Events)
- CM (Concomitant Medications)
- LB (Laboratory Test Results)
- VS (Vital Signs)
- EX (Exposure)
- MH (Medical History)
- EG (ECG Test Results)
- PE (Physical Examination)
- SUPPxx (Supplemental Domains)

## 项目结构

```
sdtm_gen/
├── cli.py                    # CLI 入口
├── config.py                 # 配置
├── parser/                   # SPEC 解析器
│   ├── excel_reader.py       # Excel/CSV 读取
│   ├── column_mapper.py      # 列映射
│   └── ir_builder.py         # IR 构建
├── ir/                       # 中间表示
│   └── models.py             # 数据模型
├── generator/                # 代码生成器
│   ├── template_renderer.py  # 模板渲染
│   └── sas_generator.py      # SAS 生成
├── templates/sas/            # Jinja2 模板
└── lint/                     # L1 检查器
    ├── sas_lexer.py          # 词法分析
    ├── sas_parser.py         # 语法分析
    └── sas_linter.py         # Linter
```

## 开发

### 运行测试

```bash
pytest tests/ -v
```

### 添加新域模板

1. 在 `templates/sas/` 创建新的模板文件，如 `xx_sdtm.sas.j2`
2. 模板自动继承 `domain_header.sas.j2`

## 许可证

MIT License
