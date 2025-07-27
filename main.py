import argparse
import logging
import os
from typing import List, Dict

import yaml
from colorama import Fore, Style

from src.converter import convert_single_file, convert_multiple_files
from src.logger_config import setup_logging


def parse_sequence_overrides(overrides: List[str]) -> Dict[str, int]:
    """解析命令行传入的序列覆盖值。"""
    parsed_overrides = {}
    for override in overrides:
        if ':' not in override:
            logging.warning(f"警告: 无效的序列覆盖格式 '{override}'，应为 'path:value'。已跳过。")
            continue
        path, value_str = override.rsplit(':', 1)
        try:
            value = int(value_str)
            parsed_overrides[path] = value
        except ValueError:
            logging.warning(f"警告: 无效的序列起始值 '{value_str}'，必须是整数。已跳过。")
    return parsed_overrides


def get_yaml_files_in_directory(directory: str) -> List[str]:
    """获取指定目录下所有 .yml 和 .yaml 文件。"""
    yaml_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith((".yml", ".yaml")):
                yaml_files.append(os.path.join(root, file))
    return sorted(yaml_files)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"{Fore.BLUE}{Style.BRIGHT}YAML 物品配置转换工具{Style.RESET_ALL}\n"
        f"{Fore.MAGENTA}  🚀 快速、可配置、现代化 YAML 数据转换 CLI{Style.RESET_ALL}",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        help=f"{Fore.CYAN}旧版物品配置文件路径 或 包含旧版文件的目录路径。{Style.RESET_ALL}\n"
        f"  必须指定输入文件或目录。{Style.RESET_ALL}",
    )
    parser.add_argument(
        "-r",
        "--rules",
        type=str,
        required=True,
        help=f"{Fore.MAGENTA}转换规则文件路径 (例如: conversion_rules.yml){Style.RESET_ALL}",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help=f"{Fore.YELLOW}新版配置文件输出路径。{Style.RESET_ALL}\n"
        f"  如果输入是单个文件，这是输出文件路径 (默认: converted_items.yml)。{Style.RESET_ALL}\n"
        f"  如果输入是目录，这是输出目录 (默认: 'converted_output/').{Style.RESET_ALL}",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help=f"{Fore.GREEN}启用批量转换模式。如果输入是目录，将转换目录下所有文件。{Style.RESET_ALL}",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=f"{Fore.BLUE}启用调试模式，显示详细日志信息。{Style.RESET_ALL}",
    )
    parser.add_argument(
        "--sequence-start",
        nargs='*',
        help=f"{Fore.YELLOW}覆盖规则文件中序列字段的起始值。{Style.RESET_ALL}\n"
        f"  格式: --sequence-start path1:value1 path2:value2\n"
        f"  示例: --sequence-start custom-model-data:50000\n"
        f"  注意: 此参数会覆盖 rules 文件中为该路径定义的 start 值。{Style.RESET_ALL}",
        default=[]
    )

    args = parser.parse_args()

    setup_logging(debug_mode=args.debug)
    logger = logging.getLogger('YAMLConverter')

    logger.debug(f"{Fore.CYAN}✨ YAML 物品配置转换工具 v1.0.0{Style.RESET_ALL}")
    logger.debug(f"➜ 规则: {args.rules}")
    if args.debug:
        logger.info(f"{Fore.BLUE}🔧 调试模式已启用。{Style.RESET_ALL}")

    if not os.path.exists(args.rules):
        logger.error(f"✖️ 错误: 规则文件 '{args.rules}' 不存在。")
        return
    # 规则文件格式校验
    try:
        with open(args.rules, 'r', encoding='utf-8') as f:
            rules_data = yaml.safe_load(f)
        if not isinstance(rules_data, dict) or 'rules' not in rules_data:
            logger.error(f"✖️ 错误: 规则文件 '{args.rules}' 格式不正确，缺少 'rules' 键。")
            return
        rules_list = rules_data['rules']
    except Exception as e:
        logger.error(f"✖️ 错误: 解析规则文件 '{args.rules}' 失败: {e}")
        return

    # --- 文件/目录处理逻辑 ---
    input_paths = []
    output_path = args.output

    if args.input:  # 用户指定了输入路径
        if os.path.isfile(args.input):
            input_paths.append(args.input)
            if args.batch:
                logger.warning(
                    f"{Fore.YELLOW}警告: 指定了单个文件 '{args.input}' 但同时启用了 --batch 模式。将仅转换此单个文件。{Style.RESET_ALL}"
                )
            if not output_path:
                output_path = "converted_items.yml"
            elif os.path.isdir(
                output_path
            ):  # 如果指定了输出目录但输入是文件，则将文件放入目录
                if not os.path.exists(output_path):
                    os.makedirs(output_path, exist_ok=True)
                base_name = os.path.basename(args.input)
                out_file = os.path.join(output_path, base_name)
                # 防止覆盖
                if os.path.abspath(args.input) == os.path.abspath(out_file):
                    name, ext = os.path.splitext(base_name)
                    out_file = os.path.join(output_path, f"{name}_converted{ext}")
                output_path = out_file
            else:
                # 如果输出路径是文件，检查是否和输入文件相同，防止覆盖
                if os.path.abspath(args.input) == os.path.abspath(output_path):
                    name, ext = os.path.splitext(os.path.basename(output_path))
                    output_path = os.path.join(os.path.dirname(output_path), f"{name}_converted{ext}")

        elif os.path.isdir(args.input):
            if not args.batch:
                logger.warning(
                    f"{Fore.YELLOW}警告: 指定了输入目录 '{args.input}' 但未启用 --batch 模式。将仅处理此目录中的第一个文件。{Style.RESET_ALL}"
                )
                # 简单处理，只取第一个文件
                first_file = get_yaml_files_in_directory(args.input)
                if first_file:
                    input_paths.append(first_file[0])
                    if not output_path:
                        output_path = "converted_items.yml"  # 默认为单文件输出
                    elif os.path.isdir(output_path):
                        if not os.path.exists(output_path):
                            os.makedirs(output_path, exist_ok=True)
                        base_name = os.path.basename(first_file[0])
                        out_file = os.path.join(output_path, base_name)
                        # 防止覆盖
                        if os.path.abspath(first_file[0]) == os.path.abspath(out_file):
                            name, ext = os.path.splitext(base_name)
                            out_file = os.path.join(output_path, f"{name}_converted{ext}")
                        output_path = out_file
                    else:
                        # 如果输出路径是文件，检查是否和输入文件相同，防止覆盖
                        if os.path.abspath(first_file[0]) == os.path.abspath(output_path):
                            name, ext = os.path.splitext(os.path.basename(output_path))
                            output_path = os.path.join(os.path.dirname(output_path), f"{name}_converted{ext}")
                else:
                    logger.error(
                        f"✖️ 错误: 目录 '{args.input}' 中没有找到 .yml 或 .yaml 文件。"
                    )
                    return
            else:  # 批量模式且指定了目录
                input_paths = get_yaml_files_in_directory(args.input)
                if not input_paths:
                    logger.error(
                        f"✖️ 错误: 目录 '{args.input}' 中没有找到 .yml 或 .yaml 文件。"
                    )
                    return
                if not output_path:
                    output_path = "converted_output"  # 批量模式默认输出目录
                if not os.path.exists(output_path):
                    os.makedirs(output_path, exist_ok=True)
                elif not os.path.isdir(output_path):
                    logger.error(
                        f"✖️ 错误: 批量转换模式下，输出路径 '{output_path}' 必须是一个目录。"
                    )
                    return
        else:
            logger.error(
                f"✖️ 错误: 输入路径 '{args.input}' 不存在或不是有效的文件/目录。"
            )
            return

    else:  # 用户未指定输入路径
        logger.error(
            f"✖️ 错误: 未指定输入文件/目录。请指定 -i 参数。"
        )
        return

    logger.debug(f"➜ 输入: {args.input if args.input else '未指定'}")
    logger.debug(f"➜ 输出: {output_path}")

    # --- 执行转换 ---
    sequence_overrides = parse_sequence_overrides(args.sequence_start)
    if sequence_overrides:
        logger.info(f"{Fore.YELLOW}🔧 检测到命令行序列起始值覆盖: {sequence_overrides}{Style.RESET_ALL}")

    if len(input_paths) == 1 and not args.batch:  # 单文件模式
        convert_single_file(
            input_paths[0],
            rules_list,
            output_path,
            sequence_overrides=sequence_overrides
        )
    elif len(input_paths) > 0 and args.batch:  # 批量模式
        convert_multiple_files(input_paths, os.path.abspath(args.rules), output_path, sequence_overrides=sequence_overrides)
    else:
        logger.warning(f"🤔 未执行任何转换操作。请检查输入参数。")

    logger.info(f"{Fore.GREEN}🎉 转换过程成功结束。{Style.RESET_ALL}")


if __name__ == "__main__":
    main()