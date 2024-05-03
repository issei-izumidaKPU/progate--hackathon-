import os
import openai
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage ,ImageMessage, AudioMessage
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
# Google Cloud Storageの設定
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
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
    "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL")
}
credentials = service_account.Credentials.from_service_account_info(credentials_dict)
storage_client = storage.Client(credentials=credentials, project=credentials.project_id)
bucket = storage_client.bucket(GCS_BUCKET_NAME)

@app.route("/")
def hello_world():
    return "Hello, World!"

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
    try:
        # Google Cloud Storageのバケットを取得
        bucket = storage_client.get_bucket(GCS_BUCKET_NAME)
        return f"バケット '{GCS_BUCKET_NAME}' に接続成功しました。"
    except Exception as e:
        app.logger.error(f"バケットへの接続に失敗しました: {e}")
        return f"バケットへの接続に失敗しました: {e}", 500

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text  # ユーザーからのメッセージを取得
    user_id = event.source.user_id  # ユーザーのIDを取得

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

if __name__ == "__main__":
    app.run()