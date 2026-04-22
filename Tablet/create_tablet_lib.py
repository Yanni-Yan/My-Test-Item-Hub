import json
import os
import shutil
import copy


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
                    with open(base_destination_path, "r", encoding="utf-8") as f_exist:
                        existing_module = json.load(f_exist)
                    existing_module_comparable = clean_for_comparison(
                        copy.deepcopy(existing_module)
                    )

                    if new_module_comparable == existing_module_comparable:
                        is_duplicate = True
                        print(f"模块 '{sanitized_file_name}' 已存在且内容相同，跳过。")

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
                    standardized_module = set_ids_to_zero(new_module_copy)
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


def set_ids_to_zero(obj):
    if isinstance(obj, dict):
        if "$id" in obj:
            obj["$id"] = "0"
        if "$ref" in obj:
            obj["$ref"] = "0"
        for value in obj.values():
            set_ids_to_zero(value)
    elif isinstance(obj, list):
        for item in obj:
            set_ids_to_zero(item)
    return obj


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "lib")

    print("--- 正在以增量模式更新 Tablet 库 ---")

    all_tablet_modules = {
        "../Hxxx PQR/HEELER_PQR_MODULE_001.tps": {
            "LDO Measurement": "LDO Measurements(10bits ADC)",
            "Create UID or check UID": "Read UID",
            "Write Module Fail Flag": "MODULE Fail Flag",
            "Check Communication Between Module MCU and PD Controller": "Get PDOs",
            "Check Communication with iPad": "ACC_DATA_SYS Check",
            "GPIO Outputs Test": "GPIO Test",
            "ADC Measurement": "Get ADC Voltages",
            "Write Module Pass Flag": "MODULE Pass Flag",
        },
        "../Hxxx PQR/HEELER_PQR_BON_001(With TP).tps": {
            "LDO Voltage Measurement": "LDO Measurement_SC_PWR",
            "CC1_CC2 Check": "Check CC1/CC2",
            "D+D- Check": "Check D+D-",
            "Module Pass Flag Check": "Read MODULE Flag",
            "Write BON Fail Flag": "BON Fail Flag",
            "Check FW Version": "Check FW Revision",
            "Check the OP_DISCHARGE Function": "Check OP_DISCHARGE",
            "Write BON Pass Flag": "BON Pass Flag",
        },
        "../Hxxx PQR/HEELER_PQR_NALA_001.tps": {
            "Record NALA UID": "Read UID",
            "BON Pass Flag Check": "Read BON Flag",
            "Write NALA Fail Flag": "NALA Fail Flag",
            "Nala Test - FW Revision": "Check FW Revision",
            "Nala Test - Tracking Test": "Tracking Test",
            "Nala Test - 5-Point Check": "Nala Touch 5-Points",
            "Nala Test - Click Function": "Nala Button Test",
            "I_Nala(mA)": "Nala Current Measurement",
            "Write NALA PASS Flag": "Nala Pass flag",
        },
        "../Hxxx PQR/HEELER_PQR_KEY-EU_001.tps": {
            "Scan 8L PN bar code_KEY": "Scan Barcode_PN",
            "Record KEY UID": "Read UID",
            "Nala Pass Flag Check": "Read NALA Flag",
            "Write KEY Fail Flag": "KEY Fail Flag",
            "Write Country Code": "Write Country Code",
            "Check & Set Manufacturer Name": "Check & Set Manufacturer Name",
            "Check & Set Marketing Name": "Check and Set Marketing Name",
            "Key Test": "KEY Test",
            "Write Key test PASS Flag": "Write Pass Flag",
        },
        "../Hxxx PQR/HEELER_PQR_RESISTANCE-EU_001.tps": {
            "Scan 8L PN&SN bar code_RESISTANCE": "Scan Barcode_PN",
            "ESD Path Resistance Measurement KBDFrame": "ESD Resistance_KBDFrame",
            "ESD Path Resistance Measurement TPFrame": "ESD Resistance_TPFrame",
            "ESD Path Resistance Measurement TPGND": "ESD Resistance_TPGND",
            "DCR measurement of the Source Path High": "DCR_PathH Measurement",
            "Record RESISTANCE UID": "Read UID",
            "Key Pass Flag Check": "Read KEY Flag",
            "Write Resistance Station Fail Flag": "RESISTANCE Fail Flag",
            "Check Country Code": "Check Country Code",
            "Write Resistance Station PASS Flag": "RESISTANCE Pass Flag",
            "I_DeepSleep@3.7V(uA)": "Set Power Deepsleep Mode",
        },
        "../Hxxx PQR/HEELER_PQR_BTM-MAGNET_001.tps": {
            "Test KBD bottom case magnets": "Magnet Measurement"
        },
        "../Hxxx PQR/HEELER_PQR_FT-EU_001.tps": {
            "All KBD Magnet Test": "Magnet Measurement",
            "All normal keys test": "KEY Test",
        },
        "../Hxxx PQR/HEELER_PQR_HG_001.tps": {
            "Scan 8L SN bar code": "Scan Barcode_SN",
            "Charging Test": "SC_PWR_Charging_CC1",
            "Hall Sensor Test": "Hall Sensor Test",
            "G Sensor Test": "G Sensor Test",
        },
        "../Hxxx PQR/HEELER_PQR_HOLDER-MAGNET_001.tps": {
            "Holder&Latch&Kickstand magnets test": "Magnet Measurement"
        },
    }

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    for tps_file, modules in all_tablet_modules.items():
        tps_full_path = os.path.join(script_dir, tps_file)
        create_library_from_tps(tps_full_path, output_dir, modules)

    print("\nTablet 库重建完成。")


if __name__ == "__main__":
    main()
