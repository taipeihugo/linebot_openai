from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os
import json
import time
import requests
import traceback

app = Flask(__name__)

# Channel Access Token and Channel Secret (從環境變數取得或自行設定)
access_token = os.getenv('CHANNEL_ACCESS_TOKEN', '你的 Access Token')
channel_secret = os.getenv('CHANNEL_SECRET', '你的 Channel Secret')
weath_api = os.getenv('WEATHER_API', '你的 Weather API')

# Line API 初始化
line_bot_api = LineBotApi(access_token)
handler = WebhookHandler(channel_secret)


# 地震查詢功能，整合中央氣象局地震資料的 API
def earth_quake():
    result = []
    code = weath_api  # 你的天氣 API 授權碼
    try:
        # 小區域地震
        url1 = f'https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0016-001?Authorization={code}'
        req1 = requests.get(url1)
        data1 = req1.json()
        eq1 = data1['records']['Earthquake'][0]
        t1 = eq1['EarthquakeInfo']['OriginTime']

        # 顯著有感地震
        url2 = f'https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization={code}'
        req2 = requests.get(url2)
        data2 = req2.json()
        eq2 = data2['records']['Earthquake'][0]
        t2 = eq2['EarthquakeInfo']['OriginTime']

        # 使用最新的地震資料
        result = [eq1['ReportContent'], eq1['ReportImageURI']]  # 使用小區域地震
        if t2 > t1:
            result = [eq2['ReportContent'], eq2['ReportImageURI']]  # 如果顯著有感地震時間較近
    except Exception as e:
        print(e)
        result = ['抓取失敗...', '']  # 如果發生錯誤，返回失敗訊息
    return result


# 主要的 LINE Bot 路由處理程式
@app.route("/", methods=['POST'])
def linebot():
    body = request.get_data(as_text=True)  # 取得收到的訊息內容
    try:
        signature = request.headers['X-Line-Signature']  # 取得 X-Line-Signature
        handler.handle(body, signature)  # 綁定訊息回傳的相關資訊
        json_data = json.loads(body)  # 轉換內容為 json 格式
        reply_token = json_data['events'][0]['replyToken']  # 取得回傳訊息的 Token
        user_id = json_data['events'][0]['source']['userId']  # 取得使用者 ID
        type = json_data['events'][0]['message']['type']  # 取得訊息類型

        if type == 'text':
            text = json_data['events'][0]['message']['text']
            if text == '雷達回波圖' or text == '雷達回波':
                line_bot_api.push_message(user_id, TextSendMessage(text='馬上找給你！抓取資料中....'))
                img_url = f'https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0058-001.png?{time.time_ns()}'
                img_message = ImageSendMessage(original_content_url=img_url, preview_image_url=img_url)
                line_bot_api.reply_message(reply_token, img_message)  # 回傳雷達圖像訊息
            elif text == '地震':
                line_bot_api.push_message(user_id, TextSendMessage(text='馬上找給你！抓取資料中....'))
                reply = earth_quake()  # 執行地震查詢函式
                text_message = TextSendMessage(text=reply[0])  # 傳送地震報告內容
                line_bot_api.reply_message(reply_token, text_message)
                if reply[1]:  # 如果有地震圖片，則回傳
                    line_bot_api.push_message(user_id, ImageSendMessage(original_content_url=reply[1], preview_image_url=reply[1]))
            else:
                text_message = TextSendMessage(text=text)  # 回應接收到的其他文字訊息
                line_bot_api.reply_message(reply_token, text_message)
    except Exception as e:
        print(e)  # 發生錯誤時印出錯誤訊息
    return 'OK'  # 驗證 Webhook 使用，不能省略

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
    app.run()
