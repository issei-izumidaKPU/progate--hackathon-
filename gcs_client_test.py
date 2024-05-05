import unittest
from unittest.mock import patch, MagicMock
from google.cloud import storage
from google.oauth2 import service_account
import os
from gcs_client import CloudStorageManager

class TestCloudStorageManager(unittest.TestCase):
    @patch('progate--hackathon-.gcs_client.storage.Client')
    def test_test_connection(self, mock_client):
        # クライアントとバケットのモックを設定
        mock_bucket = MagicMock()
        mock_client.return_value.bucket.return_value = mock_bucket
        mock_client.return_value.lookup_bucket.return_value = True  # バケットが存在すると仮定

        # CloudStorageManager インスタンスを作成
        manager = CloudStorageManager('test-bucket ')

        # test_connection メソッドを実行
        result = manager.test_connection()

        # 結果の検証
        self.assertEqual(result, "GCSとの接続が成功しました。")

        # バケットが存在しない場合のテスト
        mock_client.return_value.lookup_bucket.return_value = False
        result = manager.test_connection()
        self.assertEqual(result, "バケットが見つかりません。")

if __name__ == '__main__':
    unittest.main()