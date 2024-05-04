# google vision api ocrを使って与えられた画像から文字を抽出する

import io
import os
from google.cloud import vision
from google.oauth2 import service_account
from dotenv import load_dotenv
#環境変数を設定してない
#json_path = '/Users/mizunoshoma/Documents/ハッカソン/hackathon20240429-0505-764809e54964.json'
#credentials = service_account.Credentials.from_service_account_file(json_path)
#client = vision.ImageAnnotatorClient(credentials=credentials)
#環境変数を設定している
load_dotenv()
credentials_dict = {
            "type": os.getenv("TYPE"),
            "project_id": os.getenv("PROJECT_ID"),
            "private_key_id": os.getenv("PRIVATE_KEY_ID"),
            "private_key": os.getenv("PRIVATE_KEY"),
            "client_email": os.getenv("CLIENT_EMAIL"),
            "client_id": os.getenv("CLIENT_ID"),
            "auth_uri": os.getenv("AUTH_URI"),
            "token_uri": os.getenv("TOKEN_URI"),
            "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_X509_CERT_URL"),
            "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL")
    }
credentials = service_account.Credentials.from_service_account_info(credentials_dict)
client = vision.ImageAnnotatorClient(credentials=credentials)

# ファイルの絶対パスを取得
file_name = os.path.abspath('sample10.png')
# ファイルを開く
with io.open(file_name, 'rb') as image_file:
    content = image_file.read()
    
# テキスト抽出
image = vision.Image(content=content)
response = client.text_detection(image=image)
texts = response.text_annotations

if texts:
    print(texts[0].description)
else:
    print("テキストは抽出されませんでした。")
    
# for text in texts:
#     print(text.description)
#     print(text.bounding_poly.vertices)
    