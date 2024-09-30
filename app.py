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
weather_api = os.getenv('WEATHER_API', '你的 Weather API')

# Line API 初始化
line_bot_api = LineBotApi(access_token)
handler = WebhookHandler(channel_secret)

# 你的天氣 API 授權碼
code = weather_api 

# 地震查詢功能，整合中央氣象局地震資料的 API
def earth_quake():
    result = []     
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
    
# 取得某個地點的氣象資訊
def weather(address):
    try:
        url = [f'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization={code}',
            f'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization={code}']
        result = {}
        for item in url:
            req = requests.get(item)   # 爬取目前天氣網址的資料
            data = req.json()
            station = data['records']['Station']   # 觀測站
            for i in station:
                city = i['GeoInfo']['CountyName']  # 縣市
                area = i['GeoInfo']['TownName']    # 區域
                # 使用「縣市+區域」作為 key，例如「高雄市前鎮區」就是 key
                # 如果 result 裡沒有這個 key，就記錄相關資訊
                if not f'{city}{area}' in result:
                    weather = i['WeatherElement']['Weather']
                    temp = i['WeatherElement']['AirTemperature'] 
                    humid = i['WeatherElement']['RelativeHumidity']
                    # 回傳結果
                    result[f'{city}{area}'] = f'目前天氣狀況「{weather}」，溫度 {temp} 度，相對濕度 {humid}%！'

        output = '找不到氣象資訊'
        for i in result:
            if i in address: # 如果地址裡存在 key 的名稱
                output = f'「{address}」{result[i]}'
                break
    except Exception as e:
        print(e)
        output = '抓取失敗...'
    return output

# 主要的 LINE Bot 路由處理程式
@app.route("/", methods=['POST'])
def linebot():
    body = request.get_data(as_text=True)                    # 取得收到的訊息內容
    try:
        line_bot_api = LineBotApi(access_token)     # 確認 token 是否正確
        handler = WebhookHandler(channel_secret)    # 確認 secret 是否正確
        signature = request.headers['X-Line-Signature']             # 加入回傳的 headers
        handler.handle(body, signature)      # 綁定訊息回傳的相關資訊
        json_data = json.loads(body)         # 轉換內容為 json 格式
        reply_token = json_data['events'][0]['replyToken']    # 取得回傳訊息的 Token ( reply message 使用 )
        user_id = json_data['events'][0]['source']['userId']  # 取得使用者 ID ( push message 使用 )
        print(json_data)                                      # 印出內容
        type = json_data['events'][0]['message']['type']
        if type == 'text':
            text = json_data['events'][0]['message']['text']
            if text == '雷達回波圖' or text == '雷達回波':
                line_bot_api.push_message(user_id, TextSendMessage(text='馬上找給你！抓取資料中....'))
                img_url = f'https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0058-001.png?{time.time_ns()}'
                img_message = ImageSendMessage(original_content_url=img_url, preview_image_url=img_url)
                line_bot_api.reply_message(reply_token,img_message)
            elif text == '地震':
                line_bot_api.push_message(user_id, TextSendMessage(text='馬上找給你！抓取資料中....'))
                reply = earth_quake()
                text_message = TextSendMessage(text=reply[0])
                line_bot_api.reply_message(reply_token,text_message)
                line_bot_api.push_message(user_id, ImageSendMessage(original_content_url=reply[1], preview_image_url=reply[1]))
            else:          
                text_message = TextSendMessage(text=text)
                line_bot_api.reply_message(reply_token,text_message)
        elif type == 'location':
            line_bot_api.push_message(user_id, TextSendMessage(text='馬上找給你！抓取資料中....'))
            address = json_data['events'][0]['message']['address'].replace('台','臺')  # 取出地址資訊，並將「台」換成「臺」
            reply = weather(address)          
            text_message = TextSendMessage(text=reply)
            line_bot_api.reply_message(reply_token,text_message)
    except Exception as e:
        print(e)
    return 'OK'                 # 驗證 Webhook 使用，不能省略

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
