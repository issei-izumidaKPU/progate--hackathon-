import boto3

def transcribe_audio(audio_file_uri, job_name):
    # AWSアクセスキーとシークレットアクセスキーを指定
    aws_access_key_id = 'YOUR_ACCESS_KEY'
    aws_secret_access_key = 'YOUR_SECRET_ACCESS_KEY'

    # Transcribeクライアントを作成
    transcribe = boto3.client('transcribe', 
                            aws_access_key_id=aws_access_key_id, 
                            aws_secret_access_key=aws_secret_access_key,
                            region_name='us-west-2')  # リージョンを指定

    response = transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': audio_file_uri},
        MediaFormat='mp3',  # オーディオファイルの形式に合わせて変更
        LanguageCode='ja-JP'  # 言語コードを指定
    )
    
    while True:
        status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
            break
    
    if status['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
        response = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        transcript_uri = response['TranscriptionJob']['Transcript']['TranscriptFileUri']
        print(f"Transcription completed. Transcript URI: {transcript_uri}")
    else:
        print("Transcription failed.")

# 使用例
audio_file_uri = 's3://your-bucket/your-audio-file.mp3'
job_name = 'your-transcription-job-name'
transcribe_audio(audio_file_uri, job_name)