# lambda/index.py
import json
import os
import boto3
import re  # 正規表現モジュールをインポート
import urllib.request as ur
import urllib.error as ur_error


# Lambda コンテキストからリージョンを抽出する関数
def extract_region_from_arn(arn):
    # ARN 形式: arn:aws:lambda:region:account-id:function:function-name
    match = re.search('arn:aws:lambda:([^:]+):', arn)
    if match:
        return match.group(1)
    return "us-east-1"  # デフォルト値

# グローバル変数としてクライアントを初期化（初期値）
bedrock_client = None

# モデルID
MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-lite-v1:0")
API_URL = os.environ.get("API_URL", "https://683e-35-194-219-53.ngrok-free.app") 

def lambda_handler(event, context):
    try:
        print("Received event:", json.dumps(event))
        
        # Cognitoで認証されたユーザー情報を取得
        user_info = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            user_info = event['requestContext']['authorizer']['claims']
            print(f"Authenticated user: {user_info.get('email') or user_info.get('cognito:username')}")
        
        # リクエストボディの解析
        body = json.loads(event['body'])
        message = body['message']
        conversation_history = body.get('conversationHistory', [])
        
        print("Processing message:", message)
        print("Using model:", MODEL_ID)
        
        # 会話履歴を使用
        messages = conversation_history.copy()
        
        # ユーザーメッセージを追加
        messages.append({
            "role": "user",
            "content": message
        })
        
        url = f"{API_URL}/generate"
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": message,
            "max_new_tokens": 32,
            "do_sample": True,
            "temperature": 0.7,
            "top_p": 0.9,
        }

        data = json.dumps(payload).encode("utf-8")

        request = ur.Request(
            url, 
            data=data, 
            headers=headers, 
            method="POST"
        )
        
        try:
            with ur.urlopen(request) as res:
                resp_data = res.read()
                response_body = json.loads(resp_data)
                print("FastAPI response:", json.dumps(response_body, default=str))
        except ur.HTTPError as e:
            error_message = e.read().decode()
            print(f"HTTPエラー {e.code}: {error_message}")
            raise
        except ur_error.URLError as e:
            print(f"URLエラー: {e.reason}")
            raise

        # 応答の検証
        if "generated_text" not in response_body:
            raise Exception("No generated_text in response")
        
        # アシスタントの応答を会話履歴に追加
        messages.append({
            "role": "assistant",
            "content": response_body["generated_text"]
        })
        
        # 成功レスポンスの返却
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": response_body["generated_text"],
                "conversationHistory": messages
            })
        }
        
    except Exception as error:
        print("Error:", str(error))
        
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": False,
                "error": str(error)
            })
        }
