#
# Copyright (c) 2026 masaoikawa
# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.
#

import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import os
import sys
import queue

# OS判定フラグ：環境に応じて処理を分岐させるために使用します。
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

# macOS専用の処理：Mac環境の場合のみ、ネイティブイベント取得用のライブラリを読み込みます。
if IS_MAC:
    # macOS Sequoia等で発生する IMKCFRunLoopWakeUpReliable エラーログが
    # コンソールを汚染するのを防ぐため、標準エラー出力を無効化します。
    import AppKit
    f = open(os.devnull, 'w')
    os.dup2(f.fileno(), sys.stderr.fileno())

# AppKitスレッドから届く高速なピンチ信号を、Tkinterのメインスレッドで
# 安全かつ取りこぼしなく処理するためにスレッドセーフなキューを利用します。
pinch_queue = queue.Queue()

def native_pinch_handler(event):
    """OSレベルで発生したトラックパッドの倍率変化イベントをキューへ中継します。"""
    try:
        pinch_queue.put((event.magnification(), event.locationInWindow()))
    except:
        pass
    return event

class ImagePinchApp(tk.Tk):
    def __init__(self, default_image_path=None):
        super().__init__()
        self.title("macOS Native Pinch-to-Zoom")
        self.geometry("1100x850")

        # 画像の品質とパフォーマンスを両立させるための状態管理
        self.orig_img = None           # 拡大の基準となる非破壊の元データ
        self.zoom_level = 1.0          # 浮動小数点で保持する精密なズーム倍率
        self.high_res_job = None       # 操作中の負荷を下げ、停止後に高画質化するためのタイマー
        self._is_drawing = False       # 描画処理が重なった際のフリーズを防止するガード
        self.offset_x = 0              # キャンバス上の広大な座標系における配置起点
        self.offset_y = 0              
        self.pinch_monitor = None      # アプリ終了時にOSのリソースを解放するための監視ハンドル

        self._setup_ui()
        self._setup_events()

        # macOSの場合のみ：Tkinter標準では捕捉できない「NSEventTypeMagnify」をAppKit経由で直接監視します。
        if IS_MAC:
            # Tkinter標準では捕捉できない「NSEventTypeMagnify」をAppKit経由で直接監視します。
            self.pinch_monitor = AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(1 << 30, native_pinch_handler)
            self.protocol("WM_DELETE_WINDOW", self._on_closing) 
            self._poll_pinch_queue()
        
        # 起動直後の自動読み込み
        if default_image_path and os.path.exists(default_image_path):
            self._process_image_loading(default_image_path)

    def _setup_ui(self):
        """画像の自由な移動と拡大を支える土台を構築します。"""
        self.canvas = tk.Canvas(self, cursor="fleur", bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.controls = tk.Frame(self, bg="#2b2b2b")
        self.controls.pack(fill="x")
        tk.Button(self.controls, text="画像を開く", command=self.load_image).pack(side="left", padx=5, pady=5)
        tk.Button(self.controls, text="中央へリセット", command=self.reset_view).pack(side="left", padx=5, pady=5)
        self.info_label = tk.Label(self.controls, text="画像未選択", bg="#2b2b2b", fg="white")
        self.info_label.pack(side="left", padx=10)

    def _setup_events(self):
        """macOS標準の各種操作（ドラッグ、スクロール、フォーカス）を定義します。"""
        self.canvas.bind("<ButtonPress-1>", lambda e: self.canvas.scan_mark(e.x, e.y)) # 左クリック：ドラッグ移動の起点に設定
        self.canvas.bind("<B1-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1)) # 左ドラッグ：画像を掴んで自由に移動

        # マウスホイールイベント：OSによって挙動が異なるため振り分けます。
        if IS_WIN:
            self.canvas.bind("<MouseWheel>", self._on_dispatch) # Windows：通常のMouseWheelイベントで、Ctrl併用時は中心ズーム、Shift併用時は水平スクロール
        else:
            self.canvas.bind("<MouseWheel>", self._on_dispatch) # 2本指上下：スクロール移動、Command併用時は中心ズーム
            self.canvas.bind("<Shift-MouseWheel>", self._on_dispatch) # 2本指左右：水平方向へのスクロール移動

        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set()) # マウス進入：キー入力を有効化

    def _on_dispatch(self, event):
        """macOSの滑らかなスクロール感（moveto）を維持しつつ、ズームと移動を振り分けます。"""
        is_command = (event.state & (0x8 | 0x4)) != 0 
        is_shift = (event.state & (0x1) != 0)

        if is_command:
            # Command併用時は、スクロール量を倍率変化として中心ズームに変換します。
            self._apply_zoom_logic(event.x, event.y, event.delta * 0.01)
        elif is_shift:
            # 2本指左右スクロール：moveto を使い、現在の表示比率に基づいて滑らかに水平移動します。
            cur_x = self.canvas.xview()
            self.canvas.xview_moveto(cur_x[0] + (-event.delta * 0.01 * (cur_x[1] - cur_x[0])))
        else:
            # 2本指上下スクロール：moveto を使い、macOS特有の慣性スクロールに対応した滑らかな垂直移動を行います。
            cur_y = self.canvas.yview()
            self.canvas.yview_moveto(cur_y[0] + (-event.delta * 0.01 * (cur_y[1] - cur_y[0])))

    def _poll_pinch_queue(self):
        """AppKitスレッドから届いたピンチ信号をUIスレッドへ安全に反映させます。"""
        try:
            while True:
                mag, loc = pinch_queue.get_nowait()
                tx = loc.x - self.canvas.winfo_x()
                ty = (self.winfo_height() - loc.y) - self.canvas.winfo_y()
                self._apply_zoom_logic(tx, ty, mag) 
        except queue.Empty:
            pass
        self.after(20, self._poll_pinch_queue)

    def _apply_zoom_logic(self, cx, cy, delta_scale):
        """マウス直下の座標を固定したまま、画像を指定倍率へ精密にリサイズします。"""
        if not self.orig_img: return
        if self.high_res_job: self.after_cancel(self.high_res_job)
        
        mx, my = self.canvas.canvasx(cx), self.canvas.canvasy(cy)
        rel_x, rel_y = mx - self.offset_x, my - self.offset_y
        
        old_zoom = self.zoom_level
        self.zoom_level = max(0.01, min(self.zoom_level * (1.0 + delta_scale), 50.0))
        ratio = self.zoom_level / old_zoom
        
        # ズーム中は速度重視（NEAREST）
        self.show_image(quality=Image.Resampling.NEAREST)
        
        new_mx, new_my = self.offset_x + (rel_x * ratio), self.offset_y + (rel_y * ratio)
        self.canvas.scan_mark(int(cx), int(cy))
        self.canvas.scan_dragto(int(cx - (new_mx - mx)), int(cy - (new_my - my)), gain=1)
        
        # 停止後に高画質化
        self.high_res_job = self.after(150, lambda: self.show_image(Image.Resampling.BILINEAR))

    def show_image(self, quality=Image.Resampling.NEAREST):
        """メモリ上の画像をキャンバスの描画アイテムとして更新します。"""
        if not self.orig_img or self._is_drawing: return
        self._is_drawing = True
        try:
            nw, nh = int(self.orig_img.size[0] * self.zoom_level), int(self.orig_img.size[1] * self.zoom_level)
            sw, sh = max(self.canvas.winfo_width(), nw) * 4, max(self.canvas.winfo_height(), nh) * 4
            self.offset_x, self.offset_y = sw // 4, sh // 4
            
            self.tk_img = ImageTk.PhotoImage(self.orig_img.resize((nw, nh), quality))
            self.canvas.delete("all")
            self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw", image=self.tk_img)
            self.canvas.config(scrollregion=(0, 0, sw, sh))
        finally:
            self._is_drawing = False

    def reset_view(self):
        """画像を中央に配置し、画面に収まる最適なサイズに初期化します。"""
        if not self.orig_img: return
        self.update_idletasks()
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.orig_img.size
        
        self.zoom_level = min(cw / iw, ch / ih) * 0.9
        self.show_image(quality=Image.Resampling.BILINEAR)
        
        sr = [float(i) for i in self.canvas.config("scrollregion")[-1].split()]
        tx = (self.offset_x + (iw * self.zoom_level) / 2 - cw / 2) / sr[2]
        ty = (self.offset_y + (ih * self.zoom_level) / 2 - ch / 2) / sr[3]
        self.canvas.xview_moveto(tx)
        self.canvas.yview_moveto(ty)

    def load_image(self):
        path = filedialog.askopenfilename()
        if path: self._process_image_loading(path)

    def _process_image_loading(self, file_path):
        try:
            self.orig_img = Image.open(file_path).convert("RGB")
            self.reset_view()
            self.info_label.config(text=f"{self.orig_img.size[0]}x{self.orig_img.size[1]} | {os.path.basename(file_path)}")
        except Exception:
            pass

    def _on_closing(self):
        """OSのリソース（Macのイベントモニター等）を適切に解放して安全に終了します。"""
        if IS_MAC and self.pinch_monitor:
            AppKit.NSEvent.removeMonitor_(self.pinch_monitor)
        self.destroy()

if __name__ == "__main__":
    app = ImagePinchApp(default_image_path='assets/image.png')
    app.mainloop()
    