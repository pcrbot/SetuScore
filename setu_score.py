import os
import re

from nonebot import get_bot
from aip import AipContentCensor
from hoshino import R, Service
from hoshino.typing import CQEvent, MessageSegment

sv = Service('色图打分')

cache = ''  #你go-cqhttp.exe的文件夹 例如我的go-cqhttp.exe放在C:/go-cqhttp/这个文件夹里,那么这里就填C:/go-cqhttp/
APP_ID = '' #你的AppID
API_KEY = ''#你的API Key
SECRET_KEY = ''#你的Secret Key

client = AipContentCensor(APP_ID, API_KEY, SECRET_KEY)

def get_file_content(filePath):
    with open(filePath, 'rb') as fp:
        return fp.read()

def porn_pic_index(img):
    img = os.path.join(cache,img)
    result = client.imageCensorUserDefined(get_file_content(img))
    try:
        if (result):
            r = result
            if "error_code" in r:
                return { 'code': r['error_code'], 'msg': r['error_msg'] }
            else:
                porn = 0
                sexy = 0
                for c in r['data']:
                    #由于百度的图片审核经常给出极低分,所以不合规项置信度*500后为分数
                    if c['type'] == 1 and c['subType'] == 0:
                        porn = int(c['probability'] * 500)
                    elif c['type'] == 1 and c['subType'] == 1:
                        sexy = int(c['probability'] * 500)
                return { 'code': 0, 'msg': 'Success', 'value': max(sexy,porn) }

        else:
            return { 'code': -1, 'msg': 'API Error' }


    except FileNotFoundError:
        return { 'code': -1, 'msg': 'File not found' }

@sv.on_prefix('打分')
async def setu_score(bot,ev: CQEvent):
    ret = re.search(r"\[CQ:image,file=(.*),url=(.*)\]", str(ev.message))
    try:
        file = ret.group(1)
    except:
        await bot.send(ev,'请带上图片,需要与指令在同一消息内')
        return
    #百度api无法直接从腾讯url获取图片,所以要下载到本地后再上传
    img = await get_bot().get_image(file=file)
    img_file = img['file']
    porn = porn_pic_index(img_file)
    if porn['code'] == 0:
        score = porn['value']
    else:
        code = porn['code']
        err = porn['msg']
        await bot.send(ev,f'错误:{code}\n{err}')
        return
    url = os.path.join(cache,img_file)
    await bot.send(ev,str(MessageSegment.image(f'file:///{os.path.abspath(url)}')+f'\n色图评分:{score}'))