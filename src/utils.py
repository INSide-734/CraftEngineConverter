import re
from typing import Any, Dict
import yaml


def process_placeholders(value: Any, context: Dict[str, Any]) -> Any:
    """
    递归处理值中的占位符，支持字符串、列表和字典。
    """
    if isinstance(value, str):
        processed_str = value
        for key, val in context.items():
            processed_str = processed_str.replace(f"{{{key}}}", str(val))
        if processed_str != value:
            try:
                return yaml.safe_load(processed_str)
            except yaml.YAMLError:
                return processed_str
        return value
    elif isinstance(value, list):
        return [process_placeholders(item, context) for item in value]
    elif isinstance(value, dict):
        return {process_placeholders(k, context): process_placeholders(v, context) for k, v in value.items()}
    return value

def get_nested_value(data: dict, path: str) -> Any:
    """
    根据点分隔的路径获取嵌套字典中的值。

    Args:
        data (dict): 要查询的字典。
        path (str): 点分隔的路径字符串，例如 "behavior.block.state.id"。

    Returns:
        any: 路径对应的值，如果路径不存在则返回 None。
    """
    parts = path.split('.')
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current

def set_nested_value(data: dict, path: str, value: Any) -> None:
    """
    根据点分隔的路径设置或创建嵌套字典中的值。
    如果路径中的某些层级不存在，会自动创建字典。

    Args:
        data (dict): 要修改的字典。
        path (str): 点分隔的路径字符串。
        value (any): 要设置的值。
    """
    parts = path.split('.')
    current = data
    for i, part in enumerate(parts):
        if i == len(parts) - 1: # 最后一个部分是我们要设置的键
            current[part] = value
        else: # 中间层级，确保是字典
            if part not in current or not isinstance(current[part], dict):
                current[part] = {} # 如果不存在或不是字典，则创建一个新字典
            current = current[part]

def delete_nested_value(data: dict, path: str) -> None:
    """
    根据点分隔的路径删除嵌套字典中的值。
    如果路径不存在，不会引发错误。

    Args:
        data (dict): 要修改的字典。
        path (str): 点分隔的路径字符串。
    """
    parts = path.split('.')
    current = data
    # 遍历到倒数第二个部分，以便能够删除最后一个键
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            if isinstance(current, dict) and part in current:
                del current[part]
            return # 删除成功或路径不存在，直接返回
        else:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return # 路径不存在，无需删除

def evaluate_condition(item_config: dict, condition: dict, context: dict, current_logger) -> bool:
    """
    评估单个转换规则条件。

    Args:
        item_config (dict): 当前正在处理的物品配置字典。
        condition (dict): 单个条件规则字典 (可能包含占位符)。
        context (dict): 包含额外上下文信息的字典，用于解析占位符。
        current_logger (logging.Logger): 用于日志输出的logger实例。

    Returns:
        bool: 如果条件满足则返回 True，否则返回 False。
    """
    # 首先，使用上下文处理条件中的占位符
    processed_condition = process_placeholders(condition, context)

    path = processed_condition.get('path')
    if not path:
        current_logger.warning(f"规则中的条件缺少 'path' 字段: {processed_condition}")
        return False

    value_at_path = get_nested_value(item_config, path)
    current_logger.debug(f"  - 评估条件 '{path}': 当前值 '{value_at_path}'")

    # 1. 检查 'exists' (字段是否存在)
    if 'exists' in processed_condition:
        if processed_condition['exists'] is True and value_at_path is None:
            current_logger.debug(f"    - 条件 '{path}' exists: True 未满足 (值为 None)")
            return False
        if processed_condition['exists'] is False and value_at_path is not None:
            current_logger.debug(f"    - 条件 '{path}' exists: False 未满足 (值不为 None)")
            return False
        current_logger.debug(f"    - 条件 '{path}' exists: {processed_condition['exists']} 满足")

    # 如果字段不存在，并且条件要求检查值、正则表达式或范围，则不满足
    # 但如果 exists: False 已经匹配，则此处不应阻断
    if value_at_path is None and ('value' in processed_condition or 'regex_match' in processed_condition or 'min' in processed_condition or 'max' in processed_condition):
        current_logger.debug(f"    - 条件 '{path}' 要求检查值但路径不存在。")
        return False


    # 2. 检查 'value' (字段值是否相等)
    if 'value' in processed_condition:
        if value_at_path != processed_condition['value']:
            current_logger.debug(f"    - 条件 '{path}' value: '{processed_condition['value']}' 未满足 (实际值: '{value_at_path}')")
            return False
        current_logger.debug(f"    - 条件 '{path}' value: '{processed_condition['value']}' 满足")

    # 3. 检查 'regex_match' (正则表达式匹配)
    if 'regex_match' in processed_condition:
        if not isinstance(value_at_path, str):
            current_logger.debug(f"    - 条件 '{path}' regex_match 未满足 (值不是字符串: {type(value_at_path)})")
            return False # 只有字符串才能进行正则表达式匹配
        if not re.match(processed_condition['regex_match'], value_at_path):
            current_logger.debug(f"    - 条件 '{path}' regex_match: '{processed_condition['regex_match']}' 未满足 (实际值: '{value_at_path}')")
            return False
        current_logger.debug(f"    - 条件 '{path}' regex_match: '{processed_condition['regex_match']}' 满足")

    # 4. 检查 'min'/'max' (数字范围)
    if 'min' in processed_condition or 'max' in processed_condition:
        if not isinstance(value_at_path, (int, float)):
            current_logger.debug(f"    - 条件 '{path}' min/max 未满足 (值不是数字: {type(value_at_path)})")
            return False # 只有数字才能进行范围检查
        if 'min' in processed_condition and value_at_path < processed_condition['min']:
            current_logger.debug(f"    - 条件 '{path}' min: '{processed_condition['min']}' 未满足 (实际值: '{value_at_path}')")
            return False
        if 'max' in processed_condition and value_at_path > processed_condition['max']:
            current_logger.debug(f"    - 条件 '{path}' max: '{processed_condition['max']}' 未满足 (实际值: '{value_at_path}')")
            return False
        current_logger.debug(f"    - 条件 '{path}' min/max 满足")

    return True # 所有检查都通过