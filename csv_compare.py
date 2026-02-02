#!/usr/bin/env python3
"""
CSV比較ツール - 2つのCSVファイルの差分を検出して表示します

使用方法:
    python csv_compare.py file1.csv file2.csv [オプション]

オプション:
    --key COLUMN    比較のキーとなる列名を指定（デフォルト: 最初の列）
    --encoding ENC  ファイルのエンコーディング（デフォルト: utf-8）
    --output FILE   結果をファイルに出力
    --no-color      カラー出力を無効化
"""

import csv
import argparse
import sys
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass


# ANSIカラーコード
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


@dataclass
class DiffResult:
    """比較結果を格納するクラス"""
    added_rows: List[Dict[str, Any]]
    deleted_rows: List[Dict[str, Any]]
    modified_rows: List[Tuple[Dict[str, Any], Dict[str, Any], List[str]]]
    unchanged_count: int
    headers1: List[str]
    headers2: List[str]


def read_csv(filepath: str, encoding: str = 'utf-8') -> Tuple[List[str], List[Dict[str, Any]]]:
    """CSVファイルを読み込んでヘッダーと行データを返す"""
    try:
        with open(filepath, 'r', encoding=encoding, newline='') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
            return headers, rows
    except FileNotFoundError:
        print(f"エラー: ファイル '{filepath}' が見つかりません", file=sys.stderr)
        sys.exit(1)
    except UnicodeDecodeError:
        print(f"エラー: ファイル '{filepath}' のエンコーディングが正しくありません", file=sys.stderr)
        print(f"       --encoding オプションで正しいエンコーディングを指定してください", file=sys.stderr)
        sys.exit(1)


def compare_csv(
    file1: str,
    file2: str,
    key_column: Optional[str] = None,
    encoding: str = 'utf-8'
) -> DiffResult:
    """2つのCSVファイルを比較して差分を返す"""

    headers1, rows1 = read_csv(file1, encoding)
    headers2, rows2 = read_csv(file2, encoding)

    # キー列が指定されていない場合は最初の列を使用
    if key_column is None:
        if headers1:
            key_column = headers1[0]
        else:
            print("エラー: CSVファイルにヘッダーがありません", file=sys.stderr)
            sys.exit(1)

    # キー列の存在確認
    if key_column not in headers1:
        print(f"エラー: キー列 '{key_column}' がファイル1に存在しません", file=sys.stderr)
        sys.exit(1)
    if key_column not in headers2:
        print(f"エラー: キー列 '{key_column}' がファイル2に存在しません", file=sys.stderr)
        sys.exit(1)

    # 辞書形式でインデックス化
    dict1 = {row[key_column]: row for row in rows1}
    dict2 = {row[key_column]: row for row in rows2}

    keys1 = set(dict1.keys())
    keys2 = set(dict2.keys())

    # 追加された行（file2にのみ存在）
    added_keys = keys2 - keys1
    added_rows = [dict2[k] for k in added_keys]

    # 削除された行（file1にのみ存在）
    deleted_keys = keys1 - keys2
    deleted_rows = [dict1[k] for k in deleted_keys]

    # 変更された行を検出
    common_keys = keys1 & keys2
    modified_rows = []
    unchanged_count = 0

    for key in common_keys:
        row1 = dict1[key]
        row2 = dict2[key]

        # 全列を比較
        changed_columns = []
        all_columns = set(row1.keys()) | set(row2.keys())

        for col in all_columns:
            val1 = row1.get(col, '')
            val2 = row2.get(col, '')
            if val1 != val2:
                changed_columns.append(col)

        if changed_columns:
            modified_rows.append((row1, row2, changed_columns))
        else:
            unchanged_count += 1

    return DiffResult(
        added_rows=added_rows,
        deleted_rows=deleted_rows,
        modified_rows=modified_rows,
        unchanged_count=unchanged_count,
        headers1=headers1,
        headers2=headers2
    )


def format_row(row: Dict[str, Any], headers: List[str]) -> str:
    """行を整形して文字列として返す"""
    values = [str(row.get(h, '')) for h in headers]
    return ', '.join(f"{h}: {v}" for h, v in zip(headers, values))


def print_diff(result: DiffResult, use_color: bool = True, output_file: Optional[str] = None):
    """比較結果を表示する"""

    lines = []

    def add_line(text: str = ''):
        lines.append(text)

    def colorize(text: str, color: str) -> str:
        if use_color:
            return f"{color}{text}{Colors.RESET}"
        return text

    # サマリー
    add_line(colorize("=" * 60, Colors.BOLD))
    add_line(colorize("CSV比較結果", Colors.BOLD))
    add_line(colorize("=" * 60, Colors.BOLD))
    add_line()

    total_changes = len(result.added_rows) + len(result.deleted_rows) + len(result.modified_rows)
    add_line(f"追加された行: {colorize(str(len(result.added_rows)), Colors.GREEN)}")
    add_line(f"削除された行: {colorize(str(len(result.deleted_rows)), Colors.RED)}")
    add_line(f"変更された行: {colorize(str(len(result.modified_rows)), Colors.YELLOW)}")
    add_line(f"変更なしの行: {result.unchanged_count}")
    add_line()

    if total_changes == 0:
        add_line(colorize("差分はありません", Colors.GREEN))
    else:
        # ヘッダーの差分
        headers_diff = set(result.headers1) ^ set(result.headers2)
        if headers_diff:
            add_line(colorize("-" * 40, Colors.BLUE))
            add_line(colorize("ヘッダーの差分:", Colors.BLUE))
            only_in_1 = set(result.headers1) - set(result.headers2)
            only_in_2 = set(result.headers2) - set(result.headers1)
            if only_in_1:
                add_line(f"  ファイル1のみ: {', '.join(only_in_1)}")
            if only_in_2:
                add_line(f"  ファイル2のみ: {', '.join(only_in_2)}")
            add_line()

        # 追加された行
        if result.added_rows:
            add_line(colorize("-" * 40, Colors.GREEN))
            add_line(colorize("追加された行:", Colors.GREEN))
            for row in result.added_rows:
                add_line(colorize(f"  + {format_row(row, result.headers2)}", Colors.GREEN))
            add_line()

        # 削除された行
        if result.deleted_rows:
            add_line(colorize("-" * 40, Colors.RED))
            add_line(colorize("削除された行:", Colors.RED))
            for row in result.deleted_rows:
                add_line(colorize(f"  - {format_row(row, result.headers1)}", Colors.RED))
            add_line()

        # 変更された行
        if result.modified_rows:
            add_line(colorize("-" * 40, Colors.YELLOW))
            add_line(colorize("変更された行:", Colors.YELLOW))
            for old_row, new_row, changed_cols in result.modified_rows:
                key_col = result.headers1[0] if result.headers1 else ''
                key_val = old_row.get(key_col, '')
                add_line(colorize(f"  キー: {key_col}={key_val}", Colors.YELLOW))
                for col in changed_cols:
                    old_val = old_row.get(col, '(なし)')
                    new_val = new_row.get(col, '(なし)')
                    add_line(f"    {col}: {colorize(str(old_val), Colors.RED)} → {colorize(str(new_val), Colors.GREEN)}")
                add_line()

    # 出力
    output = '\n'.join(lines)

    if output_file:
        # ファイルに出力する場合はカラーコードを除去
        clean_output = output
        for color_attr in [Colors.RED, Colors.GREEN, Colors.YELLOW, Colors.BLUE, Colors.RESET, Colors.BOLD]:
            clean_output = clean_output.replace(color_attr, '')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(clean_output)
        print(f"結果を '{output_file}' に保存しました")
    else:
        print(output)


def main():
    parser = argparse.ArgumentParser(
        description='2つのCSVファイルを比較して差分を表示します',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  %(prog)s old.csv new.csv
  %(prog)s old.csv new.csv --key id
  %(prog)s old.csv new.csv --encoding shift_jis
  %(prog)s old.csv new.csv --output diff.txt
        '''
    )

    parser.add_argument('file1', help='比較元のCSVファイル')
    parser.add_argument('file2', help='比較先のCSVファイル')
    parser.add_argument('--key', '-k', dest='key_column',
                        help='比較のキーとなる列名（デフォルト: 最初の列）')
    parser.add_argument('--encoding', '-e', default='utf-8',
                        help='ファイルのエンコーディング（デフォルト: utf-8）')
    parser.add_argument('--output', '-o', dest='output_file',
                        help='結果を指定したファイルに出力')
    parser.add_argument('--no-color', action='store_true',
                        help='カラー出力を無効化')

    args = parser.parse_args()

    # 比較実行
    result = compare_csv(
        args.file1,
        args.file2,
        key_column=args.key_column,
        encoding=args.encoding
    )

    # 結果表示
    use_color = not args.no_color and sys.stdout.isatty()
    print_diff(result, use_color=use_color, output_file=args.output_file)

    # 差分がある場合は終了コード1を返す
    if result.added_rows or result.deleted_rows or result.modified_rows:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
