# YAML 数据转换工具 | 命令行指南

欢迎使用 YAML 数据转换工具！本文档将详细介绍如何通过命令行使用此工具，以实现对 YAML 文件的高效、自动化转换。


## 基本用法

工具的基本命令结构如下：

```bash
python main.py -r <规则文件> -i <输入文件或目录> [其他选项]
```

-   `-r` 用于指定转换规则文件。
-   `-i` 用于指定待处理的源文件或目录。

查看工具使用方法：

```bash
python main.py -h
```

## 参数详解

下面是所有可用命令行参数的详细说明。

### --input, -i

-   **说明**: 指定输入的源文件路径或目录路径。
-   **必需**: 是
-   **值**:
    -   如果只转换单个文件，请提供文件的完整路径（例如 `data/items.yml`）。
    -   如果要批量转换，请提供包含 `.yml` 或 `.yaml` 文件的目录路径（例如 `source_data/`）。

### --rules, -r

-   **说明**: 指定包含转换逻辑的 `conversion_rules.yml` 文件。
-   **必需**: 是
-   **值**: 规则文件的路径（例如 `rules/v2_to_v3.yml`）。

### --output, -o

-   **说明**: 指定转换后文件的输出路径。此参数的行为取决于输入模式。
-   **必需**: 否
-   **默认值**:
    -   **单文件模式**: 如果不指定，默认在当前目录下生成名为 `converted_items.yml` 的文件。
    -   **批量模式**: 如果不指定，默认在当前目录下创建一个名为 `converted_output/` 的目录来存放所有转换后的文件。
-   **值**:
    -   在单文件模式下，可以是一个文件名（例如 `new_items.yml`）或一个目录路径。如果提供的是目录，转换后的文件将以原名存放在该目录中。
    -   在批量模式下，必须是一个目录路径（例如 `output_data/`）。

### --batch

-   **说明**: 启用批量转换模式。当输入路径 (`-i`) 是一个目录时，必须使用此标志来告知工具处理该目录下的所有 YAML 文件。
-   **必需**: 否 (但在处理目录时是必需的)

### --debug

-   **说明**: 启用调试模式。这会在控制台打印详细的转换过程日志，包括每个规则的评估、每个动作的执行情况等。非常适合在编写规则或排查问题时使用。
-   **必需**: 否

### --sequence-start

-   **说明**: 在运行时覆盖规则文件中 `sequence` 动作的 `start` 值。这允许你在不修改规则文件的情况下，为不同的转换任务动态指定起始 ID。
-   **必需**: 否
-   **格式**: `路径:起始值`。可以同时提供多个覆盖。
-   **示例**:
    -   `--sequence-start custom-model-data:50000`
    -   `--sequence-start data.id:10001 other.id:9000`

---

## 使用示例

### 1. 转换单个文件

这是最常见的用法。将 `old_items.yml` 按照 `rules.yml` 的规则进行转换，并使用默认输出文件名 `converted_items.yml`。

```bash
python main.py -r rules.yml -i old_items.yml
```

### 2. 批量转换整个目录

转换 `input_folder/` 目录下的所有 `.yml` 文件，并将结果保存到 `output_folder/` 目录中。

```bash
python main.py -r rules.yml -i input_folder/ --output output_folder/ --batch
```
> **注意**: 处理目录时，必须使用 `--batch` 标志。

### 3. 转换单个文件并指定输出名称

将 `old_data.yml` 转换为 `new_data.yml`。

```bash
python main.py -r rules.yml -i old_data.yml -o new_data.yml
```

### 4. 覆盖序列字段的起始值

假设你的 `rules.yml` 中有一个 `sequence` 规则用于 `custom-model-data` 字段。以下命令将在转换时强制其从 `70001` 开始计数，而不是使用规则文件中定义的 `start` 值。

```bash
python main.py -r rules.yml -i items_to_update.yml --sequence-start custom-model-data:70001
```

### 5. 启用调试模式进行故障排查

如果你想查看转换的详细步骤，请使用 `--debug` 标志。

```bash
python main.py -r rules.yml -i test_item.yml --debug
```

### 6. 组合使用：批量转换并覆盖多个序列值

这是一个更复杂的示例，它会：
-   批量转换 `all_items/` 目录中的所有文件。
-   将结果保存到 `final_output/` 目录。
-   强制 `custom-model-data` 字段的序列从 `10001` 开始。
-   强制 `internal_id` 字段的序列从 `1` 开始。

```bash
python main.py -r rules.yml -i all_items/ -o final_output/ --batch --sequence-start custom-model-data:10001 internal_id:1
```