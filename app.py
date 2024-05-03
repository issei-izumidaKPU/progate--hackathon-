from dotenv import load_dotenv
import os
import openai
from flask import Flask, request, abort, render_template
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage, AudioMessage, FollowEvent, ImageSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
from gcs_client import CloudStorageManager

app = Flask(__name__)
load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY
gcs_user_manager = CloudStorageManager("user-backets")
system_prompts = "You are an assistant skilled in programming, general knowledge, and tool usage advice. You provide helpful information for tasks in Line. And You must return messages in japanese."
user_status = "INITIAL"


def chatGPTResponse(prompts, model, user_id, system_prompts=system_prompts, temperature=0.5):
    '''response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # モデルの指定
        messages=[
            {"role": "system", "content": "You are an assistant skilled in programming, general knowledge, and tool usage advice. You provide helpful information for tasks in Line. And You must return messages in japanese."},  # システムメッセージの設定
            {"role": "user", "content": transcript["text"]},  # 変換されたテキストをユーザーメッセージとして使用
        ],
        max_tokens=250  # 生成するトークンの最大数
    )'''
    cloud_storage_manager = CloudStorageManager(bucket_name="user-backets")
    user_history = cloud_storage_manager.get_user_history(user_id)
    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompts},  # システムメッセージの設定
            {"role": "system", "content": user_history},
            {"role": "user", "content": prompts},  # 変換されたテキストをユーザーメッセージとして使用
        ],
        temperature=temperature
    )
    return response.choices[0].message['content'].strip()


def send_encouragement_message():
    user_id = "YOUR_USER_ID"  # ユーザーIDを設定
    message = "おはようございます！新しい一日がんばりましょう！"  # 送るメッセージ
    line_bot_api.push_message(user_id, TextSendMessage(text=message))


scheduler = BackgroundScheduler()
scheduler.add_job(send_encouragement_message, 'cron',
                  hour=9, minute=0)  # 毎日9時0分に実行
scheduler.start()


@app.route("/")
def hello_world():
    return render_template("index.html")


@app.route("/transcribe")
def transcribe():
    return render_template("transcribe.html")


@app.route("/line/login", methods=["GET"])
def line_login():
    request_code = request.args["code"]
    # 認可コードを取得する処理をここに追加


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
    return gcs_user_manager.test_connection()


@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id  # ユーザーのIDを取得
    gcs_user_manager.initialize_user_storage(user_id)  # ユーザーストレージを初期化

    # ユーザーに歓迎メッセージを送信
    welcome_message = "ようこそ！私たちのサービスへ。以下のようなことができます："
    line_bot_api.push_message(user_id, TextSendMessage(text=welcome_message))

    # ユーザーにサービスの説明を送信
    service_description = "こちらで写真や音声の保存が可能です。また、質問に答えることでより良いサービスを提供します。"
    line_bot_api.push_message(
        user_id, TextSendMessage(text=service_description))


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    model = "gpt-3.5-turbo"
    if event.message.text == "GPT-4を使用する":
        model = "gpt-4-turbo"
    user_message = event.message.text  # ユーザーからのメッセージを取得
    user_id = event.source.user_id  # ユーザーのIDを取得
    gcs_client = CloudStorageManager("user-backets")
    gcs_client.ensure_user_storage(user_id)
    gcs_client.writeChatHistory(user_id,"user",user_message)
    # ユーザーのメッセージを使用してレスポンスを生成
    response = chatGPTResponse(user_message, model, user_id)
    res = f"あなたのユーザーIDは{user_id}です。\n"
    res += response
    gcs_client.writeChatHistory(user_id,"system",response)
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
    gcs_user_manager.upload_file(
        file_path, audio_bytes, content_type='audio/m4a')

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
            # 変換されたテキストをユーザーメッセージとして使用
            {"role": "user", "content": transcript["text"]},
        ],
        max_tokens=250  # 生成するトークンの最大数
    )

    res = f"あなたのユーザーIDは{user_id}です。\n"
    res += response.choices[0].message['content'].strip()

    # ユーザーのIDとメッセージをGoogle Cloud Storageに保存
    gcs_user_manager.upload_file(f"{user_id}/{message_id}.txt", res)

    # LINEユーザーにレスポンスを返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=res)
    )


@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id  # ユーザーのIDを取得
    message_id = event.message.id  # メッセージのIDを取得

    # メッセージIDを元に画像ファイルを取得
    message_content = line_bot_api.get_message_content(message_id)
    image = message_content.content

    # 画像ファイルをバケットに書き込み
    image_file_name = f"images/{user_id}.jpg"
    gcs_user_manager.upload_file(image_file_name, image)
    app.logger.info(f"画像ファイル '{image_file_name}' をバケットに書き込みました。")

    # ユーザーに画像の受信完了を通知
    line_bot_api.push_message(user_id, TextSendMessage(text="画像の受信が完了しました。"))

    # 画像ファイルをGoogle Cloud Vision APIに送信して解析
    vision_api_response = "この画像の特徴は次の通りです:\n"
    line_bot_api.push_message(
        user_id, TextSendMessage(text=vision_api_response))


if __name__ == "__main__":
    app.run()
