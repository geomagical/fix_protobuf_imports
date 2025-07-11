#!/usr/bin/python3

import os
import re
import sys
from typing import Tuple
from pathlib import Path

if sys.version_info >= (3, 8):
    from typing import TypedDict# pylint: disable=no-name-in-module
else:
    from typing_extensions import TypedDict

import click


class ProtobufFilePathInfo(TypedDict):
    dir: Path
    path: Path
    rel_path: Path


@click.command()
@click.option("--dry", is_flag=True, show_default=True, default=False, help="Do not write out the changes to the files.")
@click.argument("root_dir", type=click.Path(exists=True))
def fix_protobuf_imports(root_dir, dry):
    """
      A script to fix relative imports (from and to nested sub-directories) within compiled `*_pb2.py` Protobuf files.
    """

    root_dir = Path(root_dir)

    def generate_lookup(path: Path) -> Tuple[str, ProtobufFilePathInfo]:
        rel_path = path.relative_to(root_dir)
        name = str(rel_path).split('.')[0].replace('/', '.')
        directory = path.parent.relative_to(root_dir)

        return (name, {"dir": directory, "path": path, "rel_path": rel_path})

    py_files = list(root_dir.glob("**/*_pb2.py"))
    pyi_files = list(root_dir.glob("**/*_pb2.pyi"))
    grpc_files = list(root_dir.glob("**/*_pb2_grpc.py"))

    py_files_dictionary = {}
    for path in py_files:
        name, info = generate_lookup(path)
        py_files_dictionary[name] = info

    pyi_files_dictionary = {}
    for path in pyi_files:
        name, info = generate_lookup(path)
        pyi_files_dictionary[name] = info

    grpc_files_dictionary = {}
    for path in grpc_files:
        name, info = generate_lookup(path)
        grpc_files_dictionary[name] = info

    def fix_protobuf_import_in_line(
        original_line, referencing_info: ProtobufFilePathInfo, pyi=False
    ) -> str:
        line = original_line

        if pyi:
            m = re.search(r"^import\s([^\s\.]*_pb2)$", line)
        else:
            m = re.search(r"^import\s(\S*_pb2)\sas\s(.*)$", line)

        if m is not None:
            referenced_name = m.group(1)
            if pyi:
                referenced_alias = None
            else:
                referenced_alias = m.group(2)

            referenced_directory = py_files_dictionary[referenced_name]["dir"]
            relative_path_to_referenced_module = os.path.relpath(
                referenced_directory, referencing_info["dir"]
            )

            uppath_levels = relative_path_to_referenced_module.count("..")

            original_line = line.replace("\n", "")

            downpath = (
                relative_path_to_referenced_module.split("..")[-1]
                .replace("/", ".")
                .replace("\\", ".")
            )
            if referenced_alias:
                line = f'from .{"." * uppath_levels}{downpath if downpath != "." else ""} import {referenced_name} as {referenced_alias}\n'
            else:
                line = f'from .{"." * uppath_levels}{downpath if downpath != "." else ""} import {referenced_name}\n'

            new_line = line.replace("\n", "")

            print(f'{referencing_info["rel_path"]}: "{original_line}" -> "{new_line}"')
        else:
            m = re.search(r"^from\s([^\s\.]+[\S]*)\simport\s(.*_pb2)$", line)

            if m is not None:
                import_path = m.group(1).replace(".", "/")

                referenced_directory = root_dir / import_path

                if referenced_directory.exists():
                    relative_path_to_root = os.path.relpath(
                        root_dir, referencing_info["dir"]
                    )

                    uppath_levels = relative_path_to_root.count("..")

                    original_line = line.replace("\n", "")

                    line = (
                        f'from .{"." * uppath_levels}{m.group(1)} import {m.group(2)}\n'
                    )

                    new_line = line.replace("\n", "")

                    print(
                        f'{referencing_info["rel_path"]}: "{original_line}" -> "{new_line}"'
                    )

        return line

    def fix_protobuf_imports_in_file(name, info: ProtobufFilePathInfo, pyi=False):
        with open(info["path"], "r+" if not dry else "r") as f:
            lines = f.readlines()
            if not dry:
                f.seek(0)

            for line in lines:
                line = fix_protobuf_import_in_line(line, info, pyi)

                if not dry:
                    f.writelines([line])

            if not dry:
                f.truncate()
            f.close()

    for (name, info) in py_files_dictionary.items():
        fix_protobuf_imports_in_file(name, info)

    for (
        name,
        info,
    ) in pyi_files_dictionary.items():
        fix_protobuf_imports_in_file(name, info, pyi=True)

    for (
        name,
        info,
    ) in grpc_files_dictionary.items():
        fix_protobuf_imports_in_file(name, info)

def main():
    fix_protobuf_imports()

if __name__ == "__main__":
    main()
