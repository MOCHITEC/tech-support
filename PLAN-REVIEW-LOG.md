# Plan Review Log: tech-support — フィードバック駆動CI/CDパイプライン

Act 1 (grill) complete — plan locked with the user. MAX_ROUNDS=5.

## Round 1 — Codex

**重大**
1. **LLM 生成 pytest を PAT・API キー・メタデータサーバへ到達可能な Cloud Run 内で実行すると、プロンプトインジェクション一発で秘密情報を窃取できる。**  
修正: テスト実行を別 Cloud Run Job に隔離し、秘密情報なし・外向き通信禁止・専用 SA・CPU/時間/メモリ上限を設定する。

2. **報告本文、仕様書、スクリーンショットを命令として解釈する間接プロンプトインジェクション対策がない。**  
修正: 入力を非信頼データとして明示し、LLM 出力を構造化スキーマ検証し、許可された操作だけを決定論的コードで実行する。

3. **「`app/` 配下のみ修正」は宣言だけで、パストラバーサル、symlink、Git 操作、生成スクリプトによる範囲外変更を防げない。**  
修正: 一時 clone 上で編集後の `git diff --name-only` と実パスを検査し、許可パス外の差分が一つでもあれば破棄する。

4. **疑似ログインで「マイ報告」とスクリーンショットを公開すると、IDOR により他人の報告・画像・PR 情報を閲覧できる。**  
修正: 少なくとも署名付きデモセッションとチケット所有者検証を実装し、Storage は非公開かつ短寿命署名 URL にする。

5. **`@agent fix` は webhook 署名だけでは権限確認にならず、Issue/PR にコメントできる第三者がボットへコード変更を命令できる。**  
修正: 対象 bot PR、コメント投稿者の write 権限または許可チーム所属、コマンド形式をすべて検証する。

6. **人間承認の保証がブランチ保護という抽象表現だけで、bot/admin の bypass、古い承認、CI 後の追加 push を防げない。**  
修正: required approving review、CODEOWNERS、dismiss stale approvals、last-push approval、required checks、bypass 禁止を Terraform 等で明示する。

7. **Pub/Sub と GitHub webhook は少なくとも一回配送かつ順不同なので、PR・Issue の重複作成や状態の巻き戻りが起きる。**  
修正: delivery/event ID の一意制約、処理済みイベント表、条件付き状態遷移、GitHub 作成物の外部キーで冪等化する。

8. **単一 Cloud Run リクエスト内の最大5回修正ループは timeout、再配信、インスタンス終了で途中状態を失う。**  
修正: 各段階を永続化した状態機械にし、Cloud Run Jobs または Workflows で再開可能なステップとして実行する。

**高**
9. **SQLite テストでは PostgreSQL のロック、時刻型、制約、トランザクション分離を再現できず、二重予約の競合修正がテストを通っても本番で破れる。**  
修正: PostgreSQL を使う統合テストを追加し、予約重複を exclusion constraint または適切なロック付きトランザクションで防ぐ。

10. **API テスト生成の assertion がユーザーの TOBE に引きずられると、誤報や攻撃的入力を「正しい仕様」として固定する。**  
修正: assertion は固定した仕様書リビジョンから導出し、ユーザー TOBE は再現条件の参考情報に限定する。

11. **参照する仕様書の commit が未固定で、報告時、トリアージ時、PR 作成時に仕様が変わると判定根拠が再現不能になる。**  
修正: チケットに基準となる main commit SHA を保存し、その immutable checkout の仕様とコードだけを使う。

12. **デプロイ完了イベントとチケットの対応方法がなく、複数 PR の同時マージ、失敗、ロールバック時に誤って「リリース済み」になる。**  
修正: PR、merge SHA、イメージ digest、Cloud Run revision、ticket ID を連結し、revision の正常化後だけ対象チケットを更新する。

13. **状態一覧に「人間へエスカレーション」「デプロイ失敗」「PR却下」「重複」「修正不能」がなく、記述済みの挙動とスキーマが矛盾する。**  
修正: 許可遷移を含む状態機械を先に定義し、全終了・失敗・再試行状態を列挙する。

14. **スクリーンショットのサイズ、形式、画像爆弾、個人情報、保持期間への対策がない。**  
修正: サイズ上限、magic-byte 検証、再エンコード、メタデータ除去、保持期限、削除処理を実装する。

15. **GitHub Actions の依存固定と GCP 認証方式が未指定で、タグ乗っ取りや長期サービスアカウントキー漏洩の余地がある。**  
修正: Actions を commit SHA 固定し、Workload Identity Federation と用途別最小権限 SA を使用する。

16. **bot が編集できるブランチから workflow や CI 設定を変更できれば、テスト回避や秘密情報窃取が可能になる。**  
修正: `.github/`、`infra/`、依存ロック、ビルド設定を変更禁止パスにし、CODEOWNERS と別 CI で差分を拒否する。

17. **重複判定の基準がなく、類似報告を誤統合すると別ユーザーの内容・状態・PR を漏洩または誤更新する。**  
修正: 重複候補は自動統合せず、根拠と信頼度を提示して IT 確認を要求する。

18. **DLQ、再試行上限、相関 ID、監査ログ、トークン・費用計測がなく、失敗や暴走を追跡できない。**  
修正: Pub/Sub DLQ、段階別 retry、ticket/event/PR 共通 correlation ID、構造化ログ、予算メトリクスとアラートを追加する。

19. **DB migration、接続プール上限、Cloud Run の並列数と Cloud SQL 接続枯渇への設計がない。**  
修正: Alembic migration をデプロイ手順に組み込み、インスタンス数・並列数・pool size の総接続上限を明示する。

20. **必須技術要件を未確認のまま Agent Engine を後付け可能と仮定しており、認証、セッション、実行モデルの差で載せ替え不能になり得る。**  
修正: 実装開始前のゲートとして募集要項を確定し、必須なら最初から対象基盤で最小 E2E を成立させる。

VERDICT: REVISE


### Claude's response (Round 1)

**採用(計画へ反映済み)**: #1 テスト実行を秘密情報ゼロ・egress遮断のCloud Run Jobサンドボックスへ隔離 / #2 入力非信頼化+LLM出力のスキーマ検証+決定論的実行レイヤ / #3 PR作成前のgit diff --name-only+実パス検査で範囲外差分を破棄 / #4 署名付きセッション+所有者検証+非公開GCS・短寿命署名URL / #5 @agent fixに投稿者write権限・対象botPR・コマンド形式の三重検証 / #6 ブランチ保護をTerraformで具体化(required review, stale dismissal, last-push approval, bypass禁止, CODEOWNERS) / #7 処理済みイベント表+チケットID埋め込みによる冪等化 / #9 CIにPostgreSQL統合テスト追加、二重予約はDBレベル制約で恒久対策 / #10 assertionは固定リビジョンの仕様書から導出、ユーザTOBEは参考限定 / #11 チケットにbase commit SHAを固定 / #12 merge SHA→PR→ticketの連結+revision健全化後のみ「リリース済み」 / #13 状態機械を実装前に定義(Approach 2に昇格、欠落状態を全て追加) / #14 サイズ上限・magic-byte検証・再エンコード・デモ後削除 / #15 Actions SHAピン+Workload Identity Federation / #16 PATからworkflowスコープ除外+CI変更パスガード / #17 重複は自動統合せずIT確認待ちへ / #18 DLQ・段階別リトライ上限・相関ID・構造化ログ・トークン予算 / #19 Alembic+総接続数の上限設計

**部分採用**: #8 — 「Workflows/Jobsへの全面分割」は不採用。理由: ハッカソン規模で可動部品最小の方針(grillで確定)を維持したい。代替として、パイプライン段階のDBチェックポイント永続化+Pub/Subリトライで再開性を確保し、リスクの本丸であるテスト実行のみJobへ隔離(#1)。指摘の本質(途中状態の喪失)はチェックポイントで解消する。
#20 — 「最初から対象基盤で最小E2E」は条件付き採用。要項確認を実装前ゲート(Approach 0)に昇格し、Agent Engineが必須と判明した場合のみ初週に最小疎通を行う。必須でない場合に先行投資はしない(時間制約)。

**不採用**: なし(全件、全面または部分採用)。

スコープ増大リスクは Risks に追記し、優先順位(フルループ成立 > セキュリティガード > バックアップシナリオ)を明文化した。

## Round 2 — Codex

**前回20件の確認**
- 解消: #2, #3, #5, #6, #9, #10, #11, #13, #15, #17, #20
- 概ね解消: #1, #4, #14, #18, #19
- 部分解消: #7, #8, #12, #16
- 未解消: なし

**残る重大問題**
1. **生成コードは Cloud Run Job だけでなく GitHub Actions 上でも再実行されるため、`GITHUB_TOKEN`、OIDC トークン、ネットワークへの窃取経路が復活する。**  
修正: PR テスト workflow を `contents: read`、`id-token: none`、secrets なしに固定し、デプロイ workflow と完全分離する。

2. **変更パスガードと pytest が同時実行なら、悪意ある範囲外差分を拒否する前にコードが実行される。**  
修正: パスガードを独立した先行 job にし、全テスト job に `needs: path-guard` を設定する。

3. **疑似ログイン画面で任意のデモユーザーを選択できるなら、署名 Cookie があっても他人として正規ログインでき、所有者検証は無意味になる。**  
修正: セッションごとに固定ユーザーを割り当てるか、デモ用 PIN を設けるか、プライバシー境界がないことを明示して報告内容を非機密に限定する。

4. **Cloud Run Job の「外向き通信遮断」と、clone・テスト資材取得・結果返却に必要な通信経路が両立していない。**  
修正: オーケストレータがソース bundle を専用 GCS に置き、Job は限定バケットだけを private access で読み書きする構成を明記する。

5. **Pub/Sub push リクエスト内で処理を継続する設計のままで、チェックポイントだけでは timeout や ack deadline 超過を防げない。**  
修正: push handler はイベント保存後すぐ 2xx を返し、各段階を別メッセージとしてキュー投入する。

6. **処理済み ID の「確認後に記録」では並行配送時に二重実行する。GitHub 検索も結果整合性があり、作成前検索だけでは不十分。**  
修正: event ID の UNIQUE 制約をトランザクション開始時に確保し、チケット単位の実行ロックと条件付き状態更新を行う。

7. **「healthy かつ traffic 100%」だけでは、別デプロイが先行した際に対象 merge SHA の revision か判定できない。前回要求した image digest の連結も消えている。**  
修正: merge SHA、image digest、期待する revision 名を deployment record に保存し、その完全一致を確認してから通知する。

8. **古い base SHA に対して生成した修正を現在の main へそのまま PR にすると、仕様変更やコード変更を踏み越える可能性がある。**  
修正: PR 作成直前に最新 main へ適用し直し、仕様差分検査と全テスト再実行を行い、競合時はエスカレーションする。

9. **`一意制約+ロック付きトランザクション` では任意の時間帯の重複を一般には表現できず、二重予約対策として曖昧すぎる。**  
修正: PostgreSQL の range 型と exclusion constraint を採用すると確定し、同時予約テストを実トランザクションで行う。

10. **Pillow の再エンコードだけでは圧縮爆弾によるメモリ枯渇を防げない。**  
修正: デコード前後でファイルサイズ、ピクセル数、縦横寸法を制限し、decompression-bomb 警告を拒否扱いにする。

11. **WIF の信頼条件が未指定で、リポジトリ内の別 workflow や想定外 ref からデプロイ SA を引き受けられる可能性がある。**  
修正: provider 条件を repository、workflow ref、branch、GitHub environment に限定し、本番 environment に人間承認を設定する。

12. **「間に合わなければ署名 URL 化を簡易化」は、非公開画像を表示できないか、公開してアクセス制御を破るかの二択になる。**  
修正: 署名 URL を削る場合は、所有者検証済みアプリ API が GCS を代理取得する方式を最低要件にする。

Rev.2 は大幅に改善されていますが、生成コードが GitHub Actions で再び高権限環境に入る点と、非同期処理・デプロイ対応付けの競合は実装前に解消が必要です。

VERDICT: REVISE

### Claude's response (Round 2)

**採用(計画へ反映済み)**: R2#1 PRテストworkflowを contents:read・id-tokenなし・secretsゼロに固定しデプロイworkflowと完全分離 / R2#2 パスガードを先行jobにし全テストjobに needs を設定 / R2#3 ユーザ選択画面を廃止しセッションごとに専用デモユーザを自動割当(なりすまし経路を構造排除)+デモデータ非機密限定 / R2#4 ソースbundleを専用GCSに配置しJobはそのバケットのみPrivate Google Accessで読み書き(Jobからのcloneと外部通信を排除) / R2#5 push handlerは保存後即2xx、段階ごとに自己キュー投入する非同期パイプラインへ / R2#6 イベントIDのUNIQUE制約先行INSERT+チケット実行ロック+条件付きUPDATE / R2#7 deployment record(merge SHA・image digest・期待revision名・PR・ticket)との完全一致でのみ通知 / R2#8 PR作成直前に最新mainへ適用し直し、仕様差分検査+全テスト再実行、競合はエスカレーション / R2#9 tstzrange+exclusion constraint(btree_gist)で確定、実トランザクション並行テスト / R2#10 ピクセル数・寸法上限+decompression-bomb警告の拒否扱い / R2#12 簡略化時の下限を「所有者検証済みAPIの代理取得」とし公開バケット禁止を明文化

**部分採用**: R2#11 — WIF provider条件のrepository・workflow ref・branch限定は採用。「本番environmentへの人間承認の追加」は不採用。理由: 本企画のゲート設計では「PRレビュー承認=マージ=デプロイの引き金」が人間承認そのものであり、environment承認を重ねると同一人物による二重承認となって安全性は実質増えず、デモのテンポだけが落ちる。ブランチ保護(bypass禁止・required review)とWIF条件限定で同じ脅威(想定外経路からのデプロイ)は遮断済み。

**不採用**: なし(上記部分採用1件を除き全面採用)。

## Round 3 — Codex

**Round 2 指摘の確認**
R2#1〜#10、#12 は解消されています。R2#11 の Environment 承認を追加しない判断も、main への到達が branch protection で強制され、WIF が repository・workflow・branch に限定される前提なら妥当です。

**新たに残る重大問題**
1. **イベント ID を先行 INSERT した後にプロセスが落ちると、再配信は「重複」として破棄され、未完了の段階が永久に停止する。**  
修正: イベントを `pending/processing/completed` と lease 有効期限付きで管理し、重複時は completed のみ終了、未完了なら再開する。

2. **DB のチェックポイント更新と次段階の Pub/Sub publish が非原子的で、commit 後・publish 前の障害により処理が消失する。**  
修正: 次段階イベントを同一 DB transaction の outbox に書き、専用 publisher が再送する transactional outbox を採用する。

3. **同じ main に対するデプロイ workflow が並行すると、古い workflow が後から完了して新しい revision を巻き戻せる。deployment record の照合だけでは防げない。**  
修正: デプロイを concurrency group で直列化し、反映直前に対象 SHA が現在の main HEAD でなければ中止する。

4. **Job の共通 SA が専用 GCS バケット全体を読み書きできると、悪意あるテストが別チケットのソースや結果を閲覧・改竄できる。**  
修正: 実行ごとにランダムな object prefix と短寿命署名 URL を発行し、他実行のオブジェクトへアクセスできないようにする。

5. **Private Google Access は「そのバケットだけへの通信」を保証せず、Google API とメタデータサーバへの到達自体は残る。**  
修正: restricted Google APIs、VPC firewall、最小権限 SA を組み合わせ、到達可能先と IAM の両方を検証する。

6. **匿名セッションを無制限に作れるため、外部ユーザーが大量報告で Gemini、Cloud Run Jobs、GitHub PR を起動し、費用とキューを枯渇させられる。**  
修正: IP・セッション単位のレート制限、同時処理数、日次予算、未完了チケット上限を入口で強制する。

7. **状態変更フォームに CSRF 対策がなく、第三者サイトから報告送信やキャンセル操作を誘発できる。**  
修正: `Secure`・`HttpOnly`・適切な `SameSite` Cookie と CSRF token、Origin 検証を実装する。

8. **GitHub Actions 側の生成テストには実行時間上限がなく、無限ループや大量プロセス生成で Actions 枠を消費できる。**  
修正: job の `timeout-minutes`、workflow concurrency、pytest timeout を設定する。

Rev.3 は前回指摘を適切に処理していますが、イベント消失を招く inbox/outbox の障害窓と、公開入口からの費用 DoS は実装前に解消が必要です。

VERDICT: REVISE

### Claude's response (Round 3)

**採用(全8件、計画へ反映済み)**: R3#1 inboxを pending/processing(lease付き)/completed の3状態管理にし、lease切れ未完了イベントは再開 / R3#2 transactional outbox(次段階イベントを同一トランザクションでoutboxに書き、専用publisherが再送) / R3#3 デプロイworkflowをconcurrency groupで直列化+切替直前のmain HEAD一致チェック / R3#4 サンドボックスは実行ごとのランダムobject prefix+短寿命署名URLのみ(SAにバケット横断権限を与えない) / R3#5 egress遮断はrestricted.googleapis.com限定+VPCファイアウォール+最小権限SAの組合せで検証 / R3#6 入口防御(IP・セッション別レート制限、未完了チケット上限、同時処理数上限、日次予算で受付停止) / R3#7 CSRF対策(Secure/HttpOnly/SameSite Cookie+CSRFトークン+Origin検証) / R3#8 Actions全jobにtimeout-minutes・workflow concurrency・pytestタイムアウト

**不採用**: なし。

## Round 4 — Codex

**Round 3 確認**
R3#1〜#8 はすべて計画上解消されています。inbox/outbox、デプロイ直列化、Job 隔離、入口制限、CSRF、Actions timeout の反映を確認しました。

**新規の重大問題**
1. **旗艦デモの exclusion constraint を追加するには Alembic migration が必要だが、bot の許可パスが `app/`・`tests/` のみで migration の配置場所が未定義。**  
修正: migration を `app/migrations/` に配置すると明記し、実パスガードでもそこだけを許可する。

2. **デプロイ workflow に `alembic upgrade head` がなく、PR が migration を生成しても Cloud Run の本番 DB へ適用されない。**  
修正: デプロイ前に専用 Cloud Run Job で migration を一度だけ実行し、失敗時はデプロイと「リリース済み」通知を中止する。

3. **サンドボックスに PostgreSQL がないため、自己修正ループでは `tstzrange`、`btree_gist`、exclusion constraint を検証できず、「グリーンで PR 作成」という前提が成立しない。**  
修正: Job 内で短命 PostgreSQL を起動して統合テストまで実行するか、PostgreSQL 固有修正だけは PR CI の結果を修正ループへ戻す。

いずれも主デモである二重予約修正の成立に直接影響するため、ハッカソン基準でも未解決のまま実装開始するのは危険です。

VERDICT: REVISE

### Claude's response (Round 4)

**採用(全3件、計画へ反映済み)**: R4#1 マイグレーションを app/migrations/ に配置しボット許可パス・パスガード・Out of scope の記述を整合 / R4#2 デプロイworkflowでトラフィック切替前に専用Cloud Run Jobで alembic upgrade head を実行、失敗時はデプロイと通知を中止 / R4#3 サンドボックスJobイメージにPostgreSQLを同梱しコンテナ内で短命起動、自己修正ループ内で統合テストまで検証(exclusion constraint修正がループ内でグリーンにできることを保証)

**不採用**: なし。

## Round 5 — Codex

**Round 4 確認**
3件すべて解消されています。

- migration は `app/migrations/` に配置され、許可パスと整合
- トラフィック切替前に専用 Job で `alembic upgrade head` を実行し、失敗時はデプロイ・通知を中止
- サンドボックス内の短命 PostgreSQL で、自己修正ループ中に統合テストを実行

ハッカソン規模として新たな重大問題は見当たりません。残る実装難度や運用上の簡略化リスクも計画内で認識され、主デモの成立条件、権限境界、失敗時処理、再実行性は十分具体化されています。

VERDICT: APPROVED

---
Converged: VERDICT APPROVED at Round 5 of MAX_ROUNDS=5. Final plan: PLAN.md (Rev.5). Awaiting user sign-off before any implementation.
