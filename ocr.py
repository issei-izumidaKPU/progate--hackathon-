import io
import os
from google.cloud import vision
from google.oauth2 import service_account

class OCRClient:
    def __init__(self):
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

def image_to_text(imagecontent):
    client = OCRClient().client

    image = vision.Image(content=imagecontent)
    response = client.document_text_detection(image=image)#文字情報の取得

    return response.full_text_annotation.text