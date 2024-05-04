from google.cloud import storage
from google.oauth2 import service_account
import os

class CloudStorageManager:
    def __init__(self, bucket_name):
        # 環境変数から認証情報を取得して認証情報オブジェクトを作成
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
        
        # クライアントを初期化
        self.client = storage.Client(credentials=credentials, project=credentials.project_id)
        self.bucket = self.client.bucket(bucket_name)

    def test_connection(self):
        """GCSとの接続をテストする"""
        try:
            # バケットの存在を確認
            if self.client.lookup_bucket(self.bucket.name):
                return "GCSとの接続が成功しました。"
            else:
                return "バケットが見つかりません。"
        except Exception as e:
            return f"GCSとの接続に失敗しました: {e}"
        
    def upload_file(self, file_path, content, content_type='text/plain'):
        """指定したパスにファイルをアップロードする"""
        blob = self.bucket.blob(file_path)
        blob.upload_from_string(content, content_type=content_type)

    def download_file(self, file_path):
        """指定したパスからファイルをダウンロードする"""
        blob = self.bucket.blob(file_path)
        return blob.download_as_text()

    def create_folder(self, folder_path):
        """フォルダを作成する（GCSではフォルダは単なるプレフィックス）"""
        blob = self.bucket.blob(folder_path)
        blob.upload_from_string('')  # 空のファイルでフォルダを作成

    def initialize_user_storage(self, user_id):
        """新しいユーザーのストレージを初期化する"""
        # ユーザー専用のフォルダを作成
        user_folder = f"{user_id}/"
        user_images_folder = f"{user_folder}images/"
        user_audio_folder = f"{user_folder}audio/"
        folders = [user_images_folder, user_audio_folder]
        
        for folder in folders:
            self.create_folder(folder)  # 各フォルダを作成
        
        # 初期の会話履歴ファイルを作成
        history_file_path = f"{user_id}/history.txt"
        initial_history_content = "ユーザーとのインタラクション履歴:\n"
        self.upload_file(history_file_path, initial_history_content)

    def ensure_user_storage(self,user_id):
        user_folder = f"{user_id}/"
        user_images_folder = f"{user_folder}images/"
        user_audio_folder = f"{user_folder}audio/"
        folders = [user_images_folder, user_audio_folder]
        
        for folder in folders:
            if not self.client.bucket(self.bucket.name).blob(folder).exists():
                self.create_folder(folder)
        history_file_path = f"{user_id}/history.txt"
        if not self.client.bucket(self.bucket.name).blob(history_file_path).exists():
            initial_history_content = "ユーザーとのインタラクション履歴:\n"
            self.upload_file(history_file_path, initial_history_content)
        
    def writeChatHistory(self, user_id, role, message):
        history_file_path = f"{user_id}/history.txt"
        history = self.download_file(history_file_path)
        prefix = "User:" if role == "user" else "Assistant:"
        history += f"{prefix} {message}\n"
        self.upload_file(history_file_path, history.encode('utf-8'), content_type='text/plain; charset=utf-8')
        
    def readChatHistory(self, user_id):
        history_file_path = f"{user_id}/history.txt"
        history_content = self.download_file(history_file_path)
        # 履歴を改行で分割し、最後の5行だけを取得
        history_lines = history_content.split('\n')
        last_five_conversations = '\n'.join(history_lines[-6:-1])  # 最後の5行を取得（-1は最後の空行を除外するため）
        return last_five_conversations