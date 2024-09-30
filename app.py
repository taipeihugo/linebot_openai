from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os
import json
import time
import traceback

app = Flask(__name__)

# Channel Access Token and Channel Secret (從環境變數取得)
access_token = os.getenv('CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('CHANNEL_SECRET')

# Line API 初始化
line_bot_api = LineBotApi(access_token)
handler = WebhookHandler(channel_secret)


# 監聽所有來自 /callback 的 Post Request
@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


# 新增的訊息處理器，處理來自 "/" 的 Post Request
@app.route("/", methods=['POST'])
def linebot():
    body = request.get_data(as_text=True)  # 取得收到的訊息內容
    try:
        line_bot_api = LineBotApi(access_token)  # 確認 token 是否正確
        handler = WebhookHandler(channel_secret)  # 確認 secret 是否正確
        signature = request.headers['X-Line-Signature']  # 加入回傳的 headers
        handler.handle(body, signature)  # 綁定訊息回傳的相關資訊
        json_data = json.loads(body)  # 轉換內容為 json 格式
        reply_token = json_data['events'][0]['replyToken']  # 取得回傳訊息的 Token ( reply message 使用 )
        user_id = json_data['events'][0]['source']['userId']  # 取得使用者 ID ( push message 使用 )
        print(json_data)  # 印出內容
        type = json_data['events'][0]['message']['type']
        
        if type == 'text':
            text = json_data['events'][0]['message']['text']
            if text == '雷達回波圖' or text == '雷達回波':
                line_bot_api.push_message(user_id, TextSendMessage(text='馬上找給你！抓取資料中....'))  # 一開始先發送訊息
                img_url = f'https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0058-001.png?{time.time_ns()}'
                img_message = ImageSendMessage(original_content_url=img_url, preview_image_url=img_url)
                line_bot_api.reply_message(reply_token, img_message)  # 回傳雷達圖像訊息
            else:
                text_message = TextSendMessage(text=text)  # 其他文本訊息回應
                line_bot_api.reply_message(reply_token, text_message)
    except Exception as e:
        print(e)  # 發生錯誤就印出完整錯誤內容
    return 'OK'  # 驗證 Webhook 使用，不能省略


# 處理訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text
    try:
        # 模擬回應訊息
        response_message = f"你說了: {msg}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(response_message))
    except:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage('發生錯誤，請稍後再試'))


# 處理 Postback 事件
@handler.add(PostbackEvent)
def handle_postback(event):
    print(event.postback.data)


# 歡迎新成員加入的事件
@handler.add(MemberJoinedEvent)
def welcome(event):
    uid = event.joined.members[0].user_id
    gid = event.source.group_id
    profile = line_bot_api.get_group_member_profile(gid, uid)
    name = profile.display_name
    message = TextSendMessage(text=f'{name} 歡迎加入')
    line_bot_api.reply_message(event.reply_token, message)


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
