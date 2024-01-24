import requests
import pandas as pd
import time
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import streamlit as st
import pydeck as pdk
from urllib.request import urlopen #jsonファイル形式で取得するアニメーションファイルをアプリに表示する
from streamlit_option_menu import option_menu
import numpy as np

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


# 地図のピン（マーカー）に物件情報を表示する関数
def create_map(df):
    if not df.empty:
        view_state = pdk.ViewState(
            latitude=df['Lat'].mean(),
            longitude=df['Lng'].mean(),
            zoom=11,
            pitch=50,
        )

        layer = pdk.Layer(
            'ScatterplotLayer',
            data=df,
            get_position='[Lng, Lat]',
            get_color='[200, 30, 0, 160]',
            get_radius=100,
            pickable=True
        )

        tooltip = {
            "html": "<b>物件名:</b> {name}<br><b>家賃:</b> {家賃}<br><b>間取り:</b> {間取り}<br><b>面積:</b> {専有面積}<br><b>築年数:</b> {築年整数}",
            "style": {"backgroundColor": "steelblue", "color": "white"}
        }

        st.pydeck_chart(pdk.Deck(map_style='mapbox://styles/mapbox/light-v9', initial_view_state=view_state, layers=[layer], tooltip=tooltip))
    else:
        st.write("該当する物件はありません。")

# テーブルにチェックボックスを追加し、URLを格納する
def display_table_with_checkboxes(df):
    selected_urls = []
    for index, row in df.iterrows():
        if st.checkbox('', key=f"checkbox_{index}"):
            selected_urls.append(row['URL'])
    return selected_urls

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
    st.write("物件検索用のページ")
    
    # 物件データの読み込み
    df_properties = get_dataframe_from_sheet(spreadsheet, 'cleansing_suumo_bukken')
               
    # データタイプの変換とNaN値の処理
    df_properties['専有面積'] = pd.to_numeric(df_properties['専有面積'], errors='coerce')  # 数値型に変換、変換できない値はNaNにする
    df_properties.dropna(subset=['専有面積'], inplace=True)  # 専有面積がNaNの行を削除
    
    # 家賃のデータ型変換とNaN値の処理
    df_properties['家賃'] = pd.to_numeric(df_properties['家賃'], errors='coerce')  # 数値型に変換、変換できない値はNaNにする
    df_properties.dropna(subset=['家賃'], inplace=True)  # 家賃がNaNの行を削除
    
    # 築年整数のデータ型変換とNaN値の処理
    df_properties['築年整数'] = pd.to_numeric(df_properties['築年整数'], errors='coerce')  # 数値型に変換、変換できない値はNaNにする
    df_properties.dropna(subset=['築年整数'], inplace=True)  # 築年整数がNaNの行を削除
    
    # 基準階のデータ型変換とNaN値の処理
    df_properties['基準階'] = pd.to_numeric(df_properties['基準階'], errors='coerce')  # 数値型に変換、変換できない値はNaNにする
    df_properties.dropna(subset=['基準階'], inplace=True)  # 基準階がNaNの行を削除
    
    # 建物種別のデータ型変換とNaN値の処理
    df_properties['建物種別'] = df_properties['建物種別'].astype(str)  # 文字列型に変換
    df_properties['建物種別'].replace('nan', np.nan, inplace=True)  # 'nan' 文字列をNaN値に置き換え
    df_properties.dropna(subset=['建物種別'], inplace=True)  # 建物種別がNaNの行を削除
    
    # 最寄り駅1徒歩時間のデータ型変換とNaN値の処理
    df_properties['最寄り駅1徒歩時間'] = pd.to_numeric(df_properties['最寄り駅1徒歩時間'], errors='coerce')  # 数値型に変換、変換できない値はNaNにする
    df_properties.dropna(subset=['最寄り駅1徒歩時間'], inplace=True)  # 最寄り駅1徒歩時間がNaNの行を削除

    # データの前処理で 'Lat' と 'Lng' カラムを数値型に変換
    df_properties['Lat'] = pd.to_numeric(df_properties['Lat'], errors='coerce')
    df_properties['Lng'] = pd.to_numeric(df_properties['Lng'], errors='coerce')
    
    # NaN値を削除（もしくは他の方法で処理）
    df_properties.dropna(subset=['Lat', 'Lng'], inplace=True)


    # 絞り込み条件のオプションを取得
    layout_options = df_properties['間取り'].unique()
    building_type_options = df_properties['建物種別'].unique()
    direction_options = df_properties['向き'].unique()
    floor_type_options = df_properties['層分類'].unique()

    # 絞り込み条件の入力（デフォルトで全選択）
    col1, col2, col3 = st.columns(3)

    with col1:
        layout_type = st.multiselect("間取り", options=layout_options, default=layout_options)
        built_year = st.slider("築年整数", 0, 100, (0, 100))
        building_type = st.multiselect("建物種別", options=building_type_options, default=building_type_options)

    with col2:
        area = st.slider("専有面積", 0, 200, (0, 200))
        direction = st.multiselect("向き", options=direction_options, default=direction_options)
        rent = st.slider("家賃", 0, 1000000, (0, 1000000))

    with col3:
        base_floor = st.slider("基準階", 0, 50, (0, 50))
        floor_type = st.multiselect("層分類", options=floor_type_options, default=floor_type_options)
        walk_time_to_station = st.slider("最寄り駅1徒歩時間", 0, 60, (0, 60))

    # 検索ボタン
    if st.button('検索'):
        # フィルタリング
        filtered_properties = df_properties[
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

        # 結果の地図表示
        create_map(filtered_properties)

        # テーブル表示とURLの取得
        selected_urls = display_table_with_checkboxes(filtered_properties)
        
        # 選択されたURLの表示
        for url in selected_urls:
            st.write(url)


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
