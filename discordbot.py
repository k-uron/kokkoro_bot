#coding:utf-8
import requests
import discord
import re
import os
from sprd import spreadsheet
import json

# read token
if os.path.exists("./token") == True:
    TOKEN_FILE=open("./token","r")
    TOKEN=TOKEN_FILE.read().replace('\n','')
else:
    TOKEN=os.environ["DISCORD_TOKEN"]

text_channel=None
client = discord.Client()
gc = spreadsheet.__get_gc()

@client.event
async def on_ready():
    print('')

def message_start_comp(msg):
    if msg.startswith('/おはよう'):
        return True
    if msg == '/kokkoro':
        return True
    return False

def message_fin_comp(msg):
    if msg.startswith('/おやすみ'):
        return True
    if msg == '/kokkoro sleep':
        return True
    return False

async def show_help(message):
    await message.channel.send('[/kokkoro] コッコロBotが起動します')
    await message.channel.send('[/kokkoro sleep] コッコロBotが停止します')

async def show_stat(message):
    global text_channel
    if text_channel == None:
        await message.channel.send("主さま、読み上げは行っておりませんよ")
        return
    await message.channel.send("主さま、"+text_channel.name+"でございます")

def download_img(url, file_name):
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(file_name, 'wb') as f:
            f.write(r.content)

def member_search(message,name):
    for m in message.guild.members:
        if m.name.find(name) != -1:
            return m
        if m.nick is not None and m.nick.find(name) != -1:
            return m
    return None

#botに対してmentionがあったか
#またworldが含まれているか
def check_mention(message,word):
    global client
    my_mention = False
    for user in message.mentions:
        if user == client.user: 
            my_mention = True

    if my_mention == False:
        return None
    # <>で囲まれていて自信に充てられていたら反応する
    find = message.content.split(">")
    if len(find) < 2:
        print("error not split "+message.content)
        return None
    # 文字数少なすぎ
    if len(find[1]) < 2:
        return None

    return find[1] if word in find[1] else None

async def boss_mention(message,boss_name):
    print("boss_mention:"+message.content)
    userlist = spreadsheet.next_attack_member(boss_name)
    if userlist is None:
        await message.channel.send("sheetがありませんよ。主さま、名前の確認をしてくださいね")
        return False
    await message.channel.send("ともあれ"+boss_name+"を討伐するのですね")
    #await message.channel.send("@everyone "+boss_name+"に入りましたよ")
    if len(userlist) < 1:
        await message.channel.send("予約している方が1人も見つかりませんでしたよ")
        return False
    # name,damage,ra
    t = userlist[0].split(",")
    await message.channel.send(t[2]+"周目の討伐です")
    total_damage = 0
    for u in userlist:
        user_datas = u.split(",")
        name=user_datas[0]
        total_damage+=int(user_datas[1])
        member=member_search(message,name)
        if member is None:
            await message.channel.send("はて?"+name+"さまが見つかりませんね。お名前を変更なさったのでしょうか？")
            continue
        reply = f'{member.mention}'
        await message.channel.send(reply+"さま出番ですよ。頑張ってくださいまし")
    await message.channel.send("トータルで"+str(total_damage)+"万のダメージ量になるようです！")
    return True

# messageには[予約]等が期待される
def check_reserve_chennel(message):
    # boss_chennelか
    if message.channel is None:
        return None

    boss_ch_pattern = message.channel.name
    if "boss_" not in boss_ch_pattern:
        return None
       
    boss_name = boss_ch_pattern.split("boss_")[1]
    if "予約" not in message.content:
        return None

    # 予約1人目とか入れるのはなしにする？
    damage = re.sub(r'\D', '',message.content) # d only
    # ダメージ0とか?
    if len(damage) < 2:
        return None

    member = message.author
    name = member.name
    if member.nick is not None:
        name = member.nick

    return boss_name+","+name+","+damage

# 予約を行う
async def reserve_attacker(message,reserve_bundle):
    rb = reserve_bundle.split(",")
    boss_name =rb[0]
    user_name =rb[1]
    damage =int(rb[2])
    await message.channel.send(boss_name+"に予約でございますね")
    # 予約処理
    result = spreadsheet.reserve_attack_member(boss_name,user_name,damage)
    if result == -1:
        await message.channel.send("sheetがないです・・・")
        return
    elif result == -2:
        await message.channel.send(user_name+"という方はおりませんでした。")
        return
    elif result == -3:
        await message.channel.send("すみません、主さま満員でございます。(bossのhpを超えている) ")
        await message.channel.send("周回をまたぐ場合は手動にてご予約をお願いいたします")
        await message.channel.send("下記の主さまがご予約中でございます")
        result = spreadsheet.next_attack_member(boss_name)
    else:
        await message.channel.send("予約が出来ました。下記の主さまがご予約中です")

    for user in result:
        ud = user.split(",")
        name=ud[0]
        damage=ud[1]
        ra=ud[2]
        await message.channel.send(name+"さま "+damage+"万 "+ra+"周")

# messageには[予約中止]等が期待される
def check_reserve_cancel_chennel(message):
    # boss_chennelか
    if message.channel is None:
        return None

    boss_ch_pattern = message.channel.name
    if "boss_" not in boss_ch_pattern:
        return None
       
    boss_name = boss_ch_pattern.split("boss_")[1]
    if "予約中止" not in message.content:
        return None

    member = message.author
    name = member.name
    if member.nick is not None:
        name = member.nick
    return boss_name+","+name

# 予約をcancel
async def reserve_cancel_attacker(message,reserve_bundle):
    rb = reserve_bundle.split(",")
    boss_name =rb[0]
    user_name =rb[1]
    await message.channel.send(boss_name+"から予約中止でございますね")
    # 予約中止処理
    result = spreadsheet.cancel_attack_member(boss_name,user_name)
    if result == -1:
        await message.channel.send("sheetが見つかりませんでした・・・お名前の確認をお願いします")
        return
    elif result == -2:
        await message.channel.send(user_name+"という方はおりませんでした。")
        return
    elif result == -3:
        await message.channel.send(user_name+"さまはご登録なされていないようです")
    else:
        await message.channel.send("下記の主さまがご予約中です")

        
    result = spreadsheet.next_attack_member(boss_name)
    for user in result:
        ud = user.split(",")
        name=ud[0]
        damage=ud[1]
        ra=ud[2]
        await message.channel.send(name+"さま "+damage+"万 "+ra+"周")

# =================================================================
# おわり処理　
# =================================================================
# messageには[おわり]or[おわりPT]が期待される
def check_reserve_finish_chennel(message):
    # boss_chennelか
    if message.channel is None:
        return None

    boss_ch_pattern = message.channel.name
    if "boss_" not in boss_ch_pattern:
        return None
    boss_name = boss_ch_pattern.split("boss_")[1]

    fin = 0
    pt_num = -1
    if "おわり" == message.content:
        fin = 1
    elif message.content.find("おわり") != -1:
        pt_data = message.content.split("おわり")[1]
        if pt_data.find("PT") != -1:
            pt_num = pt_data.split("PT")[1]
        if pt_data.find("pt") != -1:
            pt_num = pt_data.split("pt")[1]
        if pt_data.find("Pt") != -1:
            pt_num = pt_data.split("Pt")[1]
        # pt numが1-3か確認
        ipt_num = int(pt_num)
        if (1 <= ipt_num and ipt_num <= 3):
            fin = 2
        else:
            fin = 0
    else:
        fin = 0

    # 一致なし
    if fin == 0:
        return None

    member = message.author
    name = member.name
    if member.nick is not None:
        name = member.nick
    return boss_name+","+name+","+str(pt_num)

# 予約を遂行した
async def reserve_finish_attacker_internal(message,bundle):
    rb = bundle.split(",")
    boss_name =rb[0]
    user_name =rb[1]
    pt_num =rb[2]
    await message.channel.send(boss_name+"への攻撃を完了したのですね")
    # 予約削除処理
    result = spreadsheet.cancel_attack_member(boss_name,user_name)
    if result < 0:
        return result
    else:
        # 正常終了の際はPTの確認をする
        if( int(pt_num) == -1 ):
            await message.channel.send(user_name+"さま凸記入おわすれになりませんよう、ご注意くださいませ。")
        else:
            result = spreadsheet.upd_pt_convex(user_name,pt_num)
            if result < 0:
                return result
            await message.channel.send(user_name+"さまお疲れ様でございます。PT"+str(result)+"に記入しました")
        return 0
    
# 予約を遂行した
async def reserve_finish_attacker(message,bundle):
    rb = bundle.split(",")
    boss_name =rb[0]
    user_name =rb[1]
    result = await reserve_finish_attacker_internal(message,bundle)
    if result == -1:
        await message.channel.send("sheetが見つかりませんでした・・・お名前の確認をお願いします")
        return
    elif result == -2:
        await message.channel.send(user_name+"という方はおりませんでした。")
        return
    elif result == -3:
        await message.channel.send("主さまはご登録なされていないようです")

    
    next_atk = spreadsheet.next_attack_member(boss_name)
    if len(next_atk) <= 0:
        return
    await message.channel.send("残りは下記の主さまがいらっしゃいます")
    for user in next_atk:
        ud = user.split(",")
        name=ud[0]
        damage=ud[1]
        ra=ud[2]
        await message.channel.send(name+"さま "+damage+"万 "+ra+"周")
# =================================================================
# 討伐完了
# =================================================================
# messageには[周目討伐]が期待される
def check_finish_round_in_bossch(message):
    # boss_chennelか
    if message.channel is None:
        return None

    boss_ch_pattern = message.channel.name
    if "boss_" not in boss_ch_pattern:
        return None
    boss_name = boss_ch_pattern.split("boss_")[1]

    if message.content.find("周目討伐") == -1:
        return None
    
    fin_round = message.content.split("周目討伐")[0]
    return boss_name+","+fin_round

# 討伐完了した
async def finish_round_attacker(message,bundle):
    rb = bundle.split(",")
    boss_name =rb[0]
    fin_round =rb[1]
    await message.channel.send(fin_round+"周目"+boss_name+"の討伐が完了したのですね")
    # round clear処理
    result = spreadsheet.clear_round_and_countup(boss_name,fin_round)
    result_user = result[0]
    result_round = result[1]
    if len(result_user) <= 0:
        await message.channel.send("予約している人はおりませんでした。")
    else:
        for user_name in result_user:
            await message.channel.send(user_name +"さまの予約を消しました ")

    if result_round is not None:
        await message.channel.send("次は"+str(result_round)+"周目でございます。")
# =================================================================
# spred sheet更新
# =================================================================
async def update_gss(message):
    if "/gss" not in message.content:
        return False

    words = message.content.split("/gss")
    # url返却
    if(len(words) <= 1 or len(words[1]) < 2):
        r=spreadsheet.get_url()
        await message.channel.send("現在のurlは下記でございます。\n"+r)
        return True

    if "/gssreload" not in message.content:
        return False

    r=spreadsheet.reload_url()
    if r is None:
        await message.channel.send("urlが変更できませんでした")
        return True
    await message.channel.send("urlを下記に変更いたしました\n"+r[1])
    await message.channel.send("古いurlは下記にございます\n"+r[0])
    return True

# =================================================================
# recv message
# =================================================================
# メッセージ受信時に動作する処理
@client.event
async def on_message(message):
    global text_channel
    if message.author.bot:
        return
    if message.content == '/help':
        await show_help(message)
        return
    if message.content == '/stat':
        await show_stat(message)
        return
    if message.content == '/test':
        x = prkn_img.start_template_match("./pr_input2.PNG")
        await message.channel.send('主さまテストですね')
        await message.channel.send(x)
        return
    # メンバーのリストを取得して表示
    if message.content == '/memb':
        await message.channel.send('主さまテストですね')
        for m in message.guild.members:
            reply = f'{m.mention}'
            await message.channel.send(reply)
        return
    if await update_gss(message):
        return
    if message.content == '/gssxxxxx':
        download_img("http://drive.google.com/uc?export=view&id=12Cyvx-B_WD43JLOq47e3qEmqeYkteuZK","up.png")
        await message.channel.send('主さまスプレッドシートのチェックですね')
        await message.channel.send("http://drive.google.com/uc?export=view&id=12Cyvx-B_WD43JLOq47e3qEmqeYkteuZK")
        return
    # 予約キャンセル
    cancel_bundle=check_reserve_cancel_chennel(message)
    if cancel_bundle is not None:
        await reserve_cancel_attacker(message,cancel_bundle)
        return
    # 予約finish
    finish_bundle=check_reserve_finish_chennel(message)
    if finish_bundle is not None:
        await reserve_finish_attacker(message,finish_bundle)
        return
    #予約メンション
    reserve_bundle=check_reserve_chennel(message)
    if reserve_bundle is not None:
        await reserve_attacker(message,reserve_bundle)
        return
    # 討伐完了
    fr_bundle = check_finish_round_in_bossch(message)
    if fr_bundle is not None:
        await finish_round_attacker(message,fr_bundle)
        return
    # ボスメンション
    boss_name=check_mention(message,"")
    if boss_name is not None:
        await boss_mention(message,boss_name)
        return

    # 読み上げ
    if message_start_comp(message.content):
        text_channel=message.channel
        save_text_channel_name(text_channel.name)
        await text_channel.send('主さま、こちらのチャンネルで入退室の読み上げを開始いたします')
    if message_fin_comp(message.content):
        await message.channel.send('主さま、入退室の読み上げを終了いたします')
        text_channel=None


  #  if len(message.attachments) >= 1:
  #      download_img(message.attachments[0].url,"up.png")
  #      x = prkn_img.start_template_match("./up.png")
  #      await message.channel.send("主さま、画像の解析がおわりました")
  #      await message.channel.send(x)



def save_text_channel_name(channel_name:str):
    env_list = spreadsheet.get_env_list()
    env_list["chat_channel_name"] = channel_name
    spreadsheet.save_setting_url(env_list)

def update_text_channel():
    global text_channel
    channel_name = spreadsheet.get_env_list().get("chat_channel_name")
    channels = client.get_all_channels()
    for channel in channels:
        if channel_name == channel.name:
            return channel
    return None

# =================================================================
# voice chat 
# =================================================================
@client.event
async def on_voice_state_update(member, before, after):
    global text_channel
    name = member.name
    if member.nick is not None:
        name = member.nick

    if text_channel is None:
        text_channel = update_text_channel()
        if text_channel is None:
            return

    if before.channel == after.channel:
        return
    if after.channel is not None:
        await text_channel.send(name+'さまが'+after.channel.name+'に入室しました')
    if after.channel is None:
        await text_channel.send(name+'さまが退室しました')



# Botの起動とDiscordサーバーへの接続
client.run(TOKEN)
