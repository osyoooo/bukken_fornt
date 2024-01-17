import requests
import pandas as pd
import time
from datetime import datetime
import gspread
from gspread_dataframe import set_with_dataframe
import os
import json
import streamlit as st
import pydeck as pdk
from urllib.request import urlopen #jsonファイル形式で取得するアニメーションファイルをアプリに表示する
from streamlit_option_menu import option_menu


# スプレッドシートにアクセス
gc = gspread.service_account()
spreadsheet = gc.open_by_key('1R191trRqSI7ukjSUv_ZtWCmt57ve-EntXsLS6161SUM')


# //////////////////  関数

# シートのデータをDataFrameに変換する関数
def get_dataframe_from_sheet(spreadsheet, sheet_name):
    worksheet = spreadsheet.worksheet(sheet_name)
    data = worksheet.get_all_values()
    return pd.DataFrame(data[1:], columns=data[0])

# 新規登録フォームの内容をSpreadsheetに送る
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

# //////////////////  データベース系

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

if selected == "物件検索":
    st.write("物件検索用のページ")



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