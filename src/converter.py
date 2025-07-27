import copy
import logging
import os
import re
from typing import List, Tuple, Optional, Dict, Any

import yaml
from asteval import Interpreter
from colorama import Fore, Style
from tqdm import tqdm

from src.utils import get_nested_value, set_nested_value, delete_nested_value, evaluate_condition, process_placeholders

logger = logging.getLogger('YAMLConverter')

def process_dynamic_context(context_definitions: Dict[str, Any], content_config: dict, base_context: dict, logger: logging.Logger) -> Dict[str, Any]:
    """
    处理规则文件中用户定义的 `context` 块。

    Args:
        context_definitions (Dict[str, Any]): 从规则文件中读取的上下文定义。
        content_config (dict): 当前正在处理的内容项的配置。
        base_context (dict): 包含 'content_id' 和 'content_type' 的基础上下文。
        logger (logging.Logger): 日志记录器实例。

    Returns:
        Dict[str, Any]: 包含所有已解析变量的最终上下文。
    """
    # 从基础上下文开始 (content_id, content_type)
    final_context = base_context.copy()
    
    aeval = Interpreter(no_print=True)
    # 用于上下文评估的符号表
    aeval.symtable.update({
        "get": get_nested_value,
        "str": str,
        "int": int,
        "float": float,
        "len": len,
        "data": content_config,
    })

    # 按顺序处理定义，以允许后续变量引用前面的变量
    for var_name, var_config in context_definitions.items():
        # 在每次迭代时更新符号表中的 'context'，
        # 这样表达式就可以通过 `context['var']` 引用已定义的上下文变量。
        aeval.symtable['context'] = final_context

        final_value = None
        if isinstance(var_config, dict) and 'expression' in var_config:
            expression = var_config['expression']
            try:
                final_value = aeval.eval(expression)
                logger.debug(f"      上下文变量 '{var_name}' 的计算结果为: {final_value}")
            except Exception as e:
                logger.error(f"      ✖️ 上下文变量 '{var_name}' 的表达式评估失败: {e}")
                if 'default_value' in var_config:
                    final_value = var_config['default_value']
                    logger.warning(f"        已为 '{var_name}' 使用默认值: {final_value}")
                else:
                    continue  # 如果失败则跳过此变量
        else:
            # 处理静态值
            final_value = var_config

        final_context[var_name] = final_value

    return final_context

def apply_actions(content_config: dict, actions: dict, context: dict, sequence_counters: dict, rule_name: str, sequence_overrides: Optional[Dict[str, int]] = None) -> None:
    """
    应用规则中的操作。
    content_config: 当前正在转换的内容（例如一个物品或一个方块的配置）
    actions: 来自规则的动作字典
    context: 已解析的上下文
    sequence_counters: 存储所有序列计数器的字典
    rule_name: 当前正在执行的规则名称，用于创建隔离的序列计数器。
    sequence_overrides: 命令行覆盖
    """

    if actions.get('skip', False):
        logger.debug(f"    规则动作包含 'skip: true'，跳过所有操作。")
        return
    
    if 'delete' in actions:
        processed_delete_paths = process_placeholders(actions['delete'], context)
        logger.debug(f"    正在执行删除操作: {processed_delete_paths}")
        for path_to_delete in processed_delete_paths:
            delete_nested_value(content_config, path_to_delete)
            logger.debug(f"      已删除字段: {path_to_delete}")

    if 'rename' in actions:
        processed_rename_map = process_placeholders(actions['rename'], context)
        logger.debug(f"    正在执行重命名操作: {processed_rename_map}")
        for old_path, new_path in processed_rename_map.items():
            value = get_nested_value(content_config, old_path)
            if value is not None:
                set_nested_value(content_config, new_path, value)
                delete_nested_value(content_config, old_path)
                logger.debug(f"      已重命名字段: {old_path} -> {new_path}")
            else:
                logger.debug(f"      字段 '{old_path}' 不存在，跳过重命名。")

    if 'set' in actions:
        processed_set_map = process_placeholders(actions['set'], context)
        logger.debug(f"    正在执行设置/添加操作: {processed_set_map}")
        for path, value_config in processed_set_map.items():
            final_value = None
            
            if isinstance(value_config, dict) and 'expression' in value_config:
                expression = value_config['expression']
                logger.debug(f"      路径 '{path}': 正在评估表达式...")
                
                aeval = Interpreter(no_print=True)
                aeval.symtable.update({
                    "upper": str.upper,
                    "lower": str.lower,
                    "replace": lambda s, old, new: str(s).replace(old, new),
                    "split": lambda s, sep: str(s).split(sep),
                    "str": str,
                    "int": int,
                    "float": float,
                    "len": len,
                    "data": content_config, 
                    "get": get_nested_value,
                })
                aeval.symtable.update(context)
                
                try:
                    final_value = aeval.eval(expression)
                    logger.debug(f"        表达式 '{expression}' 的计算结果为: {final_value}")
                except Exception as e:
                    logger.error(f"        ✖️ 路径 '{path}' 的表达式评估失败: {e}")
                    if 'default_value' in value_config:
                        final_value = value_config['default_value']
                        logger.warning(f"        已使用提供的默认值: {final_value}")
                    else:
                        continue 
            else:
                final_value = value_config

            set_nested_value(content_config, path, final_value)
            logger.debug(f"      已设置字段 '{path}'。")

    if 'append' in actions:
        processed_append_map = process_placeholders(actions['append'], context)
        logger.debug(f"    正在执行 append 操作: {processed_append_map}")
        for path, elements_to_add in processed_append_map.items():
            current_list = get_nested_value(content_config, path)

            if current_list is None:
                current_list = []
                set_nested_value(content_config, path, current_list)
                logger.debug(f"        路径 '{path}' 不存在，已创建新列表。")
            elif not isinstance(current_list, list):
                logger.warning(f"        警告: 路径 '{path}' 的值不是列表，无法执行 append 操作。跳过。")
                continue

            elements_to_add = elements_to_add if isinstance(elements_to_add, list) else [elements_to_add]
            current_list.extend(elements_to_add)
            logger.debug(f"        已向 '{path}' 列表末尾添加元素。")


    if 'prepend' in actions:
        processed_prepend_map = process_placeholders(actions['prepend'], context)
        logger.debug(f"    正在执行 prepend 操作: {processed_prepend_map}")
        for path, elements_to_add in processed_prepend_map.items():
            current_list = get_nested_value(content_config, path)

            if current_list is None:
                current_list = []
                set_nested_value(content_config, path, current_list)
                logger.debug(f"        路径 '{path}' 不存在，已创建新列表。")
            elif not isinstance(current_list, list):
                logger.warning(f"        警告: 路径 '{path}' 的值不是列表，无法执行 prepend 操作。跳过。")
                continue
            
            elements_to_add = elements_to_add if isinstance(elements_to_add, list) else [elements_to_add]
            current_list[:0] = elements_to_add
            logger.debug(f"        已向 '{path}' 列表开头添加元素。")


    if 'sequence' in actions:
        processed_sequence_map = process_placeholders(actions['sequence'], context)
        logger.debug(f"    正在执行 sequence 操作: {processed_sequence_map}")
        for path, sequence_info in processed_sequence_map.items():
            
            sequence_id = sequence_info.get('id')
            
            if sequence_id:
                # 模式：共享。键是用户提供的 'id'。
                counter_key = f"shared_id_{sequence_id}"
                logger.debug(f"      序列 '{path}' 使用共享ID '{sequence_id}'。")
            else:
                # 模式：隔离 (默认)。键是规则名称和路径的组合。
                if rule_name == 'Unnamed Rule':
                    logger.error(f"      ✖️ 错误: 路径 '{path}' 的 sequence 操作位于一个未命名的规则中，并且没有提供 'id'。")
                    logger.error(f"        为了确保序列不互相干扰，请为该规则命名或为 sequence 提供一个 'id'。")
                    continue
                counter_key = (rule_name, path)
                logger.debug(f"      序列 '{path}' 在规则 '{rule_name}' 内是独立的。")

            start_value = sequence_info.get('start', 0)
            step_value = sequence_info.get('step', 1)
            format_string = sequence_info.get('format')

            if counter_key not in sequence_counters:
                initial_value = start_value
                override_key = sequence_id if sequence_id else path
                if sequence_overrides and override_key in sequence_overrides:
                    initial_value = sequence_overrides[override_key]
                    logger.debug(f"      序列 '{override_key}' 的起始值被命令行覆盖为 {initial_value}")
                sequence_counters[counter_key] = initial_value

            current_value = sequence_counters[counter_key]
            final_value_to_set = None

            if format_string and isinstance(format_string, str):
                final_value_to_set = format_string.replace('{counter}', str(current_value))
                logger.debug(f"      字段 '{path}' 已使用格式 '{format_string}' 和上下文解析为 '{final_value_to_set}'")
            else:
                final_value_to_set = current_value
                logger.debug(f"      字段 '{path}' 已设置为 {current_value} (下一次递增/减 {step_value})")

            set_nested_value(content_config, path, final_value_to_set)
            sequence_counters[counter_key] += step_value
            

def convert_single_file(old_config_path: str, rules_list: list, new_config_path: str, sequence_overrides: Dict[str, int] = None) -> Tuple[bool, Optional[dict]]:
    """
    转换单个 YAML 文件。
    rules_list: 从 rules 文件中解析出来的整个 rules 列表
    """
    logger.debug(f"加载中: 旧配置文件 '{old_config_path}'")
    try:
        with open(old_config_path, 'r', encoding='utf-8') as f:
            old_data = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"✖️ 错误: 旧配置文件 '{old_config_path}' 未找到。")
        return False, None
    except yaml.YAMLError as e:
        logger.error(f"✖️ 错误: 解析旧配置文件 '{old_config_path}' 失败: {e}")
        return False, None

    new_data = {}
    sequence_counters = {}

    total_items = 0
    for top_level_rule in rules_list:
        content_type = top_level_rule.get('content')
        if not content_type:
            continue
        content_key_base = f"{content_type}s" if not content_type.endswith('s') else content_type
        matching_keys = [k for k in old_data if re.match(f"^{re.escape(content_key_base)}\d*$", k)]
        for content_key in matching_keys:
            total_items += len(old_data.get(content_key, {}))

    with tqdm(total=total_items, 
              desc=f"📦 {os.path.basename(old_config_path)}", 
              unit=" item", 
              colour="green", 
              leave=False) as pbar:
        for top_level_rule in rules_list:
            content_type = top_level_rule.get('content')
            nested_rules = top_level_rule.get('rules', [])
            
            dynamic_context_definitions = top_level_rule.get('context', {})

            if not content_type:
                logger.warning(
                    f"警告: 顶层规则 '{top_level_rule.get('name', 'Unnamed Top Rule')}' 缺少 'content' 字段，跳过。")
                continue

            content_key_base = f"{content_type}s" if not content_type.endswith('s') else content_type
            matching_keys = [k for k in old_data if re.match(f"^{re.escape(content_key_base)}\d*$", k)]

            if not matching_keys:
                continue

            for content_key in matching_keys:
                contents_to_process = old_data.get(content_key, {})
                if not contents_to_process:
                    new_data[content_key] = {}
                    continue

                new_data[content_key] = {}

                for content_id, content_config_old in contents_to_process.items():
                    pbar.set_postfix_str(f"当前: {content_id}", refresh=True)
                    
                    logger.debug(f"--- 正在处理 '{content_type}' 内容: {content_id} ---")
                    content_config_new = copy.deepcopy(content_config_old)
                    executed_rules_for_item = set()
                    
                    # 1. 创建基础上下文
                    base_context = {
                        'content_id': content_id,
                        'content_type': content_type
                    }

                    # 2. 调用新函数处理用户定义的上下文
                    logger.debug(f"  正在处理用户定义的上下文...")
                    final_context = process_dynamic_context(dynamic_context_definitions, content_config_new, base_context, logger)
                    logger.debug(f"  最终上下文: {final_context}")

                    for rule in nested_rules:
                        rule_name = rule.get('name', 'Unnamed Rule')
                        rule_actions = rule.get('actions', {})

                        # 检查前置运行条件 (depends_on)
                        dependencies = rule.get('depends_on')
                        if dependencies:
                            if isinstance(dependencies, str):
                                dependencies = [dependencies]
                            
                            missing_deps = [dep for dep in dependencies if dep not in executed_rules_for_item]

                            if missing_deps:
                                logger.debug(f"  > 规则 '{rule_name}' 的前置条件 {missing_deps} 未满足，跳过此规则。")
                                continue

                        if rule_actions.get('skip', False):
                            logger.debug(f"  > 规则 '{rule_name}' 的动作包含 'skip: true'，跳过此规则。")
                            continue

                        conditions_met = True
                        logger.debug(f"  > 评估规则: '{rule_name}'")
                        if 'conditions' in rule:
                            for condition in rule['conditions']:
                                # 修正了对 evaluate_condition 的调用，现在它是正确的
                                if not evaluate_condition(content_config_new, condition, final_context, logger):
                                    conditions_met = False
                                    logger.debug(f"    规则 '{rule_name}' 的条件未满足，跳过。")
                                    break

                        if conditions_met:
                            logger.debug(f"  > 规则 '{rule_name}' 的所有条件均满足，正在应用操作...")
                            apply_actions(content_config_new, rule_actions, final_context, sequence_counters, rule_name, sequence_overrides)
                            # 增加检查，确保规则有名称时才添加
                            if rule.get('name'):
                                executed_rules_for_item.add(rule.get('name'))
                        else:
                            logger.debug(f"  > 规则 '{rule_name}' 的条件未满足，跳过此规则。")

                    new_data[content_key][content_id] = content_config_new
                    pbar.update(1)

    logger.debug(f"保存中: 新配置文件 '{new_config_path}'")
    try:
        with open(new_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(new_data, f, indent=2, sort_keys=False, allow_unicode=True)
        logger.debug(f"完成: 新配置文件 '{new_config_path}' 已成功保存。")
        return True, new_data
    except IOError as e:
        logger.error(f"✖️ 错误: 保存新配置文件 '{new_config_path}' 失败: {e}")
        return False, None


def convert_multiple_files(input_files: List[str], rules_config_path: str, output_dir: str, sequence_overrides: Dict[str, int] = None) -> None:
    """
    批量转换多个 YAML 文件。
    """
    logger.info(f"{Fore.CYAN}⚙️ 加载中: 转换规则 '{rules_config_path}'{Style.RESET_ALL}")
    try:
        with open(rules_config_path, 'r', encoding='utf-8') as f:
            rules_config = yaml.safe_load(f)
            if not isinstance(rules_config, dict) or 'rules' not in rules_config:
                logger.error(f"✖️ 错误: 转换规则文件 '{rules_config_path}' 格式不正确，缺少 'rules' 键。")
                return
            rules_list = rules_config.get('rules', [])
    except FileNotFoundError:
        logger.error(f"✖️ 错误: 转换规则文件 '{rules_config_path}' 未找到。")
        return
    except yaml.YAMLError as e:
        logger.error(f"✖️ 错误: 解析转换规则文件 '{rules_config_path}' 失败: {e}")
        return

    os.makedirs(output_dir, exist_ok=True)

    successful_conversions = 0
    total_files = len(input_files)

    logger.info(f"{Fore.GREEN}➜ 开始批量转换 {total_files} 个文件到 '{output_dir}'。{Style.RESET_ALL}")

    with tqdm(total=total_files, desc="🚀 批量转换", unit="file", colour="cyan", leave=True) as pbar:
        for input_file in input_files:
            base_name = os.path.basename(input_file)
            pbar.set_postfix_str(f"处理中: {base_name}", refresh=True)

            output_file = os.path.join(output_dir, base_name)
            if os.path.abspath(input_file) == os.path.abspath(output_file):
                name, ext = os.path.splitext(base_name)
                output_file = os.path.join(output_dir, f"{name}_converted{ext}")

            success, _ = convert_single_file(input_file, rules_list, output_file, sequence_overrides=sequence_overrides)
            if success:
                successful_conversions += 1
            else:
                logger.error(f"✖️ 文件 '{base_name}' 转换失败。")

            pbar.update(1)

    logger.info(
        f"{Fore.GREEN}🎉 批量转换完成。成功转换 {successful_conversions}/{total_files} 个文件。{Style.RESET_ALL}")