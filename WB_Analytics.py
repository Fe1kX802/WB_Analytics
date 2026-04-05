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
import random
import os
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import webbrowser

ctk.set_appearance_mode("light") 
ctk.set_default_color_theme("blue")


# --- Цветовые схемы для графиков ---
THEMES = {
    "light": {
        "bg": "#ffffff",        
        "fg": "#4A4A8E",
        "grid": "#E0E7FF",
        "plot_style": "default"
    },
    "dark": {
        "bg": "#1e1e1e",
        "fg": "#e0e0e0",
        "grid": "#444444",
        "plot_style": "dark_background"
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

        self.is_dark_mode = False
        self.save_dir = Path.home() / 'Documents' / 'wb_reports'
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        self.reports_data = {}
        self.master_df = pd.DataFrame()
        self.barcode_map = {}
    
        self.load_barcode_map()
        self.setup_ui()
        self.load_saved_reports()

    def load_barcode_map(self):
        """Логика загрузки словаря сохранена"""
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


        # Кнопка "Удалить тест" (скрыта в релизной программе)
        '''
        self.btn_del = ctk.CTkButton(
            self.btn_group, text="🗑 Удалить тест", command=self.delete_pseudo_reports,
            fg_color="#FF8A8A", hover_color="#FF6B6B", width=120, corner_radius=15
        )
        self.btn_del.pack(side=tk.LEFT, padx=5)
        '''

        self.btn_add = ctk.CTkButton(
            self.btn_group, text="Открыть редактор баркодов", command=self.open_barcodes,
            fg_color="#FFDE71", text_color="#555143", hover_color="#FFD257", 
            width=120, corner_radius=15, font=ctk.CTkFont(weight="bold")
        )
        self.btn_add.pack(side=tk.LEFT, padx=5)


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

        # Выпадающие списки (values=[] исправляет CtkComboBox)
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
        
        # Настройка фигуры Matplotlib
        self.figure, self.ax = plt.subplots(figsize=(10, 5), facecolor='white')
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.graph_card)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        # Контейнер для нижних кнопок
        self.bottom_btn_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.bottom_btn_frame.pack(pady=(0, 10))

        # Кнопка "На графике"
        ctk.CTkButton(self.bottom_btn_frame, text="📊 ТОВАРЫ НА ГРАФИКЕ", 
                      command=self.open_separate_window, fg_color="transparent", 
                      text_color="#7B61FF", border_width=2, border_color="#7B61FF", 
                      corner_radius=15, hover_color="#F0EEFF").pack(side=tk.LEFT, padx=10)

        # Кнопка "Строкой"
        ctk.CTkButton(self.bottom_btn_frame, text="📦 ТОВАРЫ СТРОКОЙ", 
                      command=self.open_stock_window, fg_color="transparent", 
                      text_color="#7B61FF", border_width=2, border_color="#7B61FF", 
                      corner_radius=15, hover_color="#F0EEFF").pack(side=tk.LEFT, padx=10)

        # Футер
        self.lbl_author = ctk.CTkLabel(self.main_container, text="made by @iFe1kx", font=("Courier New", 11), text_color="#4A4A8E", cursor="hand2")
        self.lbl_author.pack(side=tk.BOTTOM, pady=5)
        self.lbl_author.bind("<Button-1>", lambda e: webbrowser.open("https://t.me/iFe1kx"))

    def draw_gradient_event(self, event):
        """Метод для отрисовки градиента при изменении размера окна"""
        self.bg_canvas.delete("all")
        width = event.width
        height = event.height
        
        # Твои цвета
        color1 = "#ebd1ff"
        color2 = "#ebe1fe"
        color3 = "#e5e7ff"
        
        def interpolate(c1, c2, f):
            r1, g1, b1 = self.root.winfo_rgb(c1)
            r2, g2, b2 = self.root.winfo_rgb(c2)
            r = int(r1 + f * (r2 - r1))
            g = int(g1 + f * (g2 - g1))
            b = int(b1 + f * (b2 - b1))
            return f"#{r>>8:02x}{g>>8:02x}{b>>8:02x}"

        steps = 100
        for i in range(steps):
            f = i / steps
            if f < 0.5:
                curr_color = interpolate(color1, color2, f * 2)
            else:
                curr_color = interpolate(color2, color3, (f - 0.5) * 2)

            offset = height * 0.5
            self.bg_canvas.create_polygon(
                0, i * (height/steps) + offset,
                width, i * (height/steps) - offset,
                width, (i+1) * (height/steps) - offset,
                0, (i+1) * (height/steps) + offset,
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

        # Подготовка дат
        dates = sorted([d.strftime("%Y-%m-%d") for d in self.master_df['Дата'].dt.date.unique()])

        # Обновляем списки и устанавливаем значения, чтобы убрать надпись CTkComboBox
        self.cb_from.configure(values=dates)
        self.cb_to.configure(values=dates)

        if not self.cb_from.get() or self.cb_from.get() == "CTkComboBox":
            self.cb_from.set(dates[0])
            self.cb_to.set(dates[-1])

        # Подготовка метрик
        metrics = [c for c in self.master_df.columns if c not in {'Бренд', 'Предмет', 'Баркод', 'Дата'}]
        self.cb_metric.configure(values=metrics)

        if (not self.cb_metric.get() or self.cb_metric.get() == "CTkComboBox") and metrics:
            self.cb_metric.set(metrics[0])

        self.refresh_barcode_list()

    def update_graph(self):
        # Проверка наличия данных
        if self.master_df.empty: 
            self.ax.clear()
            self.canvas.draw()
            return
        
        # Определение темы (цвета для графика)
        # Легаси код!!!
        is_dark = getattr(self, 'is_dark_mode', False)
        t = THEMES["dark"] if is_dark else THEMES["light"]
        plt.style.use(t["plot_style"])
        
        # Получение значений из фильтров
        metric = self.cb_metric.get()
        selected_ui_value = self.cb_barcode.get()
        
        # Если выбор еще не сделан или там текст по умолчанию
        if not metric or metric == "CTkComboBox" or not selected_ui_value or selected_ui_value == "CTkComboBox":
            return

        # Очистка старого рисунка
        self.ax.clear()
        self.figure.set_facecolor(t["bg"])
        self.ax.set_facecolor(t["bg"])

        # Фильтрация данных по датам
        try:
            start_date = pd.to_datetime(self.cb_from.get())
            end_date = pd.to_datetime(self.cb_to.get())
            mask = (self.master_df['Дата'] >= start_date) & (self.master_df['Дата'] <= end_date)
            df = self.master_df[mask].copy()
        except:
            return # Если даты еще не прогрузились

        df[metric] = pd.to_numeric(df[metric], errors='coerce').fillna(0)

        # Логика выбора конкретного товара или суммы
        if selected_ui_value == "Суммарно все товары":
            res = df.groupby('Дата')[metric].sum()
            label_text = "Все товары"
        else:
            # Ищем баркод (target_bc). Если включены названия — ищем по словарю
            target_bc = selected_ui_value
            if self.show_names_var.get():
                for bc, name in self.barcode_map.items():
                    if name == selected_ui_value:
                        target_bc = bc
                        break
            
            res = df[df['Баркод'] == str(target_bc)].groupby('Дата')[metric].sum()
            label_text = selected_ui_value

        # Покраска по правилам 5-15-более
        if not res.empty:
            last_val = res.iloc[-1]
            if last_val < 5:
                line_color = "#FF4C4C"
            elif 5 <= last_val <= 15:
                line_color = "#FFCC00"
            else:
                line_color = "#2ECC71"

            # Сама линия
            self.ax.plot(res.index, res.values, marker='o', color=line_color, 
                         linewidth=3, markersize=8, label=f"{label_text}")
            
            # Мягкая заливка под графиком
            # Не работает при значениях 0-0, пофиксить
            self.ax.fill_between(res.index, res.values, color=line_color, alpha=0.1)

            # Подписи чисел над точками
            for x, y in zip(res.index, res.values):
                self.ax.annotate(f'{int(y)}', (x, y), xytext=(0, 10), 
                                 textcoords="offset points", ha='center', 
                                 color=t["fg"], fontweight='bold', fontsize=10)

        # Финальное оформление осей
        self.ax.set_title(f"Показатель: {metric}", color=t["fg"], pad=20, fontsize=12, fontweight='bold')
        self.ax.tick_params(colors=t["fg"], labelsize=9)
        
        # Сетка и рамки
        self.ax.grid(True, alpha=0.2, color=t.get("grid", "#ddd"))
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['left'].set_color(t["fg"])
        self.ax.spines['bottom'].set_color(t["fg"])

        # Обновляем холст
        self.figure.tight_layout()
        self.canvas.draw()

    def open_separate_window(self):
        """Открывает окно с раздельной динамикой по всем товарам"""
        if self.master_df.empty:
            messagebox.showwarning("Внимание", "Нет данных для отображения")
            return
        
        # Собираем параметры для нового окна
        params = {
            'df': self.master_df.copy(),
            'date_from': self.cb_from.get(),
            'date_to': self.cb_to.get(),
            'metric': self.cb_metric.get(),
            'barcode_map': self.barcode_map,
            'show_names': self.show_names_var.get()
        }
        # Запускаем новое окно
        SeparateChartWindow(params)

    def open_stock_window(self):
        """Открывает окно сравнения остатков по датам"""
        if self.master_df.empty: 
            return
        params = {
            'df': self.master_df, 'date_from': self.cb_from.get(), 'date_to': self.cb_to.get(), 
            'metric': self.cb_metric.get(), 'barcode_map': self.barcode_map, 'show_names': self.show_names_var.get()
        }
        StockCompareWindow(params)


    # Легаси код, не работает!!!
    def create_gradient(self, canvas, width, height):
        color1 = "#ebd1ff"
        color2 = "#ebe1fe"
        color3 = "#e5e7ff"
        
        # Функция для интерполяции цветов
        def interpolate(c1, c2, f):
            r1, g1, b1 = canvas.winfo_rgb(c1)
            r2, g2, b2 = canvas.winfo_rgb(c2)
            r = int(r1 + f * (r2 - r1))
            g = int(g1 + f * (g2 - g1))
            b = int(b1 + f * (b2 - b1))
            return f"#{r>>8:02x}{g>>8:02x}{b>>8:02x}"

        # Отрисовка полос под углом 145 градусов
        steps = 100
        for i in range(steps):
            if i < steps // 2:
                fill = interpolate(color1, color2, i / (steps // 2))
            else:
                fill = interpolate(color2, color3, (i - steps // 2) / (steps // 2))

            canvas.create_rectangle(0, i * (height/steps), width, (i+1) * (height/steps), 
                                    fill=fill, outline=fill)

    def delete_pseudo_reports(self):
        files = list(self.save_dir.glob("pseudo_report_*"))
        if files and messagebox.askyesno("Удаление", f"Удалить {len(files)} тестов?"):
            for f in files: os.remove(f)
            self.reports_data = {}; self.load_saved_reports(); self.update_graph()

    def load_saved_reports(self):
        files = list(self.save_dir.glob("*.xlsx")) + list(self.save_dir.glob("*.csv"))
        self.process_files([str(f) for f in files])

    def add_reports(self):
        paths = filedialog.askopenfilenames(filetypes=[("Excel/CSV", "*.xlsx *.csv")])
        if paths: self.process_files(paths, copy_files=True); self.update_graph()

    def open_barcodes(self):
        path = Path.home() / 'Documents' / 'wb_reports' / 'barcodes.txt'
        if not path.exists():
            path.touch()
        try:
            os.startfile(str(path))
        except Exception as e:
            print(f"Не удалось открыть файл: {e}")


class SeparateChartWindow(ctk.CTkToplevel):
    def __init__(self, params):
        super().__init__()
        self.title("Товары на складе графиком")
        
        # Адаптивная геометрия окна для 1366x768
        screen_height = self.winfo_screenheight()
        if screen_height <= 800:
            self.after(10, lambda: self.state('zoomed'))
        else:
            self.geometry("1250x820")
            
        self.configure(fg_color="#F8FAFF")

        # Основной контейнер
        f = ctk.CTkFrame(self, fg_color="white", corner_radius=20)
        f.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 10))

        # Настройки графика
        fig, ax = plt.subplots(figsize=(9, 4.5), facecolor='white')
        self.ax = ax
        
        mask = (params['df']['Дата'] >= pd.to_datetime(params['date_from'])) & \
               (params['df']['Дата'] <= pd.to_datetime(params['date_to']))
        df = params['df'][mask].copy()
        
        unique_bcs = df['Баркод'].unique()
        num_items = len(unique_bcs)

        import numpy as np
        import matplotlib.cm as cm
        colors = cm.rainbow(np.linspace(0, 1, num_items)) if num_items > 0 else []
        
        self.lines_map = {}
        self.orig_colors = {}
        self.active_annotation = None

        # Отрисовка линий
        for bc, color in zip(unique_bcs, colors):
            d = df[df['Баркод'] == bc].groupby('Дата')[params['metric']].sum()
            label_name = params['barcode_map'].get(str(bc), bc) if params['show_names'] else bc
            
            line, = ax.plot(d.index, d.values, marker='o', label=label_name, 
                            color=color, linewidth=2, markersize=5)
            
            self.lines_map[label_name] = line
            self.orig_colors[label_name] = color
            
        ax.set_title(f"Метрика: {params['metric']}", pad=15, fontsize=12, fontweight='bold', color="#4A4A8E")
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.1, color="#E0E7FF")
        ax.tick_params(colors="#4A4A8E", labelsize=9)

        # Легенда
        if num_items > 0:
            ncol = 5 
            
            self.legend = ax.legend(
                loc='upper center', 
                bbox_to_anchor=(0.5, -0.08), # Максимально прижимаем к графику
                fancybox=True, 
                shadow=False, 
                ncol=ncol, 
                fontsize=9,
                labelcolor="#4A4A8E",
                labelspacing=0.3,
                columnspacing=0.8,
                handletextpad=0.2
            )

            self.legend_map = {}
            for leg_line, leg_text in zip(self.legend.get_lines(), self.legend.get_texts()):
                leg_line.set_picker(True)
                leg_line.set_pickradius(10)
                leg_text.set_picker(True)
                self.legend_map[leg_line] = leg_text.get_text()
                self.legend_map[leg_text] = leg_text.get_text()

        # Коррекция отступов
        plt.tight_layout()
        num_rows = int(np.ceil(num_items / ncol)) if num_items > 0 else 0
        
        # Динамический расчет места: 0.08 база + 0.025 за каждую строку легенды
        calculated_bottom = 0.08 + (0.025 * num_rows)
        bottom_margin = min(calculated_bottom, 0.38) # Лимит 38% высоты окна под легенду
        
        fig.subplots_adjust(
            bottom=bottom_margin, 
            top=0.92, 
            left=0.06, 
            right=0.96
        )

        self.canvas = FigureCanvasTkAgg(fig, master=f)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        if num_items > 0:
            self.canvas.mpl_connect('pick_event', self.on_pick)
            self.canvas.mpl_connect('button_press_event', self.on_click)
        
        # Фикс бага с открытием на заднем плане (критично)
        self.lift()
        self.focus_force()
        self.grab_set()

    def on_pick(self, event):
        # Фикс бага с выбором товара прокруткой
        if event.mouseevent.button != 1:
            return

        artist = event.artist
        if artist in getattr(self, 'legend_map', {}):
            clicked_label = self.legend_map[artist]

            if self.active_annotation:
                self.active_annotation.remove()
                self.active_annotation = None

            for label, line in self.lines_map.items():
                if label == clicked_label:
                    line.set_color(self.orig_colors[label])
                    line.set_alpha(1.0)
                    line.set_linewidth(4.5)
                    line.set_zorder(10)

                    xdata, ydata = line.get_xdata(), line.get_ydata()
                    if len(xdata) > 0:
                        last_x, last_y = xdata[-1], ydata[-1]
                        self.active_annotation = self.ax.annotate(
                            f" {int(last_y)} ", 
                            xy=(last_x, last_y), xytext=(12, 0),
                            textcoords="offset points", va="center", ha="left",
                            fontsize=11, fontweight="bold", color="white",
                            bbox=dict(boxstyle="round,pad=0.3", fc=self.orig_colors[label], ec="none", alpha=0.9)
                        )
                else:
                    line.set_color('#E0E4F0') 
                    line.set_alpha(0.15)
                    line.set_linewidth(1.0)
                    line.set_zorder(1)

            self.canvas.draw_idle()

    def on_click(self, event):
        if event.button != 1:
            return

        if hasattr(self, 'legend'):
            contains, _ = self.legend.contains(event)
            if contains: return

        if self.active_annotation:
            self.active_annotation.remove()
            self.active_annotation = None

        for label, line in self.lines_map.items():
            line.set_color(self.orig_colors[label])
            line.set_alpha(1.0)
            line.set_linewidth(2)
            line.set_zorder(2)

        self.canvas.draw_idle()


class StockCompareWindow(ctk.CTkToplevel):
    def __init__(self, params):
        super().__init__()
        self.title("Товары на складе строкой")
        self.geometry("850x700")
        self.configure(fg_color="#F8FAFF")

        metric = params['metric']
        
        # Блок с названием склада
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill=tk.X, padx=30, pady=(25, 15))
        
        ctk.CTkLabel(title_frame, text="Метрика:", font=("Segoe UI", 12), text_color="#7B61FF").pack(anchor="w")
        ctk.CTkLabel(title_frame, text=metric.upper(), 
                     font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"), 
                     text_color="#4A4A8E", anchor="w").pack(anchor="w")

        # Получаем данные и фильтруем по выбранному периоду
        mask = (params['df']['Дата'] >= pd.to_datetime(params['date_from'])) & \
               (params['df']['Дата'] <= pd.to_datetime(params['date_to']))
        df = params['df'][mask].copy()
        
        # Преобразование в числа
        if metric in df.columns:
            df[metric] = pd.to_numeric(df[metric], errors='coerce').fillna(0)
        else:
            # Защита на случай, если метрика не нашлась в колонках
            ctk.CTkLabel(self, text=f"⚠️ Ошибка: Метрика '{metric}' не найдена в данных.", 
                         font=("Segoe UI", 16, "bold"), text_color="#FF4C4C").pack(pady=50)
            return

        # Достаем все уникальные даты и сортируем
        dates = sorted(df['Дата'].unique())
        if len(dates) < 2:
            ctk.CTkLabel(self, text="⚠️ Недостаточно данных для сравнения.\nЗагрузите минимум 2 разных отчета за выбранный период.", 
                         font=("Segoe UI", 16, "bold"), text_color="#FF4C4C", justify="center").pack(pady=50)
            return

        # Берем предпоследнюю и последнюю дату
        prev_date = dates[-2]
        last_date = dates[-1]
        
        # Форматируем даты для заголовков
        prev_date_str = pd.to_datetime(prev_date).strftime('%d.%m.%Y')
        last_date_str = pd.to_datetime(last_date).strftime('%d.%m.%Y')

        # Заголовок таблицы
        header_frame = ctk.CTkFrame(self, fg_color="white", corner_radius=12, border_width=1, border_color="#E0E7FF")
        header_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        # Заголовки столбцов
        ctk.CTkLabel(header_frame, text="Название товара", font=ctk.CTkFont(weight="bold", size=14), width=380, anchor="w", text_color="#7B61FF").pack(side=tk.LEFT, padx=15, pady=12)
        ctk.CTkLabel(header_frame, text=prev_date_str, font=ctk.CTkFont(weight="bold", size=14), width=100, text_color="#7B61FF").pack(side=tk.LEFT, padx=10)
        ctk.CTkLabel(header_frame, text=" ", width=40).pack(side=tk.LEFT) # Отступ под стрелку
        ctk.CTkLabel(header_frame, text=last_date_str, font=ctk.CTkFont(weight="bold", size=14), width=100, text_color="#7B61FF").pack(side=tk.LEFT, padx=10)

        # Скролльный список товаров
        scroll_frame = ctk.CTkScrollableFrame(self, fg_color="white", corner_radius=15, border_width=1, border_color="#E0E7FF")
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Функция для получения цвета по правилу 5-15-более
        def get_color(val):
            if val < 5: return "#FF4C4C"
            if 5 <= val <= 15: return "#FFCC00"
            return "#2ECC71"

        unique_bcs = df['Баркод'].unique()
        
        # Сортируем товары по имени для удобства
        sorted_items = []
        for bc in unique_bcs:
            name = params['barcode_map'].get(str(bc), str(bc)) if params['show_names'] else str(bc)
            sorted_items.append((name, bc))
        sorted_items.sort(key=lambda x: x[0])

        for name, bc in sorted_items:
            # Вытягиваем данные по конкретному товару
            item_data = df[df['Баркод'] == bc].groupby('Дата')[metric].sum()
            
            # Получаем остатки (если товара не было в этот день, вернет 0)
            val_prev = int(item_data.get(prev_date, 0))
            val_last = int(item_data.get(last_date, 0))
            
            row_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            row_frame.pack(fill=tk.X, pady=5)

            # Столбец 1: Имя товара
            ctk.CTkLabel(row_frame, text=name, width=380, anchor="w", font=("Segoe UI", 13), text_color="#4A4A8E").pack(side=tk.LEFT, padx=15)
            
            # Столбец 2: Остаток на предпоследнюю дату
            ctk.CTkLabel(row_frame, text=str(val_prev), width=100, font=ctk.CTkFont(family="Segoe UI", weight="bold", size=15), text_color=get_color(val_prev)).pack(side=tk.LEFT, padx=10)
            
            # Стрелочка
            ctk.CTkLabel(row_frame, text="➔", width=40, font=("Segoe UI", 16), text_color="#C0C0D8").pack(side=tk.LEFT)
            
            # Столбец 3: Остаток на последнюю дату
            ctk.CTkLabel(row_frame, text=str(val_last), width=100, font=ctk.CTkFont(family="Segoe UI", weight="bold", size=15), text_color=get_color(val_last)).pack(side=tk.LEFT, padx=10)
            
            # Тонкая линия-разделитель между товарами
            divider = ctk.CTkFrame(scroll_frame, height=1, fg_color="#F0F0F5")
            divider.pack(fill=tk.X, padx=10)

        # Фикс бага с открытием на заднем плане (критично)
        self.lift()
        self.focus_force()
        self.grab_set()


if __name__ == "__main__":
    root = ctk.CTk() 
    app = WbTrackerApp(root)
    root.mainloop()