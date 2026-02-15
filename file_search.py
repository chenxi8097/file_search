# -*- coding: utf-8 -*-
"""
类似 Everything 的 Windows 文件名搜索工具
使用 Python + tkinter 实现
"""

import os
import sys
import threading
import subprocess
import time
from tkinter import *
from tkinter import ttk
from tkinter import messagebox
import fnmatch


class FileSearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("快速文件搜索 (类似 Everything)")
        self.root.geometry("900x600")

        # 文件索引数据
        self.file_index = []  # 存储 (小写文件名, 原始文件名, 完整路径, 大小)
        self.is_indexing = False
        self.indexing_complete = False

        # 搜索结果
        self.search_results = []

        # 当前索引的驱动器
        self.current_drive = "C:\\"

        # 初始化界面
        self.setup_ui()

        # 开始索引
        self.start_indexing()

    def setup_ui(self):
        """设置界面布局"""
        # 顶部搜索框区域
        top_frame = Frame(self.root, height=60)
        top_frame.pack(side=TOP, fill=X, padx=10, pady=10)

        # 驱动器选择
        drive_label = Label(top_frame, text="驱动器:", font=("微软雅黑", 10))
        drive_label.pack(side=LEFT, padx=(0, 5))

        self.drive_var = StringVar(value="C:")
        drive_combo = ttk.Combobox(top_frame, textvariable=self.drive_var,
                                    values=self.get_available_drives(),
                                    width=5, state="readonly")
        drive_combo.pack(side=LEFT, padx=(0, 10))
        drive_combo.bind('<<ComboboxSelected>>', self.on_drive_changed)

        # 重新索引按钮
        reindex_btn = Button(top_frame, text="重新索引", command=self.reindex,
                            font=("微软雅黑", 9))
        reindex_btn.pack(side=LEFT, padx=(0, 10))

        # 搜索标签
        search_label = Label(top_frame, text="搜索:", font=("微软雅黑", 12))
        search_label.pack(side=LEFT, padx=(0, 10))

        # 搜索输入框
        self.search_var = StringVar()
        self.search_entry = Entry(top_frame, textvariable=self.search_var,
                                   font=("微软雅黑", 14), width=40)
        self.search_entry.pack(side=LEFT, fill=X, expand=True)
        self.search_entry.bind('<KeyRelease>', self.on_search)

        # 状态标签
        self.status_label = Label(top_frame, text="正在建立索引...",
                                  font=("微软雅黑", 10), fg="gray")
        self.status_label.pack(side=LEFT, padx=(10, 0))

        # 结果列表区域
        list_frame = Frame(self.root)
        list_frame.pack(side=TOP, fill=BOTH, expand=True, padx=10, pady=(0, 10))

        # 创建 Treeview
        columns = ("filename", "path", "size")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                  selectmode="extended")

        # 设置列
        self.tree.heading("filename", text="文件名")
        self.tree.heading("path", text="路径")
        self.tree.heading("size", text="大小")

        self.tree.column("filename", width=250, minwidth=150)
        self.tree.column("path", width=500, minwidth=200)
        self.tree.column("size", width=100, minwidth=80)

        # 添加滚动条
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # 布局
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        # 绑定双击事件
        self.tree.bind('<Double-Button-1>', self.on_double_click)

        # 底部状态栏
        self.bottom_label = Label(self.root, text="", bd=1, relief=SUNKEN, anchor=W)
        self.bottom_label.pack(side=BOTTOM, fill=X)

        # 设置样式
        style = ttk.Style()
        style.configure("Treeview", rowheight=25)
        style.configure("Treeview.Heading", font=("微软雅黑", 10, "bold"))

    def format_size(self, size):
        """格式化文件大小"""
        if size < 0:
            return "未知"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"

    def get_available_drives(self):
        """获取可用的驱动器"""
        drives = []
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:"
            if os.path.exists(drive):
                drives.append(drive)
        return drives

    def on_drive_changed(self, event):
        """驱动器选择改变"""
        selected = self.drive_var.get()
        self.current_drive = selected + "\\"
        self.reindex()

    def reindex(self):
        """重新索引"""
        # 清空搜索结果
        self.search_var.set("")
        self.display_results([])
        self.start_indexing()

    def start_indexing(self):
        """开始索引文件"""
        self.is_indexing = True
        self.file_index = []

        # 使用线程进行索引，避免界面卡顿
        index_thread = threading.Thread(target=self.index_files, daemon=True)
        index_thread.start()

    def index_files(self):
        """遍历文件并建立索引"""
        drive = self.current_drive

        self.status_label.config(text="正在建立索引...", fg="orange")
        count = 0

        try:
            for root_dir, dirs, files in os.walk(drive):
                # 跳过系统目录和隐藏目录以加快速度
                dirs[:] = [d for d in dirs if not d.startswith('.')
                          and d not in ['$Recycle.Bin', 'System Volume Information',
                                       'Windows', 'ProgramData']]

                for filename in files:
                    try:
                        filepath = os.path.join(root_dir, filename)
                        # 获取文件大小
                        try:
                            size = os.path.getsize(filepath)
                        except (OSError, PermissionError):
                            size = -1

                        # 添加到索引
                        self.file_index.append((filename.lower(), filename, filepath, size))
                        count += 1

                        # 每1000个文件更新一次状态
                        if count % 1000 == 0:
                            self.root.after(0, lambda c=count: self.status_label.config(
                                text=f"已索引 {c:,} 个文件...", fg="orange"))
                    except (OSError, PermissionError):
                        continue

                # 限制索引深度，避免太慢
                if count > 100000:  # 限制最多10万个文件
                    break

        except Exception as e:
            print(f"索引错误: {e}")

        # 排序索引
        self.file_index.sort(key=lambda x: x[1])  # 按文件名排序

        self.is_indexing = False
        self.indexing_complete = True

        # 更新界面
        self.root.after(0, lambda: self.status_label.config(
            text=f"索引完成，共 {len(self.file_index):,} 个文件", fg="green"))
        self.root.after(0, lambda: self.bottom_label.config(
            text=f"索引完成: {len(self.file_index):,} 个文件"))

        # 自动执行一次搜索（显示所有文件）
        self.root.after(0, lambda: self.on_search(None))

    def on_search(self, event):
        """搜索框输入事件"""
        keyword = self.search_var.get().strip().lower()

        if not keyword:
            # 没有关键词，显示所有文件（限制数量）
            results = [(f, p, s) for _, f, p, s in self.file_index[:1000]]
            self.display_results(results)
            return

        # 过滤结果 - 在文件名和路径中搜索
        results = []
        for _, filename, filepath, size in self.file_index:
            if keyword in filename.lower() or keyword in filepath.lower():
                results.append((filename, filepath, size))
                if len(results) >= 1000:  # 限制显示数量
                    break

        self.display_results(results)

        # 更新状态
        self.bottom_label.config(text=f"找到 {len(results):,} 个结果")

    def display_results(self, results):
        """显示搜索结果"""
        # 清空现有结果
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 添加结果
        for filename, filepath, size in results:
            size_str = self.format_size(size)
            self.tree.insert("", END, values=(filename, filepath, size_str))

    def on_double_click(self, event):
        """双击打开文件或文件夹"""
        # 获取选中的项目
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        values = item["values"]

        if not values:
            return

        filename, filepath, _ = values

        # 检查文件是否存在
        if not os.path.exists(filepath):
            messagebox.showerror("错误", f"文件不存在或已被移动:\n{filepath}")
            return

        try:
            # 使用系统默认程序打开文件
            os.startfile(filepath)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件:\n{str(e)}")


def main():
    """主函数"""
    # 创建主窗口
    root = Tk()

    # 设置应用
    app = FileSearchApp(root)

    # 运行应用
    root.mainloop()


if __name__ == "__main__":
    main()
