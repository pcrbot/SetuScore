import os
import re
import requests
from hoshino import aiorequests
from asyncio import sleep
from datetime import datetime,timedelta
from hoshino import R, Service
from hoshino.typing import CQEvent, MessageSegment
from hoshino.util import FreqLimiter, DailyNumberLimiter


sv = Service('色图打分')
_max = 10       #一天最多打分几次
_time = 60      #打分冷却时间
EXCEED_NOTICE = f'您今天已经打了{_max}次分了，请明早5点后再来！'
_nlmt = DailyNumberLimiter(_max)
_flmt = FreqLimiter(_time)
SEARCH_TIMEOUT = 30
reply = False  #是否通过回复打分,是为True,否为False
               #如果无法回复请检查你的aiocqhttp版本是否大于等于1.4.0
               #如果你是很早以前部署的bot那么很大概率你的aiocqhttp小于1.4.0
               #可以使用指令 pip install --upgrade aiocqhttp 更新版本

API_KEY = ''   #你的API Key
SECRET_KEY = ''#你的Secret Key

async def porn_pic_index(url):
    host = f'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={API_KEY}&client_secret={SECRET_KEY}'
    response = requests.get(host)
    access_token = response.json()["access_token"]
    request_url = "https://aip.baidubce.com/rest/2.0/solution/v1/img_censor/v2/user_defined"
    request_url = request_url + "?access_token=" + access_token
    headers = {'content-type': 'application/x-www-form-urlencoded'}

    params = {"imgUrl": url}
    resp = await aiorequests.post(request_url, data=params, headers=headers)
    if resp.ok:
        data = await resp.json()
    try:
        if (data):
            r = data
            if "error_code" in r:
                return { 'code': r['error_code'], 'msg': r['error_msg'] }
            try:
                data = r['data']
            except:
                return { 'code': -1, 'msg': '请检查策略组中疑似区间是否拉满' }
            porn_0 = 0
            porn_1 = 0
            porn_2 = 0
            for c in data:
                #由于百度的图片审核经常给出极低分,所以不合规项置信度*500后为分数
                if c['type'] == 1 and c['subType'] == 0:
                    porn_0 = int(c['probability'] * 500)
                elif c['type'] == 1 and c['subType'] == 1:
                    porn_1 = int(c['probability'] * 500)
                elif c['type'] == 1 and c['subType'] == 10:
                    porn_2 = int(c['probability'] * 500)
            return { 'code': 0, 'msg': 'Success', 'value': max(porn_0,porn_1,porn_2) }

        else:
            return { 'code': -1, 'msg': 'API Error' }


    except FileNotFoundError:
        return { 'code': -1, 'msg': 'File not found' }

class PicListener:
    def __init__(self):
        self.on = {}
        self.count = {}
        self.timeout = {}

    def get_on_off_status(self, gid):
        return self.on[gid] if self.on.get(gid) is not None else False

    def turn_on(self, gid, uid):
        self.on[gid] = uid
        self.timeout[gid] = datetime.now()+timedelta(seconds=SEARCH_TIMEOUT)
        self.count[gid] = 0

    def turn_off(self, gid):
        self.on[gid] = None
        self.count[gid] = None
        self.timeout[gid] = None

    def count_plus(self, gid):
        self.count[gid] += 1

pls = PicListener()

@sv.on_prefix(('打分','评分'))
async def setu_score(bot,ev: CQEvent):
    uid = ev.user_id
    gid = ev.group_id
    msg_id = ev.message_id
    if not _nlmt.check(uid):
        await bot.send(ev, EXCEED_NOTICE, at_sender=True)
        return
    if not _flmt.check(uid):
        await bot.send(ev, f'您冲的太快了,{round(_flmt.left_time(uid))}秒后再来吧', at_sender=True)
        return
    ret = re.search(r"\[CQ:image,file=(.*),url=(.*)\]", str(ev.message))
    if not ret:
        if pls.get_on_off_status(gid):
            if uid == pls.on[gid]:
                await bot.finish(ev, f"您已经在打分模式下啦！\n如想退出打分模式请发送“退出打分”~")
            else:
                await bot.finish(ev, f"本群[CQ:at,qq={pls.on[gid]}]正在打分，请耐心等待~")
        pls.turn_on(gid, uid)
        await bot.send(ev, f"了解～请发送图片吧！\n如想退出打分模式请发送“退出打分”")
        await sleep(30)
        ct = 0
        while pls.get_on_off_status(gid):
            if datetime.now() < pls.timeout[gid] and ct<10:
                await sleep(30)
                if ct != pls.count[gid]:
                    ct = pls.count[gid]
                    pls.timeout[gid] = datetime.now()+timedelta(seconds=30)
            else:
                await bot.send(ev, f"[CQ:at,qq={pls.on[gid]}] 由于超时，已为您自动退出打分模式，以后要记得说“退出打分”来退出打分模式噢~")
                pls.turn_off(ev.group_id)
                return
        return
    await bot.send(ev,'打分中...')
    file = ret.group(1)
    url = ret.group(2)
    #↓如果你想下载图片到本地的话去掉注释↓
    #下载路径是你的go-cqhttp/data/cache
    #await get_bot().get_image(file=file)
    porn = await porn_pic_index(url)
    if porn['code'] == 0:
        score = porn['value']
    else:
        code = porn['code']
        err = porn['msg']
        await bot.send(ev,f'错误:{code}\n{err}')
        return
    if reply is False:
        await bot.send(ev,str(MessageSegment.image(url)+f'\n色图评分:{score}'))
    else:
        await bot.send(ev,MessageSegment.reply(msg_id) + f'色图评分:{score}')
    _flmt.start_cd(uid)
    _nlmt.increase(uid)

@sv.on_message('group')
async def picmessage(bot, ev: CQEvent):
    uid = ev.user_id
    msg_id = ev.message_id
    ret = re.search(r"\[CQ:at,qq=(\d*)\]", str(ev.message))
    atcheck = False
    batchcheck = False
    if ret:
        if int(ret.group(1)) == int(ev.self_id):
            atcheck = True
    if pls.get_on_off_status(ev.group_id):
        if int(pls.on[ev.group_id]) == int(ev.user_id):
            batchcheck = True
    if not(batchcheck or atcheck):
        return
    
    ret = re.search(r"\[CQ:image,file=(.*)?,url=(.*)\]", str(ev.message))
    if not ret:
        return
    await bot.send(ev,'打分中...')
    file= ret.group(1)
    url = ret.group(2)
    #↓如果你想下载图片到本地的话去掉注释↓
    #下载路径是你的go-cqhttp/data/cache
    #await get_bot().get_image(file=file)
    porn = await porn_pic_index(url)
    if porn['code'] == 0:
        score = porn['value']
    else:
        code = porn['code']
        err = porn['msg']
        await bot.send(ev,f'错误:{code}\n{err}')
        return
    if reply is False:
        await bot.send(ev,str(MessageSegment.image(url)+f'\n色图评分:{score}'))
    else:
        await bot.send(ev,MessageSegment.reply(msg_id) + f'色图评分:{score}')
    pls.turn_off(ev.group_id)
    _flmt.start_cd(uid)
    _nlmt.increase(uid)

@sv.on_fullmatch('退出打分')
async def thanks(bot, ev: CQEvent):
    if pls.get_on_off_status(ev.group_id):
        if pls.on[ev.group_id]!=ev.user_id:
            await bot.send(ev, '不能替别人退出打分哦～')
            return
        pls.turn_off(ev.group_id)
        await bot.send(ev, '已退出')
        return
    await bot.send(ev, 'にゃ～')