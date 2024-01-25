import requests
import pandas as pd
import time
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import pydeck as pdk
from urllib.request import urlopen #jsonファイル形式で取得するアニメーションファイルをアプリに表示する
from streamlit_option_menu import option_menu
import numpy as np
import folium
import streamlit as st
from streamlit_folium import st_folium

# //////////////////  関数

# 指定されたスプレッドシートとシート名からDataFrameを作成する関数
def get_dataframe_from_sheet(spreadsheet, sheet_name):
    worksheet = spreadsheet.worksheet(sheet_name)
    data = worksheet.get_all_values()
    return pd.DataFrame(data[1:], columns=data[0])


# 新規登録フォームの内容をSpに送る
def form_upload(email, password, first_name, last_name, tel, spreadsheet):
    keys = email + password
    new_data = {
        "メールアドレス": email,
        "パスワード": password,
        "氏": first_name,
        "名": last_name,
        "TEL": tel,
        "keys": keys,
    }
    try:
        worksheet = spreadsheet.worksheet('login')
        last_row = len(worksheet.get_all_values()) # スプレッドシートの最後の行を取得
        worksheet.append_row(list(new_data.values())) # 新しいデータを追加
        st.success("フォームが送信されました")
        initialize_session_state(variables) #正常に送信された場合に入力されたフォームの内容を削除する
    except Exception as e:
        st.error(f"エラーが発生しました: {e}")

# 新規登録フォームの内容を初期化する関数
def initialize_session_state(variables):
    for var in variables:
        st.session_state[var] = st.session_state.get(var, '')

# 物件データを読み込み、前処理を行う関数
def load_property_data():
    df = get_dataframe_from_sheet(spreadsheet, 'cl2')

    # データ型の変換とNaN値の処理
    df['専有面積'] = pd.to_numeric(df['専有面積'], errors='coerce')
    df['家賃'] = pd.to_numeric(df['家賃'], errors='coerce')
    df['築年整数'] = pd.to_numeric(df['築年整数'], errors='coerce')
    df['基準階'] = pd.to_numeric(df['基準階'], errors='coerce')
    df['建物種別'] = df['建物種別'].astype(str)
    df['最寄り駅1徒歩時間'] = pd.to_numeric(df['最寄り駅1徒歩時間'], errors='coerce')
    df['Lat'] = pd.to_numeric(df['Lat'], errors='coerce')
    df['Lng'] = pd.to_numeric(df['Lng'], errors='coerce')

    # NaN値を削除
    df.dropna(subset=['専有面積', '家賃', '築年整数', '基準階', '建物種別', '最寄り駅1徒歩時間', 'Lat', 'Lng'], inplace=True)
    
    return df

# 地図のマーカーに物件情報を表示する関数
def create_property_map(df):
    if not df.empty:
        m = folium.Map(
            location=[35.574977, 139.709259],
            zoom_start=11,
        )
        for i, row in df.iterrows():
            pop = (f"<b>物件名:</b> {row['name']}<br>"
                   f"<b>家賃:</b> {row['家賃']}<br>"
                   f"<b>間取り:</b> {row['間取り']}<br>"
                   f"<b>面積:</b> {row['専有面積']}<br>"
                   f"<b>築年数:</b> {row['築年整数']}<br>"
                   f"<img src='{row['外観画像カラム']}' width='120px'><br>"
                   f"<img src='{row['間取り画像カラム']}' width='120px'><br>"
                   f"<a href='{row['URL']}' target='_blank'>物件詳細</a>")
            folium.Marker(
                location=[row['Lat'], row['Lng']],
                popup=folium.Popup(pop, max_width=300),
                icon=folium.Icon(icon="home", icon_color="white", color="red")
            ).add_to(m)
        return m
    else:
        return folium.Map(location=[35.574977, 139.709259], zoom_start=6, tiles="Stamen Terrain")

#　検索結果をGAS用のスプシに送る関数
def send_url_to_gas_sheet(url, spreadsheet):
    # 'gas' シートを取得
    gas_sheet = spreadsheet.worksheet('gas')

    # スプレッドシートの最後の行にURLを追加
    gas_sheet.append_row([url])

# //////////////////  データベース系

# StreamlitのSecretsから情報を取得
gcp_service_account_info = st.secrets["gcp_service_account"]

# GCPサービスアカウントで認証
credentials = Credentials.from_service_account_info(gcp_service_account_info, 
                                                    scopes=['https://www.googleapis.com/auth/spreadsheets',
                                                            'https://www.googleapis.com/auth/drive'])
gc = gspread.authorize(credentials)

# スプレッドシートのIDを指定して開く
spreadsheet = gc.open_by_key("1R191trRqSI7ukjSUv_ZtWCmt57ve-EntXsLS6161SUM")

# シートのデータをDataFrameに変換
df_login = get_dataframe_from_sheet(spreadsheet, 'login')


# //////////////////  streamlitの設定選択された項目に基づいて表示を切り替え

# セッション状態の初期化 このコードはログインアウトによって分岐を行うコード群の一番上にしないと正しく初期化されない
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False


# サイドバーにオプションメニューを追加
with st.sidebar:
    if st.session_state['logged_in']:
        # ログイン中のメニュー
        menu_options = ["物件検索", "ログイン・マイページ"]
        menu_icons = ["house", "person"]
    else:
        # ログインしていない時のメニュー
        menu_options = ["物件検索", "ログイン・マイページ", "新規登録"]
        menu_icons = ["house", "person", "info-circle"]

    selected = option_menu(
        menu_title="Main Menu",
        options=menu_options,
        icons=menu_icons,
        default_index=0,
    )

    # ユーザー情報の表示
    if st.session_state['logged_in']:
        user_row = df_login[df_login['keys'] == st.session_state['email'] + st.session_state['password']]
        user_info = user_row.iloc[0]
        st.write(f"メールアドレス: {user_info['メールアドレス']}")
        st.write(f"氏: {user_info['氏']}")
        st.write(f"名: {user_info['名']}")
        st.write(f"TEL: {user_info['TEL']}")
        if st.button('ログアウト', key='sidebar_logout'):
            st.session_state['logged_in'] = False
            st.session_state['email'] = ''
            st.session_state['password'] = ''
            st.experimental_rerun()


# //////////////////  物件検索のメニュー

# 物件検索のメニュー
if selected == "物件検索":
    st.write("条件を選択して検索ボタンを押してください")

    # セッション状態で物件データを管理
    if 'df_properties' not in st.session_state:
        st.session_state['df_properties'] = load_property_data()
    if 'filtered_properties' not in st.session_state:
        st.session_state['filtered_properties'] = pd.DataFrame()

    df_properties = st.session_state['df_properties']

    # 絞り込み条件のオプションを取得
    layout_options = df_properties['間取り'].unique()
    building_type_options = df_properties['建物種別'].unique()
    direction_options = df_properties['向き'].unique()
    floor_type_options = df_properties['層分類'].unique()
    
    # 絞り込み条件の入力（デフォルトで全選択）
    col1, col2, col3 = st.columns(3)

    with col1:
        building_type = st.multiselect("建物種別", options=building_type_options, default=building_type_options)
        layout_type = st.multiselect("間取り", options=layout_options, default=layout_options)

    with col2:
        floor_type = st.multiselect("物件がある階層", options=floor_type_options, default=floor_type_options)
        direction = st.multiselect("向き", options=direction_options, default=direction_options)

    with col3:
        rent = st.slider("家賃", 0, 50, (0, 50))
        built_year = st.slider("築年数", 0, 50, (0, 50))
        area = st.slider("専有面積", 0, 100, (0, 100))
        base_floor = st.slider("物件の階数", 0, 50, (0, 50))
        walk_time_to_station = st.slider("最寄り駅1徒歩時間", 0, 30, (0, 30))

    # 検索ボタン
    if st.button('検索'):
        # フィルタリング処理
        st.session_state['filtered_properties'] = df_properties[
            df_properties['間取り'].isin(layout_type) &
            df_properties['築年整数'].between(*built_year) &
            df_properties['建物種別'].isin(building_type) &
            df_properties['専有面積'].between(*area) &
            df_properties['向き'].isin(direction) &
            df_properties['家賃'].between(*rent) &
            df_properties['基準階'].between(*base_floor) &
            df_properties['層分類'].isin(floor_type) &
            df_properties['最寄り駅1徒歩時間'].between(*walk_time_to_station)
        ]

    # 地図とテーブルの表示
    if not st.session_state['filtered_properties'].empty:
        num_results = len(st.session_state['filtered_properties'])
        st.write(f"検索結果: {num_results}件の物件が見つかりました。")
        property_map = create_property_map(st.session_state['filtered_properties'])
        st_data = st_folium(property_map, width=800, height=700)
        st.write("検索結果のテーブル:")
        st.dataframe(st.session_state['filtered_properties'])

        st.write(登録済みのユーザーは物件URLを関係者にメールで共有できます)
        # URL送信ボタン
        if st.button('送信'):
            # 検索結果テーブルからURLを取得
            for index, row in st.session_state['filtered_properties'].iterrows():
                gas_url = row['URL']
        
                # URLをスプレッドシートに送信
                send_url_to_gas_sheet(gas_url, spreadsheet)
        
            st.success('URLが送信されました')


# //////////////////  ログイン・マイページの項目

if selected == "ログイン・マイページ":
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if st.session_state['logged_in']:
        st.title('My Page・ログイン中')
        if st.button('ログアウト'):
            st.session_state['logged_in'] = False
            st.session_state['email'] = ''
            st.session_state['password'] = ''
            st.experimental_rerun()
    else:
        st.title('My Page')
        with st.form(key='login_form'):
            email = st.text_input("メールアドレス", value=st.session_state['email'])
            password = st.text_input("パスワード", type='password', value=st.session_state['password'])
            submit_button = st.form_submit_button("ログイン")

            if submit_button:
                my_key = email + password
                user_row = df_login[df_login['keys'] == my_key]

                if not user_row.empty:
                    st.session_state['logged_in'] = True
                    st.session_state['email'] = email
                    st.session_state['password'] = password
                    st.experimental_rerun()
                else:
                    st.write("メールアドレスかパスワードが間違っています")

    if st.session_state['logged_in']:
        user_row = df_login[df_login['keys'] == st.session_state['email'] + st.session_state['password']]
        user_info = user_row.iloc[0]
        st.write(f"メールアドレス: {user_info['メールアドレス']}")
        st.write(f"氏: {user_info['氏']}")
        st.write(f"名: {user_info['名']}")
        st.write(f"TEL: {user_info['TEL']}")


# ////////////////// 新規登録ページの項目

# 初期化する変数のリスト
variables = ['email', 'password', 'first_name', 'last_name', 'tel', 'keys']

# セッション状態の初期化を行う関数を呼び出し
initialize_session_state(variables)

# 入力フォーム
if selected == "新規登録":
    with st.form(key='new_user_form'):
        email = st.text_input("メールアドレス", value=st.session_state['email'])
        password = st.text_input("パスワード", type='password', value=st.session_state['password'])
        first_name = st.text_input("氏", value=st.session_state['first_name'])
        last_name = st.text_input("名", value=st.session_state['last_name'])
        tel = st.text_input("TEL", value=st.session_state['tel'])
        submit_button = st.form_submit_button("送信")

        if submit_button:
            if email not in df_login['メールアドレス'].values:
                form_upload(email, password, first_name, last_name, tel, spreadsheet)
            else:
                st.write("すでにそのメールアドレスは登録されています")

# ////////////////// EOE
