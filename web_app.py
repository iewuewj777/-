#!/usr/bin/env python3
"""
CSV比較ツール - Webアプリ版
ブラウザからCSVファイルをアップロードして比較できます
"""

from flask import Flask, render_template, request, jsonify
import csv
import io
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict
from werkzeug.exceptions import RequestEntityTooLarge

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return jsonify({'error': 'ファイルサイズが大きすぎます（最大50MB）'}), 413


@dataclass
class DiffResult:
    """比較結果を格納するクラス"""
    added_rows: List[Dict[str, Any]]
    deleted_rows: List[Dict[str, Any]]
    modified_rows: List[Dict[str, Any]]  # {old, new, changed_columns}
    unchanged_count: int
    headers1: List[str]
    headers2: List[str]
    key_column: str


def read_csv_content(content: str, encoding: str = 'utf-8') -> Tuple[List[str], List[Dict[str, Any]]]:
    """CSV文字列を読み込んでヘッダーと行データを返す"""
    reader = csv.DictReader(io.StringIO(content))
    headers = reader.fieldnames or []
    rows = list(reader)
    return headers, rows


def compare_csv(
    content1: str,
    content2: str,
    key_column: Optional[str] = None,
) -> DiffResult:
    """2つのCSV内容を比較して差分を返す"""

    headers1, rows1 = read_csv_content(content1)
    headers2, rows2 = read_csv_content(content2)

    # キー列が指定されていない場合は最初の列を使用
    if key_column is None or key_column == '':
        if headers1:
            key_column = headers1[0]
        else:
            raise ValueError("CSVファイルにヘッダーがありません")

    # キー列の存在確認
    if key_column not in headers1:
        raise ValueError(f"キー列 '{key_column}' がファイル1に存在しません")
    if key_column not in headers2:
        raise ValueError(f"キー列 '{key_column}' がファイル2に存在しません")

    # 辞書形式でインデックス化
    dict1 = {row[key_column]: row for row in rows1}
    dict2 = {row[key_column]: row for row in rows2}

    keys1 = set(dict1.keys())
    keys2 = set(dict2.keys())

    # 追加された行（file2にのみ存在）
    added_keys = keys2 - keys1
    added_rows = [dict2[k] for k in sorted(added_keys)]

    # 削除された行（file1にのみ存在）
    deleted_keys = keys1 - keys2
    deleted_rows = [dict1[k] for k in sorted(deleted_keys)]

    # 変更された行を検出
    common_keys = keys1 & keys2
    modified_rows = []
    unchanged_count = 0

    for key in sorted(common_keys):
        row1 = dict1[key]
        row2 = dict2[key]

        # 全列を比較
        changed_columns = []
        all_columns = set(row1.keys()) | set(row2.keys())

        for col in all_columns:
            val1 = row1.get(col, '')
            val2 = row2.get(col, '')
            if val1 != val2:
                changed_columns.append({
                    'column': col,
                    'old_value': val1,
                    'new_value': val2
                })

        if changed_columns:
            modified_rows.append({
                'key': key,
                'old': row1,
                'new': row2,
                'changed_columns': changed_columns
            })
        else:
            unchanged_count += 1

    return DiffResult(
        added_rows=added_rows,
        deleted_rows=deleted_rows,
        modified_rows=modified_rows,
        unchanged_count=unchanged_count,
        headers1=headers1,
        headers2=headers2,
        key_column=key_column
    )


@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')


@app.route('/compare', methods=['POST'])
def compare():
    """CSV比較APIエンドポイント"""
    try:
        file1 = request.files.get('file1')
        file2 = request.files.get('file2')
        key_column = request.form.get('key_column', '')
        max_display = int(request.form.get('max_display', '100'))

        if not file1 or not file2:
            return jsonify({'error': '2つのCSVファイルをアップロードしてください'}), 400

        # ファイル内容を読み込み
        try:
            content1 = file1.read().decode('utf-8')
        except UnicodeDecodeError:
            file1.seek(0)
            content1 = file1.read().decode('shift_jis')

        try:
            content2 = file2.read().decode('utf-8')
        except UnicodeDecodeError:
            file2.seek(0)
            content2 = file2.read().decode('shift_jis')

        # 比較実行
        result = compare_csv(content1, content2, key_column if key_column else None)

        # 表示件数を制限（レスポンスサイズ対策）
        result_dict = asdict(result)
        total_added = len(result_dict['added_rows'])
        total_deleted = len(result_dict['deleted_rows'])
        total_modified = len(result_dict['modified_rows'])

        result_dict['added_rows'] = result_dict['added_rows'][:max_display]
        result_dict['deleted_rows'] = result_dict['deleted_rows'][:max_display]
        result_dict['modified_rows'] = result_dict['modified_rows'][:max_display]
        result_dict['truncated'] = {
            'added': total_added > max_display,
            'deleted': total_deleted > max_display,
            'modified': total_modified > max_display,
            'total_added': total_added,
            'total_deleted': total_deleted,
            'total_modified': total_modified,
            'max_display': max_display
        }

        return jsonify({
            'success': True,
            'result': result_dict
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'エラーが発生しました: {str(e)}'}), 500


if __name__ == '__main__':
    print("CSV比較ツール Web版")
    print("ブラウザで http://localhost:5000 にアクセスしてください")
    app.run(debug=True, host='0.0.0.0', port=5000)
