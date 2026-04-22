import json
import os
import shutil
import copy
import argparse


def clean_for_comparison(obj):
    """
    Recursively remove keys like 'ErrorCode' for logical comparison.
    Also standardizes all IDs to '0' for comparison purposes.
    """
    if isinstance(obj, dict):
        if "$id" in obj:
            obj["$id"] = "0"
        if "$ref" in obj:
            obj["$ref"] = "0"

        keys_to_remove = ["ErrorCode"]
        for key in keys_to_remove:
            if key in obj:
                del obj[key]

        for key, value in list(obj.items()):
            clean_for_comparison(value)

    elif isinstance(obj, list):
        for item in obj:
            clean_for_comparison(item)
    return obj


def find_module_by_label(children, label):
    for item in children:
        if (
            item.get("Label") == label
            and item.get("$type") == "UTS2._0.TestGroup, UTS2.0"
        ):
            return item
        if "Children" in item:
            found = find_module_by_label(item["Children"], label)
            if found:
                return found
    return None


def create_library_from_tps(tps_path, output_dir, module_labels, is_incremental=True):
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"已创建目录: {output_dir}")

        with open(tps_path, "r", encoding="utf-8") as f:
            content_lines = f.readlines()
            json_start_index = next(
                (i for i, line in enumerate(content_lines) if line.strip() == "{"), -1
            )

            if json_start_index == -1:
                return
            json_content = "".join(content_lines[json_start_index:])
            data = json.loads(json_content)

        test_items_section = next(
            (g for g in data.get("TestGroups", []) if g.get("Label") == "Test Items"),
            None,
        )
        if not test_items_section:
            return

        for file_name, label in module_labels.items():
            # Sanitize the file_name to replace characters that are invalid in file paths
            sanitized_file_name = file_name.replace("/", "_").replace("\\", "_")

            module_to_extract = find_module_by_label(
                test_items_section.get("Children", []), label
            )

            if module_to_extract:
                new_module_copy = copy.deepcopy(module_to_extract)
                new_module_comparable = clean_for_comparison(
                    copy.deepcopy(new_module_copy)
                )

                base_destination_path = os.path.join(
                    output_dir, f"{sanitized_file_name}.json"
                )

                is_duplicate = False
                path_to_save = base_destination_path

                if is_incremental and os.path.exists(base_destination_path):
                    # Check base file
                    with open(base_destination_path, "r", encoding="utf-8") as f_exist:
                        existing_module = json.load(f_exist)
                    existing_module_comparable = clean_for_comparison(
                        copy.deepcopy(existing_module)
                    )

                    if new_module_comparable == existing_module_comparable:
                        is_duplicate = True
                        print(f"模块 '{sanitized_file_name}' 已存在且内容相同，跳过。")

                    # If not a duplicate of base, check suffixed files
                    if not is_duplicate:
                        counter = 1
                        while True:
                            suffixed_path = os.path.join(
                                output_dir, f"{sanitized_file_name}_{counter}.json"
                            )
                            if not os.path.exists(suffixed_path):
                                path_to_save = suffixed_path
                                break

                            with open(suffixed_path, "r", encoding="utf-8") as f_exist:
                                existing_module = json.load(f_exist)
                            existing_module_comparable = clean_for_comparison(
                                copy.deepcopy(existing_module)
                            )

                            if new_module_comparable == existing_module_comparable:
                                is_duplicate = True
                                print(
                                    f"模块 '{sanitized_file_name}' 的一个版本已存在，跳过。"
                                )
                                break
                            counter += 1

                if not is_duplicate:
                    standardized_module = set_ids_to_null(new_module_copy)
                    standardized_module["Parent"] = None
                    with open(path_to_save, "w", encoding="utf-8") as out_f:
                        json.dump(standardized_module, out_f, indent=2)
                    print(
                        f"成功保存新模块版本 '{os.path.basename(path_to_save)}' 到 {output_dir}"
                    )

            else:
                print(f"警告: 在 {tps_path} 中未找到标签为 '{label}' 的模块。")

    except Exception as e:
        print(f"发生意外错误: {e}")


def set_ids_to_null(obj):
    if isinstance(obj, dict):
        if "$id" in obj:
            obj["$id"] = None
        if "$ref" in obj:
            obj["$ref"] = None
        for value in obj.values():
            set_ids_to_null(value)
    elif isinstance(obj, list):
        for item in obj:
            set_ids_to_null(item)
    return obj


def main():
    parser = argparse.ArgumentParser(
        description="Extracts test modules from a .tps file and updates the library."
    )
    parser.add_argument("tps_file", type=str, help="Path to the source .tps file.")
    parser.add_argument(
        "product", type=str, help="Product type (e.g., Keyboard, Mouse, Tablet)."
    )
    parser.add_argument(
        "--modules",
        type=str,
        required=True,
        help='JSON string or path to a JSON file of the module labels to extract. Format: \'{"FileName1": "Label1", "FileName2": "Label2"}\'',
    )
    args = parser.parse_args()

    try:
        # Check if the --modules argument is a path to an existing file
        if os.path.exists(args.modules):
            with open(args.modules, 'r', encoding='utf-8') as f:
                module_labels = json.load(f)
        else:
            # Otherwise, treat it as a JSON string
            try:
                module_labels = json.loads(args.modules)
            except json.JSONDecodeError:
                print(f"错误: --modules 参数不是有效的JSON字符串或文件路径。内容: {args.modules}")
                return
    except (json.JSONDecodeError, IOError) as e:
        print(f"错误: --modules 参数无效。它必须是有效的 JSON 字符串或指向有效 JSON 文件的路径。错误: {e}")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming the script is in a product-specific folder, go up one level to find the parent directory.
    product_base_dir = os.path.dirname(script_dir)
    output_dir = os.path.join(product_base_dir, args.product, "lib")

    print(f"--- 正在以增量模式更新 {args.product} 库 ---")
    print(f"--- 目标文件: {args.tps_file} ---")

    create_library_from_tps(args.tps_file, output_dir, module_labels)

    print(f"\n{args.product} 库增量更新完成。")


if __name__ == "__main__":
    main()
