# Tkinter macOS Native Pinch-to-Zoom

[English Version is here](README.en.md)

Tkinterでmacのピンチズーム等が使えないため、Geminiに解決用のコードを作成してもらいました。
このREADME.md含めて全てのファイルはGeminiと作成しました。私のMac環境 (26.4 / 25E246) では正確に動くようになりました。
動作しない場合、Issuesで教えてもらえると反映できるかもしれません。

Tkinterアプリケーションで、macOS標準の **ネイティブ・ピンチズーム（拡大・縮小ジェスチャ）** を実現するためのリファレンス実装です。

## 🌟 概要

通常のTkinter（Python）では、macOS独自のジェスチャイベント（`NSEventTypeMagnify`）を `bind` メソッドで取得することができません。

このプロジェクトでは、**PyObjC** を介してOSレベルのイベントストリームにアクセスし、Tkinterのイベントループへ安全にデータを橋渡しすることで、macOS標準アプリのような滑らかなピンチ操作を実現しています。

## 🖱 デバイスと操作の解釈（内部ロジック）

本プログラムでは、物理デバイスとOSごとの挙動の違いを吸収し、以下のロジックで一貫したユーザー体験を提供します。

| カテゴリ | 物理操作 | 対象OS | 内部イベント解釈 | 実装機能 |
| :--- | :--- | :--- | :--- | :--- |
| **自由移動 (パン)** | 左ボタン・ドラッグ | 共通 | `<B1-Motion>` | 画像を掴んで移動 |
| | 3本指ドラッグ | Mac | `<B1-Motion>` (OSが変換) | 画像を掴んで移動 |
| **滑らかな移動** | 2本指スワイプ | 共通 | `<MouseWheel>` / `<Shift-MouseWheel>` | 割合(`moveto`)によるスクロール |
| | マウスホイール回転 | 共通 | `<MouseWheel>` | 割合(`moveto`)によるスクロール |
| | チルトホイール (左右倒し) | 共通 | `<Shift-MouseWheel>` | 水平方向へのスクロール |
| **ズーム** | **2本指ピンチ** | **Mac** | **NSEventTypeMagnify (AppKit)** | **ネイティブ・ズーム** |
| | Cmd + ホイール回転 | Mac | `<MouseWheel>` + State(0x8) | カーソル中心ズーム |
| | Ctrl + ホイール回転 | Win | `<MouseWheel>` + State(0x4) | カーソル中心ズーム |

## ⌨️ イベント・マッピング詳細

| Tkinterイベント / 信号源 | 判定条件 (State/System) | 対象OS | 実際のユーザー操作 | 実行される関数 |
| :--- | :--- | :--- | :--- | :--- |
| **`<ButtonPress-1>`** | なし | 共通 | 左クリック / 1本指タップ | `canvas.scan_mark` |
| **`<B1-Motion>`** | なし | 共通 | 左ドラッグ / 3本指ドラッグ | `canvas.scan_dragto` |
| **`<MouseWheel>`** | `is_zoom = False` | 共通 | 垂直ホイール回転 / 2本指スワイプ(上下) | `apply_move` |
| | `is_zoom = True` | 共通 | Cmd(Mac) or Ctrl(Win) + ホイール回転 | `apply_zoom` |
| **`<Shift-MouseWheel>`** | なし | 共通 | チルト左右 / 2本指スワイプ(左右) | `apply_move` |
| **`NSEventTypeMagnify`** | なし (AppKit) | **Mac** | **2本指ピンチ (開閉)** | **`apply_zoom`** |
| **`<Enter>`** | なし | 共通 | キャンバス内へのマウス進入 | `canvas.focus_set` |

## 🚀 主な機能

- **ネイティブ・ピンチ操作**: トラックパッドによる直感的なズーム。
- **インテリジェント・ズーム**: マウスカーソルの位置を起点とした拡大縮小。
- **スレッドセーフ設計**: `queue.Queue` を使用し、OSスレッドとTkinter間の競合（GILクラッシュ）を防止。
- **ハイパフォーマンス描画**: 操作中は低画質（NEAREST）、停止後に高画質（BILINEAR）へ切り替える適応型描画。
- **フル操作対応**: 2本指スクロール、ドラッグ移動、Command+ホイールズーム完備。

## 🛠 技術的な背景

1. **AppKit イベントモニター**: `addLocalMonitorForEventsMatchingMask` を使用し、Tkinterが標準で破棄してしまうジェスチャイベントを直接キャッチします。
2. **完全なスレッド分離**: OSのシステムスレッドから届く信号をキューに格納し、Tkinterのメインスレッド側でポーリング（`after` メソッド）することで安全にUIを更新します。
3. **OS依存のログ抑制**: macOS Sequoia等で発生する `IMKCFRunLoopWakeUpReliable` 等の不要なシステムエラー出力を抑制し、開発コンソールの視認性を保ちます。

## 📦 動作要件

- macOS (Intel / Apple Silicon) / Windows (マウス操作のみ)
- Python 3.13.12
- 依存ライブラリ: `Pillow`, `pyobjc` (macOS環境のみ)

## ⚡ クイックスタート

```bash
# リポジトリをクローン
git clone https://github.com/masaoikawa/tkinter-macos-pinch.git
cd tkinter-macos-pinch

# 依存関係のインストールと実行 (uvを使用する場合)
uv sync
uv run src/main.py
```

## 📄 ライセンス

このプロジェクトは **MIT License** のもとで公開されています。
詳細はリポジトリ内の [LICENSE](LICENSE) ファイルを参照してください。

Copyright (c) 2026 masaoikawa
