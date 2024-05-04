import os
from ocr import OCRClient
from dotenv import load_dotenv
def test_ocr(image_path):
    load_dotenv()
    # OCRClient インスタンスを作成
    ocr_client = OCRClient(image_path)
    # OCR メソッドを実行
    texts = ocr_client.ocr()
    # 結果を出力
    if texts:
        print("検出されたテキスト:")
        for text in texts:
            print(f"説明: {text.description}")
    else:
        print("テキストは検出されませんでした。")

# テスト画像のパスを指定
test_image_path = './sample10.png'
# テスト関数を実行
test_ocr(test_image_path)