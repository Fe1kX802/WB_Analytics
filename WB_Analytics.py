try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
import customtkinter as ctk 
from tkinter import filedialog, messagebox
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import re
import os
from datetime import datetime
from pathlib import Path
import shutil
import webbrowser
import numpy as np
import matplotlib.cm as cm

ctk.set_appearance_mode("light") 
ctk.set_default_color_theme("blue")


# --- Цветовые схемы для графиков ---
THEMES = {
    "light": {
        "bg": "#ffffff",        
        "fg": "#4A4A8E",
        "grid": "#E0E7FF",
        "plot_style": "default"
    }
}


class WbTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WB Analytics")
        
        screen_height = self.root.winfo_screenheight()
        if screen_height <= 800:
            self.root.after(10, lambda: self.root.state('zoomed'))
        else:
            self.root.geometry("1250x850") 

        self.save_dir = Path.home() / 'Documents' / 'wb_analytics'
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        self.reports_data = {}
        self.master_df = pd.DataFrame()
        self.barcode_map = {}
    
        self.load_barcode_map()
        self.setup_ui()
        self.load_saved_reports()

    def load_barcode_map(self):
        self.barcode_map = {}
        path = self.save_dir / 'barcodes.txt'
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and '=' in line:
                            bc, name = line.split('=', 1)
                            self.barcode_map[bc.strip()] = name.strip()
            except Exception: pass

    def setup_ui(self):
        self.bg_canvas = tk.Canvas(self.root, highlightthickness=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bg_canvas.bind("<Configure>", self.draw_gradient_event)

        self.main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Header
        self.header = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.header.pack(fill=tk.X, padx=30, pady=(10, 5))

        self.lbl_title = ctk.CTkLabel(
            self.header, text="ДИНАМИКА ТОВАРОВ WB", 
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color="#4A4A8E"
        )
        self.lbl_title.pack(side=tk.LEFT)

        # Группа кнопок управления
        self.btn_group = ctk.CTkFrame(self.header, fg_color="transparent")
        self.btn_group.pack(side=tk.RIGHT)

        self.show_names_var = tk.BooleanVar(value=True)
        self.chk_names = ctk.CTkCheckBox(
            self.btn_group, text="Названия", variable=self.show_names_var, 
            command=self.refresh_barcode_list, checkbox_width=20, checkbox_height=20,
            text_color="#4A4A8E", fg_color="#7B61FF"
        )
        self.chk_names.pack(side=tk.LEFT, padx=10)

        self.btn_open_bc = ctk.CTkButton(
            self.btn_group, text="Открыть редактор баркодов", command=self.open_barcodes,
            fg_color="#FFDE71", text_color="#555143", hover_color="#FFD257", 
            width=120, corner_radius=15, font=ctk.CTkFont(weight="bold")
        )
        self.btn_open_bc.pack(side=tk.LEFT, padx=5)

        self.btn_add = ctk.CTkButton(
            self.btn_group, text="+ Добавить отчет", command=self.add_reports,
            fg_color="#85FFD2", text_color="#2D5A4A", hover_color="#6EE7B7", 
            width=120, corner_radius=15, font=ctk.CTkFont(weight="bold")
        )
        self.btn_add.pack(side=tk.LEFT, padx=5)

        # Панель параметров
        self.filter_card = ctk.CTkFrame(
            self.main_container, fg_color="white", corner_radius=20, 
            border_width=1, border_color="#E0E7FF"
        )
        self.filter_card.pack(fill=tk.X, padx=30, pady=10)

        self.cb_from = ctk.CTkComboBox(self.filter_card, width=130, corner_radius=10, values=[], command=lambda x: self.update_graph())
        self.cb_from.pack(side=tk.LEFT, padx=15, pady=10)

        self.cb_to = ctk.CTkComboBox(self.filter_card, width=130, corner_radius=10, values=[], command=lambda x: self.update_graph())
        self.cb_to.pack(side=tk.LEFT, padx=5, pady=10)

        self.cb_barcode = ctk.CTkComboBox(self.filter_card, width=250, corner_radius=10, values=[], command=lambda x: self.update_graph())
        self.cb_barcode.pack(side=tk.LEFT, padx=15, pady=10)

        self.cb_metric = ctk.CTkComboBox(self.filter_card, width=220, corner_radius=10, values=[], command=lambda x: self.update_graph())
        self.cb_metric.pack(side=tk.LEFT, padx=5, pady=10)

        self.btn_plot = ctk.CTkButton(
            self.filter_card, text="ОБНОВИТЬ ГРАФИК", command=self.update_graph,
            fg_color="#7B61FF", hover_color="#6344FF", corner_radius=15, font=ctk.CTkFont(weight="bold")
        )
        self.btn_plot.pack(side=tk.RIGHT, padx=20, pady=10)

        # Область графика
        self.graph_card = ctk.CTkFrame(self.main_container, fg_color="white", corner_radius=20)
        self.graph_card.pack(fill=tk.BOTH, expand=True, padx=30, pady=12)
        
        self.figure, self.ax = plt.subplots(figsize=(10, 5), facecolor='white')
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.graph_card)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        # Контейнер для нижних кнопок
        self.bottom_btn_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.bottom_btn_frame.pack(pady=(0, 10))

        ctk.CTkButton(self.bottom_btn_frame, text="📊 ТОВАРЫ НА ГРАФИКЕ", 
                      command=self.open_separate_window, fg_color="transparent", 
                      text_color="#7B61FF", border_width=2, border_color="#7B61FF", 
                      corner_radius=15, hover_color="#F0EEFF").pack(side=tk.LEFT, padx=10)

        ctk.CTkButton(self.bottom_btn_frame, text="📦 ТОВАРЫ СТРОКОЙ", 
                      command=self.open_stock_window, fg_color="transparent", 
                      text_color="#7B61FF", border_width=2, border_color="#7B61FF", 
                      corner_radius=15, hover_color="#F0EEFF").pack(side=tk.LEFT, padx=10)

        # Футер
        self.lbl_author = ctk.CTkLabel(self.main_container, text="made by @iFe1kx", font=("Courier New", 11), text_color="#4A4A8E", cursor="hand2")
        self.lbl_author.pack(side=tk.BOTTOM, pady=5)
        self.lbl_author.bind("<Button-1>", lambda e: webbrowser.open("https://t.me/iFe1kx"))

    def draw_gradient_event(self, event):
        self.bg_canvas.delete("all")
        width, height = event.width, event.height
        color1, color2, color3 = "#ebd1ff", "#ebe1fe", "#e5e7ff"
        
        def interpolate(c1, c2, f):
            r1, g1, b1 = self.root.winfo_rgb(c1)
            r2, g2, b2 = self.root.winfo_rgb(c2)
            r = int(r1 + f * (r2 - r1))
            g = int(g1 + f * (g2 - g1))
            b = int(b1 + f * (b2 - b1))
            return f"#{r>>8:02x}{g>>8:02x}{b>>8:02x}"

        # Оптимизация: снижено со 100 до 50 шагов для ускорения рендера при растягивании окна
        steps = 50 
        for i in range(steps):
            f = i / steps
            curr_color = interpolate(color1, color2, f * 2) if f < 0.5 else interpolate(color2, color3, (f - 0.5) * 2)
            offset = height * 0.5
            self.bg_canvas.create_polygon(
                0, i * (height/steps) + offset, width, i * (height/steps) - offset,
                width, (i+1) * (height/steps) - offset, 0, (i+1) * (height/steps) + offset,
                fill=curr_color, outline=curr_color
            )

    def refresh_barcode_list(self):
        if self.master_df.empty: return
        unique_bcs = sorted(self.master_df['Баркод'].unique().tolist())
        display_values = ["Суммарно все товары"]
        for bc in unique_bcs:
            bc_str = str(bc).strip()
            name = self.barcode_map.get(bc_str, bc_str) if self.show_names_var.get() else bc_str
            display_values.append(name)
        
        self.cb_barcode.configure(values=display_values)
        if self.cb_barcode.get() == "CTkComboBox":
            self.cb_barcode.set(display_values[0])

    def process_files(self, file_paths, copy_files=False):
        new_added = False
        for path in file_paths:
            fname = Path(path).name
            match = re.search(r"(?:pseudo_)?report_(\d{4})_(\d{1,2})_(\d{1,2})", fname)
            if match:
                y, m, d = map(int, match.groups())
                dt = datetime(y, m, d).date()
                if copy_files:
                    dest = self.save_dir / fname
                    if Path(path) != dest: shutil.copy2(path, dest)
                try:
                    df = pd.read_excel(path) if str(path).endswith('.xlsx') else pd.read_csv(path)
                    if 'Баркод' in df.columns:
                        df['Баркод'] = df['Баркод'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                    self.reports_data[dt] = df
                    new_added = True
                except: continue
        if new_added:
            self.rebuild_master_df()
            self.update_comboboxes()

    def rebuild_master_df(self):
        frames = [df.assign(Дата=pd.to_datetime(d)) for d, df in self.reports_data.items()]
        self.master_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def update_comboboxes(self):
        if self.master_df.empty: return

        dates = sorted([d.strftime("%Y-%m-%d") for d in self.master_df['Дата'].dt.date.unique()])
        self.cb_from.configure(values=dates)
        self.cb_to.configure(values=dates)

        if not self.cb_from.get() or self.cb_from.get() == "CTkComboBox":
            self.cb_from.set(dates[0])
            self.cb_to.set(dates[-1])

        metrics = [c for c in self.master_df.columns if c not in {'Бренд', 'Предмет', 'Баркод', 'Дата'}]
        self.cb_metric.configure(values=metrics)

        if (not self.cb_metric.get() or self.cb_metric.get() == "CTkComboBox") and metrics:
            self.cb_metric.set(metrics[0])

        self.refresh_barcode_list()

    def update_graph(self):
        if self.master_df.empty: 
            self.ax.clear()
            self.canvas.draw()
            return
        
        t = THEMES["light"]
        plt.style.use(t["plot_style"])
        
        metric = self.cb_metric.get()
        selected_ui_value = self.cb_barcode.get()
        
        if not metric or metric == "CTkComboBox" or not selected_ui_value or selected_ui_value == "CTkComboBox":
            return

        self.ax.clear()
        self.figure.set_facecolor(t["bg"])
        self.ax.set_facecolor(t["bg"])

        try:
            start_date, end_date = pd.to_datetime(self.cb_from.get()), pd.to_datetime(self.cb_to.get())
            mask = (self.master_df['Дата'] >= start_date) & (self.master_df['Дата'] <= end_date)
            df = self.master_df[mask].copy()
        except: return 

        df[metric] = pd.to_numeric(df[metric], errors='coerce').fillna(0)

        if selected_ui_value == "Суммарно все товары":
            res = df.groupby('Дата')[metric].sum()
            label_text = "Все товары"
        else:
            target_bc = selected_ui_value
            if self.show_names_var.get():
                for bc, name in self.barcode_map.items():
                    if name == selected_ui_value:
                        target_bc = bc
                        break
            res = df[df['Баркод'] == str(target_bc)].groupby('Дата')[metric].sum()
            label_text = selected_ui_value

        if not res.empty:
            last_val = res.iloc[-1]
            line_color = "#FF4C4C" if last_val < 5 else "#FFCC00" if last_val <= 15 else "#2ECC71"

            self.ax.plot(res.index, res.values, marker='o', color=line_color, linewidth=3, markersize=8, label=f"{label_text}")
            self.ax.fill_between(res.index, res.values, color=line_color, alpha=0.1)

            for x, y in zip(res.index, res.values):
                self.ax.annotate(f'{int(y)}', (x, y), xytext=(0, 10), textcoords="offset points", 
                                 ha='center', color=t["fg"], fontweight='bold', fontsize=10)

        self.ax.set_title(f"Показатель: {metric}", color=t["fg"], pad=20, fontsize=12, fontweight='bold')
        self.ax.tick_params(colors=t["fg"], labelsize=9)
        self.ax.grid(True, alpha=0.2, color=t.get("grid", "#ddd"))
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['left'].set_color(t["fg"])
        self.ax.spines['bottom'].set_color(t["fg"])

        self.figure.tight_layout()
        self.canvas.draw()

    def open_separate_window(self):
        if self.master_df.empty:
            messagebox.showwarning("Внимание", "Нет данных для отображения")
            return
        params = {
            'df': self.master_df.copy(), 'date_from': self.cb_from.get(), 'date_to': self.cb_to.get(),
            'metric': self.cb_metric.get(), 'barcode_map': self.barcode_map, 'show_names': self.show_names_var.get()
        }
        SeparateChartWindow(params)

    def open_stock_window(self):
        if self.master_df.empty: return
        params = {
            'df': self.master_df.copy(), 'date_from': self.cb_from.get(), 'date_to': self.cb_to.get(), 
            'metric': self.cb_metric.get(), 'barcode_map': self.barcode_map, 'show_names': self.show_names_var.get()
        }
        StockCompareWindow(params)

    def load_saved_reports(self):
        files = list(self.save_dir.glob("*.xlsx")) + list(self.save_dir.glob("*.csv"))
        self.process_files([str(f) for f in files])

    def add_reports(self):
        paths = filedialog.askopenfilenames(filetypes=[("Excel/CSV", "*.xlsx *.csv")])
        if paths: self.process_files(paths, copy_files=True); self.update_graph()

    def open_barcodes(self):
        path = self.save_dir / 'barcodes.txt'
        if not path.exists():
            path.touch()
            messagebox.showinfo("Создание barcodes.txt", "Файл barcodes.txt только что был создан. Отсюда программа берет названия товаров, подставляя их вместо баркодов\nПри добавлении помните, что верный формат записи информации в файл -- [БАРКОД]=[НАЗВАНИЕ]\nПри иной записи программа проигнорирует ваш баркод")
        try: os.startfile(str(path))
        except Exception as e: print(f"Не удалось открыть файл: {e}")


class SeparateChartWindow(ctk.CTkToplevel):
    def __init__(self, params):
        super().__init__()
        self.title("Товары на складе графиком")
        if self.winfo_screenheight() <= 800: self.after(10, lambda: self.state('zoomed'))
        else: self.geometry("1250x820")
        self.configure(fg_color="#F8FAFF")

        f = ctk.CTkFrame(self, fg_color="white", corner_radius=20)
        f.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 10))

        fig, ax = plt.subplots(figsize=(9, 4.5), facecolor='white')
        self.ax = ax
        
        mask = (params['df']['Дата'] >= pd.to_datetime(params['date_from'])) & (params['df']['Дата'] <= pd.to_datetime(params['date_to']))
        df = params['df'][mask].copy()
        
        # Оптимизация: группируем все одним махом через pivot_table вместо цикла
        pivot_df = df.pivot_table(index='Дата', columns='Баркод', values=params['metric'], aggfunc='sum').fillna(0)
        num_items = len(pivot_df.columns)
        colors = cm.rainbow(np.linspace(0, 1, num_items)) if num_items > 0 else []
        
        self.lines_map, self.orig_colors, self.active_annotation = {}, {}, None

        for bc, color in zip(pivot_df.columns, colors):
            d = pivot_df[bc]
            label_name = params['barcode_map'].get(str(bc), str(bc)) if params['show_names'] else str(bc)
            line, = ax.plot(d.index, d.values, marker='o', label=label_name, color=color, linewidth=2, markersize=5)
            self.lines_map[label_name] = line
            self.orig_colors[label_name] = color
            
        ax.set_title(f"Метрика: {params['metric']}", pad=15, fontsize=12, fontweight='bold', color="#4A4A8E")
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.1, color="#E0E7FF")
        ax.tick_params(colors="#4A4A8E", labelsize=9)

        if num_items > 0:
            ncol = 5 
            self.legend = ax.legend(
                loc='upper center', bbox_to_anchor=(0.5, -0.08), fancybox=True, shadow=False, ncol=ncol, 
                fontsize=9, labelcolor="#4A4A8E", labelspacing=0.3, columnspacing=0.8, handletextpad=0.2
            )
            self.legend_map = {}
            for leg_line, leg_text in zip(self.legend.get_lines(), self.legend.get_texts()):
                leg_line.set_picker(True); leg_line.set_pickradius(10); leg_text.set_picker(True)
                self.legend_map[leg_line] = self.legend_map[leg_text] = leg_text.get_text()

        plt.tight_layout()
        num_rows = int(np.ceil(num_items / 5)) if num_items > 0 else 0
        fig.subplots_adjust(bottom=min(0.08 + (0.025 * num_rows), 0.38), top=0.92, left=0.06, right=0.96)

        self.canvas = FigureCanvasTkAgg(fig, master=f)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        if num_items > 0:
            self.canvas.mpl_connect('pick_event', self.on_pick)
            self.canvas.mpl_connect('button_press_event', self.on_click)
        
        self.lift(); self.focus_force(); self.grab_set()

    def on_pick(self, event):
        if event.mouseevent.button != 1: return
        artist = event.artist
        if artist in getattr(self, 'legend_map', {}):
            clicked_label = self.legend_map[artist]
            if self.active_annotation: self.active_annotation.remove(); self.active_annotation = None

            for label, line in self.lines_map.items():
                if label == clicked_label:
                    line.set_color(self.orig_colors[label]); line.set_alpha(1.0); line.set_linewidth(4.5); line.set_zorder(10)
                    xdata, ydata = line.get_xdata(), line.get_ydata()
                    if len(xdata) > 0:
                        self.active_annotation = self.ax.annotate(
                            f" {int(ydata[-1])} ", xy=(xdata[-1], ydata[-1]), xytext=(12, 0),
                            textcoords="offset points", va="center", ha="left", fontsize=11, fontweight="bold", color="white",
                            bbox=dict(boxstyle="round,pad=0.3", fc=self.orig_colors[label], ec="none", alpha=0.9)
                        )
                else:
                    line.set_color('#E0E4F0'); line.set_alpha(0.15); line.set_linewidth(1.0); line.set_zorder(1)
            self.canvas.draw_idle()

    def on_click(self, event):
        if event.button != 1: return
        if hasattr(self, 'legend') and self.legend.contains(event)[0]: return
        if self.active_annotation: self.active_annotation.remove(); self.active_annotation = None
        for label, line in self.lines_map.items():
            line.set_color(self.orig_colors[label]); line.set_alpha(1.0); line.set_linewidth(2); line.set_zorder(2)
        self.canvas.draw_idle()


class StockCompareWindow(ctk.CTkToplevel):
    def __init__(self, params):
        super().__init__()
        self.title("Товары на складе строкой")
        self.geometry("850x750")
        self.configure(fg_color="#F8FAFF")

        self.metric = params['metric']
        self.params = params
        
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill=tk.X, padx=30, pady=(25, 10))
        ctk.CTkLabel(title_frame, text="Метрика:", font=("Segoe UI", 12), text_color="#7B61FF").pack(anchor="w")
        ctk.CTkLabel(title_frame, text=self.metric.upper(), font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"), text_color="#4A4A8E", anchor="w").pack(anchor="w")

        mask = (params['df']['Дата'] >= pd.to_datetime(params['date_from'])) & (params['df']['Дата'] <= pd.to_datetime(params['date_to']))
        self.df = params['df'][mask].copy()
        
        if self.metric in self.df.columns:
            self.df[self.metric] = pd.to_numeric(self.df[self.metric], errors='coerce').fillna(0)
        else:
            ctk.CTkLabel(self, text=f"⚠️ Ошибка: Метрика '{self.metric}' не найдена в данных.", font=("Segoe UI", 16, "bold"), text_color="#FF4C4C").pack(pady=50)
            return

        dates = sorted(self.df['Дата'].unique())
        if len(dates) < 2:
            ctk.CTkLabel(self, text="⚠️ Недостаточно данных для сравнения.\nЗагрузите минимум 2 разных отчета за выбранный период.", font=("Segoe UI", 16, "bold"), text_color="#FF4C4C", justify="center").pack(pady=50)
            return

        self.prev_date, self.last_date = dates[-2], dates[-1]
        
        sort_frame = ctk.CTkFrame(self, fg_color="transparent")
        sort_frame.pack(fill=tk.X, padx=30, pady=(0, 15))
        ctk.CTkLabel(sort_frame, text="Сортировать:", font=("Segoe UI", 13, "bold"), text_color="#4A4A8E").pack(side=tk.LEFT, padx=(0, 15))
        
        self.sort_var = ctk.StringVar(value="По алфавиту")
        self.sort_menu = ctk.CTkSegmentedButton(
            sort_frame, values=["По алфавиту", "Больше остатков", "Меньше остатков"], variable=self.sort_var, command=self.render_items,
            unselected_color="#E0E0E0", selected_color="#CCCCCC", unselected_hover_color="#D5D5D5", selected_hover_color="#BDBDBD",
            text_color="black", font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.sort_menu.pack(side=tk.LEFT)

        header_frame = ctk.CTkFrame(self, fg_color="white", corner_radius=12, border_width=1, border_color="#E0E7FF")
        header_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        ctk.CTkLabel(header_frame, text="Название товара", font=ctk.CTkFont(weight="bold", size=14), width=380, anchor="w", text_color="#7B61FF").pack(side=tk.LEFT, padx=15, pady=12)
        ctk.CTkLabel(header_frame, text=pd.to_datetime(self.prev_date).strftime('%d.%m.%Y'), font=ctk.CTkFont(weight="bold", size=14), width=100, text_color="#7B61FF").pack(side=tk.LEFT, padx=10)
        ctk.CTkLabel(header_frame, text=" ", width=40).pack(side=tk.LEFT) 
        ctk.CTkLabel(header_frame, text=pd.to_datetime(self.last_date).strftime('%d.%m.%Y'), font=ctk.CTkFont(weight="bold", size=14), width=100, text_color="#7B61FF").pack(side=tk.LEFT, padx=10)

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="white", corner_radius=15, border_width=1, border_color="#E0E7FF")
        self.scroll_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Оптимизация: уходим от поиска через фильтрацию внутри цикла 
        pivot_df = self.df.pivot_table(index='Баркод', columns='Дата', values=self.metric, aggfunc='sum').fillna(0)
        
        self.item_data_list = []
        for bc in pivot_df.index:
            name = params['barcode_map'].get(str(bc), str(bc)) if params['show_names'] else str(bc)
            val_prev = int(pivot_df.loc[bc].get(self.prev_date, 0))
            val_last = int(pivot_df.loc[bc].get(self.last_date, 0))
            self.item_data_list.append({'name': name, 'val_prev': val_prev, 'val_last': val_last})

        self.render_items()
        self.lift(); self.focus_force(); self.grab_set()

    def render_items(self, *args):
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
            
        sort_mode = self.sort_var.get()
        if sort_mode == "По алфавиту": self.item_data_list.sort(key=lambda x: x['name'])
        elif sort_mode == "Больше остатков": self.item_data_list.sort(key=lambda x: x['val_last'], reverse=True)
        elif sort_mode == "Меньше остатков": self.item_data_list.sort(key=lambda x: x['val_last'])

        get_color = lambda val: "#FF4C4C" if val < 5 else "#FFCC00" if val <= 15 else "#2ECC71"

        for item in self.item_data_list:
            row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
            row_frame.pack(fill=tk.X, pady=5)

            ctk.CTkLabel(row_frame, text=item['name'], width=380, anchor="w", font=("Segoe UI", 13), text_color="#4A4A8E").pack(side=tk.LEFT, padx=15)
            ctk.CTkLabel(row_frame, text=str(item['val_prev']), width=100, font=ctk.CTkFont(family="Segoe UI", weight="bold", size=15), text_color=get_color(item['val_prev'])).pack(side=tk.LEFT, padx=10)
            ctk.CTkLabel(row_frame, text="➔", width=40, font=("Segoe UI", 16), text_color="#C0C0D8").pack(side=tk.LEFT)
            ctk.CTkLabel(row_frame, text=str(item['val_last']), width=100, font=ctk.CTkFont(family="Segoe UI", weight="bold", size=15), text_color=get_color(item['val_last'])).pack(side=tk.LEFT, padx=10)
            
            ctk.CTkFrame(self.scroll_frame, height=1, fg_color="#F0F0F5").pack(fill=tk.X, padx=10)

if __name__ == "__main__":
    root = ctk.CTk() 
    app = WbTrackerApp(root)
    root.mainloop()