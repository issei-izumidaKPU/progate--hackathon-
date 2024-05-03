import os
import openai
from flask import Flask, request, abort, render_template
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage ,ImageMessage, AudioMessage, FollowEvent
from google.cloud import storage
from google.oauth2 import service_account

app = Flask(__name__)
from dotenv import load_dotenv
load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY
# Google Cloud Storageの設
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
# 環境変数から認証情報を取得
credentials_dict = {
    "type": os.getenv("TYPE"),
    "project_id": os.getenv("PROJECT_ID"),
    "private_key_id": os.getenv("PRIVATE_KEY_ID"),
    "private_key": os.getenv("PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.getenv("CLIENT_EMAIL"),
    "client_id": os.getenv("CLIENT_ID"),
    "auth_uri": os.getenv("AUTH_URI"),
    "token_uri": os.getenv("TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL"),
    "universe_domain": os.getenv("UNIVERSE_DOMAIN")
}

credentials = service_account.Credentials.from_service_account_info(credentials_dict)
user_status = "INITIAL"
# Google Cloud Storageクライアントを初期化
storage_client = storage.Client(credentials=credentials, project=credentials.project_id)
bucket = storage_client.bucket(GCS_BUCKET_NAME)

@app.route("/")
def hello_world():
    return "Hello, World!"

@app.route("/transcribe")
def transcribe():
    return render_template("transcribe.html")


@app.route("/line/login", methods=["GET"])
def line_login():
    # 認可コードを取得する
    request_code = request.args["code"]
    



@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

@app.route("/test-gcs")
def test_gcs_connection():
    test_file_name = "test/gcs_test.txt"
    test_data = "これはテストデータです。"

    try:
        # テストファイルをバケットに書き込み
        blob = bucket.blob(test_file_name)
        blob.upload_from_string(test_data)
        app.logger.info(f"ファイル '{test_file_name}' をバケット '{GCS_BUCKET_NAME}' に書き込みました。")

        # テストファイルをバケットから読み込み
        blob = bucket.blob(test_file_name)
        data = blob.download_as_text()
        app.logger.info(f"ファイル '{test_file_name}' から読み込んだデータ: {data}")

        if data == test_data:
            return f"バケット '{GCS_BUCKET_NAME}' への書き込みおよび読み込みテストに成功しました。"
        else:
            return f"バケット '{GCS_BUCKET_NAME}' のデータ整合性エラー。", 500

    except Exception as e:
        app.logger.error(f"バケット '{GCS_BUCKET_NAME}' への接続に失敗しました: {e}")
        return f"バケットへの接続に失敗しました: {e}", 500

@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id  # ユーザーのIDを取得

    # GCSのバケット内にユーザー専用のフォルダを作成
    user_folder = f"{user_id}/"
    user_history_folder = f"{user_id}/history/"
    user_images_folder = f"{user_id}/images/"
    user_audio_folder = f"{user_id}/audio/"
    folders = [user_history_folder, user_images_folder, user_audio_folder]
    for folder in folders:
        bucket.blob(folder).upload_from_string('')  # 空のファイルでフォルダを作成

    # ユーザーに歓迎メッセージを送信
    welcome_message = "ようこそ！私たちのサービスへ。以下のようなことができます："
    line_bot_api.push_message(user_id, TextSendMessage(text=welcome_message))

    # 履歴管理用のテキストファイルを作成
    history_file_path = f"{user_history_folder}interaction_history.txt"
    initial_history_content = "ユーザーとのインタラクション履歴:\n"
    bucket.blob(history_file_path).upload_from_string(initial_history_content)

    # ユーザーにサービスの説明を送信
    service_description = "こちらで写真や音声の保存が可能です。また、質問に答えることでより良いサービスを提供します。"
    line_bot_api.push_message(user_id, TextSendMessage(text=service_description))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text  # ユーザーからのメッセージを取得
    user_id = event.source.user_id  # ユーザーのIDを取得
    if user_status != "INITIAL":
        line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="初期状態ではありません。")  # 正しいレスポンスの取得方法
        )
    else: 
        # OpenAI APIを使用してレスポンスを生成
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # モデルの指定
            messages=[{"role": "system", "content": "You are an assistant skilled in programming, general knowledge, and tool usage advice. You provide helpful information for tasks in Line.And You must return messages in japanese."},  # システムメッセージの設定
                    {"role": "user", "content": user_message}],  # ユーザーメッセー
            max_tokens=250          # 生成するトークンの最大数
        )
        res = f"あなたのユーザーIDは{user_id}です。\n"
        res += response.choices[0].message['content'].strip()
        # ユーザーのIDとメッセージをGoogle Cloud Storageに保存
        blob = bucket.blob(f"{user_id}/{user_message}.txt")
        blob.upload_from_string(res)
        # LINEユーザーにレスポンスを返信
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=res)  # 正しいレスポンスの取得方法
        )

@handler.add(MessageEvent, message=AudioMessage)
def handle_audio(event):
    user_id = event.source.user_id  # ユーザーのIDを取得
    message_id = event.message.id  # メッセージのIDを取得

    # LINEから音声コンテンツを取得
    message_content = line_bot_api.get_message_content(message_id)
    audio_bytes = b''
    for chunk in message_content.iter_content():
        audio_bytes += chunk

    # 音声ファイルをGCSに保存
    file_path = f"{user_id}/{message_id}.m4a"  # 一意のファイル名
    blob = bucket.blob(file_path)
    blob.upload_from_string(audio_bytes, content_type='audio/m4a')

    # 音声ファイルをOpenAI APIに送信してテキストに変換
    with open("audio.m4a", "wb") as f:
        f.write(audio_bytes)

    audio_file = open("audio.m4a", "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)

    # 変換されたテキストを使用してレスポンスを生成
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # モデルの指定
        messages=[
            {"role": "system", "content": "You are an assistant skilled in programming, general knowledge, and tool usage advice. You provide helpful information for tasks in Line. And You must return messages in japanese."},  # システムメッセージの設定
            {"role": "user", "content": transcript["text"]},  # 変換されたテキストをユーザーメッセージとして使用
        ],
        max_tokens=250  # 生成するトークンの最大数
    )

    res = f"あなたのユーザーIDは{user_id}です。\n"
    res += response.choices[0].message['content'].strip()

    # ユーザーのIDとメッセージをGoogle Cloud Storageに保存
    blob = bucket.blob(f"{user_id}/{message_id}.txt")
    blob.upload_from_string(res)

    # LINEユーザーにレスポンスを返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=res)
    )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id  # ユーザーのIDを取得
    message_id = event.message.id  # メッセージのIDを取得

    # LINEから画像コンテンツを取得
    message_content = line_bot_api.get_message_content(message_id)
    image_bytes = b''
    for chunk in message_content.iter_content():
        image_bytes += chunk

    # 画像をGCSに保存
    file_path = f"{user_id}/{message_id}.jpg"  # 一意のファイル名
    blob = bucket.blob(file_path)
    blob.upload_from_string(image_bytes, content_type='image/jpeg')

    # ユーザーに保存完了のメッセージを送信
    response_message = f"画像が保存されました: {file_path}"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response_message)
    )

'''
def image_flow(user_id, message_id, bucket):
    # メッセージIDを元に画像ファイルを取得
    message_content = line_bot_api.get_message_content(message_id)
    image = message_content.content

    # 画像ファイルをバケットに書き込み
    image_file_name = f"images/{user_id}.jpg"
    blob = bucket.blob(image_file_name)
    blob.upload_from_string(image)
    app.logger.info(f"画像ファイル '{image_file_name}' をバケット '{GCS_BUCKET_NAME}' に書き込みました。")

    # ユーザーに画像の受信完了を通知
    line_bot_api.push_message(user_id, TextSendMessage(text="画像の受信が完了しました。"))

    vision_api_response = "この画像の特徴は次の通りです:\n"
    
    
    # OpenAI APIを使用してレスポンスを生成
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # モデルの指定
        messages=[{"role": "system", "content": "あなたは優秀な就職アドバイザーです。次に与える情報は学生のESの画像から文字起こしされたテキストとです。このテキストに含まれる情報を元に、就職をサポートしてください。ただし、返答は日本語で行ってください。"},  # システムメッセージの設定
                  {"role": "user", "content": user_message}],  # ユーザーメッセー
        max_tokens=250          # 生成するトークンの最大数
    )
    
    
    # LINEユーザーにレスポンスを返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=res)  # 正しいレスポンスの取得方法
    )
    
    
    # バケットから画像ファイルを読み込み
    blob = bucket.blob(image_file_name)
    image_url = blob.public_url

    # ユーザーに画像のURLを送信
    line_bot_api.push_message(user_id, TextSendMessage(text=f"画像のURL: {image_url}"))

    # ユーザーに画像を送信
    line_bot_api.push_message(user_id, ImageSendMessage(original_content_url=image_url, preview_image_url=image_url)
    app.logger.info(f"画像のURL: {image_url}")
    return
''' 


if __name__ == "__main__":
    app.run()