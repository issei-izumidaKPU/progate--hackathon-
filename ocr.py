import io
import os
from google.cloud import vision
from google.oauth2 import service_account

class OCRClient:
    def __init__(self, image_path):
        self.image_path = image_path
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
        self.client = vision.ImageAnnotatorClient(credentials=credentials)

    def ocr(self):
        # ファイルの絶対パスを取得
        file_name = os.path.abspath(self.image_path)
        # ファイルを開く
        with io.open(file_name, 'rb') as image_file:
            content = image_file.read()
        
        # テキスト抽出
        image = vision.Image(content=content)
        response = self.client.text_detection(image=image)
        texts = response.text_annotations

        if texts:
            print(texts[0].description)
        else:
            print("テキストは抽出されませんでした。")
    