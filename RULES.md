🚀 YAML 数据转换规则指南

## 1. 规则文件结构概览

你的 **conversion_rules.yml** 文件必须以一个顶层的 `rules` 列表开始。这个列表中的每个元素都是一个内容规则集。一个内容规则集指定了它所针对的 YAML 内容类型（例如 `item` 或 `block`），以及一系列应用于该类型数据的具体转换规则。

```yaml
rules:
  - name: "物品配置转换规则集" # 📦 内容规则集的描述性名称
    content: "items" # 🎯 指定此规则集作用于输入 YAML 文件中的 'items' 键
    context: # ✨ 定义可在此规则集中重用的动态变量
      # ... 上下文变量定义 ...
    rules: # 📜 针对 'item' 类型数据的具体转换规则列表
      - name: "规则一：移除旧路径"
        conditions:
          # ... 条件定义 ...
        actions:
          # ... 动作定义 ...

      - name: "规则二：更新模型信息"
        # ... 更多针对 'item' 的规则 ...

  - name: "方块行为配置转换规则集" # 📦 另一个内容规则集
    content: "blocks" # 🎯 指定此规则集作用于输入 YAML 文件中的 'blocks' 键
    depends_on: "物品配置转换规则集" # 📜 依赖于某个节点
    rules: # 📜 针对 'block' 类型数据的具体转换规则列表
      - name: "方块规则一：添加默认属性"
        # ... 条件定义 ...
        actions:
          # ... 动作定义 ...

      - name: "方块规则二：调整纹理路径"
        # ... 更多针对 'block' 的规则 ...
```

### 2. 内容规则集：定义你的转换范围

列表中的每个内容规则集都用于定义针对特定数据类型的转换逻辑。

- **`name`** (字符串, 必需):
    - **用途**: 为你的内容规则集取一个清晰的名称。它将出现在日志输出中，帮助你追踪当前正在处理的组。
    - **示例**: `"物品配置转换规则集"`, `"NPC 对话系统升级规则"`

- **`depends_on`** (字符串或列表, 可选):
    - **用途**: 控制规则之间的执行顺序。在某些复杂的转换场景中，您需要确保规则按照一个特定的顺序执行。例如，您可能需要先用一个规则 (`Rule_A`) 将一个旧字段 `old_name` 重命名为 `new_name`，然后再用另一个规则 (`Rule_B`) 去读取或修改 `new_name` 的值。如果没有顺序保证，`Rule_B` 可能会在 `Rule_A` 之前执行，导致找不到 `new_name` 字段而失败。`depends_on` 就是为了解决这个问题而设计的。
    - **工作原理**:
        - 当一个规则包含 `depends_on` 字段时，转换器会在执行该规则之前，检查其依赖的所有规则是否已经**在当前处理的数据条目上成功执行完毕**。
        - 依赖关系是通过规则的 `name` 字段来匹配的。因此，作为依赖的规则必须有一个唯一的 `name`。
        - 如果任何一个依赖规则尚未执行（或因条件不满足/`skip:true`而被跳过），那么当前规则也将被跳过。
        - 这是一种 **AND** 关系：如果提供了多个依赖，则必须全部满足。
    - **示例**:
        ```yaml
        # 示例1: 单个依赖
        # Rule_B 将在 Rule_A 成功执行后才会运行
        rules:
          - name: "Rule_A_RenameField"
            # ... actions ...
          - name: "Rule_B_ModifyNewField"
            depends_on: "Rule_A_RenameField" # 依赖单个规则
            # ... actions ...
        
        # 示例2: 多个依赖
        # Rule_C 必须等待 Rule_A 和 Rule_B 都成功执行后才会运行
        rules:
          - name: "Rule_A_Setup"
            # ... actions ...
          - name: "Rule_B_Process"
            # ... actions ...
          - name: "Rule_C_Finalize"
            depends_on: # 依赖多个规则
              - "Rule_A_Setup"
              - "Rule_B_Process"
            actions:
              set:
                is_finalized: true
        ```

- **`content`** (字符串, 必需):
    - **用途**: 告诉工具这个规则集应该应用于输入 YAML 文件中的哪个顶级键下的数据。工具会自动查找输入文件中与此 `content` 值对应的复数形式键。
    - **示例**:
        - 如果 `content: "item"`，工具会寻找 `items:` 键下的数据。
        - 如果 `content: "block"`，工具会寻找 `blocks:` 键下的数据。
        - 如果 `content: "entity"`，工具会寻找 `entitys:` (或 `entities:`) 键下的数据。
    - **提示**: 确保你的输入 YAML 文件包含这个对应的顶级复数键，否则该规则集将被跳过。

- **`context`** (字典, 可选):
    - **这是实现高级动态转换的核心功能。**
    - **用途**: 在此可以定义一系列变量，这些变量可以在该内容规则集下的所有 `conditions` 和 `actions` 中被重用。变量可以是**静态值**，也可以是基于当前处理数据动态计算的[**表达式**](#4表达式语法详解)。
    - **工作原理**: 变量按顺序进行评估，这意味着后面的变量可以引用前面已经定义好的变量。
    - **示例**:
        ```yaml
        context:
          # 1. 静态变量
          texture_path_prefix: "magicmc:item/generated/"
          
          # 2. 基于表达式的动态变量
          #    从 'content_id' (如 'diamond_sword') 中提取 'material' ('diamond')
          material:
            expression: "content_id.split('_')[0]"
            default_value: "unknown" # 如果表达式失败，则使用此默认值
    
          # 3. 引用其他上下文变量的表达式
          #    组合前缀和上面提取的 material 来生成一个完整的纹理路径
          generated_texture_path:
            expression: "f'{texture_path_prefix}{material}.png'"
        ```

- **`rules`** (列表, 必需):
    - **用途**: 一个嵌套的列表，包含了针对此 `content` 类型数据的具体转换规则。每个元素都是一个具体的规则定义。

### 3. 具体转换规则：定义你的转换逻辑

每个具体的转换规则都定义了如何识别某个数据条目（例如一个具体的物品或方块）并对其执行一系列操作。

- **`name`** (字符串, 必需):
    - **用途**: 此规则的简明名称。它在调试模式下非常有用，能帮你理解具体是哪个规则在起作用。
    - **示例**: `"移除旧模型纹理和方块模型路径"`, `"为所有物品添加新标签"`

- **`conditions`** (列表, 可选):
    - **用途**: 定义一个条件列表。只有当所有列出的条件都满足时，该规则的 `actions` 部分才会被执行。如果省略，规则将始终应用。
    - **重要**: 多个条件之间是 **AND** 的关系，必须全部满足规则才会触发。
    - <details>
      <summary><strong> 点击展开：可用条件类型详解 </strong></summary>
    
      - **`path`** (字符串, 必需): 要检查的数据字段的路径，使用点号 `.` 分隔。
          - `示例: "model.path", "data.display-name"`
      - **`exists`** (布尔值, 可选): 检查路径指定的字段是否存在。
          - `示例: exists: true` (必须存在)
          - `示例: exists: false` (必须不存在)
      - **`value`** (任意类型, 可选): 要求字段值精确匹配。
          - `示例: value: "block_item"`
          - `示例: value: 123`
      - **`regex_match`** (字符串, 可选): 要求字符串字段值匹配正则表达式。
          - `示例: regex_match: "^magicmc:blocks/.*_top$"`
      - **`min`** (数字, 可选): 要求数字字段值大于或等于 `min`。
          - `示例: min: 1500`
      - **`max`** (数字, 可选): 要求数字字段值小于或等于 `max`。
          - `示例: max: 2500`
      </details>

- **`actions`** (字典, 必需):
    - **用途**: 当规则的 `conditions` 满足（或没有条件）时，要执行的操作集合。
    - **`skip`** (布尔值, 可选): 如果设置为 `true`，则此规则下的所有其他操作都将被忽略。这对于临时禁用规则进行调试非常方便。
        ```yaml
        actions:
          skip: true
        ```

#### 动作类型

你的转换工具支持以下多种动作类型，让你能够灵活地操纵数据结构：

- **`delete`** (列表, 可选):
    - **用途**: 清理不再需要的旧字段。
    - **工作原理**: 提供一个要删除的字段路径列表。
    - **示例**:
        ```yaml
        delete:
          - model.generation.textures # 删除 model.generation 下的 textures 字段
          - behavior.block.state.model.path # 删除 behavior.block.state 下的 model path 字段
        ```

- **`rename`** (字典, 可选):
    - **用途**: 更改字段的名称或在层级中移动字段。
    - **工作原理**: 提供一个“旧路径: 新路径”的映射。工具会将旧路径的值移动到新路径，并删除旧路径。
    - **示例**:
        ```yaml
        rename:
          old_nested.field: new_nested.field # 将 old_nested.field 重命名为 new_nested.field
          legacy_id: new_id # 将 legacy_id 重命名为 new_id
        ```

- **`set`** (字典, 可选):
    - **用途**: 修改现有字段的值、添加新字段、基于旧数据计算新数据。这是实现动态和自定义逻辑的核心。
    - **工作原理**: 提供一个“目标路径: 值”的映射。值可以是简单的静态值，也可以是功能强大的表达式。

    - **用法 1：静态值与简单占位符**
        - 直接提供字符串、数字或布尔值。为了向后兼容，您仍然可以在字符串中使用 `{content_id}` 和 `{content_type}` 这样的简单占位符。
        ```yaml
        set:
          is_enabled: true
          item_type: "generic_item"
          description: "这是物品 {content_id} 的描述。"
        ```

    - **用法 2：[表达式 (`expression`)](#4表达式语法详解)**
        - 这是**推荐**的动态转换方式。通过[表达式](#4表达式语法详解)，您可以访问原始数据、执行计算、调用函数以及实现条件逻辑，完全取代了旧的 `transform_func` 机制。
        ```yaml
        set:
          # 目标路径
          new_field:
            # 使用 'expression' 关键字来定义一个计算表达式
            expression: "'some_prefix_' + upper(data.display_name)"
            # (可选) 如果表达式计算失败，可以提供一个默认值
            default_value: "default_fallback_value"
        ```

- **`append`** (字典, 可选):
    - **用途**: 在现有列表的末尾追加新数据。
    - **工作原理**: 提供一个“目标列表路径: 要添加的元素”的映射。如果目标路径不存在，会自动创建新列表。如果目标路径存在但不是列表，操作将被跳过。
    - **示例**:
        ```yaml
        append:
          data.tags: # 在 data.tags 列表末尾添加
            - "new_tag_at_end_1"
            - "dynamic_tag_{content_id}" # 元素中支持占位符
          another_list: "single_element_to_add" # 也可以添加单个元素
        ```

- **`prepend`** (字典, 可选):
    - **用途**: 在现有列表的开头插入新数据。
    - **工作原理**: 提供一个“目标列表路径: 要添加的元素”的映射。如果目标路径不存在，会自动创建新列表。如果目标路径存在但不是列表，操作将被跳过。
    - **示例**:
        ```yaml
        prepend:
          data.tags: # 在 data.tags 列表开头添加
            - "new_tag_at_start_1"
            - "prefixed_tag_{content_type}" # 元素中支持占位符
          another_list: "another_single_element"
        ```

- **`sequence`** (字典, 可选):
    - **用途**: 为每个处理过的数据条目生成一个唯一的、连续的数字序列。常用于分配唯一的 `custom-model-data`。
    - **工作原理与转换模式**: `sequence` 具有两种工作模式：**独立模式 (默认)** 和 **共享模式 (可选)**。

        -   **独立序列 (默认行为)**
            -   **何时使用**: 当你不提供 `id` 字段时。
            -   **工作方式**: 每个序列的计数器都与其所在的**命名规则**和**目标路径**唯一绑定。这意味着，即使两个不同规则中的 `sequence` 操作修改的是同一个路径（例如 `display.slot`），它们也**不会**互相干扰，而是各自独立计数。
            -   **‼️ 重要**: 使用此默认模式时，包含 `sequence` 的规则**必须有一个 `name`**，否则转换器会报错并跳过该操作，以防止意外的序列冲突。

        -   **共享序列 (可选行为)**
            -   **何时使用**: 当你为 `sequence` 提供一个自定义的 `id` 字符串时。
            -   **工作方式**: 所有具有**相同 `id`** 的 `sequence` 操作将**共享同一个计数器**，无论它们位于哪个规则中或操作哪个目标路径。这对于实现一个跨越多个条件和规则的全局连续序列非常有用。

    - **配置参数**:
        - `id` (字符串, 可选): **序列的共享标识符**。提供此ID将启用**共享模式**。
        - `start` (整数, 可选, 默认为 0): 计数器的起始值。
        - `step` (整数, 可选, 默认为 1): 每次变化的步长，可为负数。
        - `format` (字符串, 可选): 一个模板字符串，`{counter}` 会被替换为当前的序列号。

    - **示例**:
        ```yaml
        rules:
          - name: "Assign_Global_CustomModelData"
            # 条件: 给所有可见物品分配
            conditions:
              - path: "is_visible"
                value: true
            actions:
              sequence:
                # --- 共享序列示例 ---
                # 为所有可见物品生成一个全局唯一的、连续的CMD
                stats.custom_model_data:
                  id: "global_cmd" # <-- 指定了共享ID
                  start: 1001
                  step: 1

          - name: "Assign_Tool_Specific_ID"
            # 条件: 只给工具类物品分配
            conditions:
              - path: "type"
                value: "tool"
            actions:
              sequence:
                # --- 独立序列示例 (默认) ---
                # 这个序列只在 "Assign_Tool_Specific_ID" 规则内部有效
                # 它的计数器与上面的 "global_cmd" 完全无关
                internal_tool_id:
                  start: 0
                  step: 1
                  format: "tool-id-{counter}"
        ```

### 4.表达式语法详解

**可用变量:**

-   `data`: 代表当前正在处理的**整个数据条目**的配置。你可以用它来读取任何原始字段。
    -   `示例: data.old_stats.level`
-   `content_id`: 当前数据条目的ID（例如 `diamond_sword`）。
-   `content_type`: 当前数据条目的类型（例如 `item`）。
-   **先前已定义的上下文变量**: 你可以直接按名称使用在当前变量之前已经定义好的任何 `context` 变量。
    -   `示例: 如果你先定义了 material，就可以在后续变量中直接使用 material`

**可用函数:**

-   `get(object, path_string, default_value)`: 一个安全的辅助函数，用于从对象（通常是 `data`）中获取深层嵌套的值。如果路径不存在，它会返回 `None` 或你提供的 `default_value`，而不是报错。
    -   `示例: get(data, 'stats.level', 0)` # 如果 stats.level 不存在，返回 0
-   **字符串操作**: `upper(s)`, `lower(s)`, `replace(s, old, new)`, `split(s, sep)`
-   **类型转换**: `str(x)`, `int(x)`, `float(x)`
-   **通用函数**: `len(x)`
-   **标准 Python 运算符**: 包括算术 (`+`, `-`), 逻辑 (`and`, `or`), 比较 (`==`, `>`), 以及三元运算符 (`value_if_true if condition else value_if_false`)。


### 5. 示例 `conversion_rules.yml`

这个综合示例展示了如何结合各种规则和动作来实现复杂的转换。

```yaml
rules:
  # ===================================================================
  # == 内容规则集 1: 针对 "item" 类型的转换
  # ===================================================================
  - name: "Minecraft 物品数据迁移 (v1 -> v2)"
    content: "item" # 此规则集应用于 YAML 文件中所有 'items' 开头的顶级键

    # -----------------------------------------------------------------
    # ✨ CONTEXT BLOCK: 定义可在此规则集中重用的动态变量
    # 变量按顺序评估，后面的可以引用前面的。
    # -----------------------------------------------------------------
    context:
      # 从 ID (如 'diamond_pickaxe') 提取材质 ('diamond')
      material:
        expression: "content_id.split('_')[0] if '_' in content_id else 'unknown'"
        default_value: "generic" # 表达式失败时的后备值

      # 从原始数据中安全地获取等级，如果不存在则默认为 0
      level:
        expression: "get(data, 'old_stats.level', 0)"

      # 基于 'level' 和 'material' 判断稀有度
      rarity:
        expression: >- # 使用 >- 保留换行符，便于阅读长表达式
          'Legendary' if level > 5 and material in ['diamond', 'netherite']
          else 'Rare' if level > 3
          else 'Common'

      # 判断是否为特殊物品 (布尔值)
      is_special:
        expression: "rarity != 'Common' or get(data, 'legacy_properties.is_quest_item', False)"

      # 组合其他上下文变量来生成一个新的显示名称
      new_display_name:
        expression: "f'[{rarity}] {material.replace('_', ' ').title()}'"

    # -----------------------------------------------------------------
    # 📜 RULES LIST: 针对 'item' 的具体转换规则
    # -----------------------------------------------------------------
    rules:
      - name: "Rule_A_Cleanup"
        # 无条件，首先对所有物品执行清理和重命名
        actions:
          delete:
            - legacy_properties # 删除整个旧的属性块
            - temp_notes      # 删除临时笔记字段
          rename:
            old_stats: stats # 将 'old_stats' 重命名为 'stats'

      - name: "Rule_B_SetCoreData"
        # 此规则依赖于前一个清理规则的完成
        depends_on: "Rule_A_Cleanup" 
        conditions:
          # 使用表达式作为条件，只有材质被成功识别的物品才会继续
          - "material != 'unknown'"
        actions:
          set:
            # 用法1: 使用 context 变量通过表达式设置值
            display_name:
              expression: "new_display_name"
            # 用法2: 静态值
            schema_version: "v2.0"
            is_migrated: true
            # 用法3: 使用简单占位符（仍然支持）
            description: "A {rarity} item made of {material}."
            # 用法4: 表达式计算失败时的后备值
            stats.attack_power:
              expression: "stats.damage * 1.5" # 如果 'stats.damage' 不存在，此表达式会失败
              default_value: 5 # 失败时，将 attack_power 设为 5

      - name: "Rule_C_HandleTagsAndLore"
        conditions:
          # 仅对被判定为 'special' 的物品执行
          - "is_special == True"
        actions:
          # 在列表末尾添加元素
          append:
            tags:
              - "special_edition"
              - "{rarity}" # 支持占位符
              - "migrated_item"
          # 在列表开头添加元素
          prepend:
            lore:
              - "This is a special item."
              - "Material: {material}, Level: {level}"

      - name: "Rule_D_GenerateUniqueIDs"
        # 无条件，为所有物品生成序列ID
        actions:
          sequence:
            # 示例: 经典的纯数字递增，用于 CustomModelData
            # 共享序列：为所有物品生成一个全局唯一的 CustomModelData
            stats.custom_model_data:
              id: "global_custom_model_data" # <-- 使用共享ID
              start: 50000
              step: 1
            # 独立序列：此序列的计数器仅在此规则("Rule_D_GenerateUniqueIDs")内部有效
            internal_id:
              start: 1
              step: 1
              format: 'item-v2-{counter}'

      - name: "Rule_E_DisabledExample"
        # 一个被临时禁用的规则，用于展示 'skip' 功能
        conditions:
          - "material == 'wood'"
        actions:
          skip: true # 因为此项为 true，下面的 delete 操作将不会执行
          delete:
            - stats.flammability

  # ===================================================================
  # == 内容规则集 2: 针对 "block" 类型的转换 (一个更简单的例子)
  # ===================================================================
  - name: "Minecraft 方块数据标准化"
    content: "block" # 此规则集应用于 'blocks' 键
    rules:
      - name: "StandardizeBlockProperties"
        # 无条件，应用于所有方块
        actions:
          set:
            # 直接在表达式中使用 content_id
            formatted_name:
              expression: "f'Block - {content_id.replace('_', ' ').title()}'"
          append:
            properties:
              - "is_solid"
              - "auto_generated"
```


