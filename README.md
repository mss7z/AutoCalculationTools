# 自動計算環境のコード

自動計算環境のコードです．
231227時点では最低限しか載せてません．

# ファイル構成

## 本科_Feko用
本科の時の研究に用いた自動計算環境のプログラムです。
Fekoのモデルは自分が作ったものベースでないので申し訳ありませんが載せられません。

### 2.4_CadFekoの自働化
CadFekoに使うLuaスクリプトが入っています

### 2.5_計算管理プログラム
計算管理プログラムが入っています。
計算用PCにSSHでログインし計算を実行してくれます。
専攻科_内政FDTDプログラム用が後継で、改良されていますが、Feko用の設定になっていないため、古いバージョンであるv19を入れています

### 2.6_計算結果表示プログラム
RunFekoが出力したファイルを読み取って、グラフにするプログラムです。

## 専攻科_内製FDTDプログラム用
専攻科の時の研究に用いた自動計算環境のプログラムです。

### runMulti_v24_vPublic.py
管理プログラムの本体です．
SSHのホスト名とパスワードを伏字にしています．

