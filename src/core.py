#
# Copyright (c) 2026 masaoikawa
# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.
#

import tkinter as tk
from PIL import Image, ImageTk
import os, sys, queue

# [Mac限定] macOS Sequoia等で発生する IMKCFRunLoopWakeUpReliable エラーログ（入力メソッドの通信エラー）を
# 抑制し、コンソールをデバッグに必要な情報のみに保つための設定です。
if sys.platform == "darwin":
    import AppKit
    f = open(os.devnull, 'w')
    os.dup2(f.fileno(), sys.stderr.fileno())

class MiniImagePinchApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Minimal Native Pinch & Zoom")
        self.geometry("1100x850")
        
        # [共通] 画像データと倍率・座標を管理する最小限の変数
        self.orig_img = Image.open('assets/image.png').convert("RGB")
        self.zoom_level = 1.0
        self.offset_x = self.offset_y = 0
        self.pinch_queue = queue.Queue()

        self.canvas = tk.Canvas(self, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self._setup_events()
        self._initial_setting()

    def _setup_events(self):
        """物理操作とOSごとの挙動を各機能へ紐付けます。"""
        
        # --- 【自由移動：パン操作】 ---
        # [マウス：Win/Mac共通] 左クリック：移動の『起点』を記録します。
        # [トラックパッド：Win/Mac共通] 1本指タップ/クリック：移動の『起点』を記録します。
        self.canvas.bind("<ButtonPress-1>", lambda e: self.canvas.scan_mark(e.x, e.y))

        # [マウス：Win/Mac共通] 左ボタンドラッグ：画像を掴んで自由に動かします。
        # [トラックパッド：Mac] 3本指ドラッグ（設定時）または1本指強押しドラッグ：画像を掴んで動かします。
        # [トラックパッド：Win] 1本指ドラッグ：画像を掴んで動かします。
        self.canvas.bind("<B1-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))

        # --- 【滑らかな移動：スクロール操作】 ---
        # [マウス：Win/Mac共通] ホイール回転：上下方向へ滑らかに移動します。
        # [トラックパッド：Win/Mac共通] 2本指スワイプ（上下）：上下方向へ滑らかに移動します。
        self.canvas.bind("<MouseWheel>", self._on_dispatch)

        # [マウス：Win/Mac共通] Shift+ホイール回転：左右方向へ滑らかに移動します。
        # [トラックパッド：Win/Mac共通] 2本指スワイプ（左右）：左右方向へ滑らかに移動します。
        self.canvas.bind("<Shift-MouseWheel>", self._on_dispatch)

        # --- 【拡大縮小：ズーム操作】 ---
        # [共通] マウス進入：Command(Mac) / Control(Win) ズームを即座に可能にするためフォーカスを強制します。
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        
        # [Mac限定：トラックパッド] 2本指のピンチ（開閉）：OSから直接ジェスチャ信号を取得してズームします。
        if sys.platform == "darwin":
            AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                1 << 30, lambda e: (self.pinch_queue.put((e.magnification(), e.locationInWindow())), e)[1]
            )
            self._poll_pinch()

    def _on_dispatch(self, event):
        """入力デバイスとOSに応じた『移動』か『ズーム』かの意図判定を行います。"""
        # [Mac] Commandキー (0x8) / [Windows] Controlキー (0x4) の押下判定
        is_zoom_modifier = (event.state & (0x8 if sys.platform == "darwin" else 0x4))
        
        if is_zoom_modifier:
            # [マウス：Win/Mac共通] Modifier + ホイール回転による中心ズーム
            # [トラックパッド：Win] Modifier + 2本指スワイプによる中心ズーム
            self.apply_zoom(event.x, event.y, event.delta * 0.01)
        else:
            # [共通] 2本指移動またはホイール移動を実行
            self.apply_move(event.delta, is_horizontal=(event.state & 0x1))

    def apply_move(self, delta, is_horizontal):
        """[共通] 割合移動(moveto)により、各OSの慣性スクロールやホイールの解像度を活かした移動を行います。"""
        view = self.canvas.xview() if is_horizontal else self.canvas.yview()
        # 0.01は移動感度。入力デバイスの回転・スワイプ量に応じた滑らかな反映。
        new_pos = view[0] + (-delta * 0.01 * (view[1] - view[0]))
        self.canvas.xview_moveto(new_pos) if is_horizontal else self.canvas.yview_moveto(new_pos)

    def apply_zoom(self, cx, cy, delta_scale):
        """[共通] マウスホイールズームとMacネイティブピンチで共用する中心固定拡大ロジック。"""
        if self.orig_img is None: return
        
        mx, my = self.canvas.canvasx(cx), self.canvas.canvasy(cy)
        rel_x, rel_y = mx - self.offset_x, my - self.offset_y
        
        old_zoom = self.zoom_level
        self.zoom_level = max(0.01, min(self.zoom_level * (1.0 + delta_scale), 50.0))
        ratio = self.zoom_level / old_zoom
        
        self._render_canvas()
        
        new_mx, new_my = self.offset_x + (rel_x * ratio), self.offset_y + (rel_y * ratio)
        self.canvas.scan_mark(int(cx), int(cy))
        self.canvas.scan_dragto(int(cx - (new_mx - mx)), int(cy - (new_my - my)), gain=1)

    def _poll_pinch(self):
        """[Mac限定：トラックパッド] OSスレッドから届く高速なピンチ入力をメインスレッドで処理します。"""
        try:
            while True:
                mag, loc = self.pinch_queue.get_nowait()
                # AppKit(座標系下原点)からTkinter(上原点)への変換。
                self.apply_zoom(loc.x, self.winfo_height() - loc.y, mag)
        except queue.Empty:
            pass
        self.after(20, self._poll_pinch)

    def _render_canvas(self):
        """[共通] 計算された倍率をPILでリサイズし、キャンバス描画を更新します。"""
        nw, nh = int(self.orig_img.size[0] * self.zoom_level), int(self.orig_img.size[1] * self.zoom_level)
        sw, sh = max(self.winfo_width(), nw) * 4, max(self.winfo_height(), nh) * 4
        self.offset_x, self.offset_y = sw // 4, sh // 4
        
        self.tk_img = ImageTk.PhotoImage(self.orig_img.resize((nw, nh), Image.Resampling.NEAREST))
        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw", image=self.tk_img)
        self.canvas.config(scrollregion=(0, 0, sw, sh))

    def _initial_setting(self):
        """[共通] 起動時に画像を中央配置し、ウィンドウに収まるサイズに調整します。"""
        self.update()
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.zoom_level = min(cw / self.orig_img.size[0], ch / self.orig_img.size[1]) * 0.9
        self._render_canvas()
        
        sr = [float(i) for i in self.canvas.config("scrollregion")[-1].split()]
        self.canvas.xview_moveto((self.offset_x + (self.orig_img.size[0] * self.zoom_level)/2 - cw/2) / sr[2])
        self.canvas.yview_moveto((self.offset_y + (self.orig_img.size[1] * self.zoom_level)/2 - ch/2) / sr[3])

if __name__ == "__main__":
    MiniImagePinchApp().mainloop()