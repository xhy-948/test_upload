# -*- coding: utf-8 -*-
"""
图片颜色查找与替换工具
依赖: pip install pillow numpy
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import numpy as np


class ColorReplaceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("图片颜色查找与替换")
        self.root.geometry("1280x820")
        self.root.minsize(900, 600)

        # ---------- 状态 ----------
        self.current_arr = None        # 当前图像 numpy (H,W,3) uint8
        self.history = []              # 撤回栈 [(ys, xs, old_values), ...]

        self.photo = None              # 显示用 PhotoImage
        self.scale = 1.0               # 显示缩放比
        self.offset_x = 0
        self.offset_y = 0

        self.picking = False           # 是否取色模式
        self.picked_color = None       # 取色临时颜色
        self.selected_color = None     # 确认后的目标颜色

        self._resize_job = None

        self._build_ui()

    # ================= UI =================
    def _build_ui(self):
        top = tk.Frame(self.root, bg="#f5f5f5", pady=6)
        top.pack(side=tk.TOP, fill=tk.X)

        tk.Button(top, text="1. 选择图片", width=12,
                  command=self.load_image).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="2. 取色", width=10,
                  command=self.start_pick).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="3. 取色确定", width=10,
                  command=self.confirm_pick).pack(side=tk.LEFT, padx=4)

        # ---- 原色预览 ----
        tk.Label(top, text="原色:", bg="#f5f5f5").pack(side=tk.LEFT, padx=(18, 2))
        self.preview = tk.Label(top, text="  ", bg="#f5f5f5", width=3,
                                relief=tk.SUNKEN, borderwidth=1)
        self.preview.pack(side=tk.LEFT)

        # ---- 新色输入 ----
        tk.Label(top, text="替换为 RGB:", bg="#f5f5f5").pack(side=tk.LEFT, padx=(18, 4))
        self.rgb_var = tk.StringVar(value="255,0,0")
        self.rgb_var.trace_add("write", lambda *_: self.update_color_preview())
        self.rgb_entry = tk.Entry(top, width=14, textvariable=self.rgb_var)
        self.rgb_entry.pack(side=tk.LEFT, padx=4)

        # ---- 新色预览 ----
        tk.Label(top, text="新色:", bg="#f5f5f5").pack(side=tk.LEFT, padx=(6, 2))
        self.back = tk.Label(top, text="  ", bg="#f5f5f5", width=3,
                             relief=tk.SUNKEN, borderwidth=1)
        self.back.pack(side=tk.LEFT)

        tk.Label(top, text="容差:", bg="#f5f5f5").pack(side=tk.LEFT, padx=(18, 2))
        self.tol_var = tk.IntVar(value=10)
        tk.Spinbox(top, from_=0, to=255, width=4,
                   textvariable=self.tol_var).pack(side=tk.LEFT)

        tk.Button(top, text="4. 确认替换", width=12,
                  command=self.replace_color).pack(side=tk.LEFT, padx=(18, 4))
        tk.Button(top, text="5. 撤回", width=10,
                  command=self.undo).pack(side=tk.LEFT, padx=4)
        # ★ 新增保存按钮
        tk.Button(top, text="6. 保存图片", width=12,
                  command=self.save_image).pack(side=tk.LEFT, padx=(18, 4))

        # 状态栏
        self.status = tk.Label(self.root, text="请先点击“1. 选择图片”",
                               anchor="w", bg="#e8e8e8", padx=10, pady=4)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        # 画布
        self.canvas = tk.Canvas(self.root, bg="#2b2b2b", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        self.update_color_preview()

    # ================= 新色预览 =================
    def update_color_preview(self):
        try:
            r, g, b = self.parse_rgb(self.rgb_var.get())
            self.back.config(bg=f"#{r:02x}{g:02x}{b:02x}", text="  ")
        except Exception:
            self.back.config(bg="#d9d9d9", text="?")

    # ================= 渲染 =================
    def render(self):
        self._resize_job = None
        if self.current_arr is None:
            return
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        h, w = self.current_arr.shape[:2]
        scale = min(cw / w, ch / h, 1.0)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        self.scale = scale

        img = Image.fromarray(self.current_arr)
        try:
            img_disp = img.resize((new_w, new_h), Image.LANCZOS)
        except AttributeError:
            img_disp = img.resize((new_w, new_h), Image.ANTIALIAS)
        self.photo = ImageTk.PhotoImage(img_disp)

        self.canvas.delete("all")
        self.offset_x = (cw - new_w) // 2
        self.offset_y = (ch - new_h) // 2
        self.canvas.create_image(self.offset_x, self.offset_y,
                                 anchor=tk.NW, image=self.photo)

    def on_canvas_resize(self, _event):
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(80, self.render)

    # ================= 1. 选择图片 =================
    def load_image(self):
        path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif *.tif *.tiff"),
                       ("所有文件", "*.*")]
        )
        if not path:
            return
        try:
            img = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开图片：\n{e}")
            return

        self.current_arr = np.array(img, dtype=np.uint8)
        self.history.clear()
        self.picking = False
        self.picked_color = None
        self.selected_color = None
        self.preview.config(bg="#f5f5f5", text="  ")
        self.canvas.config(cursor="")

        self.root.update_idletasks()
        self.render()

        h, w = self.current_arr.shape[:2]
        self.status.config(
            text=f"已加载：{path}    尺寸 {w}×{h}    请点击“2. 取色”后在图片上点选颜色"
        )

    # ================= 2. 取色 =================
    def start_pick(self):
        if self.current_arr is None:
            messagebox.showwarning("提示", "请先选择图片")
            return
        self.picking = True
        self.picked_color = None
        self.selected_color = None
        self.canvas.config(cursor="crosshair")
        self.canvas.delete("marker")
        self.preview.config(bg="#f5f5f5", text="  ")
        self.status.config(text="取色模式：请在图片上点击要替换的颜色（可反复点击，满意后点“3. 取色确定”）")

    def on_canvas_click(self, event):
        if not self.picking or self.current_arr is None or self.photo is None:
            return

        ix = int((event.x - self.offset_x) / self.scale)
        iy = int((event.y - self.offset_y) / self.scale)
        h, w = self.current_arr.shape[:2]
        if ix < 0 or ix >= w or iy < 0 or iy >= h:
            return

        r, g, b = (int(c) for c in self.current_arr[iy, ix])
        self.picked_color = (r, g, b)

        self.status.config(
            text=f"取色中：坐标 ({ix}, {iy})    RGB = ({r}, {g}, {b})    点击“3. 取色确定”锁定"
        )
        self.preview.config(bg=f"#{r:02x}{g:02x}{b:02x}", text="  ")

        self.canvas.delete("marker")
        rr = 7
        self.canvas.create_oval(event.x - rr, event.y - rr, event.x + rr, event.y + rr,
                                outline="#ff0000", width=2, tags="marker")
        self.canvas.create_oval(event.x - 2, event.y - 2, event.x + 2, event.y + 2,
                                fill="#ffff00", outline="", tags="marker")

    # ================= 3. 取色确定 =================
    def confirm_pick(self):
        if self.picked_color is None:
            messagebox.showwarning("提示", "请先在图片上点击取色")
            return
        self.selected_color = self.picked_color
        self.picking = False
        self.canvas.config(cursor="")
        r, g, b = self.selected_color
        self.status.config(
            text=f"已确定目标颜色：RGB = ({r}, {g}, {b})    "
                 f"请在输入框填写替换颜色，然后点“4. 确认替换”"
        )

    # ================= 4. 确认替换 =================
    @staticmethod
    def parse_rgb(s):
        """支持 255,0,0 / 255 0 0 / #FF0000 / FF0000"""
        s = s.strip()
        if s.startswith("#"):
            s = s[1:]
        if "，" in s:
            s = s.replace("，", ",")
        if "," in s:
            parts = s.split(",")
        elif " " in s:
            parts = s.split()
        else:
            if len(s) == 6:
                return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
            raise ValueError("bad format")
        parts = [p.strip() for p in parts if p.strip() != ""]
        if len(parts) != 3:
            raise ValueError("bad format")
        vals = [int(p) for p in parts]
        if any(v < 0 or v > 255 for v in vals):
            raise ValueError("out of range")
        return tuple(vals)

    def replace_color(self):
        if self.current_arr is None:
            messagebox.showwarning("提示", "请先选择图片")
            return
        if self.selected_color is None:
            messagebox.showwarning("提示", "请先取色，并点击“3. 取色确定”")
            return
        try:
            new_color = self.parse_rgb(self.rgb_entry.get())
        except Exception:
            messagebox.showerror("错误",
                                 "RGB 格式不正确。\n示例：255,0,0  或  255 0 0  或  #FF0000")
            return

        tol = int(self.tol_var.get())
        arr = self.current_arr
        target = np.array(self.selected_color, dtype=np.int16)

        diff = np.abs(arr.astype(np.int16) - target)
        mask = np.all(diff <= tol, axis=-1)
        count = int(mask.sum())

        if count == 0:
            messagebox.showinfo("提示",
                                f"未找到匹配的像素（容差 {tol}）。\n可尝试增大容差，或重新取色。")
            return

        ys, xs = np.where(mask)
        self.history.append((ys, xs, arr[ys, xs].copy()))

        arr[ys, xs] = np.array(new_color, dtype=np.uint8)

        self.render()
        self.status.config(
            text=f"已替换 {count} 个像素："
                 f"({self.selected_color[0]},{self.selected_color[1]},{self.selected_color[2]}) "
                 f"→ ({new_color[0]},{new_color[1]},{new_color[2]})    容差={tol}"
        )

    # ================= 5. 撤回 =================
    def undo(self):
        if not self.history:
            messagebox.showinfo("提示", "没有可撤回的操作")
            return
        ys, xs, old_values = self.history.pop()
        self.current_arr[ys, xs] = old_values
        self.render()
        self.status.config(text=f"已撤回一步，剩余可撤回 {len(self.history)} 步")

    # ================= 6. 保存图片 ★ =================
    def save_image(self):
        if self.current_arr is None:
            messagebox.showwarning("提示", "请先选择图片")
            return

        path = filedialog.asksaveasfilename(
            title="保存图片",
            defaultextension=".png",
            filetypes=[
                ("PNG 图片（推荐，无损）", "*.png"),
                ("JPEG 图片", "*.jpg *.jpeg"),
                ("BMP 图片", "*.bmp"),
                ("TIFF 图片", "*.tif *.tiff"),
                ("所有文件", "*.*"),
            ],
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        img = Image.fromarray(self.current_arr)

        try:
            if ext in (".jpg", ".jpeg"):
                # JPEG 不支持透明通道，也无损压缩不可选，这里给个高质量
                img.save(path, quality=95, subsampling=0)
            elif ext in (".tif", ".tiff"):
                img.save(path, compression="tiff_lzw")
            else:
                img.save(path)
        except Exception as e:
            messagebox.showerror("错误", f"保存失败：\n{e}")
            return

        self.status.config(text=f"已保存：{path}")
        messagebox.showinfo("成功", f"图片已保存到：\n{path}")


def main():
    root = tk.Tk()
    ColorReplaceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()