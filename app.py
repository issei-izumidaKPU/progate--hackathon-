from dotenv import load_dotenv
import os
import jwt as pyjwt
import requests
import json
import openai
import re
import sys
import sqlite3
from pathlib import Path
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, request, abort, render_template
from flask_socketio import SocketIO, emit
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, ButtonsTemplate,  TemplateSendMessage, PostbackAction, TextSendMessage, ImageMessage, AudioMessage, FollowEvent, ImageSendMessage, PostbackEvent
import linebot.v3.messaging
from linebot.v3.messaging.rest import ApiException
from apscheduler.schedulers.background import BackgroundScheduler
from gcs_client import CloudStorageManager
# from . import MicrophoneStream
from datetime import datetime
import ocr as gcpapi
from chat_gpt import chatGPTResponse, chatGPTResponseFromImages
load_dotenv()
# APIクライアントの設定
configuration = linebot.v3.messaging.Configuration(
    access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
)
api_client = linebot.v3.messaging.ApiClient(configuration)

db = SQLAlchemy()
socketio = SocketIO()


class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.String(255), primary_key=True)
    nickname = db.Column(db.String(255), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    residence = db.Column(db.String(255), nullable=False)
    grade = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now)


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config["SECRET_KEY"] = "sample1216"
    db.init_app(app)
    socketio.init_app(app)  # 既存の socketio インスタンスに app を関連付ける
    migrate = Migrate(app, db)
    return app


app = create_app()

if __name__ == "__main__":
    socketio.run(app, debug=True)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINE_CHANNEL_ID = os.getenv("LINE_CHANNEL_ID")
LINE_LOGIN_CHANNEL_SECRET = os.getenv("LINE_LOGIN_CHANNEL_SECRET")
REDIRECT_URL = os.getenv("REDIRECT_URL")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY
gcs_user_manager = CloudStorageManager("user-backets")
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
    user_history = cloud_storage_manager.readChatHistory(user_id)
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


def chatGPTResponseFromImages(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k-0613",
        messages=[
            {"role": "system", "content": "あなたは就活生をサポートする優秀な教師です"},
            {"role": "system", "content": "あなたは送られてきた文章の文法的な間違いや、論理構造の欠陥を指摘して修正します"},
            {"role": "system", "content": "さらに、文章の内容を補完して、より魅力的な文章に仕上げます"},
            {"role": "system",
                "content": "与えられた文章で、定量的でない発言や、抽象的意見がある場合は、具体性や数字を使った説明をしてください"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3)
    text = response.choices[0].message['content'].strip()
    return text

def sqlite_update(USER_ID, NICKNAME, AGE, RESIDENCE, GRADE):
    conn = sqlite3.connect('instance/db.sqlite3')
    cursor = conn.cusor()
    
    user_id = USER_ID
    nickname = NICKNAME
    age = AGE
    residence = RESIDENCE
    grade = GRADE
    
    # SQLインジェクション対策
    update_query = """
        UPDATE users
        SET nickname = ?,
            age = ?,
            residence = ?,
            grade = ?
        WHERE user_id = ?
    """
    
    cursor.execute(update_query, (nickname, age, residence, grade, user_id))
    conn.commit()
    conn.close()
    
def get_user_ids():
    # SQLite3データベースに接続
    conn = sqlite3.connect('instance/db.sqlite3')
    cursor = conn.cursor()

    try:
        # ユーザーIDの一覧を取得するSQLクエリ
        select_query = """
            SELECT user_id
            FROM users
        """
        
        # SQLクエリを実行し、結果を取得
        cursor.execute(select_query)
        user_ids = [row[0] for row in cursor.fetchall()]  # ユーザーIDの一覧を取得
        
        return user_ids

    finally:
        # データベース接続を閉じる
        conn.close()

# メッセージの送信
def send_encouragement_message(USER_ID):
    user_id = USER_ID  # ユーザーIDを設定
    message = "おはようございます！新しい一日がんばりましょう！"  # 送るメッセージ
    line_bot_api.push_message(user_id, TextSendMessage(text=message))

# スケジューラの設定
scheduler = BackgroundScheduler()

for user_id in get_user_ids():# ユーザーIDのリストを取得して要素毎にメッセージを送信
    scheduler.add_job(send_encouragement_message(user_id), 'cron',
                  hour=22, minute=10)  # 毎日22時10分に実行
    scheduler.start()

# データベースの更新->ユーザーの任意のタイミングで実行する
def sqlite_update(USER_ID, NICKNAME, AGE, RESIDENCE, GRADE):
    conn = sqlite3.connect('instance/db.sqlite3')
    cursor = conn.cursor()
    
    user_id = USER_ID
    nickname = NICKNAME
    age = AGE
    residence = RESIDENCE
    grade = GRADE
    
    # SQLインジェクション対策
    update_query = """
        UPDATE users
        SET nickname = ?,
            age = ?,
            residence = ?,
            grade = ?
        WHERE user_id = ?
    """
    
    cursor.execute(update_query, (nickname, age, residence, grade, user_id))
    conn.commit()
    conn.close()
    
#user_idを集めたリストを取得
def get_user_ids():
    # SQLite3データベースに接続
    conn = sqlite3.connect('instance/db.sqlite3')
    cursor = conn.cursor()

    try:
        # ユーザーIDの一覧を取得するSQLクエリ
        select_query = """
            SELECT user_id
            FROM users
        """
        
        # SQLクエリを実行し、結果を取得
        cursor.execute(select_query)
        user_ids = [row[0] for row in cursor.fetchall()]  # ユーザーIDの一覧を取得
        
        return user_ids

    finally:
        # データベース接続を閉じる
        conn.close()



@app.route("/", methods=["GET"])
def index():
    LINE_CHANNEL_ID = os.getenv("LINE_CHANNEL_ID")
    REDIRECT_URL = os.getenv("REDIRECT_URL")
    return render_template("index.html",
                           random_state="line1216",
                           channel_id=LINE_CHANNEL_ID,
                           redirect_url=REDIRECT_URL)


@app.route("/line/login", methods=["GET"])
def line_login():
    LINE_CHANNEL_ID = os.getenv("LINE_CHANNEL_ID")
    REDIRECT_URL = os.getenv("REDIRECT_URL")
    LINE_LOGIN_CHANNEL_SECRET = os.getenv("LINE_LOGIN_CHANNEL_SECRET")
    # 認可コードを取得する
    request_code = request.args["code"]
    uri_access_token = "https://api.line.me/oauth2/v2.1/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data_params = {
        "grant_type": "authorization_code",
        "code": request_code,
        "redirect_uri": REDIRECT_URL,
        "client_id": LINE_CHANNEL_ID,
        "client_secret": LINE_LOGIN_CHANNEL_SECRET
    }

    # トークンを取得するためにリクエストを送る
    response_post = requests.post(
        uri_access_token, headers=headers, data=data_params)
    line_id_token = json.loads(response_post.text)["id_token"]

    # ペイロード部分をデコードすることで、ユーザ情報を取得する
    decoded_id_token = pyjwt.decode(line_id_token,
                                  LINE_LOGIN_CHANNEL_SECRET,
                                  audience=LINE_CHANNEL_ID,
                                  issuer='https://access.line.me',
                                  algorithms=['HS256'])

    return render_template("line_success.html", user_profile=decoded_id_token)


@app.route("/transcribe")
# リアルタイム音声認譞
def transcribe():
    return render_template("transcribe.html")



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
    display_name = line_bot_api.get_profile(user_id).display_name
    app.logger.info(f"ユーザーの表示名: {display_name}")
    # ユーザーのデータベースに新しいユーザーを追加
    new_user = User(
        user_id=user_id,
        nickname="未設定",
        age=0,
        residence="未設定",
        grade="未設定",
    )
    db.session.add(new_user)
    db.session.commit()
    # ユーザーIDをログに記録
    app.logger.info(f"新しいユーザーが追加されました: {new_user.user_id}")  # 修正された行
    # ユーザーに歓迎メッセージを送信
    welcome_message = "ようこそ！私たちのサービスへ。まずは以下のフォーマットに従って自己紹介をお願いします。\n自己紹介: \n ニックネーム：\n年齢：\n居住地：\n学年：\n希望職種：\n簡単な経歴：\n"
    line_bot_api.push_message(user_id, TextSendMessage(text=welcome_message))

    # ユーザーにサービスの説明を送信
    service_description = "こちらで写真や音声の保存が可能です。また、質問に答えることでより良いサービスを提供します。"
    line_bot_api.push_message(
        user_id, TextSendMessage(text=service_description))


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id  # ユーザーのIDを取得
    data = event.postback.data  # ポストバックデータを取得

    # ポストバックデータを解析
    action, info = data.split(':')
    if action == "update":
        field, value = info.split(',')
        # ユーザー情報を更新
        user = User.query.filter_by(user_id=user_id).first()
        if user:
            setattr(user, field, value)
            db.session.commit()
            response_message = f"{field}を更新しました。新しい値: {value}"
        else:
            response_message = "ユーザー情報が見つかりません。"
    else:
        response_message = "不明なアクションです。"

    # ユーザーに応答メッセージを送信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response_message)
    )


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        # APIインスタンスの作成
        api_instance = linebot.v3.messaging.MessagingApi(api_client)
        chat_id = event.source.user_id
        # ローディングアニメーションの表示リクエストを送信
        show_loading_animation_request = linebot.v3.messaging.ShowLoadingAnimationRequest(
            chat_id=chat_id)
        api_instance.show_loading_animation(show_loading_animation_request)

        # 以下、メッセージ処理ロジック（省略）
        # ユーザーからのポストバックアクションを処理する
        if event.message.text == "ボタン":
            buttons_template = ButtonsTemplate(
                title='あなたの選択', text='以下から選んでください', actions=[
                    PostbackAction(label='選択肢 1', data='action1'),
                    PostbackAction(label='選択肢 2', data='action2')
                ]
            )
            template_message = TemplateSendMessage(
                alt_text='Buttons alt text', template=buttons_template
            )
            line_bot_api.reply_message(event.reply_token, template_message)
        model = "gpt-3.5-turbo"
        if event.message.text == "GPT-4を使用する":
            model = "gpt-4-turbo"
        user_message = event.message.text  # ユーザーからのメッセージを取得
        user_id = event.source.user_id  # ユーザーのIDを取得
        display_name = line_bot_api.get_profile(
            user_id).display_name  # ユーザーの表示名を取得
        gcs_client = CloudStorageManager("user-backets")
        gcs_client.ensure_user_storage(user_id)
        gcs_client.writeChatHistory(user_id, "user", user_message)
        # ユーザーのメッセージを使用してレスポンスを生成
        response = chatGPTResponse(user_message, model, user_id)
        res = f"あなたのユーザーIDは{user_id}です。\n"
        res = f"{display_name}さん、こんにちは！\n"
        res += response
        gcs_client.writeChatHistory(user_id, "system", response)
        # LINEユーザーにレスポンスを返信
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=res)  # 正しいレスポンスの取得方法
        )
    except ApiException as e:
        print(
            f"API exception when calling MessagingApi->show_loading_animation: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="申し訳ありませんが、エラーが発生しました。")
        )
    except Exception as e:
        print(f"Exception in handle_message: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="予期せぬエラーが発生しました。")
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
    message_id = event.message.id
    message_content = line_bot_api.get_message_content(message_id)
    image = message_content.content
    res = gcpapi.image_to_text(image)
    # ユーザーに画像の受信完了を通知
    line_bot_api.push_message(user_id, TextSendMessage(text="画像の受信が完了しました。"))

    # GPTに渡してテキストを修正
    corrected_text = chatGPTResponseFromImages(res)

    # ユーザーに修正されたテキストを送信
    line_bot_api.push_message(user_id, TextSendMessage(text=corrected_text))

    # ユーザーのIDとメッセージをGoogle Cloud Storageに保存
    gcs_client = CloudStorageManager("user-backets")
    gcs_client.ensure_user_storage(user_id)
    gcs_client.upload_file(
        f"{user_id}/images/{message_id}.txt", image, content_type='image/jpeg')
    gcs_client.writeChatHistory(user_id, "asssytant", corrected_text)
