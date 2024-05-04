import openai
from dotenv import load_dotenv
import os
from gcs_client import CloudStorageManager
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY
system_prompts = "You are an assistant skilled in programming, general knowledge, and tool usage advice. You provide helpful information for tasks in Line. And You must return messages in japanese."
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