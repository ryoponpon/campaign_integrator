from flask import Flask, request, render_template, send_file, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
import os
import pandas as pd
import tempfile
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
import logging
import re
from flask_cors import CORS  # 先頭に追加

# Flask アプリケーションの設定
app = Flask(__name__)
CORS(app)  # CORSを有効化

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask アプリケーションの設定
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

# 一時ディレクトリの設定
UPLOAD_FOLDER = tempfile.mkdtemp()
OUTPUT_FOLDER = tempfile.mkdtemp()

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    OUTPUT_FOLDER=OUTPUT_FOLDER,
    MAX_CONTENT_LENGTH=32 * 1024 * 1024,  # 32MB
    TEMPLATES_AUTO_RELOAD=True
)

ALLOWED_EXTENSIONS = {'csv'}
executor = ThreadPoolExecutor(max_workers=4)

def allowed_file(filename):
    """許可されたファイル拡張子かチェック"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_filename(filename):
    """ファイル名から不適切な文字を除去"""
    invalid_chars = '<>:"/\\|?*\0'
    clean_name = ''.join(c for c in filename if c not in invalid_chars)
    return clean_name.strip()

def clean_campaign_name(campaign_name):
    """キャンペーン名から先頭の数字と全角/半角スラッシュを削除"""
    if pd.isna(campaign_name):
        return campaign_name
    
    # 文字列に変換
    campaign_name = str(campaign_name)
    
    # パターン: 数字や全角/半角スラッシュを含むプレフィックスを削除
    patterns = [
        r'^\d+[/／]',          # 数字 + 全角/半角スラッシュ
        r'^\d+\s*[/／]',       # 数字 + 任意の空白 + 全角/半角スラッシュ
        r'^[\d\s/／]+',        # 数字、空白、全角/半角スラッシュの組み合わせ
        r'^[/／]+',            # 連続する全角/半角スラッシュ
        r'^\d+[/／]\d+[/／]',  # 数字 + スラッシュ + 数字 + スラッシュ
    ]
    
    cleaned = campaign_name
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned)
    
    # さらに残っている可能性のある全角/半角スラッシュを削除
    cleaned = re.sub(r'^[/／]+', '', cleaned)
    
    # 前後の空白を削除
    cleaned = cleaned.strip()
    
    return cleaned

def process_file(filepath, original_filename):
    """CSVファイルを処理"""
    try:
        # CSVファイルの読み込み
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        # キャンペーン名のカラムを探す
        campaign_columns = [col for col in df.columns if 'キャンペーン' in col]
        if not campaign_columns:
            raise ValueError("キャンペーン名を含むカラムが見つかりません")
        
        campaign_col = campaign_columns[0]
        
        # キャンペーン名の清掃
        df[campaign_col] = df[campaign_col].apply(clean_campaign_name)
        
        # 結果を一時ファイルとして保存
        output_filename = f"cleaned_{sanitize_filename(original_filename)}"
        output_filepath = os.path.join(app.config["OUTPUT_FOLDER"], output_filename)
        
        # 結果をCSVとして保存
        df.to_csv(output_filepath, encoding='utf-8-sig', index=False)
        
        return output_filename

    except Exception as e:
        logger.error(f"ファイル処理エラー: {str(e)}", exc_info=True)
        return None

@app.route("/")
def index():
    """メインページの表示"""
    return render_template("index.html")

@app.route('/upload', methods=['POST'])
def upload_file():
    """ファイルアップロード処理"""
    if 'files[]' not in request.files:
        return jsonify({'error': 'ファイルがありません'}), 400
    
    files = request.files.getlist('files[]')
    uploaded_files = []
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(sanitize_filename(file.filename))
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            uploaded_files.append(filename)
    
    return jsonify({
        'success': True,
        'files': uploaded_files
    })

@app.route('/process', methods=['POST'])
def process_files():
    """アップロードされたファイルの処理"""
    filenames = request.json.get('files', [])
    output_files = []
    
    for filename in filenames:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            future = executor.submit(process_file, filepath, filename)
            output_files.append(future)
    
    results = []
    for future in output_files:
        try:
            result = future.result()
            if result:
                results.append(result)
        except Exception as e:
            logger.error(f"処理エラー: {str(e)}", exc_info=True)

    session['output_files'] = results
    
    return jsonify({
        'success': True,
        'redirect': url_for('complete')
    })

@app.route("/complete")
def complete():
    """完了ページの表示"""
    output_files = session.get('output_files', [])
    return render_template("complete.html", output_files=output_files)

@app.route("/download/<path:filename>")
def download_file(filename):
    """ファイルダウンロード処理"""
    try:
        filepath = os.path.join(app.config["OUTPUT_FOLDER"], filename)
        if not os.path.exists(filepath):
            return "ファイルが見つかりません", 404

        response = send_file(
            filepath,
            as_attachment=True,
            mimetype='text/csv;charset=utf-8',
            download_name=filename
        )
        
        response.headers["Content-Disposition"] = \
            f"attachment; filename*=UTF-8''{quote(filename)}"
        
        return response

    except Exception as e:
        logger.error(f"ダウンロードエラー: {str(e)}", exc_info=True)
        return "ダウンロードに失敗しました", 500

def cleanup_files():
    """一時ファイルのクリーンアップ"""
    for folder in [app.config["UPLOAD_FOLDER"], app.config["OUTPUT_FOLDER"]]:
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"ファイル削除エラー: {str(e)}", exc_info=True)

@app.errorhandler(413)
def request_entity_too_large(error):
    """ファイルサイズ超過エラーのハンドリング"""
    return jsonify({'error': 'ファイルサイズが大きすぎます'}), 413

if __name__ == "__main__":
    app.run(debug=True)