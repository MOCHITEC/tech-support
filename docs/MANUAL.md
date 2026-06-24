# tech-support 構築マニュアル(ジュニアエンジニア向け)

このマニュアルは、**インフラやクラウドが初めての人でも、上から順にコピペすれば動かせる**ことを目標に書いています。専門用語にはそのつど短い説明をつけます。分からない単語が出てきたら、まず末尾の[用語集](#用語集)を見てください。

対象 OS は **Windows**、ターミナルは **PowerShell** を使います(スタートメニューで「PowerShell」と検索して起動)。

---

## 0. このプロジェクトは何をするもの?

ユーザーが「アプリのここがおかしい」と報告すると、

1. AI エージェントがその報告を**自動でテストに変換**し、
2. 原因を直す**コードの修正案(PR)を作り**、
3. **人間(IT 担当)が承認したときだけ**本番にリリースされ、
4. 報告した本人に「直りました」と通知が届く

——という「**ユーザーの声が CI/CD(自動テスト・自動デプロイの仕組み)に入る**」アプリです。

題材として「会議室予約アプリ」が入っていて、わざと 3 つのバグが仕込んであります。エージェントはこのバグを直す練習台にします。

全体像はリポジトリ直下の `PLAN.md` に書いてあります。

---

## 1. 作業の全体マップ

やることは大きく 3 段階です。**まずは段階 A だけで「動くアプリ」が手元で見られます。** 焦らず A から進めましょう。

| 段階 | 何をする | クラウド費用 | 所要時間 |
|---|---|---|---|
| **A. ローカルで動かす** | 自分の PC でアプリとテストを動かす | 無料 | 15 分 |
| **B. インフラを作る** | GCP(Google のクラウド)に置き場所を作る | 課金あり | 30〜40 分 |
| **C. デプロイ** | 作ったアプリをクラウドに載せる | 課金あり | (別マニュアル) |

> **GCP(ジーシーピー)** = Google Cloud Platform。Google が貸し出すサーバーやデータベースの集まり。使った分だけお金がかかります。

---

## 2. 段階 A:ローカルで動かす(まずこれ)

### A-1. ツールを入れる

PowerShell を開いて、次を 1 行ずつ実行します。

```powershell
# Git(ソースコードを取ってくる道具)
winget install Git.Git

# Python(このアプリを動かす言語)3.13 系
winget install Python.Python.3.13
```

> **winget(ウィンゲット)** = Windows 標準のアプリ自動インストーラ。`winget install ◯◯` で◯◯を入れられます。

入れ終わったら **PowerShell を一度閉じて開き直します**(新しいツールを認識させるため)。確認:

```powershell
git --version      # git version 2.xx と出れば OK
py --version       # Python 3.13.x と出れば OK
```

> ⚠️ Windows では `python` と打つと「Microsoft Store が開くだけの偽物」が動くことがあります。**このプロジェクトでは必ず `py` を使ってください。**

### A-2. ソースコードを取得する

```powershell
cd C:\
git clone https://github.com/MOCHITEC/tech-support.git
cd tech-support
```

> **clone(クローン)** = GitHub 上のコードを自分の PC に丸ごとコピーすること。

### A-3. 部品(ライブラリ)を入れる

このアプリ専用の「箱」を作って、その中に必要な部品を入れます。

```powershell
# .venv という専用の箱(仮想環境)を作る
py -m venv .venv

# 箱の中の Python を使って部品をインストール
.venv\Scripts\python -m pip install -r requirements.txt
```

> **仮想環境(.venv)** = このプロジェクト専用の Python 部品置き場。PC 全体を汚さずに済みます。
> **requirements.txt** = 必要な部品の一覧表。

### A-4. テストを動かして「壊れていない」ことを確認

```powershell
.venv\Scripts\python -m pytest -q
```

期待する表示:

```
...................................
35 passed in 8.xx s
```

> **pytest(パイテスト)** = 自動テストを実行する道具。`passed` が出れば全テスト合格です。
> 1 つでも `failed` が出たら、その下にエラー内容が表示されます。まずはそのメッセージを読みましょう。

### A-5. アプリを起動して画面を見る

まず初期データ(会議室)を作ります。

```powershell
$env:PYTHONUTF8 = "1"                 # 日本語表示の文字化け対策
.venv\Scripts\python -m app.seed
```

`会議室を 3 件投入しました。` と出れば成功です。次にアプリを起動します。

```powershell
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

> **uvicorn(ユビコーン)** = Python の Web アプリを動かすサーバー。
> 起動したまま動き続けます。**止めるときは PowerShell で `Ctrl + C`。**

ブラウザで **http://127.0.0.1:8000** を開きます。次の画面が見られます。

- `予約する` … 会議室を予約(2 時間予約すると料金が 2000 円のまま=**わざと仕込んだ割引バグ**)
- `報告する` … 不具合をテンプレ(操作手順 / 想定結果 / 実際の結果)で報告
- `マイ報告` … 報告した内容の進捗(受付 → トリアージ中 → …)が見える

これで段階 A は完了です。お疲れさまでした。

---

## 3. 段階 B:インフラを作る(クラウドに置き場所を作る)

> ここからは **お金がかかります**(小さなテスト構成で 1 日あたり数百円程度の目安)。終わったら必ず[5. 後片付け](#5-後片付けお金を止める)で消してください。

### B-1. ツールを追加で入れる

```powershell
# Terraform(インフラを設計図から自動構築する道具)
winget install HashiCorp.Terraform

# gcloud(Google クラウドを操作するコマンド)
winget install Google.CloudSDK
```

PowerShell を開き直して確認:

```powershell
terraform version    # Terraform v1.x
gcloud version       # Google Cloud SDK xxx
```

> **Terraform(テラフォーム)** = 「こういうサーバーが欲しい」と設計図(`.tf` ファイル)に書いておくと、その通りにクラウドへ自動構築してくれる道具。手作業のミスを防げます。
> **インフラ** = アプリを動かす土台(サーバー・データベース・ネットワークなど)。

### B-2. Google クラウドにログインし、プロジェクトを用意

```powershell
# あなた個人としてログイン(ブラウザが開きます)
gcloud auth login

# Terraform が裏で使うログイン(これも必要。別物なので両方やる)
gcloud auth application-default login

# プロジェクト(請求やリソースのまとまり)を作る。ID は世界で唯一の名前にする
gcloud projects create tech-support-XXXX     # XXXX を自分用の数字などに変える
gcloud config set project tech-support-XXXX
```

> **プロジェクト** = GCP の中の「1 つの作業部屋」。リソースも料金もこの単位でまとまります。

請求先(クレジットカード等)を紐付けます。請求アカウント ID を調べてから繋ぎます。

```powershell
gcloud billing accounts list                  # 表示された ID をコピー
gcloud billing projects link tech-support-XXXX --billing-account=コピーしたID
```

> ⚠️ 請求の紐付けが終わっていないと、次の `apply` が途中で失敗します。

### B-3. 設定ファイルを用意

```powershell
cd infra
Copy-Item terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars
```

メモ帳が開くので、`project_id` をさっき作った ID(`tech-support-XXXX`)に書き換えて保存します。他はそのままで OK。

> `terraform.tfvars` には秘密情報が入るので、**GitHub には上げません**(自動で除外設定済み)。

### B-4. 設計図を読み込んで、内容を確認してから作る

```powershell
terraform init      # 必要なプラグインをダウンロード(初回だけ時間がかかる)
terraform plan      # 「これから何を作るか」の一覧を表示(まだ作らない)
terraform apply     # 本当に作る。最後に yes と入力
```

> **init / plan / apply の役割**
> - `init` … 準備(道具をそろえる)
> - `plan` … 下見(何ができるか確認。ここでは何も変わらない)
> - `apply` … 実行(実際にクラウドに作る)
>
> `apply` は **10〜20 分**かかります(データベース作成が長い)。`Apply complete!` が出れば成功です。

### B-5. 作った後の仕上げ

#### (1) 秘密の値を登録する
GitHub ボットのトークンと Gemini(AI)の API キーを安全な金庫(Secret Manager)に入れます。

```powershell
# GitHub ボットのトークン("ghp_..." の部分を実際の値に)
"ghp_実際のトークン" | gcloud secrets versions add tech-support-github-bot-pat --data-file=-

# Gemini API キー("AIza_..." を実際の値に)
"AIza_実際のキー" | gcloud secrets versions add tech-support-gemini-api-key --data-file=-
```

> **Secret Manager** = パスワードや API キーを暗号化して保管する Google の金庫。コードに直接書かないための仕組み。
> これらのキーが未入手なら、この手順は後回しで構いません(インフラ自体は作れています)。

#### (2) 接続情報を控える
あとで GitHub Actions(自動デプロイ)の設定に使う値を表示します。メモしておきましょう。

```powershell
terraform output
```

---

## 4. うまくいかないときは(よくあるエラー)

| 症状 | 原因と対処 |
|---|---|
| `py` が見つからない | Python を入れた後、PowerShell を開き直す。`winget install Python.Python.3.13` を再実行 |
| `python` を実行すると Store が開く | `python` ではなく **`py`** を使う(本マニュアルの通り) |
| 日本語が `???` になる | `$env:PYTHONUTF8 = "1"` を実行してからコマンドを打つ |
| `pytest` で `no such table` | `.venv\Scripts\python -m app.seed` を実行してテーブルを作る |
| ポート 8000 が使用中 | `--port 8001` のように番号を変える |
| `terraform apply` で billing エラー | B-2 の請求アカウント紐付けが未完。`gcloud billing projects link ...` を実行 |
| `terraform apply` で permission/API エラー | `gcloud auth application-default login` をやり直す。少し待って再 `apply`(API 有効化の反映待ちのことがある) |
| `apply` の途中で失敗した | もう一度 `terraform apply` を実行(Terraform は途中から続きを作れる) |

---

## 5. 後片付け(お金を止める)

クラウドを使い終わったら、**必ず**消します。これを忘れると課金が続きます。

```powershell
cd C:\tech-support\infra
terraform destroy      # 最後に yes
```

`Destroy complete!` が出れば、作ったクラウド資源はすべて削除され、課金も止まります。

---

## 用語集

| 用語 | やさしい説明 |
|---|---|
| **GCP / Google Cloud** | Google が貸すサーバーやデータベース。使った分だけ課金 |
| **プロジェクト** | GCP 内の「作業部屋」。リソースと料金のまとまり |
| **Terraform** | 設計図(`.tf`)からインフラを自動構築する道具 |
| **インフラ** | アプリを動かす土台(サーバー・DB・ネットワーク) |
| **Cloud Run** | コンテナ(アプリの箱)を動かす GCP のサービス |
| **Cloud SQL** | GCP 上のデータベース(PostgreSQL) |
| **Pub/Sub** | 「イベントが起きたよ」を非同期で伝える郵便受けのような仕組み |
| **Secret Manager** | パスワードや API キーを保管する金庫 |
| **CI/CD** | コードを自動でテスト(CI)し、自動でデプロイ(CD)する仕組み |
| **PR(プルリク)** | 「このコード変更を取り込んでください」という提案。人間がレビューして承認する |
| **仮想環境(.venv)** | プロジェクト専用の Python 部品置き場 |
| **uvicorn** | Python の Web アプリを動かすサーバー |
| **pytest** | 自動テストを実行する道具 |
| **API キー** | 外部サービス(例: Gemini)を使うための合言葉 |

---

困ったら、エラーメッセージの**最後の数行**をそのままコピーして質問してください。多くの場合、原因はそこに書いてあります。
