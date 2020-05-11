import gspread 
from oauth2client.service_account import ServiceAccountCredentials
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8') # UTF-8に
import json
import os.path
import re
import base64

#================================
#define
SETTINGS_URL="https://docs.google.com/spreadsheets/d/1Xxb6OgdY_LqdpV7SfmqyfX_IdSGry0t7-y-sXeHWFLE/edit?usp=sharing"
SETTINGS_SHEET_NAME="settings"
SETTINGS_ENV_LIMIT=20 
WORKBOOK_URL=""
cell_ROUNDABOUT='B1' #周回数
cell_BOSS_HP='F2'
#cell_NAMELIST_TOP_BOTTOM='L5:O34' #予約範囲
cell_NAMELIST_TOP_BOTTOM='n5:q34' #予約範囲
cell_USERLIST='B5:B34' #メンバーリスト
cell_RESERVELIST='F5:I34' #予約リスト
PT_CONVEX_SHEET_NAME='凸記入用'
cell_PT_CONVEX_USERLIST='C3:C32' #メンバーリスト

cell_RANGE_NAME=0
cell_RANGE_DAMAGE=1
cell_RANGE_RA=3
#define
#================================

#================================
# global
path=os.path.dirname(__file__)+"/"
env_list = dict()


#================================
# private class

class AttackInfo:
    name = ""
    damage_str = ""
    ra_str = ""
    def __init__(self,_name,_damage,_ra):
        self.name = _name
        self.damage_str = _damage
        self.ra_str = _ra

    def get_string(self):
        return self.name+","+self.damage_str+","+self.ra_str

    def equal_ra(self,ra_value):
        # 周回数
        if len(self.ra_str) < 1 or ra_value != int(self.ra_str):
            return False
        return True

#================================
# private func

def __get_gc():
    auth_path='.gspread'
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    if os.path.exists(path+auth_path) == True:
        #dev
        credentials = ServiceAccountCredentials.from_json_keyfile_name(path+auth_path+'/gspread-sample-2bf9fcc59d37.json', scope)
    else:
        #release
        base64_key=os.environ["SPREAD_SHEET_KEY"]
        json_key=json.loads(base64.b64decode(base64_key).decode())
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_key,scope)
    
    return gspread.authorize(credentials)

def search_sheet(sheet_list,search_name):
    for w in sheet_list:
        if w.title == search_name:
            return w
    return None

def create_member_list(wks):
    #メンバー取得
    cell_list = wks.range(cell_NAMELIST_TOP_BOTTOM)
    c=4
    r_member_list = []
    for i in range(0,20):
        name = cell_list[cell_RANGE_NAME+i*c].value
        damage = cell_list[cell_RANGE_DAMAGE+i*c].value
        ra = cell_list[cell_RANGE_RA+i*c].value
        if name == "":
            continue
        ra=re.sub(r'\D', '',ra) # d only
        r_member_list.append(AttackInfo(name,damage,ra))
    return r_member_list

# 予約ダメージ合計
def calc_total_reserve_damage(wks,ra_value):
    member_list = create_member_list(wks)
    total = 0
    for member in member_list:
        # 周回数 check
        if member.equal_ra(ra_value)  == False:
            continue
        total += int(member.damage_str)
    return total

# 周回数をintで返す
def get_roundabout(wks:gspread.models.Worksheet):
    val = wks.acell(cell_ROUNDABOUT).value
    val = re.sub(r'\D', '',val) # d only
    return int(val) # type int

# 周回数をsetする
def set_roundabout(wks,round_num):
    wks.update_acell(cell_ROUNDABOUT,str(round_num))

# wksを返す
def setup(sheet_name):
    sheet_name=sheet_name.replace(" ", "")
    
    gc = __get_gc()
    try:
        workbook=gc.open_by_url(WORKBOOK_URL)
        worksheet_list = workbook.worksheets()
    except:
        return None
    return search_sheet(worksheet_list,sheet_name)

# 
def _next_attack_member(wks):
    #周回数
    #cell_ra_value = get_roundabout(wks)
    #メンバー取得
    member_list = create_member_list(wks)
    r_list = []
    ra_value = get_roundabout(wks)
    for member in member_list:
        # 周回数 check
        if member.equal_ra(ra_value)  == False:
            continue
        r_list.append(member.get_string())

    return r_list

# -1 not found boss
# -2 not found user
# -3 not reserve user   
# userの攻撃情報更新
def upd_attack_member_cell(wks,user_name:str,damage:str,ra_value:str):
    # ユーザーがいるかチェック
    cell_user_list = wks.range(cell_USERLIST)
    user_cell = None
    for cell in cell_user_list:
        if user_name in cell.value:
            user_cell = cell

    # 名前一致ユーザーなし
    if user_cell is None:
        return -2

    is_reserve = True
    if damage == 0:
        is_reserve = False

    col_sp_offset = 4 #sp1
    col_ra_offset = 7 #round about

    # 予約をいれるならhp check
    if is_reserve == True:
        # boss hp 取得
        boss_hp = int(wks.acell(cell_BOSS_HP).value)
        # トータルダメージの計算
        total_damage = calc_total_reserve_damage(wks,ra_value)
        if boss_hp < total_damage:
            return -3
    else:
        cell = wks.cell(user_cell.row,user_cell.col+col_sp_offset)
        if len(cell.value) <= 0:
            return -3

    # 登録/解除
    if is_reserve:
        wks.update_cell(user_cell.row,user_cell.col+col_sp_offset,damage)
    else:
        wks.update_cell(user_cell.row,user_cell.col+col_sp_offset,"")

    wks.update_cell(user_cell.row,user_cell.col+col_ra_offset,ra_value)
    return 0

# fin_round周目の攻撃情報を消す
def clear_round_member_cell(wks,fin_round):

    cell_list = wks.range(cell_RESERVELIST)
    c=4
    r_member_list = []
    upd_cells = []
    for i in range(0,30):
        sp_cell = cell_list[0+i*c]
        sp2_cell = cell_list[1+i*c]
        remark_cell = cell_list[2+i*c]
        round_num_cell = cell_list[3+i*c]
        if round_num_cell.value == "":
            continue
        if int(round_num_cell.value) != fin_round:
            continue

        # cell clear
        sp_cell.value = ""
        upd_cells.append(sp_cell)
        sp2_cell.value = ""
        upd_cells.append(sp2_cell)
        remark_cell.value = ""
        upd_cells.append(remark_cell)
        round_num_cell.value = ""
        upd_cells.append(round_num_cell)
    
        # 消したuserをlistで返す
        offset_name=-4
        name_cell = wks.cell(sp_cell.row,sp_cell.col+offset_name)
        r_member_list.append(name_cell.value)
        
    # bach update
    if len(upd_cells) > 0:
        wks.update_cells(upd_cells)
    return r_member_list

#================================
# api func

# 次回攻撃メンバーを配列で返す
def next_attack_member(boss_name):
    wks = setup(boss_name)
    if(wks == None):
        print("not found wks["+boss_name+"]")
        return None

    return _next_attack_member(wks)

# -1 not found boss
# -2 not found user
# -3 not reserve user
def reserve_attack_member(boss_name:str,user_name:str,damage:int):
    wks = setup(boss_name)
    if(wks == None):
        print("not found wks["+boss_name+"]")
        return -1

    #周回数
    ra_value = get_roundabout(wks)
    result = upd_attack_member_cell(wks,user_name,damage,ra_value)
    if result != 0:
        return result
    
    return _next_attack_member(wks)

# -1 not found boss
# -2 not found user
# -3 not reserve user
def cancel_attack_member(boss_name,user_name):
    wks = setup(boss_name)
    if(wks == None):
        print("not found wks["+boss_name+"]")
        return -1
    # cancel
    result = upd_attack_member_cell(wks,user_name,0,"")
    if result != 0:
        return result
    
    return 0
    #_next_attack_member(wks)


# -1 not found boss
# 周回数の情報を消し、消した周回数が現在の周回数と一致するなら+1する
def clear_round_and_countup(boss_name,fin_round):
    wks = setup(boss_name)
    if(wks == None):
        print("not found wks["+boss_name+"]")
        return [[],None]
    # clear
    result = clear_round_member_cell(wks,int(fin_round))
    # 周回数が一致しているなら+1する
    next_round = int(fin_round)+1
    if get_roundabout(wks) == int(fin_round):
        set_roundabout(wks,next_round)
        return [result,next_round]

    return [result,None]

# -2
# -1
# 指定PTの凸記入をする
def upd_pt_convex(user_name,pt_num):
    wks = setup(PT_CONVEX_SHEET_NAME)
    if(wks == None):
        print("not found wks["+PT_CONVEX_SHEET_NAME+"]")
        return -1

    # ユーザーがいるかチェック
    cell_user_list = wks.range(cell_PT_CONVEX_USERLIST)
    user_cell = None
    for cell in cell_user_list:
        if user_name in cell.value:
            user_cell = cell

    # 名前一致ユーザーなし
    if user_cell is None:
        return -2
    
    col_offset = 2+int(pt_num)
    wks.update_cell(user_cell.row,user_cell.col+col_offset,"PT"+str(pt_num))
    return int(pt_num)

#クラバトurlを返す
def get_url():
    return WORKBOOK_URL

# settingをロードする
def load_setting_url():
    gc = __get_gc()
    try:
        workbook=gc.open_by_url(SETTINGS_URL)
        worksheet_list = workbook.worksheets()
    except:
        return None
    wks = search_sheet(worksheet_list,SETTINGS_SHEET_NAME)
    load_env_list = wks.range('A1:B'+str(SETTINGS_ENV_LIMIT))
    c=2

    global env_list
    for i in range(0,SETTINGS_ENV_LIMIT):
        env_name = load_env_list[i*c].value
        env_data = load_env_list[1+i*c].value
        if env_name == "":
            continue
        print(env_name)
        env_list[env_name]=env_data

# settingをsaveする
def save_setting_url(new_env_list:dict):
    if new_env_list is None:
        return
    
    gc = __get_gc()
    try:
        workbook=gc.open_by_url(SETTINGS_URL)
        worksheet_list = workbook.worksheets()
    except:
        return
    wks = search_sheet(worksheet_list,SETTINGS_SHEET_NAME)

    count=1
    for k,v in new_env_list.items():
        wks.update_cell(count,1,k)
        wks.update_cell(count,2,v)
        count+=1

#  クラバトurlをリロードする
def reload_url():
    load_setting_url()
    if env_list["clanbattle_url"] is None:
        return None


    global WORKBOOK_URL
    old = WORKBOOK_URL
    WORKBOOK_URL = env_list["clanbattle_url"]
    return [old,WORKBOOK_URL]

def get_env_list():
    load_setting_url()
    global env_list
    return env_list

def main():
    load_setting_url()
    global env_list
    print(json.dumps(env_list))
    env_list["chat_channel_name"]=1222
    save_setting_url(env_list)

if __name__ == "__main__":
    main()
else:
    f=open(path+"workbook","r",encoding="utf-8")
    SETTINGS_URL=f.read().replace('\n','')
    reload_url()

