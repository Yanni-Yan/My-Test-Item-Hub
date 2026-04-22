import json
import os
import copy


def set_ids_to_null(obj):
    """
    Recursively traverses the object and sets all '$id' and '$ref' values to None.
    """
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


def find_module_in_library(library_base_path, item_name, used_files):
    """
    Searches for a module, handling numbered suffixes for duplicates.
    """
    module_filename = f"{item_name}.json"
    module_path = os.path.join(library_base_path, module_filename)

    if module_path not in used_files and os.path.exists(module_path):
        used_files.add(module_path)
        return module_path

    for i in range(1, 20):
        suffixed_filename = f"{item_name}_{i}.json"
        suffixed_path = os.path.join(library_base_path, suffixed_filename)
        if suffixed_path not in used_files and os.path.exists(suffixed_path):
            used_files.add(suffixed_path)
            return suffixed_path

    return None


def generate_tps(base_tps_path, library_base_path, test_item_names, output_filename):
    """
    Generates a new .tps file by assembling modules from a flat library structure.
    """
    try:
        with open(base_tps_path, "r", encoding="utf-8") as f:
            content = f.readlines()
            json_start_index = next(
                (i for i, line in enumerate(content) if line.strip() == "{"), -1
            )
            if json_start_index == -1:
                print(f"Error: Could not find JSON start in {base_tps_path}")
                return
            base_data = json.loads("".join(content[json_start_index:]))

        initialization_section = copy.deepcopy(
            next(
                (
                    g
                    for g in base_data["TestGroups"]
                    if g.get("Label") == "Initialization"
                ),
                None,
            )
        )
        post_items_section = copy.deepcopy(
            next(
                (g for g in base_data["TestGroups"] if g.get("Label") == "Post Items"),
                None,
            )
        )
        termination_section = copy.deepcopy(
            next(
                (g for g in base_data["TestGroups"] if g.get("Label") == "Termination"),
                None,
            )
        )
        function_section = copy.deepcopy(
            next(
                (g for g in base_data["TestGroups"] if g.get("Label") == "Function"),
                None,
            )
        )

        if not all([initialization_section, post_items_section, termination_section]):
            print("Error: Base TPS file is missing required sections.")
            return

        new_test_items = {
            "$type": "UTS2._0.TestGroup, UTS2.0",
            "Name": "",
            "Children": [],
            "Label": "Test Items",
            "Description": "",
            "Status": 0,
            "BackupStatus": 0,
            "Parent": None,
            "Section": 1,
        }

        used_module_files = set()

        for item_name in test_item_names:
            module_path = find_module_in_library(
                library_base_path, item_name, used_module_files
            )
            if module_path:
                with open(module_path, "r", encoding="utf-8") as mf:
                    module_data = json.load(mf)
                    new_test_items["Children"].append(copy.deepcopy(module_data))
            else:
                print(
                    f"Warning: Module '{item_name}' not found or already used in '{library_base_path}'. Skipping."
                )

        final_tps_data = {
            "TestGroups": [
                initialization_section,
                new_test_items,
                post_items_section,
                termination_section,
            ]
        }
        if function_section:
            final_tps_data["TestGroups"].append(function_section)

        set_ids_to_null(final_tps_data)

        with open(output_filename, "w", encoding="utf-8") as out_f:
            json.dump(final_tps_data, out_f, indent=2)

        print(f"Successfully generated new TPS file with null IDs: {output_filename}")

    except Exception as e:
        print(f"An error occurred during TPS generation: {e}")


def main():
    tablet_test_items = [
        "LDO Measurement",
        "Create UID or check UID",
        "Check Module FW Version",
        "Read UID",
        "Nala Test - Tracking Test",
        "Key Test",
        "Hall Sensor Test",
        "G Sensor Test",
        "Write Pass Flag",
    ]

    generate_tps(
        base_tps_path="../Hxxx PQR/HEELER_PQR_MODULE_001.tps",
        library_base_path="lib",
        test_item_names=tablet_test_items,
        output_filename="../Generated_Tablet_Test_flat.tps",
    )


if __name__ == "__main__":
    main()
