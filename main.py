import os
import sys
import shutil

os.environ["OPENBLAS_NUM_THREADS"] = "1"

from kivy.utils import platform as kivy_platform
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.clock import Clock

if kivy_platform == 'win':
    Window.maximize()
else:
    Window.softinput_mode = 'below_target'

if hasattr(sys, '_MEIPASS'):
    RESOURCE_DIR = sys._MEIPASS
else:
    RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_exe_safe_path(filename):
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else ''
    for folder in [RESOURCE_DIR, exe_dir]:
        if folder:
            full_path = os.path.join(folder, filename)
            if os.path.exists(full_path):
                return full_path
    return filename

if kivy_platform == 'android':
    try:
        from android.storage import app_storage_path
        DATA_DIR = app_storage_path()
    except Exception:
        DATA_DIR = os.path.expanduser('~')
    PUBLIC_EXPORT_DIR = '/storage/emulated/0/Download/Primary_School_Panauta'
else:
    DATA_DIR = os.path.join(os.path.expanduser('~'), 'Documents', 'Primary_School_Panauta_Data')
    PUBLIC_EXPORT_DIR = DATA_DIR

os.makedirs(DATA_DIR, exist_ok=True)
try:
    os.makedirs(PUBLIC_EXPORT_DIR, exist_ok=True)
except Exception:
    PUBLIC_EXPORT_DIR = DATA_DIR
os.chdir(DATA_DIR)

def compress_image_under_30kb(src_path, dest_path, max_kb=28):
    try:
        abs_src = os.path.abspath(src_path)
        abs_dest = os.path.abspath(dest_path)
        os.makedirs(os.path.dirname(abs_dest), exist_ok=True)
        tmp_out = abs_dest + ".tmp_cmp.jpg"

        compressed_ok = False
        try:
            from PIL import Image as PILImage
            img = PILImage.open(abs_src)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((320, 400))
            quality = 75
            while quality >= 15:
                img.save(tmp_out, format="JPEG", quality=quality, optimize=True)
                if os.path.getsize(tmp_out) <= max_kb * 1024:
                    break
                quality -= 10
            compressed_ok = os.path.exists(tmp_out)
        except ImportError:
            if kivy_platform == 'android':
                from jnius import autoclass
                BitmapFactory = autoclass('android.graphics.BitmapFactory')
                Bitmap = autoclass('android.graphics.Bitmap')
                FileOutputStream = autoclass('java.io.FileOutputStream')
                CompressFormat = autoclass('android.graphics.Bitmap$CompressFormat')
                bmp = BitmapFactory.decodeFile(abs_src)
                if bmp:
                    scaled = Bitmap.createScaledBitmap(bmp, 240, 300, True)
                    q = 75
                    while q >= 15:
                        fos = FileOutputStream(tmp_out)
                        scaled.compress(CompressFormat.JPEG, q, fos)
                        fos.close()
                        if os.path.getsize(tmp_out) <= max_kb * 1024:
                            break
                        q -= 15
                    compressed_ok = os.path.exists(tmp_out)

        if compressed_ok and os.path.exists(tmp_out):
            if os.path.exists(abs_dest):
                try: os.remove(abs_dest)
                except Exception: pass
            os.replace(tmp_out, abs_dest)
            return abs_dest

        if abs_src != abs_dest:
            shutil.copyfile(abs_src, abs_dest)
        return abs_dest
    except Exception:
        return src_path

def capture_mobile_camera_safe(save_path, on_success_callback, popup_func):
    try:
        from android.permissions import request_permissions, check_permission, Permission
        perms = [Permission.CAMERA, Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE]
        if hasattr(Permission, 'READ_MEDIA_IMAGES'):
            perms.append(Permission.READ_MEDIA_IMAGES)

        def _launch_camera():
            try:
                from jnius import autoclass
                from android import activity
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')
                MediaStore = autoclass('android.provider.MediaStore')
                FileOutputStream = autoclass('java.io.FileOutputStream')
                CompressFormat = autoclass('android.graphics.Bitmap$CompressFormat')

                os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
                temp_cam_file = os.path.join(DATA_DIR, "raw_cam_" + os.path.basename(save_path))

                def on_activity_result(request_code, result_code, intent):
                    if request_code == 9001:
                        activity.unbind(on_activity_result=on_activity_result)
                        if result_code == -1 and intent is not None:
                            try:
                                extras = intent.getExtras()
                                if extras is not None:
                                    bmp = extras.get("data")
                                    if bmp is not None:
                                        fos = FileOutputStream(temp_cam_file)
                                        bmp.compress(CompressFormat.JPEG, 85, fos)
                                        fos.close()
                                        final_p = compress_image_under_30kb(temp_cam_file, save_path, max_kb=28)
                                        Clock.schedule_once(lambda dt: on_success_callback(final_p), 0.1)
                                        return
                                data_uri = intent.getData()
                                if data_uri is not None:
                                    resolver = PythonActivity.mActivity.getContentResolver()
                                    inp = resolver.openInputStream(data_uri)
                                    with open(temp_cam_file, "wb") as f_out:
                                        buf = bytearray(8192)
                                        while True:
                                            n = inp.read(buf)
                                            if n <= 0: break
                                            f_out.write(bytes(buf[:n]))
                                    inp.close()
                                    final_p = compress_image_under_30kb(temp_cam_file, save_path, max_kb=28)
                                    Clock.schedule_once(lambda dt: on_success_callback(final_p), 0.1)
                            except Exception as cap_err:
                                Clock.schedule_once(lambda dt: popup_func('Camera Save Info', str(cap_err)), 0.1)

                activity.bind(on_activity_result=on_activity_result)
                cam_intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                PythonActivity.mActivity.startActivityForResult(cam_intent, 9001)
            except Exception as cam_err:
                popup_func('Camera Info', f'Camera Error: {str(cam_err)}')

        if not check_permission(Permission.CAMERA):
            def _on_perm(permissions, grants):
                if any(grants):
                    Clock.schedule_once(lambda dt: _launch_camera(), 0.2)
                else:
                    popup_func('Permission Required', 'Please Allow Camera permission to capture photo.')
            request_permissions(perms, _on_perm)
        else:
            _launch_camera()
    except Exception as e:
        popup_func('Camera Info', f'Camera Error: {str(e)}')

# 📄 Windows + Android दोनों पर PDF/Excel खोलने और Downloads फ़ोल्डर में दिखाने का इंजन
def open_file_cross_platform(filepath, operation="open"):
    try:
        abs_path = os.path.abspath(filepath)
        # Android पर फ़ाइल को सीधे फोन के Downloads/Primary_School_Panauta में भी कॉपी करें ताकि यूजर देख सके
        if kivy_platform == 'android' and os.path.exists(abs_path):
            try:
                os.makedirs(PUBLIC_EXPORT_DIR, exist_ok=True)
                pub_copy = os.path.join(PUBLIC_EXPORT_DIR, os.path.basename(abs_path))
                if os.path.abspath(pub_copy) != abs_path:
                    shutil.copy(abs_path, pub_copy)
                    abs_path = pub_copy
            except Exception:
                pass

        if kivy_platform == 'win':
            os.startfile(abs_path, operation)
        elif kivy_platform == 'android':
            from jnius import autoclass
            StrictMode = autoclass('android.os.StrictMode')
            VmPolicyBuilder = autoclass('android.os.StrictMode$VmPolicy$Builder')
            StrictMode.setVmPolicy(VmPolicyBuilder().build())

            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            Uri = autoclass('android.net.Uri')
            File = autoclass('java.io.File')

            intent = Intent(Intent.ACTION_VIEW)
            uri = Uri.fromFile(File(abs_path))
            if abs_path.lower().endswith('.pdf'):
                mime = "application/pdf"
            elif abs_path.lower().endswith(('.xlsx', '.xls')):
                mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            else:
                mime = "*/*"
            intent.setDataAndType(uri, mime)
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_GRANT_READ_URI_PERMISSION)
            PythonActivity.mActivity.startActivity(Intent.createChooser(intent, "Open Report"))
    except Exception as e:
        print("File Open Log:", str(e))

LOGO_FILE = get_exe_safe_path('logo.png')
BASIC_FILE = get_exe_safe_path('basic.png')

def select_file_cross_platform(title_text, filters_list, on_file_selected_callback):
    if kivy_platform == 'win':
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
            fp = filedialog.askopenfilename(title=title_text, filetypes=filters_list)
            root.destroy()
            if fp:
                on_file_selected_callback(fp)
        except Exception as e:
            print("Windows Picker Error:", str(e))
    else:
        try:
            from jnius import autoclass
            from android import activity
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')

            f_str = str(filters_list).lower()
            has_docs = any(ext in f_str for ext in ['pdf', 'doc', 'xls', 'csv', 'document', 'notice'])
            is_only_image = (not has_docs) and any(ext in f_str for ext in ['jpg', 'png', 'jpeg', 'image'])

            if is_only_image:
                pick_intent = Intent(Intent.ACTION_PICK)
                pick_intent.setType("image/*")
            else:
                pick_intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
                pick_intent.addCategory(Intent.CATEGORY_OPENABLE)
                pick_intent.setType("*/*")

            def on_file_result(request_code, result_code, intent):
                if request_code == 9002:
                    activity.unbind(on_activity_result=on_file_result)
                    if result_code == -1 and intent is not None and intent.getData() is not None:
                        uri = intent.getData()
                        try:
                            resolver = PythonActivity.mActivity.getContentResolver()
                            mime_type = str(resolver.getType(uri) or "").lower()
                            input_stream = resolver.openInputStream(uri)

                            ext = ".jpg" if is_only_image else ".pdf"
                            uri_str = str(uri.toString()).lower()
                            if "png" in mime_type or ".png" in uri_str: ext = ".png"
                            elif "jpeg" in mime_type or "jpg" in mime_type or ".jpg" in uri_str or ".jpeg" in uri_str: ext = ".jpg"
                            elif "pdf" in mime_type or ".pdf" in uri_str: ext = ".pdf"
                            elif "sheet" in mime_type or "excel" in mime_type or ".xlsx" in uri_str: ext = ".xlsx"
                            elif ".xls" in uri_str: ext = ".xls"
                            elif "csv" in mime_type or ".csv" in uri_str: ext = ".csv"

                            import random
                            raw_copy = os.path.join(DATA_DIR, f"picked_{random.randint(10000,99999)}{ext}")
                            with open(raw_copy, "wb") as f_out:
                                buf = bytearray(8192)
                                while True:
                                    n = input_stream.read(buf)
                                    if n <= 0: break
                                    f_out.write(bytes(buf[:n]))
                            input_stream.close()

                            if ext in ['.jpg', '.jpeg', '.png']:
                                comp_copy = os.path.join(DATA_DIR, f"comp_{random.randint(10000,99999)}.jpg")
                                final_file = compress_image_under_30kb(raw_copy, comp_copy, max_kb=28)
                            else:
                                final_file = raw_copy

                            Clock.schedule_once(lambda dt: on_file_selected_callback(final_file), 0.1)
                        except Exception as copy_err:
                            print("Uri Copy Error:", str(copy_err))

            activity.bind(on_activity_result=on_file_result)
            PythonActivity.mActivity.startActivityForResult(pick_intent, 9002)
        except Exception as e:
            print("Android Native Picker Error:", str(e))
import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# विंडोज़ और Android दोनों के लिए सुरक्षित हिंदी-इंग्लिश फ़ॉन्ट इंजन
MY_PROJECT_FONT = 'Helvetica-Bold'

if kivy_platform == 'win':
    GLOBAL_NIRMALA_FONT = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'Nirmala.ttf')
    BACKUP_MANGAL_FONT = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'mangal.ttf')

    if os.path.exists(GLOBAL_NIRMALA_FONT):
        try:
            pdfmetrics.registerFont(TTFont('NirmalaHindi', GLOBAL_NIRMALA_FONT))
            MY_PROJECT_FONT = 'NirmalaHindi'
        except:
            MY_PROJECT_FONT = 'Helvetica-Bold'
    elif os.path.exists(BACKUP_MANGAL_FONT):
        try:
            pdfmetrics.registerFont(TTFont('MangalHindi', BACKUP_MANGAL_FONT))
            MY_PROJECT_FONT = 'MangalHindi'
        except:
            MY_PROJECT_FONT = 'Helvetica-Bold'
else:
    # Android के लिए यदि प्रोजेक्ट फ़ोल्डर में Nirmala.ttf रखी है तो उसे लोड करना
    android_font = get_exe_safe_path('Nirmala.ttf')
    if os.path.exists(android_font):
        try:
            pdfmetrics.registerFont(TTFont('NirmalaHindi', android_font))
            MY_PROJECT_FONT = 'NirmalaHindi'
        except:
            MY_PROJECT_FONT = 'Helvetica-Bold'
# =========================================================================
from datetime import datetime
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, Line
from kivy.uix.image import Image
from kivy.uix.spinner import Spinner
from kivy.clock import Clock
import os
import shutil
# 👑 [हल्का Excel इंजन - बिना भारी Pandas के मोबाइल ऐप चलाने के लिए]
try:
    import pandas as pd
except ImportError:
    import openpyxl
    import csv

    class SimpleSeries:
        def __init__(self, data):
            self.data = list(data)
        @property
        def empty(self):
            return len(self.data) == 0
        def __len__(self):
            return len(self.data)
        def astype(self, t):
            return SimpleSeries([str(x) if x is not None else "" for x in self.data])
        @property
        def str(self):
            return self
        def strip(self):
            return SimpleSeries([str(x).strip() for x in self.data])
        def lower(self):
            return SimpleSeries([str(x).lower() for x in self.data])
        def upper(self):
            return SimpleSeries([str(x).upper() for x in self.data])
        def replace(self, old, new, regex=False, case=True):
            import re
            res = []
            for x in self.data:
                s = str(x)
                if regex:
                    s = re.sub(old, new, s, flags=0 if case else re.IGNORECASE)
                else:
                    s = s.replace(old, new) if case else re.sub(re.escape(old), new, s, flags=re.IGNORECASE)
                res.append(s)
            return SimpleSeries(res)
        def isin(self, values):
            vals = set(values)
            return [x in vals for x in self.data]
        def __ne__(self, other):
            return [x != other for x in self.data]
        def __eq__(self, other):
            return [x == other for x in self.data]
        def __iter__(self):
            return iter(self.data)
        def __getitem__(self, idx):
            return self.data[idx]

    class SimpleDataFrame:
        def __init__(self, rows=None, columns=None):
            if isinstance(rows, dict):
                self.columns = list(rows.keys())
                length = max((len(v) for v in rows.values()), default=0)
                self._rows = [{k: rows[k][i] if i < len(rows[k]) else "" for k in self.columns} for i in range(length)]
            else:
                self._rows = list(rows) if rows else []
                self.columns = list(columns) if columns else (list(self._rows[0].keys()) if self._rows else [])

        @property
        def empty(self):
            return len(self._rows) == 0

        @property
        def index(self):
            return list(range(len(self._rows)))

        def __len__(self):
            return len(self._rows)

        def __getitem__(self, key):
            if isinstance(key, list):
                if all(isinstance(k, bool) for k in key):
                    return SimpleDataFrame([r for r, flag in zip(self._rows, key) if flag], columns=self.columns)
                return SimpleDataFrame([{c: r.get(c, "") for c in key} for r in self._rows], columns=key)
            return SimpleSeries([r.get(key, "") for r in self._rows])

        def __setitem__(self, key, val):
            if key not in self.columns:
                self.columns.append(key)
            if isinstance(val, (list, SimpleSeries)):
                for r, v in zip(self._rows, val):
                    r[key] = v
            else:
                for r in self._rows:
                    r[key] = val

        def iterrows(self):
            for idx, r in enumerate(self._rows):
                yield idx, r

        def dropna(self, subset=None):
            if not subset:
                return self
            filtered = [r for r in self._rows if all(str(r.get(c, "")).strip() not in ["", "None", "nan"] for c in subset)]
            return SimpleDataFrame(filtered, columns=self.columns)

        def drop_duplicates(self, subset=None, keep='last', inplace=False):
            seen = {}
            for i, r in enumerate(self._rows):
                k = tuple(r.get(c, "") for c in subset) if subset else tuple(r.items())
                if keep == 'last' or k not in seen:
                    seen[k] = r
            res = list(seen.values())
            if inplace:
                self._rows = res
            else:
                return SimpleDataFrame(res, columns=self.columns)

        def drop_columns(self, cols):
            for c in cols:
                if c in self.columns: self.columns.remove(c)
                for r in self._rows: r.pop(c, None)

        def drop(self, labels=None, columns=None, inplace=False):
            if columns:
                if inplace:
                    self.drop_columns(columns)
                    return None
                df_c = self.copy()
                df_c.drop_columns(columns)
                return df_c
            if isinstance(labels, int):
                labels = [labels]
            idx_set = set(labels) if labels is not None else set()
            return SimpleDataFrame([r for i, r in enumerate(self._rows) if i not in idx_set], columns=self.columns)

        def copy(self):
            return SimpleDataFrame([dict(r) for r in self._rows], columns=list(self.columns))

        def astype(self, t):
            return SimpleDataFrame([{k: str(v) if v is not None else "" for k, v in r.items()} for r in self._rows], columns=self.columns)

        def replace(self, old, new):
            return SimpleDataFrame([{k: (new if v == old else v) for k, v in r.items()} for r in self._rows], columns=self.columns)

        def to_excel(self, filepath, index=False):
            wb = openpyxl.Workbook()
            ws = wb.active
            if self.columns:
                ws.append(self.columns)
                for r in self._rows:
                    ws.append([r.get(c, "") for c in self.columns])
            wb.save(filepath)

    class SimplePandas:
        DataFrame = SimpleDataFrame
        @staticmethod
        def notna(val):
            return val is not None and str(val).strip().lower() not in ["", "nan", "none"]
        @staticmethod
        def read_excel(filepath, dtype=str, skiprows=0):
            wb = openpyxl.load_workbook(filepath, data_only=True)
            ws = wb.active
            all_rows = list(ws.iter_rows(values_only=True))
            if len(all_rows) <= skiprows:
                return SimpleDataFrame()
            headers = [str(h).strip() if h is not None else f"Col_{i}" for i, h in enumerate(all_rows[skiprows])]
            data_rows = []
            for row in all_rows[skiprows + 1:]:
                if all(cell is None for cell in row): continue
                r_dict = {headers[i]: (str(row[i]).strip() if row[i] is not None else "") for i in range(len(headers)) if i < len(row)}
                data_rows.append(r_dict)
            return SimpleDataFrame(data_rows, columns=headers)
        @staticmethod
        def read_csv(filepath, dtype=str, skiprows=0):
            with open(filepath, mode='r', encoding='utf-8-sig', errors='ignore') as f:
                reader = list(csv.reader(f))
            if len(reader) <= skiprows:
                return SimpleDataFrame()
            headers = [str(h).strip() for h in reader[skiprows]]
            data_rows = []
            for row in reader[skiprows + 1:]:
                if not row: continue
                r_dict = {headers[i]: (str(row[i]).strip() if i < len(row) else "") for i in range(len(headers))}
                data_rows.append(r_dict)
            return SimpleDataFrame(data_rows, columns=headers)
        @staticmethod
        def concat(dfs, ignore_index=True):
            all_cols = []
            all_rows = []
            for d in dfs:
                for c in d.columns:
                    if c not in all_cols: all_cols.append(c)
                for r in d._rows:
                    all_rows.append(dict(r))
            return SimpleDataFrame(all_rows, columns=all_cols)

    pd = SimplePandas()

PHOTO_DIR = 'student_photos'
if not os.path.exists(PHOTO_DIR):
    os.makedirs(PHOTO_DIR)

STAFF_PHOTO_DIR = 'staff_photos'
if not os.path.exists(STAFF_PHOTO_DIR):
    os.makedirs(STAFF_PHOTO_DIR)
try:
    import openpyxl
except ImportError:
    import openpyxl
if kivy_platform == 'win':
    Window.size = (1180, 750)
EXCEL_FILE = 'Student_Database.xlsx'
MARKS_FILE = 'Marks_Database.xlsx'
ATTENDANCE_FILE = 'Attendance_Database.xlsx'
LOGO_FILE = get_exe_safe_path('logo.png')
def validate_verhoeff(num_str):
    try:
        if not num_str.isdigit() or len(num_str) != 12: return False
        digits = [int(x) for x in num_str]
        odd_sum = sum(digits[-1::-2])
        even_sum = sum([sum(divmod(2 * x, 10)) for x in digits[-2::-2]])
        return (odd_sum + even_sum) % 10 == 0
    except: return False
def number_to_words(n):
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteenth", "Seventeenth", "Eighteenth", "Nineteenth"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    if n < 20: return ones[n]
    if n < 100: return tens[n // 10] + (" " + ones[n % 10] if n % 10 != 0 else "")
    if n < 1000: return ones[n // 100] + " Hundred" + (" and " + number_to_words(n % 100) if n % 100 != 0 else "")
    return str(n)

def date_to_words_eng(date_str):
    try:
        clean_date = date_str.replace('-', '').replace('/', '').replace('.', '').strip()
        if len(clean_date) == 8:
            day = int(clean_date[0:2])
            month = int(clean_date[2:4])
            year = int(clean_date[4:8])
        else: return ""
        days_ord = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth", 6: "Sixth", 7: "Seventh", 8: "Eighth", 9: "Ninth", 10: "Tenth", 11: "Eleventh", 12: "Twelfth", 13: "Thirteenth", 14: "Fourteenth", 15: "Fifteenth", 16: "Sixteenth", 17: "Seventeenth", 18: "Eighteenth", 19: "Nineteenth", 20: "Twentieth", 21: "Twenty First", 22: "Twenty Second", 23: "Twenty Third", 24: "Twenty Fourth", 25: "Twenty Fifth", 26: "Twenty Sixth", 27: "Twenty Seventh", 28: "Twenty Eighth", 29: "Twenty Ninth", 30: "Thirtieth", 31: "Thirty First"}
        standard_months = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        m_name = standard_months[month]
        d_word = days_ord.get(day, "")
        y_word = "Two Thousand " + number_to_words(year - 2000) if year >= 2000 else number_to_words(year // 100) + " Hundred " + number_to_words(year % 100)
        return f"{d_word} {m_name} {y_word}" if d_word and m_name else ""
    except: return ""

# 📅 [यूनिवर्सल डेट फ़ॉर्मेटर]: 2022-01-04 00:00:00 या किसी भी फॉर्मेट को शुद्ध DD-MM-YYYY बनाना
def format_date_dd_mm_yyyy(raw_val):
    try:
        s = str(raw_val).strip().split(' ')[0] # ' 00:00:00' को पूरी तरह हटाना
        if not s or s.lower() in ['nan', 'none', '---', '']:
            return ""
        for sep in ['/', '-', '.']:
            if sep in s:
                parts = s.split(sep)
                if len(parts) == 3:
                    # यदि Excel से YYYY-MM-DD आया है (जैसे 2022-01-04 या 2016-05-02)
                    if len(parts[0]) == 4:
                        y, p1, p2 = parts[0], int(parts[1]), int(parts[2])
                        # यदि पहला अंक 12 से छोटा है और दूसरा भी 12 या उससे कम है (जैसे 01-04), 
                        # और यह प्रवेश तिथि है जहाँ माह 04 से 10 के बीच होता है, तो DD और MM को सही करना
                        if p1 <= 3 and 4 <= p2 <= 10:
                            d_str, m_str = f"{p1:02d}", f"{p2:02d}"
                        else:
                            m_str, d_str = f"{p1:02d}", f"{p2:02d}"
                        return f"{d_str}-{m_str}-{y}"
                    else:
                        d_str = parts[0].zfill(2)
                        m_str = parts[1].zfill(2)
                        y_str = parts[2].zfill(4)
                        return f"{d_str}-{m_str}-{y_str}"
        digits = ''.join(filter(str.isdigit, s))
        if len(digits) == 8:
            return f"{digits[0:2]}-{digits[2:4]}-{digits[4:8]}"
        elif len(digits) == 7:
            return f"0{digits[0]}-{digits[1:3]}-{digits[3:7]}"
        return s
    except:
        return str(raw_val).strip()

# 👑 [अकादमिक सत्र एवं ऑटो-प्रमोशन इंजन - Session 1 April to 31 March]
def get_academic_session_start_year(date_str):
    clean_dt = format_date_dd_mm_yyyy(date_str) # पहले तारीख को शुद्ध DD-MM-YYYY बनाएँ
    try:
        parts = clean_dt.split('-')
        if len(parts) == 3:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            # चूँकि परिषदीय विद्यालयों में प्रवेश अप्रैल (4) से शुरू होता है
            return y if m >= 4 else y - 1
    except:
        pass
    return 2026

def calculate_promoted_class_history(adm_date, adm_class_str, max_school_class=5, target_session_start=2026):
    import re
    m = re.search(r'(\d+)', str(adm_class_str))
    start_cls = int(m.group(1)) if m else 1
    adm_start_yr = get_academic_session_start_year(adm_date)
    
    history_dict = {}
    current_cls_label = f"Class {start_cls}"
    
    # 01-04-2022 (सत्र 2022-23) में Class 1:
    # 2022 -> Class 1, 2023 -> Class 2, 2024 -> Class 3, 2025 -> Class 4, 2026 -> Class 5
    for yr in range(adm_start_yr, target_session_start + 1):
        sess_label = f"SESSION_{yr}_{yr+1}"
        diff = yr - adm_start_yr
        calc_cls = start_cls + diff
        
        if calc_cls <= max_school_class:
            cls_name = f"Class {calc_cls}"
            history_dict[sess_label] = cls_name
            current_cls_label = cls_name
        else:
            history_dict[sess_label] = f"Passed Out (Class {max_school_class})"
            current_cls_label = f"Passed Out (Class {max_school_class})"
            
    return current_cls_label, history_dict

class CustomText(TextInput):
    def __init__(self, max_chars=None, only_digits=False, **kwargs):
        self.max_chars = max_chars
        self.only_digits = only_digits
        if kivy_platform != 'win':
            kwargs['font_size'] = sp(14)
            kwargs['padding'] = [dp(8), dp(8), dp(8), dp(8)]
            if kwargs.get('size_hint_y') is None:
                kwargs['height'] = dp(42)
        super().__init__(**kwargs)
        self.write_tab = False
        with self.canvas.after:
            self.focus_color = Color(0, 0, 0, 0)
            self.focus_line = Line(rectangle=(self.x, self.y, self.width, self.height), width=2)
        self.bind(pos=self._up_rect, size=self._update_size)
    def _up_rect(self, instance, value): self.focus_line.rectangle = (instance.x, instance.y, instance.width, instance.height)
    def _update_size(self, instance, value): self.focus_line.rectangle = (instance.x, instance.y, instance.width, instance.height)
    def insert_text(self, substring, from_undo=False):
        if self.only_digits and not substring.isdigit(): return
        if self.max_chars and (len(self.text) + len(substring) > self.max_chars): return
        return super().insert_text(substring, from_undo=from_undo)
    def set_visual_focus(self, is_active):
        if is_active:
            self.focus_color.rgba = (0, 0.7, 0.2, 1); self.focus = True
        else:
            self.focus_color.rgba = (0, 0, 0, 0); self.focus = False
            
class CustomSpinner(Spinner):
    def __init__(self, **kwargs):
        if kivy_platform != 'win':
            kwargs['font_size'] = sp(13)
            if kwargs.get('size_hint_y') is None:
                kwargs['height'] = dp(42)
        super().__init__(**kwargs)
        with self.canvas.after:
            self.focus_color = Color(0, 0, 0, 0)
            self.focus_line = Line(rectangle=(self.x, self.y, self.width, self.height), width=2)
        self.bind(pos=self._up_rect, size=self._update_size)
    def _up_rect(self, instance, value): self.focus_line.rectangle = (instance.x, instance.y, instance.width, instance.height)
    def _update_size(self, instance, value): self.focus_line.rectangle = (instance.x, instance.y, instance.width, instance.height)
    def set_visual_focus(self, is_active):
        self.focus = False
        if is_active: self.focus_color.rgba = (0, 0.7, 0.2, 1)
        else: self.focus_color.rgba = (0, 0, 0, 0)

class CustomButton(Button):
    def __init__(self, **kwargs):
        if kivy_platform != 'win':
            kwargs['font_size'] = sp(12)
            kwargs['halign'] = 'center'
            kwargs['valign'] = 'middle'
            if kwargs.get('size_hint_y') is None:
                kwargs['height'] = dp(42)
        super().__init__(**kwargs)
        if kivy_platform != 'win':
            self.bind(size=lambda ins, val: setattr(ins, 'text_size', (ins.width - dp(6), None)))
        with self.canvas.after:
            self.focus_color = Color(0, 0, 0, 0)
            self.focus_line = Line(rectangle=(self.x, self.y, self.width, self.height), width=2)
        self.bind(pos=self._up_rect, size=self._update_size)
    def _up_rect(self, instance, value): self.focus_line.rectangle = (instance.x, instance.y, instance.width, instance.height)
    def _update_size(self, instance, value): self.focus_line.rectangle = (instance.x, instance.y, instance.width, instance.height)
    def set_visual_focus(self, is_active):
        if is_active: self.focus_color.rgba = (0, 0.7, 0.2, 1)
        else: self.focus_color.rgba = (0, 0, 0, 0)

class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        is_mob = (kivy_platform != 'win')
        self.USERS_FILE = 'Users_Database.xlsx'
        self.UDISE_CACHE_FILE = 'UDISE_Master.xlsx'
        self.USER_PHOTO_DIR = 'User_Photos'
        os.makedirs(self.USER_PHOTO_DIR, exist_ok=True)
        self.login_direct_photo_path = ""

        main = BoxLayout(orientation='vertical', padding=dp(12) if is_mob else 20)
        with main.canvas.before:
            Color(0.93, 0.94, 0.96, 1)
            self.bg = Rectangle(size=Window.size, pos=main.pos)
        main.bind(size=lambda ins, val: setattr(self.bg, 'size', ins.size), pos=lambda ins, val: setattr(self.bg, 'pos', main.pos))

        if is_mob:
            card = BoxLayout(orientation='vertical', padding=(dp(18), dp(16)), spacing=dp(8), size_hint=(0.96, 0.97), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        else:
            card = BoxLayout(orientation='vertical', padding=(40, 20, 40, 20), spacing=9, size_hint=(None, None), size=(510, 680), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        with card.canvas.before:
            Color(1, 1, 1, 1)
            self.cd = Rectangle(size=card.size, pos=card.pos)
        card.bind(size=lambda ins, val: setattr(self.cd, 'size', ins.size), pos=lambda ins, val: setattr(self.cd, 'pos', ins.pos))

        top_avatar_row = BoxLayout(orientation='horizontal', size_hint=(None, None), size=(dp(150), dp(96)) if is_mob else (165, 108), spacing=dp(8), pos_hint={'center_x': 0.5})
        default_logo = get_exe_safe_path('logo.png')
        self.login_user_photo = Image(source=default_logo if os.path.exists(default_logo) else '', size_hint=(None, None), size=(dp(88), dp(94)) if is_mob else (98, 105), allow_stretch=True, keep_ratio=False)
        top_avatar_row.add_widget(self.login_user_photo)

        mini_cam_box = BoxLayout(orientation='vertical', size_hint=(None, None), size=(dp(52), dp(94)) if is_mob else (56, 105), spacing=dp(4), padding=(0, dp(8)))
        btn_mini_cam = Button(text='CAM', font_size=sp(10.5) if is_mob else 10, bold=True, background_color=(0.05, 0.45, 0.7, 1))
        btn_mini_gal = Button(text='GAL', font_size=sp(10.5) if is_mob else 10, bold=True, background_color=(0.2, 0.25, 0.3, 1))
        mini_cam_box.add_widget(btn_mini_cam); mini_cam_box.add_widget(btn_mini_gal)
        top_avatar_row.add_widget(mini_cam_box)
        card.add_widget(top_avatar_row)

        self.lbl_welcome_user = Label(text='PRIMARY SCHOOL PANAUTA', font_size=sp(19) if is_mob else 22, bold=True, color=(0.02, 0.4, 0.15, 1), size_hint_y=None, height=dp(26) if is_mob else 28, halign='center')
        self.lbl_school_sub = Label(text='School ERP & Management Portal', font_size=sp(12.5) if is_mob else 13.5, bold=True, color=(0.25, 0.35, 0.3, 1), size_hint_y=None, height=dp(20) if is_mob else 22, halign='center')
        card.add_widget(self.lbl_welcome_user); card.add_widget(self.lbl_school_sub)

        card.add_widget(Label(text='Mobile Number (or Admin ID)', font_size=sp(14) if is_mob else 13.5, bold=True, color=(0, 0, 0, 1), size_hint_y=None, height=dp(22) if is_mob else 22, halign='left'))
        self.username = TextInput(multiline=False, size_hint_y=None, height=dp(44) if is_mob else 40, hint_text='Enter 10-digit Mobile No.', font_size=sp(15) if is_mob else 15, padding=[dp(10), dp(10)], background_color=(0.95, 0.97, 0.95, 1))
        card.add_widget(self.username)

        card.add_widget(Label(text='Password', font_size=sp(14) if is_mob else 13.5, bold=True, color=(0, 0, 0, 1), size_hint_y=None, height=dp(22) if is_mob else 22, halign='left'))
        self.password = TextInput(password=True, multiline=False, size_hint_y=None, height=dp(44) if is_mob else 40, hint_text='Enter Password', font_size=sp(15) if is_mob else 15, padding=[dp(10), dp(10)], background_color=(0.95, 0.97, 0.95, 1))
        card.add_widget(self.password)
        def on_login_mobile_change(inst, val):
            mb = val.strip()
            if len(mb) == 10 and os.path.exists(self.USERS_FILE):
                try:
                    df_u = pd.read_excel(self.USERS_FILE, dtype=str)
                    for _, r in df_u.iterrows():
                        if str(r.get('Mobile', '')).strip().replace('.0', '') == mb:
                            u_nm = str(r.get('Name', '')).strip()
                            u_pic = str(r.get('Photo', '')).strip()
                            if u_nm and u_nm.lower() != 'nan': self.lbl_welcome_user.text = f"WELCOME, {u_nm}"
                            if u_pic and u_pic.lower() != 'nan' and os.path.exists(u_pic):
                                self.login_user_photo.source = u_pic; self.login_user_photo.reload()
                            return
                except Exception: pass
            if not self.login_direct_photo_path:
                self.lbl_welcome_user.text = 'PRIMARY SCHOOL PANAUTA'
                if os.path.exists(default_logo):
                    self.login_user_photo.source = default_logo; self.login_user_photo.reload()

        self.username.bind(text=on_login_mobile_change)

        def _set_login_photo(fp):
            if fp and os.path.exists(fp):
                mb = self.username.text.strip() or "quick_user"
                dest_p = os.path.abspath(os.path.join(self.USER_PHOTO_DIR, f"user_{mb}.jpg"))
                comp_p = compress_image_under_30kb(fp, dest_p, max_kb=28)
                self.login_direct_photo_path = comp_p
                self.login_user_photo.source = comp_p; self.login_user_photo.reload()
                if len(mb) == 10 and os.path.exists(self.USERS_FILE):
                    try:
                        df_u = pd.read_excel(self.USERS_FILE, dtype=str)
                        rows_u = []
                        for _, r in df_u.iterrows():
                            rd = dict(r)
                            if str(rd.get('Mobile', '')).strip().replace('.0', '') == mb: rd['Photo'] = comp_p
                            rows_u.append(rd)
                        pd.DataFrame(rows_u, columns=df_u.columns).to_excel(self.USERS_FILE, index=False)
                    except Exception: pass

        btn_mini_cam.bind(on_press=lambda x: select_file_cross_platform("Select Photo", [("Images", "*.png *.jpg *.jpeg")], _set_login_photo) if kivy_platform == 'win' else capture_mobile_camera_safe(os.path.abspath(os.path.join(self.USER_PHOTO_DIR, f"user_{self.username.text.strip() or 'quick'}.jpg")), _set_login_photo, self._msg_popup))
        btn_mini_gal.bind(on_press=lambda x: select_file_cross_platform("Select Photo", [("Images", "*.png *.jpg *.jpeg")], _set_login_photo))

        btns = BoxLayout(spacing=dp(10) if is_mob else 12, size_hint_y=None, height=dp(46) if is_mob else 44)
        b1 = Button(text='Sign In (Password)', background_color=(0.05, 0.55, 0.25, 1), font_size=sp(14) if is_mob else 14, bold=True)
        b1.bind(on_press=self.validate)
        b_otp = Button(text='Login via OTP', background_color=(0.04, 0.45, 0.52, 1), font_size=sp(14) if is_mob else 14, bold=True)
        b_otp.bind(on_press=self.open_otp_login_popup)
        btns.add_widget(b1); btns.add_widget(b_otp)
        card.add_widget(btns)

        auth_links = BoxLayout(spacing=dp(8) if is_mob else 10, size_hint_y=None, height=dp(42) if is_mob else 40)
        btn_signup = Button(text='Sign Up', background_color=(0.08, 0.35, 0.68, 1), font_size=sp(13) if is_mob else 13, bold=True)
        btn_signup.bind(on_press=self.open_signup_popup)
        btn_forgot = Button(text='Forgot Password?', background_color=(0.82, 0.45, 0.05, 1), font_size=sp(13) if is_mob else 13, bold=True)
        btn_forgot.bind(on_press=self.open_forgot_password_popup)
        b2 = Button(text='Exit', size_hint_x=0.55, background_color=(0.75, 0.15, 0.15, 1), font_size=sp(13) if is_mob else 13, bold=True)
        b2.bind(on_press=App.get_running_app().stop)
        auth_links.add_widget(btn_signup); auth_links.add_widget(btn_forgot); auth_links.add_widget(b2)
        card.add_widget(auth_links)

        footer_credit_lbl = Label(text="Designed & Developed by: Mr. Pappu Singh (A.T.)\nPrimary School Panauta, Wazirganj (Budaun) | Mob: 9458500800", font_size=sp(11.5) if is_mob else 12, color=(0.05, 0.2, 0.45, 1), halign='center', valign='middle', size_hint_y=None, height=dp(44) if is_mob else 45)
        footer_credit_lbl.bind(size=footer_credit_lbl.setter('text_size'))
        card.add_widget(footer_credit_lbl)

        main.add_widget(card)
        if not is_mob: main.add_widget(BoxLayout())
        self.add_widget(main)

    def _msg_popup(self, title, msg):
        is_mob = (kivy_platform != 'win')
        pl = BoxLayout(orientation='vertical', padding=dp(15) if is_mob else 18, spacing=dp(12))
        lbl = Label(text=str(msg), halign='center', valign='middle', color=(1, 1, 1, 1), font_size=sp(14) if is_mob else 14)
        lbl.bind(size=lambda ins, val: setattr(ins, 'text_size', (ins.width - dp(10), None)))
        pl.add_widget(lbl)
        cb = Button(text='OK', size_hint_y=None, height=dp(42) if is_mob else 38, background_color=(0.05, 0.55, 0.25, 1), bold=True)
        pl.add_widget(cb)
        pop = Popup(title=str(title), content=pl, size_hint=(0.90, 0.36) if is_mob else (0.45, 0.32), background='', background_color=(0.14, 0.14, 0.14, 0.98))
        cb.bind(on_press=pop.dismiss); pop.open()

    def _dispatch_sms_or_popup_otp(self, mobile_no, otp_code, purpose_label="Verification"):
        if kivy_platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([Permission.SEND_SMS])
                from jnius import autoclass
                SmsManager = autoclass('android.telephony.SmsManager')
                SmsManager.getDefault().sendTextMessage(mobile_no, None, f"Primary School Panauta {purpose_label} OTP: {otp_code}", None, None)
            except Exception:
                pass
        self._msg_popup(f'{purpose_label} OTP', f'6-Digit OTP for {mobile_no} is:\n\n{otp_code}')

    def _lookup_school_by_udise(self, udise_code):
        code = str(udise_code).strip()
        if code == '09191204201': return 'PRIMARY SCHOOL PANAUTA, WAZIRGANJ (BUDAUN)'
        if os.path.exists(self.UDISE_CACHE_FILE):
            try:
                df_u = pd.read_excel(self.UDISE_CACHE_FILE, dtype=str)
                for _, r in df_u.iterrows():
                    if str(r.get('UDISE', '')).strip() == code:
                        s_nm = str(r.get('School Name', '')).strip()
                        if s_nm and s_nm.lower() != 'nan': return s_nm
            except Exception: pass
        try:
            import urllib.request, json
            url = f"https://udiseplus.gov.in{code}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8', errors='ignore'))
                s_list = data.get('data') or data.get('schoolList') or []
                if s_list and isinstance(s_list, list):
                    sch_name = s_list.get('schoolName') or s_list.get('schName') or ''
                    dist_name = s_list.get('districtName') or ''
                    if sch_name: return (f"{sch_name} ({dist_name})".strip() if dist_name else sch_name).upper()
        except Exception: pass
        return ""
    def open_signup_popup(self, instance):
        is_mob = (kivy_platform != 'win')
        outer = BoxLayout(orientation='vertical', padding=dp(12) if is_mob else 15, spacing=dp(8))
        sc = ScrollView(do_scroll_x=False, do_scroll_y=True)
        form = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=(dp(4), dp(4)))
        form.bind(minimum_height=form.setter('height'))

        h_inp = dp(42) if is_mob else 36
        fs_lbl = sp(13) if is_mob else 13
        self.signup_photo_path = ""
        self._signup_otp_val = ""
        self._signup_otp_mob = ""

        photo_strip = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(74) if is_mob else 68, spacing=dp(10), padding=(dp(4), dp(2)))
        signup_img = Image(source=get_exe_safe_path('logo.png'), size_hint=(None, None), size=(dp(60), dp(68)) if is_mob else (56, 64), allow_stretch=True, keep_ratio=False)
        photo_strip.add_widget(signup_img)

        icon_btns = BoxLayout(orientation='vertical', spacing=dp(4))
        icon_btns.add_widget(Label(text='Profile Photo (<30KB)', color=(1, 1, 0.7, 1), bold=True, font_size=sp(12) if is_mob else 12, size_hint_y=None, height=dp(20), halign='left'))
        row_mini = BoxLayout(orientation='horizontal', spacing=dp(8), size_hint_y=None, height=dp(36))
        btn_s_cam = Button(text='CAMERA', size_hint_x=None, width=dp(85), background_color=(0.05, 0.45, 0.7, 1), bold=True, font_size=sp(11.5) if is_mob else 11)
        btn_s_gal = Button(text='GALLERY', size_hint_x=None, width=dp(85), background_color=(0.25, 0.25, 0.25, 1), bold=True, font_size=sp(11.5) if is_mob else 11)
        row_mini.add_widget(btn_s_cam); row_mini.add_widget(btn_s_gal)
        icon_btns.add_widget(row_mini); photo_strip.add_widget(icon_btns); form.add_widget(photo_strip)

        def _on_signup_photo(fp):
            if fp and os.path.exists(fp):
                import random
                dest_p = os.path.abspath(os.path.join(self.USER_PHOTO_DIR, f"signup_{random.randint(1000,9999)}.jpg"))
                comp_p = compress_image_under_30kb(fp, dest_p, max_kb=28)
                self.signup_photo_path = comp_p
                signup_img.source = comp_p; signup_img.reload()

        btn_s_cam.bind(on_press=lambda x: select_file_cross_platform("Select Photo", [("Images", "*.png *.jpg *.jpeg")], _on_signup_photo) if kivy_platform == 'win' else capture_mobile_camera_safe(os.path.abspath(os.path.join(self.USER_PHOTO_DIR, "signup_cam.jpg")), _on_signup_photo, self._msg_popup))
        btn_s_gal.bind(on_press=lambda x: select_file_cross_platform("Select Photo", [("Images", "*.png *.jpg *.jpeg")], _on_signup_photo))

        def add_field(label_txt, hint_txt, is_pass=False, max_c=None, digits_only=False):
            form.add_widget(Label(text=label_txt, color=(1, 1, 1, 1), bold=True, font_size=fs_lbl, size_hint_y=None, height=dp(22), halign='left'))
            ti = CustomText(hint_text=hint_txt, password=is_pass, max_chars=max_c, only_digits=digits_only, multiline=False, size_hint_y=None, height=h_inp)
            form.add_widget(ti)
            return ti

        in_name = add_field('Full Name *', 'Enter Your Full Name')

        form.add_widget(Label(text='Mobile Number (10 Digits) *', color=(1, 1, 1, 1), bold=True, font_size=fs_lbl, size_hint_y=None, height=dp(22), halign='left'))
        mob_verify_row = BoxLayout(orientation='horizontal', spacing=dp(6), size_hint_y=None, height=h_inp)
        in_mob = CustomText(hint_text='10-digit Mobile No.', max_chars=10, only_digits=True, multiline=False, size_hint_x=0.65)
        btn_s_otp = Button(text='SEND OTP', size_hint_x=0.35, background_color=(0.05, 0.5, 0.75, 1), bold=True, font_size=sp(12.5) if is_mob else 12)
        mob_verify_row.add_widget(in_mob); mob_verify_row.add_widget(btn_s_otp)
        form.add_widget(mob_verify_row)

        in_reg_otp = add_field('Mobile Verification OTP (6 Digits) *', 'Enter 6-Digit OTP', max_c=6, digits_only=True)

        def _send_signup_otp(x):
            mb = in_mob.text.strip()
            if len(mb) != 10 or not mb.isdigit():
                self._msg_popup('Alert', 'Please enter valid 10-digit Mobile Number first!'); return
            import random
            otp_c = str(random.randint(100000, 999999))
            self._signup_otp_val = otp_c
            self._signup_otp_mob = mb
            in_reg_otp.text = otp_c
            self._dispatch_sms_or_popup_otp(mb, otp_c, "Sign Up")

        btn_s_otp.bind(on_press=_send_signup_otp)

        in_email = add_field('Email ID *', 'example@gmail.com')

        form.add_widget(Label(text='School UDISE Code (11 Digits) *', color=(1, 1, 1, 1), bold=True, font_size=fs_lbl, size_hint_y=None, height=dp(22), halign='left'))
        udise_row = BoxLayout(orientation='horizontal', spacing=dp(6), size_hint_y=None, height=h_inp)
        in_udise = CustomText(hint_text='e.g. 09191204201', max_chars=11, only_digits=True, multiline=False, size_hint_x=0.68)
        btn_find_sch = Button(text='SEARCH', size_hint_x=0.32, background_color=(0.05, 0.5, 0.75, 1), bold=True, font_size=sp(12.5) if is_mob else 12)
        udise_row.add_widget(in_udise); udise_row.add_widget(btn_find_sch)
        form.add_widget(udise_row)

        in_school = add_field('School Name (Auto-Filled from UDISE) *', 'School Name will appear here')
        in_pass = add_field('Create Password *', 'Enter Password', is_pass=True)
        in_cpass = add_field('Confirm Password *', 'Re-enter Password', is_pass=True)

        in_udise.bind(text=lambda inst, val: setattr(in_school, 'text', self._lookup_school_by_udise(val.strip()) or in_school.text) if len(val.strip()) == 11 else None)
        btn_find_sch.bind(on_press=lambda x: setattr(in_school, 'text', self._lookup_school_by_udise(in_udise.text.strip()) or in_school.text) if len(in_udise.text.strip()) == 11 else self._msg_popup('UDISE Alert', 'Enter 11-digit UDISE Code!'))

        sc.add_widget(form); outer.add_widget(sc)

        b_bar = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(44) if is_mob else 40)
        btn_reg = Button(text='VERIFY & REGISTER', background_color=(0.05, 0.55, 0.25, 1), bold=True, font_size=sp(14) if is_mob else 14)
        btn_cls = Button(text='CANCEL', background_color=(0.75, 0.15, 0.15, 1), bold=True, font_size=sp(14) if is_mob else 14)
        b_bar.add_widget(btn_reg); b_bar.add_widget(btn_cls); outer.add_widget(b_bar)

        pop_reg = Popup(title='Create Verified User Account (Sign Up)', content=outer, size_hint=(0.95, 0.92) if is_mob else (0.52, 0.90), auto_dismiss=False, background='', background_color=(0.14, 0.14, 0.14, 0.98))
        btn_cls.bind(on_press=pop_reg.dismiss)
        def save_new_user(ins):
            nm, mb, otp_in, em, ud, sc_nm, pw, cpw = in_name.text.strip(), in_mob.text.strip(), in_reg_otp.text.strip(), in_email.text.strip(), in_udise.text.strip(), in_school.text.strip(), in_pass.text.strip(), in_cpass.text.strip()
            if not nm: self._msg_popup('Validation Error', 'Please enter Full Name!'); return
            if len(mb) != 10 or not mb.isdigit(): self._msg_popup('Validation Error', 'Please enter valid 10-digit Mobile Number!'); return
            if not self._signup_otp_val or mb != self._signup_otp_mob or otp_in != self._signup_otp_val:
                self._msg_popup('OTP Verification Required', 'Please click SEND OTP and verify your 6-digit Mobile OTP!'); return
            if '@' not in em or '.' not in em: self._msg_popup('Validation Error', 'Please enter a valid Email ID!'); return
            if len(ud) != 11 or not ud.isdigit(): self._msg_popup('Validation Error', 'UDISE Code must be 11 digits!'); return
            if not sc_nm: self._msg_popup('Validation Error', 'School Name cannot be blank!'); return
            if len(pw) < 4: self._msg_popup('Validation Error', 'Password must be at least 4 characters!'); return
            if pw != cpw: self._msg_popup('Validation Error', 'Password and Confirm Password do not match!'); return

            try:
                final_user_photo = ""
                if self.signup_photo_path and os.path.exists(self.signup_photo_path):
                    final_user_photo = os.path.abspath(os.path.join(self.USER_PHOTO_DIR, f"user_{mb}.jpg"))
                    if os.path.abspath(self.signup_photo_path) != final_user_photo:
                        shutil.copyfile(self.signup_photo_path, final_user_photo)

                df_new = pd.DataFrame([{'Name': nm.upper(), 'Mobile': mb, 'Email': em.lower(), 'UDISE': ud, 'School Name': sc_nm.upper(), 'Password': pw, 'Photo': final_user_photo}])
                if not os.path.exists(self.USERS_FILE):
                    df_new.to_excel(self.USERS_FILE, index=False)
                else:
                    df_old = pd.read_excel(self.USERS_FILE, dtype=str)
                    kept = [dict(r) for _, r in df_old.iterrows() if str(r.get('Mobile', '')).strip().replace('.0', '') != mb]
                    pd.concat([pd.DataFrame(kept, columns=df_old.columns), df_new], ignore_index=True).to_excel(self.USERS_FILE, index=False)

                df_u_new = pd.DataFrame([{'UDISE': ud, 'School Name': sc_nm.upper()}])
                if not os.path.exists(self.UDISE_CACHE_FILE):
                    df_u_new.to_excel(self.UDISE_CACHE_FILE, index=False)
                else:
                    df_u_old = pd.read_excel(self.UDISE_CACHE_FILE, dtype=str)
                    kept_u = [dict(r) for _, r in df_u_old.iterrows() if str(r.get('UDISE', '')).strip() != ud]
                    pd.concat([pd.DataFrame(kept_u, columns=df_u_old.columns), df_u_new], ignore_index=True).to_excel(self.UDISE_CACHE_FILE, index=False)

                self.username.text = mb; self.password.text = ''
                if final_user_photo and os.path.exists(final_user_photo):
                    self.login_user_photo.source = final_user_photo; self.login_user_photo.reload()
                self.lbl_welcome_user.text = f"WELCOME, {nm.upper()}"
                pop_reg.dismiss()
                self._msg_popup('Account Verified & Created', f'Welcome {nm}!\nMobile {mb} verified successfully.\nYou can now login with Password or OTP.')
            except Exception as ex:
                self._msg_popup('Save Error', f'Could not save account: {str(ex)}')

        btn_reg.bind(on_press=save_new_user); pop_reg.open()

    def open_otp_login_popup(self, instance):
        is_mob = (kivy_platform != 'win')
        pl = BoxLayout(orientation='vertical', padding=dp(15) if is_mob else 18, spacing=dp(10))
        h_inp = dp(42) if is_mob else 36

        pl.add_widget(Label(text='Enter Registered Mobile Number:', color=(1, 1, 1, 1), bold=True, font_size=sp(13.5) if is_mob else 13, size_hint_y=None, height=dp(24)))
        mob_row = BoxLayout(spacing=dp(6), size_hint_y=None, height=h_inp)
        in_mob_otp = CustomText(text=self.username.text.strip(), hint_text='10-digit Mobile No.', max_chars=10, only_digits=True, multiline=False, size_hint_x=0.62)
        btn_send = Button(text='SEND OTP', size_hint_x=0.38, background_color=(0.05, 0.45, 0.75, 1), bold=True, font_size=sp(12.5) if is_mob else 12)
        mob_row.add_widget(in_mob_otp); mob_row.add_widget(btn_send); pl.add_widget(mob_row)

        pl.add_widget(Label(text='Enter 6-Digit OTP:', color=(1, 1, 1, 1), bold=True, font_size=sp(13.5) if is_mob else 13, size_hint_y=None, height=dp(24)))
        in_code = CustomText(hint_text='Enter 6-Digit OTP', max_chars=6, only_digits=True, multiline=False, size_hint_y=None, height=h_inp)
        pl.add_widget(in_code)

        btn_row = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(44) if is_mob else 40)
        btn_verify = Button(text='VERIFY & LOGIN', background_color=(0.05, 0.55, 0.25, 1), bold=True, font_size=sp(13) if is_mob else 13)
        btn_cls = Button(text='CANCEL', background_color=(0.75, 0.15, 0.15, 1), bold=True, font_size=sp(13) if is_mob else 13)
        btn_row.add_widget(btn_verify); btn_row.add_widget(btn_cls); pl.add_widget(btn_row)

        pop_otp = Popup(title='Login via Mobile OTP', content=pl, size_hint=(0.92, 0.48) if is_mob else (0.44, 0.42), auto_dismiss=False, background='', background_color=(0.14, 0.14, 0.14, 0.98))
        btn_cls.bind(on_press=pop_otp.dismiss)
        self._login_otp_val = ""; self._login_otp_mob = ""; self._login_otp_user_row = None

        def _send_login_otp(x):
            mb = in_mob_otp.text.strip()
            if len(mb) != 10: self._msg_popup('Alert', 'Please enter 10-digit Mobile Number!'); return
            found_user = None
            if os.path.exists(self.USERS_FILE):
                try:
                    df_u = pd.read_excel(self.USERS_FILE, dtype=str)
                    for _, r in df_u.iterrows():
                        if str(r.get('Mobile', '')).strip().replace('.0', '') == mb:
                            found_user = dict(r); break
                except Exception: pass
            if not found_user:
                self._msg_popup('Not Registered', f'Mobile {mb} is not registered! Please Sign Up first.'); return
            import random
            otp_c = str(random.randint(100000, 999999))
            self._login_otp_val = otp_c; self._login_otp_mob = mb; self._login_otp_user_row = found_user
            in_code.text = otp_c
            self._dispatch_sms_or_popup_otp(mb, otp_c, "Login")

        def _verify_login_otp(x):
            if not self._login_otp_val or in_mob_otp.text.strip() != self._login_otp_mob:
                self._msg_popup('Alert', 'Please click SEND OTP first!'); return
            if in_code.text.strip() != self._login_otp_val:
                self._msg_popup('Invalid OTP', 'Entered OTP is incorrect!'); return
            u_pic = str(self._login_otp_user_row.get('Photo', '')).strip()
            if u_pic and u_pic.lower() != 'nan' and os.path.exists(u_pic):
                self.login_user_photo.source = u_pic; self.login_user_photo.reload()
            App.get_running_app().logged_in_user = self._login_otp_user_row
            pop_otp.dismiss(); self.manager.current = 'dashboard'

        btn_send.bind(on_press=_send_login_otp); btn_verify.bind(on_press=_verify_login_otp); pop_otp.open()
    
    def open_forgot_password_popup(self, instance):
        is_mob = (kivy_platform != 'win')
        pl = BoxLayout(orientation='vertical', padding=dp(15) if is_mob else 18, spacing=dp(10))
        h_inp = dp(42) if is_mob else 36

        pl.add_widget(Label(text='Enter Registered Mobile Number:', color=(1, 1, 1, 1), bold=True, font_size=sp(13.5) if is_mob else 13, size_hint_y=None, height=dp(24)))
        mob_row = BoxLayout(spacing=dp(6), size_hint_y=None, height=h_inp)
        in_reg_mob = CustomText(hint_text='10-digit Mobile No.', max_chars=10, only_digits=True, multiline=False, size_hint_x=0.62)
        btn_send_otp = Button(text='SEND OTP', size_hint_x=0.38, background_color=(0.05, 0.45, 0.75, 1), bold=True, font_size=sp(12.5) if is_mob else 12)
        mob_row.add_widget(in_reg_mob); mob_row.add_widget(btn_send_otp); pl.add_widget(mob_row)

        pl.add_widget(Label(text='Enter 6-Digit OTP:', color=(1, 1, 1, 1), bold=True, font_size=sp(13.5) if is_mob else 13, size_hint_y=None, height=dp(24)))
        in_otp = CustomText(hint_text='Enter OTP', max_chars=6, only_digits=True, multiline=False, size_hint_y=None, height=h_inp)
        pl.add_widget(in_otp)

        pl.add_widget(Label(text='New Password:', color=(1, 1, 1, 1), bold=True, font_size=sp(13.5) if is_mob else 13, size_hint_y=None, height=dp(24)))
        in_new_pw = CustomText(hint_text='Enter New Password', password=True, multiline=False, size_hint_y=None, height=h_inp)
        pl.add_widget(in_new_pw)

        pl.add_widget(Label(text='Confirm New Password:', color=(1, 1, 1, 1), bold=True, font_size=sp(13.5) if is_mob else 13, size_hint_y=None, height=dp(24)))
        in_cnew_pw = CustomText(hint_text='Confirm New Password', password=True, multiline=False, size_hint_y=None, height=h_inp)
        pl.add_widget(in_cnew_pw)

        btn_row = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(44) if is_mob else 40)
        btn_reset = Button(text='RESET PASSWORD', background_color=(0.05, 0.55, 0.25, 1), bold=True, font_size=sp(13) if is_mob else 13)
        btn_cancel = Button(text='CANCEL', background_color=(0.75, 0.15, 0.15, 1), bold=True, font_size=sp(13) if is_mob else 13)
        btn_row.add_widget(btn_reset); btn_row.add_widget(btn_cancel); pl.add_widget(btn_row)

        pop_fp = Popup(title='Forgot Password - OTP Recovery', content=pl, size_hint=(0.94, 0.72) if is_mob else (0.48, 0.65), auto_dismiss=False, background='', background_color=(0.14, 0.14, 0.14, 0.98))
        btn_cancel.bind(on_press=pop_fp.dismiss)
        self._generated_otp = ""; self._otp_target_mobile = ""

        def send_otp_action(ins):
            mb = in_reg_mob.text.strip()
            if len(mb) != 10: self._msg_popup('Alert', 'Please enter 10-digit registered Mobile Number!'); return
            user_exists = False
            if os.path.exists(self.USERS_FILE):
                try:
                    df_u = pd.read_excel(self.USERS_FILE, dtype=str)
                    for _, r in df_u.iterrows():
                        if str(r.get('Mobile', '')).strip().replace('.0', '') == mb: user_exists = True; break
                except Exception: pass
            if not user_exists:
                self._msg_popup('Not Registered', f'Mobile Number {mb} is not registered!\nPlease Sign Up first.'); return
            import random
            otp_code = str(random.randint(100000, 999999))
            self._generated_otp = otp_code; self._otp_target_mobile = mb
            in_otp.text = otp_code
            self._dispatch_sms_or_popup_otp(mb, otp_code, "Password Reset")

        def reset_password_action(ins):
            mb, entered_otp, npw, cnpw = in_reg_mob.text.strip(), in_otp.text.strip(), in_new_pw.text.strip(), in_cnew_pw.text.strip()
            if not self._generated_otp or mb != self._otp_target_mobile:
                self._msg_popup('OTP Error', 'Please click SEND OTP first!'); return
            if entered_otp != self._generated_otp:
                self._msg_popup('Invalid OTP', 'Entered OTP is incorrect!'); return
            if len(npw) < 4: self._msg_popup('Validation Error', 'New Password must be at least 4 characters!'); return
            if npw != cnpw: self._msg_popup('Validation Error', 'Passwords do not match!'); return
            try:
                df_u = pd.read_excel(self.USERS_FILE, dtype=str)
                updated_rows = []
                for _, r in df_u.iterrows():
                    rd = dict(r)
                    if str(rd.get('Mobile', '')).strip().replace('.0', '') == mb: rd['Password'] = npw
                    updated_rows.append(rd)
                pd.DataFrame(updated_rows, columns=df_u.columns).to_excel(self.USERS_FILE, index=False)
                self._generated_otp = ""; self.username.text = mb; self.password.text = ""
                pop_fp.dismiss()
                self._msg_popup('Password Updated', 'Password reset successfully! Please login.')
            except Exception as ex:
                self._msg_popup('Error', f'Password update failed: {str(ex)}')

        btn_send_otp.bind(on_press=send_otp_action); btn_reset.bind(on_press=reset_password_action); pop_fp.open()

    def validate(self, instance):
        u_in, p_in = self.username.text.strip(), self.password.text.strip()
        if not u_in or not p_in: self._msg_popup('Login Alert', 'Please enter Mobile Number and Password!'); return
        if u_in == "admin" and p_in == "1234":
            self.manager.current = 'dashboard'; return
        if os.path.exists(self.USERS_FILE):
            try:
                df_u = pd.read_excel(self.USERS_FILE, dtype=str)
                for _, r in df_u.iterrows():
                    if str(r.get('Mobile', '')).strip().replace('.0', '') == u_in and str(r.get('Password', '')).strip() == p_in:
                        u_pic = str(r.get('Photo', '')).strip()
                        if u_pic and u_pic.lower() != 'nan' and os.path.exists(u_pic):
                            self.login_user_photo.source = u_pic; self.login_user_photo.reload()
                        App.get_running_app().logged_in_user = dict(r)
                        self.manager.current = 'dashboard'; return
            except Exception: pass
        self._msg_popup('Login Failed', 'Invalid Mobile Number or Password! Use Sign Up or Login via OTP.')

class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        is_mob = (kivy_platform != 'win')
        self.outer = BoxLayout(orientation='vertical')
        self.header = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(68) if is_mob else 100, padding=dp(6) if is_mob else 10, spacing=dp(6) if is_mob else 10)
        with self.header.canvas.before:
            Color(0.0, 0.35, 0.05, 1)
            self.hr = Rectangle(size=self.header.size, pos=self.header.pos)
        self.header.bind(size=lambda ins, val: setattr(self.hr, 'size', ins.size), pos=lambda ins, val: setattr(self.hr, 'pos', ins.pos))
        
        BASIC_LOGO_FILE = get_exe_safe_path('basic.png')
        if os.path.exists(BASIC_LOGO_FILE):
            self.header.add_widget(Image(source=BASIC_LOGO_FILE, size_hint_x=0.12 if is_mob else 0.09, allow_stretch=True))
        else:
            self.header.add_widget(BoxLayout(size_hint_x=0.09))
            
        tb = BoxLayout(orientation='vertical', size_hint_x=0.60 if is_mob else 0.72)
        self.lbl_dash_main = Label(text='PRIMARY SCHOOL PANAUTA - 09191204201', font_size=sp(14) if is_mob else 36, bold=True, color=(1, 0.9, 0, 1), halign='center', valign='middle')
        lbl_sub = Label(text='BLOCK- WAZIRGANJ, DISTRICT- BUDAUN, 243601', font_size=sp(10.5) if is_mob else 18, bold=True, color=(0.9, 1, 0.9, 1), halign='center', valign='middle')
        tb.add_widget(self.lbl_dash_main); tb.add_widget(lbl_sub)
        self.lbl_dash_main.bind(size=lambda ins, val: setattr(ins, 'text_size', ins.size))
        lbl_sub.bind(size=lambda ins, val: setattr(ins, 'text_size', ins.size))
        self.header.add_widget(tb)
        
        resolved_school_logo = get_exe_safe_path('logo.png')
        if os.path.exists(resolved_school_logo): 
            self.header.add_widget(Image(source=resolved_school_logo, size_hint_x=0.11 if is_mob else 0.08, allow_stretch=True))
        else:
            self.header.add_widget(BoxLayout(size_hint_x=0.08))

        # दाईं ओर यूज़र की फोटो आइकन और नाम
        user_badge = BoxLayout(orientation='vertical', size_hint_x=0.17 if is_mob else 0.11, spacing=2, padding=(2, 2))
        self.dash_user_img = Image(source=resolved_school_logo if os.path.exists(resolved_school_logo) else '', size_hint=(None, None), size=(dp(36), dp(36)) if is_mob else (50, 50), pos_hint={'center_x': 0.5}, allow_stretch=True, keep_ratio=False)
        self.dash_user_lbl = Label(text='Admin', font_size=sp(10) if is_mob else 12, bold=True, color=(1, 1, 1, 1), size_hint_y=None, height=dp(16) if is_mob else 20, halign='center')
        self.dash_user_lbl.bind(size=self.dash_user_lbl.setter('text_size'))
        user_badge.add_widget(self.dash_user_img)
        user_badge.add_widget(self.dash_user_lbl)
        self.header.add_widget(user_badge)
            
        self.outer.add_widget(self.header)
        menu = ['STUDENT REGISTRATION', 'STUDENT ATTENDANCE', 'MARKS ENTRY', 'RESULTS', 'HEIGHT & WEIGHT', 'D.B.T.', 'MDM', 'STAFF DETAIL', 'S.M.C. MEMBERS', 'COOK DETAILS', 'GRANT DETAILS', 'TRANSFER CERTIFICATE', 'PHOTO GALLERY', 'GOOGLE DRIVE SYNC', 'LOGOUT']

        if is_mob:
            # मोबाइल Portrait मोड: ऊपर क्षैतिज स्क्रॉल मेनू बार + नीचे 100% फुल पेज
            top_menu_scroll = ScrollView(size_hint=(1, None), height=dp(48), do_scroll_x=True, do_scroll_y=False)
            top_menu_box = BoxLayout(orientation='horizontal', spacing=dp(6), padding=(dp(6), dp(4)), size_hint_x=None)
            top_menu_box.bind(minimum_width=top_menu_box.setter('width'))
            for name in menu:
                btn_color = (0.7, 0.1, 0.1, 1) if name == 'EXIT' else (0.02, 0.45, 0.2, 1)
                btn = Button(text=name, background_color=btn_color, font_size=sp(12), bold=True, size_hint=(None, 1), width=dp(165), background_normal='')
                btn.bind(on_press=self.menu_nav)
                top_menu_box.add_widget(btn)
            top_menu_scroll.add_widget(top_menu_box)
            self.outer.add_widget(top_menu_scroll)
            self.content_area = BoxLayout(orientation='vertical', size_hint=(1, 1), padding=dp(6))
            self.outer.add_widget(self.content_area)
        else:
            # Windows डेस्कटॉप मोड: पुराना साइडबार लेआउट 100% सुरक्षित
            self.main_layout = BoxLayout(orientation='horizontal')
            sidebar_container = BoxLayout(orientation='vertical', size_hint_x=0.20)
            with sidebar_container.canvas.before:
                Color(0.01, 0.28, 0.12, 1)
                self.sr = Rectangle(size=sidebar_container.size, pos=sidebar_container.pos)
            sidebar_container.bind(size=lambda ins, val: setattr(self.sr, 'size', ins.size), pos=lambda ins, val: setattr(self.sr, 'pos', ins.pos))
            sidebar_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True)
            sidebar_buttons_grid = GridLayout(cols=1, spacing=8, padding=(10, 15, 10, 15), size_hint_y=None)
            sidebar_buttons_grid.bind(minimum_height=sidebar_buttons_grid.setter('height'))
            for name in menu:
                btn_color = (0.7, 0.1, 0.1, 1) if name in ['EXIT', 'LOGOUT'] else (0.02, 0.45, 0.2, 1)
                btn = Button(text=name, background_color=btn_color, font_size=12, bold=True, size_hint_y=None, height=44, background_normal='')
                btn.bind(on_press=self.menu_nav)
                sidebar_buttons_grid.add_widget(btn)
            sidebar_scroll.add_widget(sidebar_buttons_grid)
            sidebar_container.add_widget(sidebar_scroll)
            self.content_area = BoxLayout(orientation='vertical', size_hint_x=0.80, padding=10)
            self.main_layout.add_widget(sidebar_container)
            self.main_layout.add_widget(self.content_area)
            self.outer.add_widget(self.main_layout)

        self.add_widget(self.outer)
        self.current_view = 'welcome'
        self.marks_tab_index = 0; self.reg_tab_index = 0; self.att_tab_index = 0
        self.show_welcome()
        Window.unbind(on_key_down=self.on_keyboard_down) if hasattr(Window, 'on_key_down') else None
        Window.bind(on_key_down=self.on_keyboard_down)

def on_pre_enter(self, *args):
        u_info = getattr(App.get_running_app(), 'logged_in_user', None)
        if u_info and isinstance(u_info, dict):
            u_nm = str(u_info.get('Name', 'User')).strip()
            u_pic = str(u_info.get('Photo', '')).strip()
            sch_nm = str(u_info.get('School Name', '')).strip()
            ud_code = str(u_info.get('UDISE', '')).strip()
            if u_nm and u_nm.lower() != 'nan':
                self.dash_user_lbl.text = u_nm.split()[0]
            if u_pic and u_pic.lower() != 'nan' and os.path.exists(u_pic):
                self.dash_user_img.source = u_pic
                self.dash_user_img.reload()
            if sch_nm and sch_nm.lower() != 'nan' and hasattr(self, 'lbl_dash_main'):
                self.lbl_dash_main.text = f"{sch_nm} - {ud_code}" if ud_code else sch_nm

    def logout_user_action(self):
        App.get_running_app().logged_in_user = None
        if not self.manager.has_screen('login'):
            self.manager.add_widget(LoginScreen(name='login'))
        self.manager.current = 'login'

    def popup(self, title, msg):
        is_mob = (kivy_platform != 'win')
        pl = BoxLayout(orientation='vertical', padding=dp(15) if is_mob else 20, spacing=dp(12) if is_mob else 10)
        lbl = Label(text=str(msg), halign='center', valign='middle', color=(1, 1, 1, 1), font_size=sp(14) if is_mob else 14)
        lbl.bind(size=lambda ins, val: setattr(ins, 'text_size', (ins.width - dp(10), None)))
        pl.add_widget(lbl)
        cb = Button(text='OK', size_hint_y=None, height=dp(44) if is_mob else 40, background_color=(0.05, 0.55, 0.25, 1), bold=True, font_size=sp(15) if is_mob else 14)
        pl.add_widget(cb)
        pop = Popup(title=str(title), content=pl, size_hint=(0.90, 0.38) if is_mob else (0.5, 0.35), background='', background_color=(0.14, 0.14, 0.14, 0.98))
        cb.bind(on_press=pop.dismiss)
        pop.open()


    def show_welcome(self):
        self.content_area.clear_widgets()
        self.current_view = 'welcome'
        BULLETIN_DB = 'Bulletin_Database.xlsx'
        is_mob = (kivy_platform != 'win')
        
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.label import Label
        from kivy.uix.image import Image
        from kivy.uix.button import Button
        from kivy.uix.scrollview import ScrollView
        from kivy.graphics import Color, Rectangle
        from kivy.uix.popup import Popup
        from kivy.uix.behaviors import ButtonBehavior
        import os
        from datetime import datetime

        with self.content_area.canvas.before:
            Color(0.93, 0.94, 0.96, 1)
            self.welcome_canvas_rect = Rectangle(size=self.content_area.size, pos=self.content_area.pos)
        self.content_area.bind(size=lambda ins, val: setattr(self.welcome_canvas_rect, 'size', ins.size), pos=lambda ins, val: setattr(self.welcome_canvas_rect, 'pos', ins.pos))

        class ClickableImage(ButtonBehavior, Image):
            pass

        def open_image_zoom_popup(img_path, title_text):
            popup_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
            large_img = Image(source=img_path, allow_stretch=True, keep_ratio=True, size_hint=(1, 0.88))
            popup_layout.add_widget(large_img)
            close_btn = Button(text="❌ CLOSE", size_hint=(1, 0.12), background_color=(0.7, 0.1, 0.1, 1), font_size=sp(15) if is_mob else 16, bold=True)
            popup_layout.add_widget(close_btn)
            image_popup = Popup(title=f"🔍 {title_text} - FULL VIEW", content=popup_layout, size_hint=(0.94, 0.82) if is_mob else (0.85, 0.85), auto_dismiss=True)
            close_btn.bind(on_release=image_popup.dismiss)
            image_popup.open()

        def build_visual_card(img_name, cap_title, sub_text):
            card = BoxLayout(orientation='vertical', spacing=3, padding=5, size_hint_x=None if is_mob else 1, width=dp(165) if is_mob else 150)
            with card.canvas.before:
                Color(1, 1, 1, 1)
                card.rect = Rectangle(size=card.size, pos=card.pos)
            card.bind(size=lambda ins, val: setattr(ins.rect, 'size', ins.size), pos=lambda ins, val: setattr(card.rect, 'pos', ins.pos))
            
            resolved_photo_path = get_exe_safe_path(img_name)
            if os.path.exists(resolved_photo_path):
                img_widget = ClickableImage(source=resolved_photo_path, allow_stretch=True, keep_ratio=False, size_hint=(1, 0.68))
                img_widget.bind(on_release=lambda instance: open_image_zoom_popup(resolved_photo_path, cap_title))
                card.add_widget(img_widget)
            else:
                card.add_widget(Label(text="📸\n[Image Box]", color=(0.5, 0.5, 0.5, 1), font_size=sp(11) if is_mob else 11, halign='center', size_hint=(1, 0.68)))
                
            lbl_title = Label(text=f"📌 {cap_title}", color=(0.05, 0.2, 0.4, 1), font_size=sp(11.5) if is_mob else 12, bold=True, halign='center', valign='middle', size_hint=(1, 0.17))
            lbl_sub = Label(text=sub_text, color=(0.4, 0.4, 0.4, 1), font_size=sp(10) if is_mob else 10, halign='center', valign='middle', size_hint=(1, 0.15))
            lbl_title.bind(size=lambda ins, val: setattr(ins, 'text_size', ins.size))
            lbl_sub.bind(size=lambda ins, val: setattr(ins, 'text_size', ins.size))
            card.add_widget(lbl_title)
            card.add_widget(lbl_sub)
            return card

        def make_gallery_strip(items_list):
            row_box = BoxLayout(orientation='horizontal', spacing=dp(10) if is_mob else 12, size_hint_y=None, height=dp(155) if is_mob else 145)
            if is_mob:
                row_box.size_hint_x = None
                row_box.bind(minimum_width=row_box.setter('width'))
            for img, cap, sub in items_list:
                row_box.add_widget(build_visual_card(img, cap, sub))
            if is_mob:
                sc = ScrollView(size_hint=(1, None), height=dp(160), do_scroll_x=True, do_scroll_y=False)
                sc.add_widget(row_box)
                return sc
            return row_box

        if is_mob:
            outer_scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
            split_master_box = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(8), size_hint_y=None)
            split_master_box.bind(minimum_height=split_master_box.setter('height'))
            left_panel = BoxLayout(orientation='vertical', spacing=dp(8), size_hint=(1, None))
            left_panel.bind(minimum_height=left_panel.setter('height'))
        else:
            split_master_box = BoxLayout(orientation='horizontal', spacing=15, padding=10)
            left_panel = BoxLayout(orientation='vertical', spacing=10, size_hint_x=0.75)

        lbl_wel = Label(text="Welcome to Primary School Panauta", font_size=sp(17) if is_mob else 24, bold=True, color=(0.05, 0.2, 0.4, 1), size_hint_y=None, height=dp(32) if is_mob else 32, halign='left', valign='middle')
        lbl_wel.bind(size=lbl_wel.setter('text_size'))
        left_panel.add_widget(lbl_wel)
        
        school_activities = [
            ('smart_class.jpg', 'SMART CLASS', 'Use of ICT'),
            ('sports_day.jpg', 'Republic Day Program', 'Cultural Program'),
            ('mdm_dining.jpg', 'TLM Presentation', 'District Level TLM Exhibition')
        ]
        left_panel.add_widget(make_gallery_strip(school_activities))
        
        lbl_ach = Label(text="🏆 SCHOOL HISTORIC ACHIEVEMENTS & GLORY", font_size=sp(12.5) if is_mob else 12, bold=True, color=(0.5, 0.2, 0, 1), size_hint_y=None, height=dp(24) if is_mob else 18, halign='left', valign='middle')
        lbl_ach.bind(size=lbl_ach.setter('text_size'))
        left_panel.add_widget(lbl_ach)
        achievements_list = [
            ('achieve1.jpg', 'Dakshta Pariksha Award', 'Block Level Educational Excellence'),
            ('achieve2.jpg', 'Kabaddi CHAMPIONSHIP', 'Block Sports Tournament Winner'),
            ('achieve3.jpg', 'Report Card Distribution', '100% Standard Literacy Locked')
        ]
        left_panel.add_widget(make_gallery_strip(achievements_list))
        
        lbl_cmp = Label(text="🏫 SCHOOL CAMPUS INFRASTRUCTURE", font_size=sp(12.5) if is_mob else 12, bold=True, color=(0, 0.35, 0.2, 1), size_hint_y=None, height=dp(24) if is_mob else 18, halign='left', valign='middle')
        lbl_cmp.bind(size=lbl_cmp.setter('text_size'))
        left_panel.add_widget(lbl_cmp)
        campus_list = [
            ('campus1.jpg', 'MAIN SCHOOL BUILDING', 'Safe and Green Eco-Friendly Campus'),
            ('campus2.jpg', 'FLOWER HERBAL GARDEN', 'Clean Environment & Nature Study'),
            ('campus3.jpg', 'MORNING ASSEMBLY GROUND', 'Physical Fitness and Recreation Arena')
        ]
        left_panel.add_widget(make_gallery_strip(campus_list))
        if not is_mob:
            left_panel.add_widget(BoxLayout())
        
        split_master_box.add_widget(left_panel)
        
        # ➡️ [LIVE BULLETIN BOARD PANEL - Marquee Ticker + Image/Document Viewer]
        right_bulletin_panel = BoxLayout(orientation='vertical', spacing=dp(8) if is_mob else 10, size_hint=(1, None) if is_mob else (0.25, 1), height=dp(360) if is_mob else 500, padding=dp(8) if is_mob else 6)
        with right_bulletin_panel.canvas.before:
            Color(0.12, 0.16, 0.22, 1)
            right_bulletin_panel.rect = Rectangle(size=right_bulletin_panel.size, pos=right_bulletin_panel.pos)
        right_bulletin_panel.bind(size=lambda ins, val: setattr(right_bulletin_panel.rect, 'size', ins.size), pos=lambda ins, val: setattr(right_bulletin_panel.rect, 'pos', ins.pos))
        
        right_bulletin_panel.add_widget(Label(text="LIVE BULLETIN BOARD", font_size=sp(15) if is_mob else 15, bold=True, color=(1, 1, 0.6, 1), size_hint_y=None, height=dp(28) if is_mob else 25))
        
        # 🎞️ चलता हुआ Live Marquee Ticker पट्टी
        marquee_bar = BoxLayout(size_hint_y=None, height=dp(28) if is_mob else 26, padding=(dp(6), 0))
        with marquee_bar.canvas.before:
            Color(0.65, 0.1, 0.1, 1)
            marquee_bar.rect = Rectangle(size=marquee_bar.size, pos=marquee_bar.pos)
        marquee_bar.bind(size=lambda ins, val: setattr(marquee_bar.rect, 'size', ins.size), pos=lambda ins, val: setattr(marquee_bar.rect, 'pos', ins.pos))
        
        marquee_lbl = Label(text="WELCOME TO DIGITAL NOTICE BOARD - PRIMARY SCHOOL PANAUTA   ***   ", font_size=sp(12) if is_mob else 12, bold=True, color=(1, 1, 0.85, 1), halign='left', valign='middle')
        marquee_bar.add_widget(marquee_lbl)
        right_bulletin_panel.add_widget(marquee_bar)

        btn_upload_bulletin = Button(text="UPLOAD NOTICE / PDF / DOC", background_color=(0.02, 0.45, 0.35, 1), bold=True, font_size=sp(13) if is_mob else 12, size_hint_y=None, height=dp(42) if is_mob else 36)
        
        def local_notice_upload_action(instance):
            def on_notice_picked(file_path):
                if not file_path:
                    return
                try:
                    import shutil
                    os.makedirs('Bulletin_Uploads', exist_ok=True)
                    f_base = os.path.basename(file_path)
                    dest_path = os.path.abspath(os.path.join('Bulletin_Uploads', f_base))
                    if os.path.abspath(file_path) != dest_path:
                        shutil.copyfile(file_path, dest_path)
                    
                    from kivy.uix.textinput import TextInput
                    from kivy.uix.popup import Popup
                    pl = BoxLayout(orientation='vertical', padding=dp(12) if is_mob else 10, spacing=dp(10) if is_mob else 8)
                    pl.add_widget(Label(text="Enter Brief Notice Headline Caption:", bold=True, color=(1,1,1,1), font_size=sp(14) if is_mob else 13))
                    cap_in = TextInput(multiline=False, size_hint_y=None, height=dp(44) if is_mob else 36, font_size=sp(15) if is_mob else 14)
                    pl.add_widget(cap_in)
                    btn_save_n = Button(text='PUBLISH TO BOARD', background_color=(0,0.6,0.1,1), bold=True, size_hint_y=None, height=dp(44) if is_mob else 38, font_size=sp(14) if is_mob else 13)
                    pl.add_widget(btn_save_n)
                    pop = Popup(title="Notice Caption Manager", content=pl, size_hint=(0.92, 0.42) if is_mob else (0.7, 0.35), background='', background_color=(0.14, 0.14, 0.14, 0.98))
                    
                    def commit_notice_to_excel(x):
                        txt_cap = cap_in.text.strip().upper() if cap_in.text.strip() else "OFFICIAL ORDER RELEASED"
                        new_row = {'Date': datetime.now().strftime("%d-%m-%Y"), 'Caption': txt_cap, 'File_Path': dest_path}
                        df_new = pd.DataFrame([new_row])
                        if not os.path.exists(BULLETIN_DB):
                            df_new.to_excel(BULLETIN_DB, index=False)
                        else:
                            pd.concat([pd.read_excel(BULLETIN_DB, dtype=str), df_new], ignore_index=True).to_excel(BULLETIN_DB, index=False)
                        pop.dismiss()
                        self.popup('Live', 'Notice published successfully!')
                        self.show_welcome()
                        
                    btn_save_n.bind(on_press=commit_notice_to_excel)
                    pop.open()
                except Exception as ex:
                    self.popup('Error', str(ex))

            select_file_cross_platform(
                "Select Notice (Documents, PDF or Images)",
                [("Documents & Images", "*.pdf *.doc *.docx *.xlsx *.png *.jpg *.jpeg")],
                on_notice_picked
            )
        btn_upload_bulletin.bind(on_press=local_notice_upload_action)
        right_bulletin_panel.add_widget(btn_upload_bulletin)
        
        notices_scroll = ScrollView()
        notices_grid = GridLayout(cols=1, spacing=dp(10) if is_mob else 10, size_hint_y=None, padding=5)
        notices_grid.bind(minimum_height=notices_grid.setter('height'))
        
        ticker_headlines = []
        if os.path.exists(BULLETIN_DB):
            try:
                df_bulletin = pd.read_excel(BULLETIN_DB, dtype=str)
                all_notices = [dict(r_n) for _, r_n in df_bulletin.iterrows()]
                for row in reversed(all_notices):
                    n_date = str(row.get('Date', ''))
                    n_cap = str(row.get('Caption', ''))
                    n_path = str(row.get('File_Path', ''))
                    ticker_headlines.append(f"[{n_date}] {n_cap}")
                    
                    notice_box = BoxLayout(orientation='vertical', spacing=2, padding=8, size_hint_y=None, height=dp(80) if is_mob else 75)
                    with notice_box.canvas.before:
                        Color(0.2, 0.25, 0.35, 1)
                        notice_box.rect = Rectangle(size=notice_box.size, pos=notice_box.pos)
                    notice_box.bind(size=lambda ins, val: setattr(notice_box.rect, 'size', ins.size), pos=lambda ins, val: setattr(notice_box.rect, 'pos', ins.pos))
                    
                    notice_box.add_widget(Label(text=f"Date: {n_date}", font_size=sp(11.5) if is_mob else 11, color=(1, 1, 0.6, 1), bold=True, size_hint_y=None, height=dp(18) if is_mob else 16, halign='left'))
                    
                    btn_lnk = Button(text=n_cap, font_size=sp(13.5) if is_mob else 13.5, bold=True, color=(1,1,1,1), background_normal='', background_color=(0,0,0,0), halign='left', valign='middle')
                    btn_lnk.bind(size=btn_lnk.setter('text_size'))

                    def _open_notice_item(inst, pth=n_path, cap_t=n_cap):
                        if not os.path.exists(pth):
                            self.popup('Alert', 'Notice file missing!'); return
                        if pth.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                            open_image_zoom_popup(pth, cap_t)
                        else:
                            open_file_cross_platform(pth)

                    btn_lnk.bind(on_press=_open_notice_item)
                    
                    notice_box.add_widget(btn_lnk)
                    notices_grid.add_widget(notice_box)
            except Exception: 
                pass
        else:
            notice_box = BoxLayout(orientation='vertical', padding=6, size_hint_y=None, height=dp(65) if is_mob else 60)
            notice_box.add_widget(Label(text="NO OFFICIAL NOTICES YET\nWelcome to Digital Bulletin Center.", font_size=sp(12.5) if is_mob else 12, color=(0.8,0.8,0.8,1), halign='center'))
            notices_grid.add_widget(notice_box)
            
        notices_scroll.add_widget(notices_grid)
        right_bulletin_panel.add_widget(notices_scroll)

        # 🎞️ Marquee Ticker व Auto-Scroll एनिमेशन इंजन
        from kivy.clock import Clock
        if hasattr(self, '_bulletin_marquee_ev') and self._bulletin_marquee_ev:
            Clock.unschedule(self._bulletin_marquee_ev)

        full_ticker_str = ("   ***   ".join(ticker_headlines) + "   ***   ") if ticker_headlines else "WELCOME TO DIGITAL BULLETIN BOARD - PRIMARY SCHOOL PANAUTA   ***   "
        marquee_lbl.text = full_ticker_str

        def _tick_marquee(dt):
            if self.current_view != 'welcome':
                return
            t = marquee_lbl.text
            if len(t) > 1:
                marquee_lbl.text = t[1:] + t[0]
            if notices_grid.height > notices_scroll.height:
                nxt = notices_scroll.scroll_y - 0.008
                notices_scroll.scroll_y = 1.0 if nxt <= 0 else nxt

        self._bulletin_marquee_ev = Clock.schedule_interval(_tick_marquee, 0.16)
        
        split_master_box.add_widget(right_bulletin_panel)
        if is_mob:
            outer_scroll.add_widget(split_master_box)
            self.content_area.add_widget(outer_scroll)
        else:
            self.content_area.add_widget(split_master_box)

    def menu_nav(self, instance):
        if instance.text in ['EXIT', 'LOGOUT']:
            self.logout_user_action()
        elif instance.text == 'STUDENT REGISTRATION': self.load_form()
        elif instance.text == 'STUDENT ATTENDANCE': self.load_attendance_view()
        elif instance.text == 'MARKS ENTRY': self.load_marks_entry_view()
        elif instance.text == 'HEIGHT & WEIGHT': self.load_height_weight_view()
        elif instance.text == 'D.B.T.': self.load_dbt_view()
        elif instance.text == 'MDM': self.load_mdm_view()
        elif instance.text == 'STAFF DETAIL': self.load_staff_view()
        elif instance.text == 'TRANSFER CERTIFICATE': self.load_tc_view()
        elif instance.text == 'GRANT DETAILS': self.load_grant_details_view()
        elif instance.text == 'S.M.C. MEMBERS': self.load_smc_details_view()
        elif instance.text == 'COOK DETAILS': self.load_cook_details_view()
        elif instance.text == 'RESULTS': self.open_results_search_popup(None)
        elif instance.text == 'PHOTO GALLERY': self.load_photo_gallery_view()
        elif instance.text == 'GOOGLE DRIVE SYNC': self.open_google_drive_sync_popup()
        else:
            self.content_area.clear_widgets()
            with self.content_area.canvas.before: 
                Color(0.95, 0.95, 0.95, 1)
                self.c_bg = Rectangle(size=self.content_area.size, pos=self.content_area.pos)
            self.content_area.add_widget(Label(text=f'{instance.text} Module Layout Linked Successfully!', font_size=18, color=(0.2,0.2,0.2,1), halign='center'))
  
    def open_results_search_popup(self, instance):
        from kivy.core.window import Window
        from kivy.clock import Clock
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.textinput import TextInput
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from kivy.uix.popup import Popup
        from kivy.uix.spinner import Spinner
        from kivy.uix.widget import Widget
        import os
        import openpyxl

        is_mob = (kivy_platform != 'win')

        # मुख्य वर्टिकल बॉक्स लेआउट पैनल
        pl = BoxLayout(orientation='vertical', padding=(dp(15), dp(12)) if is_mob else (15, 12, 15, 12), spacing=dp(10) if is_mob else 10)
        
        # --- [विकल्प 1]: सिंगल छात्र का रिपोर्ट कार्ड पैनल ---
        lbl1 = Label(text='[OPTION 1] Enter Name or SR NO for Single Report Card:', color=(1,1,1,1), bold=True, font_size=sp(13) if is_mob else 13, size_hint_y=None, height=dp(26) if is_mob else 22, halign='left', valign='middle')
        lbl1.bind(size=lbl1.setter('text_size'))
        pl.add_widget(lbl1)
        
        search_input = TextInput(multiline=False, size_hint_y=None, height=dp(44) if is_mob else 34, halign='center', font_size=sp(15) if is_mob else 15, background_color=(0.95, 0.95, 0.95, 1), padding=[dp(8), dp(8)] if is_mob else (6, 6, 6, 6))
        pl.add_widget(search_input)
        
        btn_box = BoxLayout(spacing=dp(15) if is_mob else 15, size_hint_y=None, height=dp(44) if is_mob else 34)
        btn_find = Button(text='PRINT REPORT CARD', background_color=(0, 0.5, 0.1, 1), bold=True, font_size=sp(13) if is_mob else 14)
        btn_box.add_widget(btn_find)
        pl.add_widget(btn_box)
        
        # --- [विकल्प 2]: संपूर्ण क्लास का समेकित रिज़ल्ट (Excel + PDF) ---
        lbl2 = Label(text='[OPTION 2] Select Class for Full Class Consolidated (Excel + PDF):', color=(1,1,1,1), bold=True, font_size=sp(13) if is_mob else 13, size_hint_y=None, height=dp(26) if is_mob else 22, halign='left', valign='middle')
        lbl2.bind(size=lbl2.setter('text_size'))
        pl.add_widget(lbl2)
        
        class_spinner = Spinner(text='Class 3', values=('Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5'), size_hint_y=None, height=dp(44) if is_mob else 34, font_size=sp(14) if is_mob else 14, background_color=(0.05, 0.35, 0.6, 1))
        pl.add_widget(class_spinner)
        
        btn_class_box = BoxLayout(size_hint_y=None, height=dp(46) if is_mob else 34)
        btn_print_class = Button(text='⚡ DOWNLOAD EXCEL + PRINT REGISTER PDF ⚡', background_color=(0.85, 0.45, 0.0, 1), bold=True, font_size=sp(12) if is_mob else 13, halign='center', valign='middle')
        if is_mob:
            btn_print_class.bind(size=lambda ins, val: setattr(ins, 'text_size', (ins.width - dp(10), None)))
        btn_class_box.add_widget(btn_print_class); pl.add_widget(btn_class_box)
        
        # 🛡️ [सटीक पैरेंट फिक्स]: क्लोज बटन को केवल एक बार मुख्य लेआउट 'pl' में जोड़ा गया है
        pl.add_widget(Widget(size_hint_y=None, height=dp(5) if is_mob else 5))
        btn_cancel = Button(text='CLOSE PANEL', background_color=(0.6, 0.1, 0.1, 1), bold=True, size_hint_y=None, height=dp(44) if is_mob else 34, font_size=sp(13) if is_mob else 14)
        pl.add_widget(btn_cancel)
        
        if is_mob:
            pop = Popup(title='Results Hub', content=pl, size_hint=(0.94, 0.68), auto_dismiss=False, background='', background_color=(0.14, 0.14, 0.14, 0.98))
        else:
            pop = Popup(title='Results ', content=pl, size_hint=(None, None), size=(550, 370), auto_dismiss=False, background='', background_color=(0.14, 0.14, 0.14, 0.98))
        
        def close_popup_and_clean_hook(ins):
            try: Window.unbind(on_key_down=keyboard_hook)
            except: pass
            pop.dismiss()
            
        btn_cancel.bind(on_press=close_popup_and_clean_hook)
        
                # 🎯 एक्शन 1: सिंगल छात्र रिपोर्ट कार्ड प्रिंट इंजन (Windows + Android क्रॉस-प्लेटफ़ॉर्म)
        def find_and_print_action():
            query = search_input.text.strip().lower().replace('.0', '')
            if not query:
                self.popup('Alert', 'Please enter a student name or SR NO!'); return
                
            student_file = 'Student_Database.xlsx'
            marks_file = 'Marks_Database.xlsx'
            if not os.path.exists(student_file):
                self.popup('File Error', f'Student Database file ({student_file}) not found!'); return
                
            try:
                st_df = pd.read_excel(student_file, dtype=str)
                matched_st_row = None

                for _, r_st in st_df.iterrows():
                    nm = str(r_st.get('NAME', '')).strip().lower()
                    sr = str(r_st.get('SR NO', '')).strip().replace('.0', '').lower()
                    if nm == query or sr == query:
                        matched_st_row = r_st
                        break
                    
                if matched_st_row is not None:
                    student_row = matched_st_row
                    sr_no_loaded = str(student_row.get('SR NO', '')).strip().replace('.0', '')
                    
                    self.current_report_student_profile = {
                        'NAME': str(student_row.get('NAME', '')).strip(), 'SR NO': sr_no_loaded, 'CLASS': str(student_row.get('CLASS', '')).strip(),
                        'GENDER': str(student_row.get('GENDER', '---')).strip(), "FATHER'S NAME": str(student_row.get("FATHER'S NAME", '')).strip(),
                        'DATE OF BIRTH': str(student_row.get('DATE OF BIRTH (DDMMYYYY)', '')).strip(), "MOTHER'S NAME": str(student_row.get("MOTHER'S NAME", '')).strip(),
                        'ST Aadhaar NO': str(student_row.get('ST Aadhaar NO', student_row.get('ST Aadhaar ID', '---'))).strip(), 'PEN NO': str(student_row.get('PEN NO', '---')).strip(), 'APAAR ID': str(student_row.get('APAAR ID', '---')).strip()
                    }
                    self.student_marks_summary = {}
                    
                    if os.path.exists(marks_file):
                        try:
                            m_df = pd.read_excel(marks_file, dtype=str)
                            for _, row in m_df.iterrows():
                                r_sr = str(row.get('SR No', row.get('SR NO', ''))).strip().replace('.0', '')
                                if r_sr != sr_no_loaded:
                                    continue
                                raw_exam = str(row.get('Exam Type', '')).strip().lower()
                                if 'satra' in raw_exam and '1' in raw_exam: exam_key = "ST1"
                                elif 'half' in raw_exam: exam_key = "HALF"
                                elif 'satra' in raw_exam and '2' in raw_exam: exam_key = "ST2"
                                elif 'annual' in raw_exam: exam_key = "ANNUAL"
                                else: continue
                                
                                subjects_to_check = ["Hindi", "English", "Maths", "Sanskrit", "Hamara ParivesH", "Art", "Naitik Shiksha", "Environment", "Work Experience", "Physical Education"]
                                for sub in subjects_to_check:
                                    db_sub_name = "EVS" if sub.upper() == "HAMARA PARIVESH" else sub
                                    o_val = str(row.get(f"{db_sub_name}_Oral", row.get(f"{db_sub_name.capitalize()}_Oral", '0'))).strip()
                                    w_val = str(row.get(f"{db_sub_name}_Written", row.get(f"{db_sub_name.capitalize()}_Written", '0'))).strip()
                                    o_num = int(float(o_val)) if o_val.replace('.','',1).isdigit() else 0
                                    w_num = int(float(w_val)) if w_val.replace('.','',1).isdigit() else 0
                                    self.student_marks_summary[f"{sub.upper()}_{exam_key}"] = o_num + w_num
                        except Exception as m_err: print("Marks Compilation Error:", str(m_err))
                    close_popup_and_clean_hook(None)
                    self.generate_student_report_card_pdf(None)
                else: self.popup('Not Found', f'Error: No student profile found matching "{search_input.text.strip()}"')
            except Exception as e: self.popup('Database Error', f'Error accessing database files: {str(e)}')

        # 🎯 एक्शन 2: संपूर्ण क्लासवाइज़ Excel डाउनलोड + सुव्यवस्थित प्रिंटर पीडीएफ रजिस्टर इंजन
        def print_classwise_excel_action():
            selected_class = class_spinner.text.strip()
            student_file = 'Student_Database.xlsx'
            marks_file = 'Marks_Database.xlsx'
            if not os.path.exists(student_file) or not os.path.exists(marks_file):
                self.popup('Database Alert', 'Database files are missing!'); return
            try:
                st_df = pd.read_excel(student_file, dtype=str)
                class_students_rows = []
                for _, r_st in st_df.iterrows():
                    if str(r_st.get('CLASS', '')).strip().lower() == selected_class.lower():
                        class_students_rows.append(dict(r_st))

                if not class_students_rows:
                    self.popup('No Data', f'No student data found for {selected_class}'); return
                
                is_c12 = any(x in selected_class.lower() for x in ['1', '2', 'one', 'two'])
                subs = ["HINDI", "ENGLISH", "MATHS"] if is_c12 else ["HINDI", "ENGLISH", "SANSKRIT", "MATHS", "HAMARA PARIVESH", "ART", "PHYSICAL EDUCATION", "ENVIRONMENT", "WORK EXPERIENCE", "NAITIK SHIKSHA"]
                max_subjects = len(subs)
                
                m_df = pd.read_excel(marks_file, dtype=str)
                all_marks_rows = [dict(r_m) for _, r_m in m_df.iterrows()]
                
                rows_list = []
                for st_row in class_students_rows:
                    sr = str(st_row.get('SR NO', '')).strip().replace('.0', '')
                    name = str(st_row.get('NAME', '')).strip().upper()
                    f_name = str(st_row.get("FATHER'S NAME", '')).strip().upper()
                    
                    student_total = 0
                    actual_active_subjects = 0
                    student_marks_dict = {"SR NO": sr, "STUDENT NAME": name, "FATHER NAME": f_name}
                    st_marks_rows = [rm for rm in all_marks_rows if str(rm.get('SR No', rm.get('SR NO', ''))).strip().replace('.0', '') == sr]
                    
                    for sub in subs:
                        sub_grand_total = 0
                        clean_sub_title = "EVS" if sub == "HAMARA PARIVESH" else sub.title()
                        
                        for m_row in st_marks_rows:
                            o_val = str(m_row.get(f"{clean_sub_title}_Oral", m_row.get(f"{sub}_Oral", '0'))).strip()
                            w_val = str(m_row.get(f"{clean_sub_title}_Written", m_row.get(f"{sub}_Written", '0'))).strip()
                            sub_grand_total += (int(float(o_val)) if o_val.replace('.','',1).isdigit() else 0) + (int(float(w_val)) if w_val.replace('.','',1).isdigit() else 0)
                            
                        student_marks_dict[sub] = sub_grand_total
                        if sub_grand_total > 0:
                            actual_active_subjects += 1
                        student_total += sub_grand_total
                    
                    if actual_active_subjects == 0: 
                        actual_active_subjects = max_subjects
                        
                    student_max_marks = actual_active_subjects * 100
                    
                    perc = (student_total / student_max_marks) * 100 if student_max_marks > 0 else 0
                    grade = 'A' if perc >= 91 else 'B' if perc>=76 else 'C' if perc>=56 else 'D' if perc>=41 else 'E'
                    status = "PASS" if perc >= 40 else "FAIL" if student_total > 0 else "ABSENT"
                    
                    student_marks_dict["GRAND TOTAL"] = f"{student_total} / {student_max_marks}"
                    student_marks_dict["PERCENTAGE"] = f"{perc:.1f}%"
                    student_marks_dict["GRADE"] = grade                    
                    student_marks_dict["STATUS"] = status
                    rows_list.append(student_marks_dict)

                # 📊 [पार्ट ए]: क्रॉस-प्लेटफ़ॉर्म OpenPyXL Excel एक्सपोर्ट इंजन (Windows + Android दोनों पर चलेगा)
                out_excel_filename = f"{selected_class.replace(' ', '_')}_Final_Result_2026.xlsx"
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = 'Consolidated Result'
                headers_excel = ["SR NO", "STUDENT NAME", "FATHER NAME"] + subs + ["GRAND TOTAL", "PERCENTAGE", "GRADE", "STATUS"]
                ws.append(headers_excel)
                for r_item in rows_list:
                    ws.append([r_item.get(h, '') for h in headers_excel])
                for col in ws.columns:
                    max_len = max(len(str(cell.value or '')) for cell in col)
                    col_letter = openpyxl.utils.get_column_letter(col[0].column)
                    ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
                wb.save(out_excel_filename)

                # 📄 [पार्ट बी]: शासकीय लैंडस्केप रजिस्टर पीडीएफ इंजन लॉक
                from reportlab.lib.pagesizes import landscape, A4
                from reportlab.platypus import SimpleDocTemplate, TableStyle, Table, Paragraph, Spacer
                from reportlab.lib.styles import ParagraphStyle
                from reportlab.lib import colors
                
                out_pdf_filename = f"{selected_class.replace(' ', '_')}_Print_Register_2026.pdf"
                doc_pdf = SimpleDocTemplate(out_pdf_filename, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
                pdf_story = []
                
                PURPLE_THEME = colors.HexColor("#3F2583")
                LIGHT_PURPLE = colors.HexColor("#F1EEF9")
                
                h_style_main = ParagraphStyle('H_M', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=PURPLE_THEME, alignment=1)
                h_style_sub = ParagraphStyle('H_S', fontName='Helvetica-Bold', fontSize=10, leading=14, textColor=colors.black, alignment=1)
                th_style = ParagraphStyle('T_H_Reg', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white, alignment=1)
                td_bold = ParagraphStyle('T_D_B', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=colors.black, alignment=1)
                td_norm = ParagraphStyle('T_D_N', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.black, alignment=1)
                
                pdf_story.append(Paragraph("<b>PRIMARY SCHOOL PANAUTA, WAZIRGANJ (BUDAUN)</b>", h_style_main))
                pdf_story.append(Paragraph(f"<b>CONSOLIDATED MARKS REGISTER & TABULATION SHEET - {selected_class.upper()} (SESSION : 2025-2026)</b>", h_style_sub))
                pdf_story.append(Spacer(1, 12))
                
                reg_headers = [Paragraph("<b>SR NO</b>", th_style), Paragraph("<b>STUDENT NAME</b>", th_style), Paragraph("<b>FATHER NAME</b>", th_style)]
                for sub in subs: reg_headers.append(Paragraph(f"<b>{sub}</b>", th_style))
                reg_headers.extend([Paragraph("<b>TOTAL</b>", th_style), Paragraph("<b>PER%</b>", th_style), Paragraph("<b>GRADE</b>", th_style), Paragraph("<b>STATUS</b>", th_style)])
                
                reg_table_rows = [reg_headers]
                for idx, r_data in enumerate(rows_list, start=1):
                    row_cells = [Paragraph(str(r_data["SR NO"]), td_norm), Paragraph(str(r_data["STUDENT NAME"]), td_bold), Paragraph(str(r_data["FATHER NAME"]), td_norm)]
                    for sub in subs: row_cells.append(Paragraph(str(r_data[sub]), td_norm))
                    row_cells.extend([Paragraph(str(r_data["GRAND TOTAL"]), td_bold), Paragraph(str(r_data["PERCENTAGE"]), td_bold), Paragraph(f"<b>{r_data['GRADE']}</b>", td_bold), Paragraph(f"<font color='green'><b>{r_data['STATUS']}</b></font>" if r_data['STATUS']=="PASS" else f"<font color='red'><b>{r_data['STATUS']}</b></font>", td_bold)])
                    reg_table_rows.append(row_cells)
                
                w_reg_sr = 32
                w_reg_name = 110
                w_reg_fname = 110
                w_reg_sub = 38
                w_reg_tot = 60
                w_reg_per = 45
                w_reg_grd = 35
                w_reg_sts = 45
                col_w_list = [w_reg_sr, w_reg_name, w_reg_fname] + [w_reg_sub] * len(subs) + [w_reg_tot, w_reg_per, w_reg_grd, w_reg_sts]
                
                t_register = Table(reg_table_rows, colWidths=col_w_list, repeatRows=1)
                t_reg_style = [('GRID', (0,0), (-1,-1), 0.8, colors.HexColor("#595959")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BACKGROUND', (0,0), (-1,0), PURPLE_THEME), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)]
                for i in range(1, len(reg_table_rows)):
                    if i % 2 == 0: t_reg_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor("#F7F5FB")))
                t_register.setStyle(TableStyle(t_reg_style))
                pdf_story.append(t_register); pdf_story.append(Spacer(1, 40))
                
                sig_grid = [[Paragraph("________________________", td_bold), Paragraph("________________________", td_bold), Paragraph("________________________", td_bold)], [Paragraph("CLASS TEACHER SIGN", td_bold), Paragraph("EXAM CONTROLLER", td_bold), Paragraph("PRINCIPAL SEAL & SIGN", td_bold)]]
                t_reg_sig = Table(sig_grid, colWidths=[188.3]*3)
                t_reg_sig.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'BOTTOM'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
                pdf_story.append(t_reg_sig)
                
                doc_pdf.build(pdf_story)
                close_popup_and_clean_hook(None)
                self.popup('Success Hub', f"Consolidated Ledgers Generated!\n💾 Excel Saved: {out_excel_filename}\n🖨️ PDF Register: {out_pdf_filename}")
                open_file_cross_platform(out_pdf_filename)
            except Exception as ex: self.popup('Export Error', f"Excel Compilation Failed: {str(ex)}")

        btn_find.bind(on_press=lambda x: find_and_print_action())
        btn_print_class.bind(on_press=lambda x: print_classwise_excel_action())
        
        # ✨ [विज़ुअल फ़ोकस चक्र इंजन]
        self.res_popup_focus_index = 0
        def update_button_colors():
            search_input.focus = (self.res_popup_focus_index == 0)
            class_spinner.focus = (self.res_popup_focus_index == 2)
            btn_find.background_color = (0, 0.9, 0.2, 1) if self.res_popup_focus_index == 1 else (0, 0.5, 0.1, 1)
            btn_print_class.background_color = (1.0, 0.6, 0.1, 1) if self.res_popup_focus_index == 3 else (0.85, 0.45, 0.0, 1)
            btn_cancel.background_color = (0.9, 0.2, 0.2, 1) if self.res_popup_focus_index == 4 else (0.6, 0.1, 0.1, 1)
            
        def keyboard_hook(window, key, scancode, codepoint, modifiers):
            if key == 13 or key == 271:
                if self.res_popup_focus_index == 0 or self.res_popup_focus_index == 1: find_and_print_action(); return True
                elif self.res_popup_focus_index == 2: class_spinner.is_open = True; return True
                elif self.res_popup_focus_index == 3: print_classwise_excel_action(); return True
                elif self.res_popup_focus_index == 4: close_popup_and_clean_hook(None); return True
            elif key == 27:
                close_popup_and_clean_hook(None); return True
            elif key == 9:
                self.res_popup_focus_index = (self.res_popup_focus_index + 1) % 5
                update_button_colors(); return True
            return False

        Window.bind(on_key_down=keyboard_hook)
        Clock.schedule_once(lambda dt: [setattr(search_input, 'focus', True), update_button_colors()], 0.05)
        pop.open()

        # ⌨️ 🚀 [अल्टीमेट ग्लोबल कीबोर्ड इंजन - शत-प्रतिशत छात्र सिंक]: ड्रॉपडाउन पॉपअप ट्रैप का 100% गारंटेड फिक्स
    def on_keyboard_down(self, window, key, scancode, codepoint, modifiers):
        if self.manager.current != 'dashboard' or self.current_view == 'welcome': 
            return False
        
        from kivy.uix.textinput import TextInput
        from kivy.uix.spinner import Spinner
        from kivy.uix.button import Button

        # 🎯 1. चालू स्क्रीन के अनुसार कड़ाई से सही मास्टर एरे कतार लोड करना
        master_arr = []
        curr_idx = 0
        
        if self.current_view == 'marks' and hasattr(self, 'marks_master_tabs'): master_arr = self.marks_master_tabs; curr_idx = self.marks_tab_index
        elif self.current_view == 'attendance' and hasattr(self, 'attendance_master_tabs'): master_arr = self.attendance_master_tabs; curr_idx = self.att_tab_index
        elif self.current_view == 'height_weight' and hasattr(self, 'hw_master_tabs'): master_arr = self.hw_master_tabs; curr_idx = self.hw_tab_index
        elif self.current_view == 'dbt' and hasattr(self, 'dbt_master_tabs'): master_arr = self.dbt_master_tabs; curr_idx = self.dbt_tab_index
        elif self.current_view == 'mdm' and hasattr(self, 'mdm_master_tabs'): master_arr = self.mdm_master_tabs; curr_idx = self.mdm_tab_index
        elif self.current_view == 'registration' and hasattr(self, 'reg_master_tabs'): master_arr = self.reg_master_tabs; curr_idx = self.reg_tab_index
        elif self.current_view == 'staff_registration' and hasattr(self, 'staff_master_tabs'): master_arr = self.staff_master_tabs; curr_idx = self.staff_tab_index
        elif self.current_view == 'tc_module' and hasattr(self, 'tc_master_tabs'): master_arr = self.tc_master_tabs; curr_idx = self.tc_tab_index
        
        # 🔗 [सत्र चयन कड़ाई से लॉक]: सत्र ड्रॉपडाउन को हर हाल में कतार की शुरुआत (Index 0) पर री-लॉक किया गया
        elif self.current_view == 'smc_details' and hasattr(self, 'smc_seq'):
            master_arr = []
            if hasattr(self, 'smc_session_spinner'): master_arr.append(self.smc_session_spinner)
            master_arr.extend(self.smc_seq)
            if not hasattr(self, 'smc_popup_focus_index') or self.smc_popup_focus_index is None: self.smc_popup_focus_index = 0
            curr_idx = self.smc_popup_focus_index
            
        elif self.current_view == 'cook_details' and hasattr(self, 'cook_seq'):
            master_arr = []
            if hasattr(self, 'cook_session_spinner'): master_arr.append(self.cook_session_spinner)
            master_arr.extend(self.cook_seq)
            if not hasattr(self, 'cook_popup_focus_index') or self.cook_popup_focus_index is None: self.cook_popup_focus_index = 0
            curr_idx = self.cook_popup_focus_index
            
        elif self.current_view == 'grant_details' and hasattr(self, 'grant_seq'):
            master_arr = []
            if hasattr(self, 'g_tx_type'): master_arr.append(self.g_tx_type)
            master_arr.extend(self.grant_seq)
            if not hasattr(self, 'grant_popup_focus_index') or self.grant_popup_focus_index is None: self.grant_popup_focus_index = 0
            curr_idx = self.grant_popup_focus_index
        else: 
            return False

        if not master_arr or curr_idx >= len(master_arr): 
            return False

        # 📑 2. [TAB / ENTER KEY LOGIC]: सीधे 'Tab' से ही अगला विजेट एक्टिवेट करने का मास्टर चक्र
        if key in (9, 13, 271): # 9 = Tab, 13/271 = Enter
            old_w = master_arr[curr_idx]
            old_type_str = str(type(old_w))
            
            # पुराने विजेट का चमकीला विज़ुअल फ़ोकस और बैकग्राउंड रंग साफ़ करना
            if hasattr(old_w, 'set_visual_focus'): old_w.set_visual_focus(False)
            if isinstance(old_w, TextInput) or 'TextInput' in old_type_str or 'CustomText' in old_type_str: old_w.background_color = (1, 1, 1, 1)
            
            # कर्सर आगे खिसकते ही पुराने ड्रॉपडाउन को कड़ाई से स्क्रीन से क्लोज करना
            if isinstance(old_w, Spinner) or 'Spinner' in old_type_str or 'CustomSpinner' in old_type_str:
                if hasattr(old_w, 'dismiss'): old_w.dismiss()
                elif hasattr(old_w, 'dropdown_uid') and old_w.dropdown_uid: old_w.dismiss()
                old_w.is_open = False

            # अगला इंडेक्स कैलकुलेट करना (Shift+Tab पर पीछे जाने की क्षमता सिंक)
            shift = -1 if 'shift' in modifiers else 1
            next_idx = (curr_idx + shift) % len(master_arr)
            
            while next_idx != curr_idx:
                w = master_arr[next_idx]
                if hasattr(w, 'disabled') and w.disabled:
                    next_idx = (next_idx - 1 if 'shift' in modifiers else next_idx + 1) % len(master_arr); continue
                break

            # एक्टिव इंडेक्स वेरिएबल को रीयल-टाइम अपडेट लॉक करना
            if self.current_view == 'marks': self.marks_tab_index = next_idx
            elif self.current_view == 'attendance': self.att_tab_index = next_idx
            elif self.current_view == 'height_weight': self.hw_tab_index = next_idx
            elif self.current_view == 'dbt': self.dbt_tab_index = next_idx
            elif self.current_view == 'mdm': self.mdm_tab_index = next_idx
            elif self.current_view == 'registration': self.reg_tab_index = next_idx
            elif self.current_view == 'staff_registration': self.staff_tab_index = next_idx
            elif self.current_view == 'tc_module': self.tc_tab_index = next_idx
            elif self.current_view == 'smc_details': self.smc_popup_focus_index = next_idx
            elif self.current_view == 'cook_details': self.cook_popup_focus_index = next_idx
            elif self.current_view == 'grant_details': self.grant_popup_focus_index = next_idx

            target_w = master_arr[next_idx]
            target_type_str = str(type(target_w))
            
            # 🟢 [स्टूडेंट विज़ुअल कड़क बॉर्डर इफ़ेक्ट]: कर्सर पहुँचते ही विज़ुअल फ़ोकस स्वतः ड्रा होगा
            if hasattr(target_w, 'set_visual_focus'): 
                target_w.set_visual_focus(True)
                
            if isinstance(target_w, Spinner) or 'Spinner' in target_type_str or 'CustomSpinner' in target_type_str:
                # ✨ [पॉपअप ट्रैप बाईपास फिक्स]: स्वतः ड्रॉपडाउन ओपनिंग कमांड को हटा दिया गया ताकि कर्सर कभी न फंसे (Bypass Mode Lock)
                if hasattr(target_w, 'focus'): target_w.focus = True
                target_w.is_open = False 
            elif isinstance(target_w, Button) or 'Button' in target_type_str or 'CustomButton' in target_type_str:
                target_w.state = 'down' # बटन विज़ुअली दबा हुआ हाइलाइट होगा
                if key in (13, 271) and "PHOTO" not in getattr(target_w, 'text', '').upper() and "CAPTURE" not in getattr(target_w, 'text', '').upper():
                    target_w.state = 'normal'
                    target_w.dispatch('on_press')
            else:
                target_w.background_color = (0.9, 1.0, 0.9, 1) # स्टूडेंट थीम चमकीला हरा बैकग्राउंड सक्रिय [image__oZa3T.png]
                target_w.focus = True
            return True
            
        # 📑 3. [UP / DOWN ARROW LOGIC]: अब एरो कीज़ दबाने पर बिना पॉपअप विंडो खोले सीधे मान रीयल-टाइम बदलेंगे!
        elif key in (273, 274, 275, 276): 
            tgt_widget = master_arr[curr_idx]
            tgt_type_str = str(type(tgt_widget))
            if isinstance(tgt_widget, Spinner) or 'Spinner' in tgt_type_str or 'CustomSpinner' in tgt_type_str:
                vals = tgt_widget.values
                s_idx = vals.index(tgt_widget.text) if tgt_widget.text in vals else -1
                shift_val = -1 if key in (273, 276) else 1
                new_s_idx = (s_idx + shift_val) % len(vals)
                tgt_widget.text = vals[new_s_idx] # सीधे मान लाइव बदलेंगे, कोई पॉपअप विंडो बीच में अड़ंगा नहीं डालेगी
                return True
            
            if isinstance(tgt_widget, Button): tgt_widget.state = 'normal'
            shift = -1 if key in (273, 276) else 1
            next_idx = (curr_idx + shift) % len(master_arr)
            
            if self.current_view == 'smc_details': self.smc_popup_focus_index = next_idx
            elif self.current_view == 'cook_details': self.cook_popup_focus_index = next_idx
            elif self.current_view == 'grant_details': self.grant_popup_focus_index = next_idx
            
            target_w = master_arr[next_idx]
            target_type_str = str(type(target_w))
            if hasattr(target_w, 'set_visual_focus'): target_w.set_visual_focus(True)
            if isinstance(target_w, TextInput) or 'TextInput' in target_type_str or 'CustomText' in target_type_str:
                target_w.background_color = (0.9, 1.0, 0.9, 1)
                target_w.focus = True
            return True
        return False

    def on_dob_type(self, instance, value):
        if len(value) == 8:
            words_value = date_to_words_eng(value)
            if words_value and 'DATE OF BIRTH (IN WORDS)' in self.fields: self.fields['DATE OF BIRTH (IN WORDS)'].text = words_value

    def _get_student_photo_filename(self):
        sr_val = self.fields['SR NO'].text.strip().replace('.0', '') if 'SR NO' in self.fields else ''
        nm_val = self.fields['NAME'].text.strip().replace(' ', '_') if 'NAME' in self.fields else ''
        clean_nm = ''.join(c for c in nm_val if c.isalnum() or c == '_')
        if sr_val:
            return f"{sr_val}.jpg"
        elif clean_nm:
            return f"Student_{clean_nm}.jpg"
        return "student_temp.jpg"

    def upload_photo_action(self, instance):
        def on_photo_picked(file_path):
            if file_path and os.path.exists(file_path):
                fname = self._get_student_photo_filename()
                dest_p = os.path.abspath(os.path.join(PHOTO_DIR, fname))
                comp_p = compress_image_under_30kb(file_path, dest_p, max_kb=28)
                self.selected_photo_path = comp_p
                self.photo_path_input.text = fname
                self.student_photo.source = comp_p
                self.student_photo.reload()

        select_file_cross_platform(
            "Select Student Photo",
            [("Image Files", "*.png *.jpg *.jpeg *.bmp")],
            on_photo_picked
        )

    def reset_all(self, instance):
        if hasattr(self, 'fields') and self.fields:
            for k, w in self.fields.items():
                if not isinstance(w, Spinner): w.text = ''
        if hasattr(self, 'photo_path_input'): self.photo_path_input.text = ''
        if hasattr(self, 'student_photo'): self.student_photo.source = get_exe_safe_path("logo.png") if os.path.exists(get_exe_safe_path("logo.png")) else ''
    def load_form(self):
        self.content_area.clear_widgets(); self.current_view = 'registration'
        is_mob = (kivy_platform != 'win')
        with self.content_area.canvas.before: 
            Color(1.0, 0.5, 0.9, 1); self.c_bg = Rectangle(size=self.content_area.size, pos=self.content_area.pos)
        self.content_area.bind(size=lambda ins, val: setattr(self.c_bg, 'size', ins.size), pos=lambda ins, val: setattr(self.c_bg, 'pos', ins.pos))
        
        self.content_area.add_widget(Label(text='STUDENT PROFILE REGISTRATION', font_size=sp(18) if is_mob else 24, bold=True, color=(0,0,0,1), size_hint_y=None, height=dp(36) if is_mob else 45))
        
        form_body = BoxLayout(orientation='vertical' if is_mob else 'horizontal', spacing=dp(8) if is_mob else 15, padding=(5, 5, 5, 5))
        scroll = ScrollView(scroll_y=1, size_hint=(1, 0.72) if is_mob else (0.74, 1))
        grid = GridLayout(cols=1 if is_mob else 2, spacing=(dp(10), dp(10)) if is_mob else (15, 12), size_hint_y=None, padding=5)
        grid.bind(minimum_height=grid.setter('height'))
        
        self.fields_list = ['PEN NO', 'CATEGORY', 'APAAR ID', 'SR NO', 'ADDRESS', 'NAME', 'BANK IFSC CODE', "FATHER'S NAME", 'BANK NAME', "MOTHER'S NAME", 'A/C HOLDER NAME', 'GENDER', 'A/C NUMBER', 'DATE OF BIRTH (DDMMYYYY)', 'A/C HOLDER Aadhaar NUMBER', 'DATE OF BIRTH (IN WORDS)', 'SAME FAMILY', 'CLASS', 'ST Aadhaar NO', 'RELATION OF A/C HOLDER WITH STUDENT', 'FATHER Aadhaar NO', 'PRESENT TIME AVAILABILITY', 'MOTHER Aadhaar NO', 'ADMISSION DATE', "FATHER'S NAME AS PER STUDENT'S Aadhaar", 'CWSN (YES/NO)', 'MOBILE NUMBER']
        self.fields, self.inputs_list, self.reg_master_tabs = {}, [], []
        
        for f in self.fields_list:
            box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44) if is_mob else 40, spacing=5)
            lbl = Label(text=f, size_hint_x=0.44 if is_mob else 0.42, color=(0, 0, 0.4, 1), font_size=sp(12) if is_mob else 12, bold=True, halign='left', valign='middle')
            lbl.bind(size=lbl.setter('text_size'))
            box.add_widget(lbl)
            
            if f == 'CATEGORY':
                spin = CustomSpinner(text='General', values=('General', 'OBC', 'SC', 'ST'), size_hint_x=0.56 if is_mob else 0.58)
                self.fields[f] = spin; box.add_widget(spin); self.reg_master_tabs.append(spin)
            elif f == 'GENDER':
                spin = CustomSpinner(text='Boy', values=('Boy', 'Girl'), size_hint_x=0.56 if is_mob else 0.58)
                self.fields[f] = spin; box.add_widget(spin); self.reg_master_tabs.append(spin)
            elif f == 'CLASS':
                spin = CustomSpinner(text='Class 1', values=('Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5'), size_hint_x=0.56 if is_mob else 0.58)
                self.fields[f] = spin; box.add_widget(spin); self.reg_master_tabs.append(spin)
            elif f == 'RELATION OF A/C HOLDER WITH STUDENT':
                spin = CustomSpinner(text='Father', values=('Father', 'Mother', 'Other'), size_hint_x=0.56 if is_mob else 0.58)
                self.fields[f] = spin; box.add_widget(spin); self.reg_master_tabs.append(spin)
            elif f == 'SAME FAMILY':
                spin = CustomSpinner(text='No', values=('Yes', 'No'), size_hint_x=0.56 if is_mob else 0.58)
                spin.bind(text=self.on_same_family_toggle)
                self.fields[f] = spin; box.add_widget(spin); self.reg_master_tabs.append(spin)
            elif f in ['CWSN (YES/NO)', 'PRESENT TIME AVAILABILITY']:
                spin = CustomSpinner(text='No', values=('Yes', 'No'), size_hint_x=0.56 if is_mob else 0.58)
                self.fields[f] = spin; box.add_widget(spin); self.reg_master_tabs.append(spin)
            else:
                limit, only_dig = None, False
                if f == 'PEN NO': limit = 11; only_dig = True
                elif ('Aadhaar' in f or 'AADHAR' in f) and 'NAME' not in f.upper(): limit = 12; only_dig = True
                elif f == 'APAAR ID': limit = 12; only_dig = True
                elif f == 'SR NO': only_dig = True
                elif f == 'MOBILE NUMBER': limit = 10; only_dig = True
                elif f == 'DATE OF BIRTH (DDMMYYYY)' or f == 'ADMISSION DATE': limit = 10; only_dig = False

                if f in ['DATE OF BIRTH (DDMMYYYY)', 'ADMISSION DATE']:
                    db_box = BoxLayout(orientation='horizontal', size_hint_x=0.56 if is_mob else 0.58, spacing=2)
                    txt = CustomText(max_chars=limit, only_digits=only_dig, multiline=False)
                    if f == 'DATE OF BIRTH (DDMMYYYY)': txt.bind(text=self.on_dob_type)
                    btn_cal = Button(text='📅', size_hint_x=0.25 if is_mob else 0.22)
                    btn_cal.bind(on_press=lambda instance, target=txt: self.open_calendar_popup(target))
                    db_box.add_widget(txt); db_box.add_widget(btn_cal)
                    self.fields[f] = txt; self.inputs_list.append(txt); self.reg_master_tabs.append(txt); box.add_widget(db_box)
                else:
                    txt = CustomText(max_chars=limit, only_digits=only_dig, multiline=False, size_hint_x=0.56 if is_mob else 0.58)
                    if f == 'SR NO':
                        def auto_photo_mapper(instance, value):
                            if hasattr(self, 'photo_path_input') and value.strip():
                                self.photo_path_input.text = f"{value.strip()}.jpg"
                        txt.bind(text=auto_photo_mapper)
                    self.fields[f] = txt; self.inputs_list.append(txt); self.reg_master_tabs.append(txt); box.add_widget(txt)
            grid.add_widget(box)
        scroll.add_widget(grid)

        if is_mob:
            photo_panel = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(145), padding=(dp(8), dp(6)), spacing=dp(12))
            self.student_photo = Image(source=get_exe_safe_path("logo.png") if os.path.exists(get_exe_safe_path("logo.png")) else '', size_hint=(None, None), size=(dp(110), dp(132)), allow_stretch=True, keep_ratio=False)
            photo_panel.add_widget(self.student_photo)
            right_cam_box = BoxLayout(orientation='vertical', spacing=dp(8), padding=(0, dp(4)))
            self.photo_path_input = CustomText(text='', hint_text='Photo filename', multiline=False, size_hint_y=None, height=dp(38))
            right_cam_box.add_widget(self.photo_path_input); self.reg_master_tabs.append(self.photo_path_input)
            b_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(38), spacing=dp(8))
            btn_upload = CustomButton(text='GALLERY', size_hint_x=None, width=dp(95), background_color=(0.2, 0.2, 0.2, 1), bold=True)
            btn_upload.bind(on_press=self.upload_photo_action)
            btn_cam = CustomButton(text='CAMERA', size_hint_x=None, width=dp(95), background_color=(0, 0.4, 0.6, 1), bold=True)
            btn_cam.bind(on_press=self.capture_live_camera_action)
            b_box.add_widget(btn_upload); b_box.add_widget(btn_cam); right_cam_box.add_widget(b_box)
            right_cam_box.add_widget(BoxLayout())
            photo_panel.add_widget(right_cam_box)
            form_body.add_widget(photo_panel); form_body.add_widget(scroll)
        else:
            photo_panel = BoxLayout(orientation='vertical', size_hint_x=0.26, padding=(10, 20, 10, 10), spacing=8)
            photo_panel.add_widget(Label(text='STUDENT PHOTO CONTROLLER', font_size=13, bold=True, color=(0,0,0,1), size_hint_y=None, height=22))
            self.student_photo = Image(source=get_exe_safe_path("logo.png") if os.path.exists(get_exe_safe_path("logo.png")) else '', size_hint=(None, None), size=(160, 180), pos_hint={'center_x': 0.5})
            photo_panel.add_widget(self.student_photo)
            self.photo_path_input = CustomText(text='', hint_text='Photo filename', multiline=False, size_hint_y=None, height=36)
            photo_panel.add_widget(self.photo_path_input); self.reg_master_tabs.append(self.photo_path_input)
            b_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=38, spacing=5)
            btn_upload = CustomButton(text='BROWSE', font_size=10, background_color=(0.2, 0.2, 0.2, 1), bold=True)
            btn_upload.bind(on_press=self.upload_photo_action)
            btn_cam = CustomButton(text='CAMERA', font_size=10, background_color=(0, 0.4, 0.6, 1), bold=True)
            btn_cam.bind(on_press=self.capture_live_camera_action)
            b_box.add_widget(btn_upload); b_box.add_widget(btn_cam); photo_panel.add_widget(b_box)
            photo_panel.add_widget(BoxLayout())
            form_body.add_widget(photo_panel); form_body.add_widget(scroll)

        self.content_area.add_widget(form_body)
        
        # --- 🎛️ निचला बटन पैनल (मोबाइल पर स्क्रॉल करने योग्य पट्टी ताकि कोई भी बटन न कटे) ---
        al = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 48, spacing=8, padding=(0, 5, 0, 0))
        if is_mob:
            al.size_hint_x = None
            al.bind(minimum_width=al.setter('width'))
        
        self.btn_save_reg = CustomButton(text='ADD/SAVE', background_color=(0.6, 0.05, 0.05, 1), bold=True, font_size=11, size_hint_x=None if is_mob else 1, width=dp(115))
        self.btn_save_reg.bind(on_press=self.save_data)
        
        self.btn_reset_reg = CustomButton(text='RESET', background_color=(0.0, 0.5, 0.1, 1), bold=True, font_size=11, size_hint_x=None if is_mob else 1, width=dp(100))
        self.btn_reset_reg.bind(on_press=self.reset_all)
        
        self.btn_close_reg = CustomButton(text='CLOSE', background_color=(0.0, 0.0, 0.6, 1), bold=True, font_size=11, size_hint_x=None if is_mob else 1, width=dp(100))
        self.btn_close_reg.bind(on_press=lambda x: self.show_welcome())
        
        self.btn_search_reg = CustomButton(text='SEARCH', background_color=(0.5, 0.05, 0.5, 1), bold=True, font_size=11, size_hint_x=None if is_mob else 1, width=dp(110))
        self.btn_search_reg.bind(on_press=self.open_search_popup)
       
        self.btn_update_reg = CustomButton(text='UPDATE', background_color=(0.1, 0.4, 0.6, 1), bold=True, font_size=11, size_hint_x=None if is_mob else 1, width=dp(110))
        self.btn_update_reg.bind(on_press=self.save_data) 
        
        self.btn_print_reg = CustomButton(text='PRINT', background_color=(0.05, 0.3, 0.1, 1), bold=True, font_size=11, size_hint_x=None if is_mob else 1, width=dp(100))
        self.btn_print_reg.bind(on_press=self.generate_admission_form_pdf)
        
        # 📥 7. [नया विकल्प 1]: EXCEL FORMAT DOWNLOAD BUTTON
        self.btn_download_fmt = CustomButton(text='📥 DOWNLOAD FORMAT', background_color=(0.45, 0.45, 0.45, 1), bold=True, font_size=10.5, size_hint_x=None if is_mob else 1, width=dp(145))
        self.btn_download_fmt.bind(on_press=self.action_download_student_excel_format)
        
        # 📤 8. [नया विकल्प 2]: EXCEL DATA UPLOAD BUTTON
        self.btn_upload_excel = CustomButton(text='📤 UPLOAD FROM EXCEL', background_color=(0.35, 0.05, 0.55, 1), bold=True, font_size=10.5, size_hint_x=None if is_mob else 1, width=dp(155))
        self.btn_upload_excel.bind(on_press=self.action_upload_student_excel_database)
        
        # क्रमानुसार सभी बटन्स को रो में सजाना
        al.add_widget(self.btn_save_reg)
        al.add_widget(self.btn_reset_reg)
        al.add_widget(self.btn_close_reg)
        al.add_widget(self.btn_search_reg)
        al.add_widget(self.btn_update_reg)
        al.add_widget(self.btn_print_reg)
        al.add_widget(self.btn_download_fmt)
        al.add_widget(self.btn_upload_excel)
        
        if is_mob:
            btn_scroll = ScrollView(size_hint=(1, None), height=dp(52), do_scroll_x=True, do_scroll_y=False)
            btn_scroll.add_widget(al)
            self.content_area.add_widget(btn_scroll)
        else:
            self.content_area.add_widget(al)
        
        # कीबोर्ड टैब श्रृंखला में दोनों बटन्स को आखिरी कतार में हुक किया गया
        self.reg_master_tabs = self.reg_master_tabs + [self.btn_save_reg, self.btn_reset_reg, self.btn_close_reg, self.btn_search_reg, self.btn_update_reg, self.btn_print_reg, self.btn_download_fmt, self.btn_upload_excel]
        self.reg_tab_index = 0

    # 📥 [बैकएंड इंजन 1]: प्रवेश कक्षा सहित २७ कॉलम्स वाली ब्लैंक टेम्पलेट शीट (Windows + Android क्रॉस-प्लेटफ़ॉर्म)
    def action_download_student_excel_format(self, instance):
        import os, openpyxl
        TEMPLATE_FILE = 'Student_Upload_Template.xlsx'
        ordered_columns = [
            'SR NO', 'PEN NO', 'APAAR ID', 'NAME', "FATHER'S NAME", "MOTHER'S NAME",
            'DATE OF BIRTH (DDMMYYYY)', 'GENDER', 'CLASS AT ADMISSION', 'ST Aadhaar NO', 
            'FATHER Aadhaar NO', 'MOTHER Aadhaar NO', "FATHER'S NAME AS PER STUDENT'S Aadhaar",
            'MOBILE NUMBER', 'CATEGORY', 'BANK NAME', 'BANK IFSC CODE', 'A/C NUMBER', 
            'A/C HOLDER NAME', 'A/C HOLDER Aadhaar NUMBER', 'RELATION OF A/C HOLDER WITH STUDENT',
            'ADMISSION DATE', 'CWSN (YES/NO)', 'SAME FAMILY', 'PRESENT TIME AVAILABILITY', 
            'ADDRESS', 'DATE OF BIRTH (IN WORDS)'
        ]
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(ordered_columns)
            wb.save(TEMPLATE_FILE)
            self.popup('Template Downloaded', f"✅ Template Generated successfully!\n\nFile Name: '{TEMPLATE_FILE}' saved in app data folder.")
            open_file_cross_platform(TEMPLATE_FILE)
        except Exception as e:
            self.popup('Export Failed', f"File Export Error:\n{str(e)}")

    def action_upload_student_excel_database(self, instance):
        import os, re

        def process_student_excel(file_path):
            if not file_path:
                return
            try:
                df_up = pd.read_excel(file_path, dtype=str)
                df_up.columns = [str(c).strip() for c in df_up.columns]
                
                if 'SR NO' not in df_up.columns or 'NAME' not in df_up.columns:
                    self.popup('Validation Error', "Invalid Excel Format! 'SR NO' and 'NAME' columns are required.")
                    return
                    
                df_up = df_up.dropna(subset=['SR NO'])
                df_up['SR NO'] = df_up['SR NO'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
                df_up = df_up[df_up['SR NO'] != 'nan']
                
                if df_up.empty:
                    self.popup('Empty Sheet', 'No valid records found in the selected Excel sheet.'); return
                    
                MAX_CLASS_LIMIT = 5
                CURRENT_SESSION_YEAR = 2026
                
                for c in df_up.columns:
                    df_up[c] = df_up[c].astype(str).str.strip().str.replace('nan', '', case=False)
                    
                promoted_rows = []
                all_session_cols = set()
                
                for _, row in df_up.iterrows():
                    r_dict = dict(row)
                    
                    clean_adm_date = format_date_dd_mm_yyyy(r_dict.get('ADMISSION DATE', ''))
                    clean_dob_date = format_date_dd_mm_yyyy(r_dict.get('DATE OF BIRTH (DDMMYYYY)', ''))
                    
                    r_dict['ADMISSION DATE'] = clean_adm_date
                    r_dict['DATE OF BIRTH (DDMMYYYY)'] = clean_dob_date
                    
                    if clean_dob_date and not str(r_dict.get('DATE OF BIRTH (IN WORDS)', '')).strip():
                        r_dict['DATE OF BIRTH (IN WORDS)'] = date_to_words_eng(clean_dob_date)
                    
                    raw_adm_cls = r_dict.get('CLASS AT ADMISSION', '') or r_dict.get('CLASS', 'Class 1')
                    m_cls = re.search(r'(\d+)', str(raw_adm_cls))
                    clean_adm_cls = f"Class {m_cls.group(1)}" if m_cls else "Class 1"
                    r_dict['CLASS AT ADMISSION'] = clean_adm_cls
                    
                    curr_cls, sess_history = calculate_promoted_class_history(
                        clean_adm_date, clean_adm_cls, max_school_class=MAX_CLASS_LIMIT, target_session_start=CURRENT_SESSION_YEAR
                    )
                    
                    curr_status = str(r_dict.get('STUDENT STATUS', '')).strip()
                    if 'Left School with TC' not in curr_status:
                        r_dict['CLASS'] = curr_cls
                        r_dict['STUDENT STATUS'] = 'Active' if 'Passed Out' not in curr_cls else 'Passed Out'
                    
                    for s_col, s_val in sess_history.items():
                        r_dict[s_col] = s_val
                        all_session_cols.add(s_col)
                        
                    promoted_rows.append(r_dict)
                    
                df_processed = pd.DataFrame(promoted_rows)
                
                base_columns = [
                    'SR NO', 'PEN NO', 'APAAR ID', 'NAME', "FATHER'S NAME", "MOTHER'S NAME",
                    'DATE OF BIRTH (DDMMYYYY)', 'GENDER', 'CLASS AT ADMISSION', 'CLASS', 'STUDENT STATUS',
                    'TC NUMBER', 'TERMINATION DATE', 'TC REASON',
                    'ST Aadhaar NO', 'FATHER Aadhaar NO', 'MOTHER Aadhaar NO', "FATHER'S NAME AS PER STUDENT'S Aadhaar",
                    'MOBILE NUMBER', 'CATEGORY', 'BANK NAME', 'BANK IFSC CODE', 'A/C NUMBER', 
                    'A/C HOLDER NAME', 'A/C HOLDER Aadhaar NUMBER', 'RELATION OF A/C HOLDER WITH STUDENT',
                    'ADMISSION DATE', 'CWSN (YES/NO)', 'SAME FAMILY', 'PRESENT TIME AVAILABILITY', 
                    'ADDRESS', 'DATE OF BIRTH (IN WORDS)'
                ]
                sorted_session_cols = sorted(list(all_session_cols))
                final_columns = base_columns + sorted_session_cols
                
                if not os.path.exists(EXCEL_FILE):
                    for col in final_columns:
                        if col not in df_processed.columns: df_processed[col] = ""
                    df_processed[final_columns].to_excel(EXCEL_FILE, index=False)
                else:
                    df_old = pd.read_excel(EXCEL_FILE, dtype=str)
                    for c in df_old.columns:
                        df_old[c] = df_old[c].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.replace('nan', '', case=False)
                    
                    df_old = df_old.drop(df_old[df_old['SR NO'].isin(df_processed['SR NO'])].index)
                    df_merged = pd.concat([df_old, df_processed], ignore_index=True)
                    
                    extra_old_sessions = [c for c in df_old.columns if c.startswith('SESSION_') and c not in final_columns]
                    all_ordered = base_columns + sorted(list(set(sorted_session_cols + extra_old_sessions)))
                    
                    for col in all_ordered:
                        if col not in df_merged.columns: df_merged[col] = ""
                    df_merged[all_ordered].to_excel(EXCEL_FILE, index=False)
                    
                self.popup('Auto-Promotion Success', f"🎉 {len(df_processed)} Students Uploaded & Promoted!\n\nSabhi bachhon ko Current Session (2026-27) ki sahi class me promote kar diya gaya hai.")
            except Exception as ex:
                self.popup('Upload Interrupted', f"Excel import crashed: {str(ex)}")

        select_file_cross_platform(
            "Select Student Excel File",
            [("Excel Files", "*.xlsx *.xls")],
            process_student_excel
        )

    def on_same_family_toggle(self, spinner, text):
        if text == 'Yes':
            is_mob = (kivy_platform != 'win')
            pl = BoxLayout(orientation='vertical', padding=dp(15) if is_mob else 15, spacing=dp(10) if is_mob else 10)
            pl.add_widget(Label(text="Enter Sibling's SR No / Admission No:", color=(1,1,1,1), bold=True, font_size=sp(14) if is_mob else 14))
            sib_in = CustomText(multiline=False, only_digits=True, size_hint_y=None, height=dp(44) if is_mob else 38)
            pl.add_widget(sib_in)
            btn_box = BoxLayout(spacing=dp(10) if is_mob else 10, size_hint_y=None, height=dp(44) if is_mob else 40)
            btn_link = Button(text='LINK FAMILY', background_color=(0,0.6,0.1,1), bold=True, font_size=sp(13) if is_mob else 14)
            btn_cancel = Button(text='CANCEL', background_color=(0.7,0.1,0.1,1), bold=True, font_size=sp(13) if is_mob else 14)
            btn_box.add_widget(btn_link); btn_box.add_widget(btn_cancel); pl.add_widget(btn_box)
            pop = Popup(title="Sibling Auto-Fill System", content=pl, size_hint=(0.92, 0.42) if is_mob else (0.6, 0.35))
            btn_cancel.bind(on_press=pop.dismiss)
            
            def link_sibling_action(instance):
                s_id = sib_in.text.strip()
                if s_id and os.path.exists(EXCEL_FILE):
                    try:
                        df = pd.read_excel(EXCEL_FILE, dtype=str)
                        if 'SR NO' in df.columns:
                            matched_row = None
                            for _, r_item in df.iterrows():
                                sr_clean = str(r_item.get('SR NO', '')).strip().replace('.0', '')
                                if sr_clean == str(s_id):
                                    matched_row = r_item
                                    break
                            if matched_row is not None:
                                shared_fields = ['ADDRESS', "FATHER'S NAME", 'BANK NAME', "MOTHER'S NAME", 'A/C HOLDER NAME', 'A/C NUMBER', 'BANK IFSC CODE', 'A/C HOLDER Aadhaar NUMBER', 'FATHER Aadhaar NO', 'MOTHER Aadhaar NO', 'MOBILE NUMBER', "FATHER'S NAME AS PER STUDENT'S Aadhaar", 'RELATION OF A/C HOLDER WITH STUDENT']
                                for f in shared_fields:
                                    if f in df.columns and f in self.fields:
                                        raw_val = str(matched_row.get(f, '')).strip()
                                        if raw_val.endswith('.0'):
                                            raw_val = raw_val[:-2]
                                        if raw_val.lower() == 'nan':
                                            raw_val = ""
                                        self.fields[f].text = raw_val
                                pop.dismiss()
                                self.popup('Success', f'Family linked! Records successfully copied from Sibling SR No: {s_id}')
                            else:
                                self.popup('Error', f'Sibling SR No: {s_id} not found in database!')
                        else:
                            self.popup('Data Error', 'Column "SR NO" missing from Excel database!')
                    except Exception as e:
                        self.popup('Error', str(e))
            btn_link.bind(on_press=link_sibling_action); pop.open()

    def capture_live_camera_action(self, instance):
        fname = self._get_student_photo_filename()
        dest_path = os.path.abspath(os.path.join(PHOTO_DIR, fname))

        if kivy_platform == 'win':
            try:
                import cv2
                cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                ret, frame = cap.read()
                if ret:
                    cv2.imwrite(dest_path, frame)
                    comp_p = compress_image_under_30kb(dest_path, dest_path, max_kb=28)
                    self.selected_photo_path = comp_p
                    self.photo_path_input.text = fname
                    self.student_photo.source = comp_p
                    self.student_photo.reload()
                    self.popup('Camera System', f'Photo saved as {fname}!')
                else:
                    self.popup('Camera Error', 'Could not access the live webcam feed!')
                cap.release()
            except Exception as e:
                self.popup('Error', str(e))
        else:
            def on_cam_ok(fp):
                self.selected_photo_path = fp
                self.photo_path_input.text = os.path.basename(fp)
                self.student_photo.source = fp
                self.student_photo.reload()
                self.popup('Camera System', f'Photo saved as {os.path.basename(fp)}!')

            capture_mobile_camera_safe(dest_path, on_cam_ok, self.popup)
   
    def open_calendar_popup(self, target_input):
        is_mob = (kivy_platform != 'win')
        pl = BoxLayout(orientation='vertical', padding=dp(10) if is_mob else 10, spacing=dp(8) if is_mob else 10)
        selectors = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44) if is_mob else 40, spacing=dp(6) if is_mob else 5)
        month_spin = Spinner(text='January', values=('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'), font_size=sp(14) if is_mob else 14)
        year_spin = Spinner(text='2026', values=[str(x) for x in range(2010, 2036)], font_size=sp(14) if is_mob else 14)
        selectors.add_widget(month_spin); selectors.add_widget(year_spin); pl.add_widget(selectors)
        
        days_grid = GridLayout(cols=7, size_hint_y=None, height=dp(30) if is_mob else 30, spacing=2)
        for dh in ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']:
            days_grid.add_widget(Label(text=dh, bold=True, color=(1,1,0,1), font_size=sp(13) if is_mob else 13))
        pl.add_widget(days_grid)
        
        grid = GridLayout(cols=7, spacing=dp(5) if is_mob else 5)
        pop = Popup(title='Select Date Hub', content=pl, size_hint=(0.94, 0.72) if is_mob else (0.6, 0.65))
        months_dict = {'January':'01','February':'02','March':'03','April':'04','May':'05','June':'06','July':'07','August':'08','September':'09','October':'10','November':'11','December':'12'}
        
        for d in range(1, 32):
            btn_d = Button(text=str(d), background_color=(0.05, 0.45, 0.2, 1), font_size=sp(14) if is_mob else 14, bold=True)
            def select_date_click(ins, day_num=d):
                m_code = months_dict[month_spin.text]
                target_input.text = f"{day_num:02d}-{m_code}-{year_spin.text}"
                pop.dismiss()
            btn_d.bind(on_press=select_date_click); grid.add_widget(btn_d)
            
        pl.add_widget(grid)
        btn_close = Button(text='CLOSE', size_hint_y=None, height=dp(44) if is_mob else 40, background_color=(0.7,0,0,1), bold=True, font_size=sp(14) if is_mob else 14)
        btn_close.bind(on_press=pop.dismiss); pl.add_widget(btn_close); pop.open()

    def open_search_popup(self, instance):
        from kivy.core.window import Window
        from kivy.clock import Clock
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.textinput import TextInput
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from kivy.uix.popup import Popup

        is_mob = (kivy_platform != 'win')

        # 1. मुख्य इनर लेआउट
        pl = BoxLayout(orientation='vertical', padding=(dp(15), dp(12)) if is_mob else (22, 12, 22, 12), spacing=dp(12) if is_mob else 12)
        
        # मुख्य हेडिंग
        heading_label = Label(
            text='Enter Student Name or SR NO to Search:', 
            color=(1, 1, 1, 1), 
            bold=True, 
            font_size=sp(14) if is_mob else 13,
            size_hint_y=None,
            height=dp(28) if is_mob else 22
        )
        pl.add_widget(heading_label)
        
        # इनपुट बॉक्स
        search_input = TextInput(
            multiline=False, 
            size_hint_y=None, 
            height=dp(44) if is_mob else 34, 
            halign='center', 
            font_size=sp(15) if is_mob else 14,
            background_color=(0.95, 0.95, 0.95, 1),
            padding=[dp(8), dp(8)] if is_mob else (6, 6, 6, 6)
        )
        pl.add_widget(search_input)

                # बटन्स कतार
        btn_box = BoxLayout(spacing=dp(15) if is_mob else 15, size_hint_y=None, height=dp(44) if is_mob else 34)
        btn_find = Button(text='FIND', background_color=(0, 0.5, 0.1, 1), bold=True, font_size=sp(14) if is_mob else 14)
        btn_cancel = Button(text='CANCEL', background_color=(0.6, 0.1, 0.1, 1), bold=True, font_size=sp(14) if is_mob else 14)
        btn_box.add_widget(btn_find); btn_box.add_widget(btn_cancel); pl.add_widget(btn_box)
        
        if is_mob:
            pop = Popup(
                title='Search Student Database Panel', 
                content=pl, 
                size_hint=(0.94, 0.42),
                auto_dismiss=False,
                background='', 
                background_color=(0.14, 0.14, 0.14, 0.98)
            )
        else:
            pop = Popup(
                title='Search Student Database Panel', 
                content=pl, 
                size_hint=(None, None), 
                size=(500, 200),
                auto_dismiss=False,
                background='', 
                background_color=(0.14, 0.14, 0.14, 0.98)
            )
        
        def close_popup_and_clean_hook(ins):
            try: Window.unbind(on_key_down=keyboard_hook)
            except: pass
            pop.dismiss()
            
        btn_cancel.bind(on_press=close_popup_and_clean_hook)
        
        # 🔄 कोर सर्च और ऑटो-कीबोर्ड अलर्ट इंजन (Windows + Android दोनों के लिए सुरक्षित)
        def find_action(ins):
            query = search_input.text.strip().lower()
            if not query: 
                self.popup('Alert', 'Please enter a search query!'); return
                
            if not os.path.exists(EXCEL_FILE): 
                self.popup('File Error', f'Excel database file ({EXCEL_FILE}) not found!'); return
            
            try:
                df = pd.read_excel(EXCEL_FILE, dtype=str)
                matched_row = None
                matched_idx = None

                for r_idx, r_item in df.iterrows():
                    r_name = str(r_item.get('NAME', '')).strip().lower()
                    r_sr = str(r_item.get('SR NO', '')).strip().replace('.0', '').lower()
                    if r_name == query or r_sr == query.replace('.0', ''):
                        matched_row = r_item
                        matched_idx = r_idx
                        break
                    
                if matched_row is not None:
                    self.current_loaded_index = [matched_idx]
                    row = matched_row  
                    
                    for f in self.fields_list:
                        if f in df.columns and f in self.fields: 
                            val = row.get(f, '')
                            if pd.notna(val) and str(val).lower() != 'nan':
                                clean_v = str(val).replace('.0', '').strip()
                                if 'DATE' in f.upper() and 'WORDS' not in f.upper():
                                    clean_v = format_date_dd_mm_yyyy(clean_v)
                                self.fields[f].text = clean_v
                            else:
                                self.fields[f].text = ""
                                
                    dob_loaded = self.fields['DATE OF BIRTH (DDMMYYYY)'].text.strip()
                    if dob_loaded and not self.fields['DATE OF BIRTH (IN WORDS)'].text.strip():
                        self.fields['DATE OF BIRTH (IN WORDS)'].text = date_to_words_eng(dob_loaded)

                    sr_no_loaded = str(row.get('SR NO', '')).strip().replace('.0', '')
                    photo_found = False
                    for folder in [PHOTO_DIR, os.getcwd()]:
                        for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                            photo_path = os.path.join(folder, f"{sr_no_loaded}{ext}")
                            if os.path.exists(photo_path):
                                self.student_photo.source = photo_path
                                self.student_photo.reload()
                                self.photo_path_input.text = f"{sr_no_loaded}{ext}"
                                photo_found = True; break
                        if photo_found: break
                    
                    if not photo_found:
                        self.student_photo.source = get_exe_safe_path("logo.png") if os.path.exists(get_exe_safe_path("logo.png")) else ''
                        self.student_photo.reload()
                        self.photo_path_input.text = ''

                    close_popup_and_clean_hook(None)
                    
                    alert_pl = BoxLayout(orientation='vertical', padding=dp(15) if is_mob else 15, spacing=dp(10) if is_mob else 10)
                    lbl_ok = Label(text=f'Record for SR NO {sr_no_loaded} loaded successfully!', bold=True, color=(1,1,1,1), font_size=sp(14) if is_mob else 14, halign='center')
                    lbl_ok.bind(size=lbl_ok.setter('text_size'))
                    alert_pl.add_widget(lbl_ok)
                    btn_ok = Button(text='OK', background_color=(0, 0.6, 0.1, 1), bold=True, size_hint_y=None, height=dp(42) if is_mob else 36, font_size=sp(14) if is_mob else 14)
                    alert_pl.add_widget(btn_ok)
                    
                    if is_mob:
                        alert_pop = Popup(title='System Notification', content=alert_pl, size_hint=(0.90, 0.32), auto_dismiss=False, background='', background_color=(0.15, 0.15, 0.15, 0.98))
                    else:
                        alert_pop = Popup(title='System Notification', content=alert_pl, size_hint=(None, None), size=(450, 150), auto_dismiss=False, background='', background_color=(0.15, 0.15, 0.15, 0.98))
                    
                    def dismiss_alert(x):
                        try: Window.unbind(on_key_down=alert_keyboard_hook)
                        except: pass
                        alert_pop.dismiss()
                    btn_ok.bind(on_press=dismiss_alert)

                    def alert_keyboard_hook(window, key, scancode, codepoint, modifiers):
                        if key == 13 or key == 271: # Enter / Numpad Enter
                            dismiss_alert(None); return True
                        return False
                        
                    Window.bind(on_key_down=alert_keyboard_hook)
                    alert_pop.open()
                    
                else:
                    self.popup('Not Found', f'Error: No student found matching "{search_input.text.strip()}"')
                    
            except Exception as e:
                self.popup('Database Error', f'Error reading excel: {str(e)}')

        btn_find.bind(on_press=find_action)

        # ⌨️ [मास्टर कीबोर्ड ट्रैकर]: विज़ुअल Color रिस्पॉन्स इंजन
        self.popup_focus_index = 0  # 0 = Input, 1 = FIND, 2 = CANCEL
        
        def update_button_colors():
            if self.popup_focus_index == 0:
                search_input.focus = True
                btn_find.background_color = (0, 0.5, 0.1, 1)    # सामान्य हरा
                btn_cancel.background_color = (0.6, 0.1, 0.1, 1) # सामान्य लाल
            elif self.popup_focus_index == 1:
                search_input.focus = False
                btn_find.background_color = (0, 0.9, 0.2, 1)    # चमकीला हरा
                btn_cancel.background_color = (0.6, 0.1, 0.1, 1)
            elif self.popup_focus_index == 2:
                search_input.focus = False
                btn_find.background_color = (0, 0.5, 0.1, 1)
                btn_cancel.background_color = (1, 0, 0, 1)      # चमकीला लाल

        def keyboard_hook(window, key, scancode, codepoint, modifiers):
            if key == 13 or key == 271: # Enter / Numpad Enter
                if self.popup_focus_index == 0 or self.popup_focus_index == 1:
                    find_action(None); return True
                elif self.popup_focus_index == 2:
                    close_popup_and_clean_hook(None); return True
            elif key == 9: # Tab की
                self.popup_focus_index = (self.popup_focus_index + 1) % 3
                update_button_colors(); return True
            return False

        Window.bind(on_key_down=keyboard_hook)
        Clock.schedule_once(lambda dt: [setattr(search_input, 'focus', True), update_button_colors()], 0.05)
        
        pop.open()

    def save_data(self, instance):
        import shutil
        import os, re
        pass
        
        sr_no_val = self.fields['SR NO'].text.strip()
        pen_val = self.fields['PEN NO'].text.strip()
        apaar_val = self.fields['APAAR ID'].text.strip()
        st_aadhaar_val = self.fields['ST Aadhaar NO'].text.strip()
        name_val = self.fields['NAME'].text.strip()
        mobile_val = self.fields['MOBILE NUMBER'].text.strip()

        # --- 1. वैलिडेशन चेक ---
        if not sr_no_val:
            self.popup('Validation Error', 'Error: SR NO cannot be blank!'); return
        if pen_val and len(pen_val) != 11:
            self.popup('Validation Error', 'Error: PEN NO must be 11 digits!'); return
        if apaar_val and len(apaar_val) != 12:
            self.popup('Validation Error', 'Error: APAAR ID must be 12 digits!'); return
        if st_aadhaar_val and len(st_aadhaar_val) != 12:
            self.popup('Validation Error', 'Error: ST Aadhaar NO must be 12 digits!'); return
        if not name_val:
            self.popup('Validation Error', 'Error: Student NAME cannot be blank!'); return
        if len(mobile_val) != 10: 
            self.popup('Validation Error', 'Error: MOBILE NUMBER must be 10 digits!'); return
            
        # वर्तमान स्क्रीन की सभी फ़ील्ड्स का साफ़ डेटा निकालना
        current_data = {k: str(v.text.strip()) for k, v in self.fields.items()}
        
        # 👑 [सिंगल फॉर्म डेट क्लीनर, ऑटो-प्रमोशन एवं सेशन हिस्ट्री लॉजिक - UPDATE SAFE]
        MAX_CLASS_LIMIT = 5  # उच्च प्राथमिक (Upper Primary) के लिए इसे 8 कर दें
        CURRENT_SESSION_YEAR = 2026 # वर्तमान सत्र 2026-2027
        
        # 1. दोनों तारीखों को हमेशा शुद्ध DD-MM-YYYY फॉर्मेट में लॉक करना
        clean_adm_date = format_date_dd_mm_yyyy(current_data.get('ADMISSION DATE', ''))
        clean_dob_date = format_date_dd_mm_yyyy(current_data.get('DATE OF BIRTH (DDMMYYYY)', ''))
        
        current_data['ADMISSION DATE'] = clean_adm_date
        current_data['DATE OF BIRTH (DDMMYYYY)'] = clean_dob_date
        
        if clean_dob_date and not current_data.get('DATE OF BIRTH (IN WORDS)', '').strip():
            current_data['DATE OF BIRTH (IN WORDS)'] = date_to_words_eng(clean_dob_date)
        
        # 2. यदि यह छात्र पहले से डेटाबेस में है (UPDATE मोड), तो उसकी असली 'CLASS AT ADMISSION' उठाना
        saved_adm_cls = ""
        if os.path.exists(EXCEL_FILE):
            try:
                chk_df = pd.read_excel(EXCEL_FILE, dtype=str)
                if 'SR NO' in chk_df.columns and 'CLASS AT ADMISSION' in chk_df.columns:
                    target_sr_clean = sr_no_val.replace('.0', '').strip()
                    for _, r_chk in chk_df.iterrows():
                        if str(r_chk.get('SR NO', '')).strip().replace('.0', '') == target_sr_clean:
                            val_adm = str(r_chk.get('CLASS AT ADMISSION', '')).strip()
                            if val_adm and val_adm.lower() != 'nan':
                                saved_adm_cls = val_adm
            except Exception:
                pass
  
        # यदि डेटाबेस में पहले से प्रवेश कक्षा सुरक्षित है तो वही लें, वरना स्क्रीन से लें
        raw_adm_cls = saved_adm_cls if saved_adm_cls else current_data.get('CLASS', 'Class 1')
        m_cls = re.search(r'(\d+)', str(raw_adm_cls))
        clean_adm_cls = f"Class {m_cls.group(1)}" if m_cls else "Class 1"
        current_data['CLASS AT ADMISSION'] = clean_adm_cls
        
        # 3. असली प्रवेश कक्षा और प्रवेश तिथि के आधार पर सही वर्तमान कक्षा निकालना
        curr_cls, sess_history = calculate_promoted_class_history(
            clean_adm_date, clean_adm_cls, max_school_class=MAX_CLASS_LIMIT, target_session_start=CURRENT_SESSION_YEAR
        )

        current_data['CLASS'] = curr_cls
        current_data['STUDENT STATUS'] = 'Active' if 'Passed Out' not in curr_cls else 'Passed Out'
        for s_col, s_val in sess_history.items():
            current_data[s_col] = s_val
            
        base_columns = [
            'SR NO', 'PEN NO', 'APAAR ID', 'NAME', "FATHER'S NAME", "MOTHER'S NAME",
            'DATE OF BIRTH (DDMMYYYY)', 'GENDER', 'CLASS AT ADMISSION', 'CLASS', 'STUDENT STATUS',
            'TC NUMBER', 'TERMINATION DATE', 'TC REASON',
            'ST Aadhaar NO', 'FATHER Aadhaar NO', 'MOTHER Aadhaar NO', "FATHER'S NAME AS PER STUDENT'S Aadhaar",
            'MOBILE NUMBER', 'CATEGORY', 'BANK NAME', 'BANK IFSC CODE', 'A/C NUMBER', 
            'A/C HOLDER NAME', 'A/C HOLDER Aadhaar NUMBER', 'RELATION OF A/C HOLDER WITH STUDENT',
            'ADMISSION DATE', 'CWSN (YES/NO)', 'SAME FAMILY', 'PRESENT TIME AVAILABILITY', 
            'ADDRESS', 'DATE OF BIRTH (IN WORDS)'
        ]
        
        try:
            # --- 📸 फोटो मैनेजर ---
            if hasattr(self, 'selected_photo_path') and self.selected_photo_path and os.path.exists(self.selected_photo_path):
                _, ext = os.path.splitext(self.selected_photo_path)
                shutil.copy(self.selected_photo_path, os.path.join(PHOTO_DIR, f"{sr_no_val}{ext}"))
                self.selected_photo_path = None

            # --- 🧹 2. डेटाबेस क्लीनर, सेशन मर्जर और री-ऑर्डर इंजन ---
            records_list = []
            all_session_cols = set(sess_history.keys())
            
            if os.path.exists(EXCEL_FILE):
                old_df = pd.read_excel(EXCEL_FILE, dtype=str)
                for c in old_df.columns:
                    if str(c).startswith('SESSION_'):
                        all_session_cols.add(str(c).strip())
                        
                for _, row in old_df.iterrows():
                    row_dict = {}
                    raw_sr = ""
                    for c in old_df.columns:
                        if str(c).strip().upper() == 'SR NO':
                            raw_sr = str(row[c]).strip().replace('.0', '')
                            break
                    
                    if not raw_sr or raw_sr == 'nan' or raw_sr == '' or len(raw_sr) > 8:
                        continue
                        
                    for expected_col in base_columns:
                        val = ""
                        for old_col in old_df.columns:
                            clean_ec = expected_col.lower().replace("'", "").replace("’", "").strip()
                            clean_oc = str(old_col).lower().replace("'", "").replace("’", "").strip()
                            if clean_ec == clean_oc:
                                val = str(row[old_col]).strip().replace('.0', '')
                                if val.lower() == 'nan': val = ""
                                break
                        row_dict[expected_col] = val
                        
                    # पुराने सेशन कॉलम्स का डेटा सुरक्षित रखना
                    for s_c in all_session_cols:
                        if s_c in old_df.columns:
                            s_v = str(row[s_c]).strip()
                            row_dict[s_c] = "" if s_v.lower() == 'nan' else s_v
                        else:
                            row_dict[s_c] = ""
                            
                    if row_dict.get('SR NO'):
                        records_list.append(row_dict)
            
            # --- 🔄 3. डुप्लीकेट डिलीटर और लाइव अपडेट मार्चिंग ---
            new_records = []
            sr_updated = False
            clean_target_sr = str(sr_no_val).replace('.0', '').strip().lower()
            
            for rec in records_list:
                if str(rec['SR NO']).lower() == clean_target_sr:
                    # यदि पहले से TC विवरण दर्ज है और नया स्टेटस Active है, तो TC कॉलम साफ़ रखना या पुराने सुरक्षित रखना
                    for tc_col in ['TC NUMBER', 'TERMINATION DATE', 'TC REASON']:
                        if tc_col not in current_data:
                            current_data[tc_col] = ""
                    new_records.append(current_data)
                    sr_updated = True
                else:
                    new_records.append(rec)
            
            if not sr_updated:
                for tc_col in ['TC NUMBER', 'TERMINATION DATE', 'TC REASON']:
                    if tc_col not in current_data:
                        current_data[tc_col] = ""
                new_records.append(current_data)
                
            final_df = pd.DataFrame(new_records)
            
            if not final_df.empty and 'SR NO' in final_df.columns:
                final_df['SR_CLEAN_KEY'] = final_df['SR NO'].astype(str).str.strip().str.lower()
                final_df.drop_duplicates(subset=['SR_CLEAN_KEY'], keep='last', inplace=True)
                final_df.drop(columns=['SR_CLEAN_KEY'], inplace=True)
            
            ordered_columns = base_columns + sorted(list(all_session_cols))
            for col in ordered_columns:
                if col not in final_df.columns:
                    final_df[col] = ""
            
            final_ordered_df = final_df[ordered_columns].copy()
            final_ordered_df = final_ordered_df.astype(str).replace('nan', '')
            final_ordered_df.to_excel(EXCEL_FILE, index=False)
            
            if hasattr(self, 'current_loaded_index'):
                self.current_loaded_index = None
                
            self.popup('System Message', f"SR NO: {sr_no_val} Saved!\nAdmission Class: {clean_adm_cls} ➔ Current Session Class: {curr_cls}")
            self.reset_all(None)
            
        except Exception as e: 
            self.popup('Error', f"Saving System Failed: {str(e)}")

    def load_dbt_view(self):
        self.content_area.clear_widgets(); self.current_view = 'dbt'; self.dbt_fields = {}; self.dbt_inputs = []
        is_mob = (kivy_platform != 'win')
        with self.content_area.canvas.before:
            Color(0.93, 0.95, 0.94, 1); self.c_bg = Rectangle(size=self.content_area.size, pos=self.content_area.pos)
        self.content_area.bind(size=lambda ins, val: setattr(self.c_bg, 'size', ins.size), pos=lambda ins, val: setattr(self.c_bg, 'pos', ins.pos))
        
        lbl_hdr = Label(text='STUDENT D.B.T. MASTER PORTAL', font_size=sp(17) if is_mob else 19, bold=True, color=(0,0.35,0.25,1), size_hint_y=None, height=dp(36) if is_mob else 38, halign='center', valign='middle')
        lbl_hdr.bind(size=lbl_hdr.setter('text_size'))
        self.content_area.add_widget(lbl_hdr)
        
        # 🎛️ टॉप कंट्रोल पैनल (मोबाइल पर 2 कॉलम ताकि कोई बटन या स्पिनर न कटे)
        top_bar = GridLayout(cols=2 if is_mob else 7, size_hint_y=None, height=dp(190) if is_mob else 50, spacing=dp(8) if is_mob else 10, padding=5)
        top_bar.add_widget(Label(text='Select Class:', color=(0,0,0,1), bold=True, font_size=sp(13) if is_mob else 13))
        self.dbt_class_spinner = CustomSpinner(text='Class 1', values=('Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5'), size_hint_y=None, height=dp(42) if is_mob else 36)
        self.dbt_class_spinner.bind(text=lambda sp, tx: self.refresh_dbt_grid()); top_bar.add_widget(self.dbt_class_spinner)
        
        top_bar.add_widget(Label(text='Select Year:', color=(0,0,0,1), bold=True, font_size=sp(13) if is_mob else 13))
        self.dbt_year_spinner = CustomSpinner(text='2026', values=('2026', '2027', '2028', '2029', '2030'), size_hint_y=None, height=dp(42) if is_mob else 36)
        self.dbt_year_spinner.bind(text=lambda sp, tx: self.refresh_dbt_grid()); top_bar.add_widget(self.dbt_year_spinner)
        
        btn_upload_dbt_excel = Button(text='📂 UPLOAD EXCEL', background_color=(0.1, 0.4, 0.8, 1), bold=True, font_size=sp(12) if is_mob else 11, size_hint_y=None, height=dp(42) if is_mob else 36)
        btn_upload_dbt_excel.bind(on_press=self.upload_department_dbt_excel)
        top_bar.add_widget(btn_upload_dbt_excel)
        
        btn_print_school_dbt = Button(text='🖨️ PRINT REPORT', background_color=(0.85, 0.45, 0.0, 1), bold=True, font_size=sp(12) if is_mob else 11, size_hint_y=None, height=dp(42) if is_mob else 36)
        btn_prerna_sync = Button(text='PRERNA OTP SYNC', background_color=(0.05, 0.55, 0.25, 1), bold=True, font_size=sp(12) if is_mob else 11, size_hint_y=None, height=dp(42) if is_mob else 36)
        btn_prerna_sync.bind(on_press=self.open_prerna_portal_dbt_sync)
        top_bar.add_widget(btn_prerna_sync)

        btn_print_school_dbt.bind(on_press=lambda x: self.generate_school_consolidated_dbt_pdf())
        top_bar.add_widget(btn_print_school_dbt)
        
        self.content_area.add_widget(top_bar)
        
        self.dbt_grid_box = BoxLayout(orientation='vertical', padding=5); self.content_area.add_widget(self.dbt_grid_box)
        
        al = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 45, spacing=10)
        self.btn_save_dbt = CustomButton(text='SAVE DBT DATA', background_color=(0.02, 0.45, 0.35, 1), bold=True)
        self.btn_save_dbt.bind(on_press=self.save_dbt_data)
        self.btn_back_dbt = CustomButton(text='BACK', background_color=(0.7, 0.1, 0.1, 1), bold=True)
        self.btn_back_dbt.bind(on_press=lambda x: self.show_welcome())
        al.add_widget(self.btn_save_dbt); al.add_widget(self.btn_back_dbt); self.content_area.add_widget(al)
        
        self.dbt_tab_index = 0
        self.refresh_dbt_grid()

    def refresh_dbt_grid(self):
        self.dbt_grid_box.clear_widgets()
        self.dbt_fields = {}
        dynamic_inputs = []
        is_mob = (kivy_platform != 'win')
        
        import os
        from kivy.graphics import Color, Rectangle
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        
        sel_class = self.dbt_class_spinner.text.strip().lower()
        sel_year = self.dbt_year_spinner.text.strip()
        dbt_file = 'DBT_Database.xlsx'
        
        scroll = ScrollView(do_scroll_x=True, do_scroll_y=True)
        grid_table = GridLayout(cols=7, spacing=(1, 1), size_hint_x=None if is_mob else 1, size_hint_y=None, padding=(2, 2, 2, 10))
        grid_table.bind(minimum_height=grid_table.setter('height'))
        
        col_w = [dp(60), dp(150), dp(150), dp(85), dp(130), dp(140), dp(145)] if is_mob else [55, 130, 135, 75, 120, 120, 125]
        if is_mob:
            grid_table.width = sum(col_w)
        grid_table.cols_minimum = {i: col_w[i] for i in range(7)}
        
        with grid_table.canvas.before:
            Color(0.35, 0.35, 0.35, 1)
            self.gt_dbt_bg = Rectangle(size=grid_table.size, pos=grid_table.pos)
        grid_table.bind(size=lambda ins, val: setattr(self.gt_dbt_bg, 'size', ins.size), pos=lambda ins, val: setattr(self.gt_dbt_bg, 'pos', ins.pos))
        
        def make_dbt_hdr_cell(txt, idx):
            lbl = Label(text=txt, color=(1,1,1,1), bold=True, font_size=sp(12) if is_mob else 11, size_hint_x=None if is_mob else 1, width=col_w[idx], size_hint_y=None, height=dp(42) if is_mob else 38, halign='center', valign='middle')
            with lbl.canvas.before:
                Color(0, 0.35, 0.25, 1)
                lbl.rect = Rectangle(size=lbl.size, pos=lbl.pos)
            lbl.bind(size=lambda ins, val: setattr(lbl.rect, 'size', ins.size), pos=lambda ins, val: setattr(lbl.rect, 'pos', ins.pos))
            return lbl

        headers_dbt = ['SR NO', 'STUDENT NAME', "FATHER'S NAME", 'CLASS', 'PAYMENT STATUS', 'A/C NUMBER', 'BANK NAME']
        for i, h in enumerate(headers_dbt): 
            grid_table.add_widget(make_dbt_hdr_cell(h, i))
            
        def make_dbt_data_cell(txt, bg_col, idx, is_status=False):
            t_col = (0,0,0,1)
            is_bold = False
            if is_status:
                is_bold = True
                if 'SUCCESS' in str(txt).upper(): t_col = (0.02, 0.45, 0.1, 1)
                else: t_col = (0.75, 0.1, 0.1, 1)
            lbl = Label(text=str(txt), color=t_col, bold=is_bold, font_size=sp(12) if is_mob else 11, size_hint_x=None if is_mob else 1, width=col_w[idx], size_hint_y=None, height=dp(38) if is_mob else 34, halign='center', valign='middle')
            with lbl.canvas.before:
                Color(*bg_col)
                lbl.rect = Rectangle(size=lbl.size, pos=lbl.pos)
            lbl.bind(size=lambda ins, val: setattr(lbl.rect, 'size', ins.size), pos=lambda ins, val: setattr(lbl.rect, 'pos', ins.pos))
            return lbl

        saved_dbt_records = {}
        if os.path.exists(dbt_file):
            try:
                df_old = pd.read_excel(dbt_file, dtype=str)
                for col in df_old.columns: df_old[col] = df_old[col].astype(str).str.strip()
                for _, r in df_old.iterrows():
                    s_id = str(r.get('SR NO', '')).strip()
                    r_class = str(r.get('Class', '')).lower()
                    r_year = str(r.get('Year', ''))
                    if r_class == sel_class and r_year == sel_year:
                        saved_dbt_records[s_id] = {
                            'status': str(r.get('Payment Status', 'Pending')),
                            'acc': str(r.get('Account No', '---')),
                            'bank': str(r.get('Bank Name', '---')),
                            'tx': str(r.get('Transaction ID', '---'))
                        }
            except: pass
            
        if os.path.exists(EXCEL_FILE):
            try:
                df = pd.read_excel(EXCEL_FILE, dtype=str)
                if 'CLASS' in df.columns:
                    df['CLASS_CLEAN'] = df['CLASS'].astype(str).str.strip().str.lower().str.replace('class', '').str.strip()
                    df = df[(df['CLASS'].astype(str).str.strip().str.lower() == sel_class) | (df['CLASS_CLEAN'] == sel_class.replace('class','').strip())]
                
                for r_idx, (idx, row) in enumerate(df.iterrows()):
                    raw_sr = str(row.get('SR NO', '')).strip()
                    sr_val = raw_sr.split('.')[0] if '.' in raw_sr else raw_sr
                    if not raw_sr or raw_sr == 'nan': sr_val = str(idx+1)
                    
                    name_val = str(row.get('NAME', '')).strip().upper()
                    father_val = str(row.get("FATHER'S NAME", '')).strip().upper()
                    class_val = str(row.get('CLASS', '')).strip()
                    
                    record = saved_dbt_records.get(sr_val, {'status': 'Pending', 'acc': '---', 'bank': '---', 'tx': '---'})
                    
                    # पासबुक अल्टरनेटिंग रो शेडिंग कलर कस्टमाइजेशन
                    c_bg = (0.98, 0.98, 0.98, 1) if r_idx % 2 == 0 else (0.92, 0.94, 0.96, 1)
                    
                    grid_table.add_widget(make_dbt_data_cell(sr_val, c_bg, 0))
                    grid_table.add_widget(make_dbt_data_cell(name_val, c_bg, 1))
                    grid_table.add_widget(make_dbt_data_cell(father_val, c_bg, 2))
                    grid_table.add_widget(make_dbt_data_cell(class_val, c_bg, 3))
                    grid_table.add_widget(make_dbt_data_cell(record['status'], c_bg, 4, is_status=True))
                    grid_table.add_widget(make_dbt_data_cell(record['acc'], c_bg, 5))
                    grid_table.add_widget(make_dbt_data_cell(record['bank'], c_bg, 6))
                    
                    self.dbt_fields[sr_val] = {
                        'name': name_val, 'father': father_val, 'class': class_val,
                        'status': record['status'], 'acc': record['acc'], 'bank': record['bank'], 'tx': record['tx']
                    }
            except Exception as e: print("DBT UI Loader Error:", str(e))
            
        scroll.add_widget(grid_table); self.dbt_grid_box.add_widget(scroll)
        self.dbt_master_tabs = [self.dbt_class_spinner, self.dbt_year_spinner, self.btn_save_dbt, self.btn_back_dbt]

    def upload_department_dbt_excel(self, instance):
        def process_dbt_excel_file(file_path):
            if not file_path:
                return
            try:
                if file_path.endswith('.csv'):
                    dept_df = pd.read_csv(file_path, dtype=str)
                else:
                    dept_df = pd.read_excel(file_path, dtype=str)
                    
                dept_df.columns = [str(c).strip() for c in dept_df.columns]
                
                if 'Student SR No.' not in dept_df.columns and not any('student sr' in c.lower() for c in dept_df.columns):
                    if file_path.endswith('.csv'):
                        dept_df = pd.read_csv(file_path, dtype=str, skiprows=1)
                    else:
                        dept_df = pd.read_excel(file_path, dtype=str, skiprows=1)
                    dept_df.columns = [str(c).strip() for c in dept_df.columns]
                
                sr_col = next((c for c in dept_df.columns if 'student sr' in c.lower()), None)
                if not sr_col:
                    self.popup('Process Error', "Excel file me 'Student SR No.' column nahi mila!"); return
                    
                status_col = next((c for c in dept_df.columns if 'payment status' in c.lower()), 'Payment Status')
                acc_col = next((c for c in dept_df.columns if 'account no' in c.lower()), 'Payment Account No')
                tx_col = next((c for c in dept_df.columns if 'transaction id' in c.lower()), 'Transaction ID')
                bank_col = next((c for c in dept_df.columns if 'bank name' in c.lower()), 'Payment Bank Name')
                
                dept_df = dept_df.dropna(subset=[sr_col])
                dept_lookup = {}
                for _, d_row in dept_df.iterrows():
                    raw_d_sr = str(d_row.get(sr_col, '')).strip()
                    clean_d_sr = raw_d_sr.split('.')[0] if '.' in raw_d_sr else raw_d_sr
                    if clean_d_sr and clean_d_sr.lower() != 'nan':
                        dept_lookup[clean_d_sr] = d_row
                
                match_counter = 0
                for sr_id in list(self.dbt_fields.keys()):
                    raw_scr_sr = str(sr_id).strip()
                    clean_screen_sr = raw_scr_sr.split('.')[0] if '.' in raw_scr_sr else raw_scr_sr
                    
                    if clean_screen_sr in dept_lookup:
                        match_counter += 1
                        target_row = dept_lookup[clean_screen_sr]
                        
                        raw_acc = str(target_row.get(acc_col, '---')).strip()
                        if 'e+' in raw_acc.lower():
                            try:
                                from decimal import Decimal
                                raw_acc = f"{Decimal(raw_acc):.0f}"
                            except:
                                try: raw_acc = f"{float(raw_acc):.0f}"
                                except: pass
                                
                        p_status = str(target_row.get(status_col, 'Pending')).strip()
                        p_tx = str(target_row.get(tx_col, '---')).strip()
                        p_bank = str(target_row.get(bank_col, '---')).strip()
                        
                        self.dbt_fields[sr_id]['status'] = p_status if p_status and p_status != '-' else 'Pending'
                        self.dbt_fields[sr_id]['acc'] = raw_acc if raw_acc and raw_acc not in ['nan', '-'] else '---'
                        self.dbt_fields[sr_id]['tx'] = p_tx if p_tx and p_tx not in ['nan', '-'] else '---'
                        self.dbt_fields[sr_id]['bank'] = p_bank if p_bank and p_bank not in ['nan', '-'] else '---'
                
                if match_counter > 0:
                    self.rebuild_dbt_ui_from_memory()
                    self.popup('Upload Hub', f"Success! {match_counter} Students records and Bank details updated from Excel.")
                else:
                    self.popup('Alert', "SR NO Mismatch! Selected Class ke bachhon ka SR No. Excel file se match nahi hua.")
            except Exception as ex:
                self.popup('Process Error', f"Excel Parsing Failed: {str(ex)}")

        select_file_cross_platform(
            "Select Department DBT Excel File",
            [("Excel/CSV Files", "*.xlsx *.xls *.csv")],
            process_dbt_excel_file
        )

    def rebuild_dbt_ui_from_memory(self):
        if not hasattr(self, 'dbt_grid_box'): return
        self.dbt_grid_box.clear_widgets()
        is_mob = (kivy_platform != 'win')
        from kivy.graphics import Color, Rectangle
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        
        scroll = ScrollView(do_scroll_x=True, do_scroll_y=True)
        grid_table = GridLayout(cols=7, spacing=(1, 1), size_hint_x=None if is_mob else 1, size_hint_y=None, padding=(2, 2, 2, 10))
        grid_table.bind(minimum_height=grid_table.setter('height'))
        
        col_w = [dp(60), dp(150), dp(150), dp(85), dp(130), dp(140), dp(145)] if is_mob else [55, 130, 135, 75, 120, 120, 125]
        grid_table.width = sum(col_w)
        grid_table.cols_minimum = {i: col_w[i] for i in range(7)}
        
        with grid_table.canvas.before:
            Color(0.35, 0.35, 0.35, 1)
            self.gt_dbt_bg2 = Rectangle(size=grid_table.size, pos=grid_table.pos)
        grid_table.bind(size=lambda ins, val: setattr(self.gt_dbt_bg2, 'size', ins.size), pos=lambda ins, val: setattr(self.gt_dbt_bg2, 'pos', ins.pos))
        
        def make_dbt_hdr_cell(txt, idx):
            lbl = Label(text=txt, color=(1,1,1,1), bold=True, font_size=sp(12) if is_mob else 11, size_hint_x=None if is_mob else 1, width=col_w[idx], size_hint_y=None, height=dp(42) if is_mob else 38, halign='center', valign='middle')
            with lbl.canvas.before:
                Color(0, 0.35, 0.25, 1)
                lbl.rect = Rectangle(size=lbl.size, pos=lbl.pos)
            lbl.bind(size=lambda ins, val: setattr(lbl.rect, 'size', ins.size), pos=lambda ins, val: setattr(lbl.rect, 'pos', ins.pos))
            return lbl

        headers = ['SR NO', 'STUDENT NAME', "FATHER'S NAME", 'CLASS', 'PAYMENT STATUS', 'A/C NUMBER', 'BANK NAME']
        for i, h in enumerate(headers): grid_table.add_widget(make_dbt_hdr_cell(h, i))
        
        def make_dbt_data_cell(txt, bg_col, idx, is_status=False):
            t_col = (0,0,0,1)
            is_bold = False
            if is_status:
                is_bold = True
                if 'SUCCESS' in str(txt).upper(): t_col = (0.02, 0.45, 0.1, 1)
                else: t_col = (0.75, 0.1, 0.1, 1)
            lbl = Label(text=str(txt), color=t_col, bold=is_bold, font_size=sp(12) if is_mob else 11, size_hint_x=None if is_mob else 1, width=col_w[idx], size_hint_y=None, height=dp(38) if is_mob else 34, halign='center', valign='middle')
            with lbl.canvas.before:
                Color(*bg_col)
                lbl.rect = Rectangle(size=lbl.size, pos=lbl.pos)
            lbl.bind(size=lambda ins, val: setattr(lbl.rect, 'size', ins.size), pos=lambda ins, val: setattr(lbl.rect, 'pos', ins.pos))
            return lbl
        
        for r_idx, (sr_id, record) in enumerate(self.dbt_fields.items()):
            c_bg = (0.98, 0.98, 0.98, 1) if r_idx % 2 == 0 else (0.92, 0.94, 0.96, 1)
            grid_table.add_widget(make_dbt_data_cell(str(sr_id), c_bg, 0))
            grid_table.add_widget(make_dbt_data_cell(record['name'], c_bg, 1))
            grid_table.add_widget(make_dbt_data_cell(record['father'], c_bg, 2))
            grid_table.add_widget(make_dbt_data_cell(record['class'], c_bg, 3))
            grid_table.add_widget(make_dbt_data_cell(record['status'], c_bg, 4, is_status=True))
            grid_table.add_widget(make_dbt_data_cell(record['acc'], c_bg, 5))
            grid_table.add_widget(make_dbt_data_cell(record['bank'], c_bg, 6))
            
        scroll.add_widget(grid_table); self.dbt_grid_box.add_widget(scroll)
    
    def save_dbt_data(self, instance):
        if not self.dbt_fields: return
        cls = self.dbt_class_spinner.text.strip(); yr = self.dbt_year_spinner.text.strip(); dbt_list = []
        dbt_file = 'DBT_Database.xlsx'
        
        for sr, record in self.dbt_fields.items():
            dbt_list.append({
                'Class': cls, 'Year': yr, 'SR NO': str(sr).strip(), 
                'NAME': record['name'], "FATHER'S NAME": record['father'],
                'Payment Status': record['status'], 'Account No': record['acc'], 'Bank Name': record['bank'], 'Transaction ID': record['tx']
            })
        try:
            new_df = pd.DataFrame(dbt_list)
            if not os.path.exists(dbt_file): 
                new_df.to_excel(dbt_file, index=False)
            else:
                old_df = pd.read_excel(dbt_file, dtype=str)
                kept_rows = []
                for _, r_old in old_df.iterrows():
                    r_c = str(r_old.get('Class', '')).strip().lower()
                    r_y = str(r_old.get('Year', '')).strip()
                    if not (r_c == cls.lower() and r_y == yr):
                        kept_rows.append(dict(r_old))
                cleaned_old_df = pd.DataFrame(kept_rows, columns=old_df.columns)
                pd.concat([cleaned_old_df, new_df], ignore_index=True).to_excel(dbt_file, index=False)
                
            self.popup('Success', f"{cls} सत्र {yr} का DBT रिकॉर्ड बैंक विवरण के साथ सुरक्षित!")
            self.refresh_dbt_grid()
        except Exception as e: self.popup('Error', str(e))
            
    def open_prerna_portal_dbt_sync(self, instance):
        is_mob = (kivy_platform != 'win')
        pl = BoxLayout(orientation='vertical', padding=dp(14) if is_mob else 18, spacing=dp(10))

        info_lbl = Label(
            text="1. Click 'OPEN PRERNA PORTAL' below.\n2. Enter Mobile No. & Verify OTP on Prerna.\n3. Open 'DBT Report / Student Payment Status' & click Export Excel.\n4. Click 'AUTO-LOAD DOWNLOADED DBT DATA' below.",
            color=(1, 1, 1, 1),
            font_size=sp(13) if is_mob else 13,
            halign='left',
            valign='middle',
            size_hint_y=None,
            height=dp(115) if is_mob else 100
        )
        info_lbl.bind(size=lambda ins, val: setattr(ins, 'text_size', (ins.width - dp(8), None)))
        pl.add_widget(info_lbl)

        btn_open_web = Button(
            text='1. OPEN PRERNA PORTAL (OTP LOGIN)',
            background_color=(0.08, 0.42, 0.78, 1),
            bold=True,
            font_size=sp(13) if is_mob else 13,
            size_hint_y=None,
            height=dp(44) if is_mob else 40
        )

        btn_auto_fetch = Button(
            text='2. AUTO-LOAD DOWNLOADED DBT DATA',
            background_color=(0.05, 0.58, 0.25, 1),
            bold=True,
            font_size=sp(13) if is_mob else 13,
            size_hint_y=None,
            height=dp(44) if is_mob else 40
        )

        btn_close_p = Button(
            text='CLOSE',
            background_color=(0.75, 0.15, 0.15, 1),
            bold=True,
            font_size=sp(13) if is_mob else 13,
            size_hint_y=None,
            height=dp(42) if is_mob else 38
        )

        pl.add_widget(btn_open_web)
        pl.add_widget(btn_auto_fetch)
        pl.add_widget(btn_close_p)

        pop_prerna = Popup(
            title='Prerna Portal Live DBT Sync',
            content=pl,
            size_hint=(0.94, 0.62) if is_mob else (0.50, 0.52),
            auto_dismiss=False,
            background='',
            background_color=(0.14, 0.14, 0.14, 0.98)
        )
        btn_close_p.bind(on_press=pop_prerna.dismiss)

        def _launch_prerna_browser(x):
            prerna_url = "https://prernaup.in"
            try:
                if kivy_platform == 'android':
                    from jnius import autoclass
                    PythonActivity = autoclass('org.kivy.android.PythonActivity')
                    Intent = autoclass('android.content.Intent')
                    Uri = autoclass('android.net.Uri')
                    intent = Intent(Intent.ACTION_VIEW, Uri.parse(prerna_url))
                    PythonActivity.mActivity.startActivity(intent)
                else:
                    import webbrowser
                    webbrowser.open(prerna_url)
            except Exception as e:
                self.popup('Browser Alert', f'Please open https://prernaup.in in browser.\n({str(e)})')

        def _auto_scan_and_load_dbt(x):
            search_dirs = ['/storage/emulated/0/Download', '/storage/emulated/0/Downloads'] if kivy_platform == 'android' else [os.path.join(os.path.expanduser('~'), 'Downloads')]
            latest_file = None
            latest_mtime = 0

            for d_path in search_dirs:
                if os.path.exists(d_path):
                    try:
                        for fname in os.listdir(d_path):
                            low_f = fname.lower()
                            if low_f.endswith(('.xlsx', '.xls', '.csv')) and any(k in low_f for k in ['dbt', 'student', 'payment', 'prerna', 'beneficiary', 'pfms']):
                                full_p = os.path.join(d_path, fname)
                                mt = os.path.getmtime(full_p)
                                if mt > latest_mtime:
                                    latest_mtime = mt
                                    latest_file = full_p
                    except Exception:
                        pass

            if latest_file and os.path.exists(latest_file):
                pop_prerna.dismiss()
                self._import_dbt_file_direct(latest_file)
            else:
                pop_prerna.dismiss()
                self.popup('Auto-Scan Info', 'No recent DBT file found in Downloads.\nPlease select the downloaded file manually.')
                self.upload_department_dbt_excel(None)

        btn_open_web.bind(on_press=_launch_prerna_browser)
        btn_auto_fetch.bind(on_press=_auto_scan_and_load_dbt)
        pop_prerna.open()

    def _import_dbt_file_direct(self, file_path):
        try:
            dept_df = pd.read_csv(file_path, dtype=str) if file_path.lower().endswith('.csv') else pd.read_excel(file_path, dtype=str)
            dept_df.columns = [str(c).strip() for c in dept_df.columns]
            if not any('student sr' in c.lower() or 'sr no' in c.lower() for c in dept_df.columns):
                dept_df = pd.read_csv(file_path, dtype=str, skiprows=1) if file_path.lower().endswith('.csv') else pd.read_excel(file_path, dtype=str, skiprows=1)
                dept_df.columns = [str(c).strip() for c in dept_df.columns]

            sr_col = next((c for c in dept_df.columns if 'student sr' in c.lower() or 'sr no' in c.lower()), None)
            if not sr_col:
                self.popup('Format Alert', "Prerna Excel me 'Student SR No.' column nahi mila!"); return

            status_col = next((c for c in dept_df.columns if 'payment status' in c.lower() or 'status' in c.lower()), 'Payment Status')
            acc_col = next((c for c in dept_df.columns if 'account no' in c.lower() or 'a/c' in c.lower()), 'Payment Account No')
            tx_col = next((c for c in dept_df.columns if 'transaction id' in c.lower()), 'Transaction ID')
            bank_col = next((c for c in dept_df.columns if 'bank name' in c.lower()), 'Payment Bank Name')

            dept_lookup = {}
            for _, d_row in dept_df.iterrows():
                clean_d_sr = str(d_row.get(sr_col, '')).strip().split('.')[0]
                if clean_d_sr and clean_d_sr.lower() != 'nan':
                    dept_lookup[clean_d_sr] = d_row

            match_counter = 0
            for sr_id in list(self.dbt_fields.keys()):
                clean_screen_sr = str(sr_id).strip().split('.')[0]
                if clean_screen_sr in dept_lookup:
                    match_counter += 1
                    target_row = dept_lookup[clean_screen_sr]
                    raw_acc = str(target_row.get(acc_col, '---')).strip()
                    if 'e+' in raw_acc.lower():
                        try:
                            from decimal import Decimal
                            raw_acc = f"{Decimal(raw_acc):.0f}"
                        except Exception:
                            pass
                    p_status = str(target_row.get(status_col, 'Pending')).strip()
                    p_tx = str(target_row.get(tx_col, '---')).strip()
                    p_bank = str(target_row.get(bank_col, '---')).strip()

                    self.dbt_fields[sr_id]['status'] = p_status if p_status and p_status != '-' else 'Pending'
                    self.dbt_fields[sr_id]['acc'] = raw_acc if raw_acc and raw_acc not in ['nan', '-'] else '---'
                    self.dbt_fields[sr_id]['tx'] = p_tx if p_tx and p_tx not in ['nan', '-'] else '---'
                    self.dbt_fields[sr_id]['bank'] = p_bank if p_bank and p_bank not in ['nan', '-'] else '---'

            if match_counter > 0:
                self.rebuild_dbt_ui_from_memory()
                self.popup('Prerna Sync Success', f"Prerna Portal se {match_counter} bachhon ka DBT data auto-load ho gaya!\nAb 'SAVE DBT DATA' dabakar lock karein.")
            else:
                self.popup('SR Mismatch', 'Selected Class ke bachhon ka SR No. Prerna file se match nahi hua.')
        except Exception as ex:
            self.popup('Prerna Sync Error', str(ex))

    def generate_school_consolidated_dbt_pdf(self):
        import os, re
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, TableStyle, Table, Paragraph, Spacer
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib import colors
        
        sel_year = self.dbt_year_spinner.text.strip()
        dbt_file = 'DBT_Database.xlsx'
        if not os.path.exists(dbt_file):
            self.popup('Database Alert', 'DBT Database is empty!'); return
            
        try:
            main_df = pd.read_excel(dbt_file, dtype=str)
            session_rows = []
            for _, r in main_df.iterrows():
                if str(r.get('Year', '')).strip() == sel_year:
                    session_rows.append(dict(r))

            if not session_rows:
                self.popup('No Data', f'No records found for year {sel_year}'); return
                
            total_students = len(session_rows)
            received_count = sum(1 for r in session_rows if any(k in str(r.get('Payment Status', '')).lower() for k in ['receive', 'success']))
            pending_count = total_students - received_count
            
            out_pdf_name = f"School_Consolidated_DBT_Report_{sel_year}.pdf"
            doc_pdf = SimpleDocTemplate(out_pdf_name, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
            pdf_story = []
            
            TEAL_THEME = colors.HexColor("#005A43"); LIGHT_TEAL = colors.HexColor("#E0F2F1")
            h_style_main = ParagraphStyle('H_M_D', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=TEAL_THEME, alignment=1)
            h_style_sub = ParagraphStyle('H_S_D', fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=colors.black, alignment=1)
            th_style = ParagraphStyle('T_H_D', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white, alignment=1)
            td_bold = ParagraphStyle('T_D_B_D', fontName='Helvetica-Bold', fontSize=8, leading=10.5, textColor=colors.black, alignment=1)
            td_norm = ParagraphStyle('T_D_N_D', fontName='Helvetica', fontSize=8, leading=10.5, textColor=colors.black, alignment=1)
            
            smry_style_title = ParagraphStyle('S_T', fontName='Helvetica-Bold', fontSize=12, leading=14, textColor=TEAL_THEME, alignment=1)
            smry_style_val = ParagraphStyle('S_V', fontName='Helvetica-Bold', fontSize=13, leading=15, textColor=colors.black, alignment=1)
            
            pdf_story.append(Spacer(1, 15))
            pdf_story.append(Paragraph("<b>PRIMARY SCHOOL PANAUTA, WAZIRGANJ (BUDAUN)</b>", h_style_main))
            pdf_story.append(Paragraph(f"<b>CONSOLIDATED SCHOOL DIRECT BENEFIT TRANSFER (D.B.T.) STATUS REPORT - SESSION: {sel_year}</b>", h_style_sub))
            pdf_story.append(Spacer(1, 12))

            summary_table_data = [
                [Paragraph("<b>TOTAL REGISTERED STUDENTS</b>", smry_style_title), Paragraph("<b>TOTAL STUDENTS RECEIVED DBT</b>", smry_style_title), Paragraph("<b>TOTAL PENDING CASES</b>", smry_style_title)],
                [Paragraph(f"<b>{total_students}</b>", smry_style_val), Paragraph(f"<font color='green'><b>{received_count}</b></font>", smry_style_val), Paragraph(f"<font color='red'><b>{pending_count}</b></font>", smry_style_val)]
            ]
            t_summary = Table(summary_table_data, colWidths=[270, 270, 272])
            t_summary.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1.2, TEAL_THEME), ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F2F9F6")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 8), ('BOTTOMPADDING', (0,0), (-1,-1), 8)]))
            pdf_story.append(t_summary); pdf_story.append(Spacer(1, 15))
            
            reg_headers = [Paragraph("<b>SR NO</b>", th_style), Paragraph("<b>STUDENT NAME</b>", th_style), Paragraph("<b>FATHER NAME</b>", th_style), Paragraph("<b>CLASS</b>", th_style), Paragraph("<b>DBT STATUS</b>", th_style), Paragraph("<b>ACCOUNT NO</b>", th_style), Paragraph("<b>BANK NAME</b>", th_style), Paragraph("<b>TRANSACTION ID</b>", th_style)]
            reg_table_rows = [reg_headers]
            
            def sort_key_dbt(r_item):
                m = re.search(r'(\d+)', str(r_item.get('Class', '99')))
                c_num = int(m.group(1)) if m else 99
                return (c_num, str(r_item.get('NAME', '')).upper())

            sorted_session_rows = sorted(session_rows, key=sort_key_dbt)
            
            for idx, row_val in enumerate(sorted_session_rows, start=1):
                p_status = str(row_val.get('Payment Status', 'Pending')).strip()
                status_html = f"<font color='green'><b>{p_status}</b></font>" if any(k in p_status.lower() for k in ['success', 'received']) else f"<font color='red'><b>{p_status}</b></font>"
                
                reg_table_rows.append([
                    Paragraph(str(row_val.get('SR NO', str(idx))).strip().replace('.0', ''), td_norm),
                    Paragraph(str(row_val.get('NAME', '')).strip().upper(), td_bold),
                    Paragraph(str(row_val.get("FATHER'S NAME", '')).strip().upper(), td_norm),
                    Paragraph(str(row_val.get('Class', '')).strip(), td_bold),
                    Paragraph(status_html, td_bold),
                    Paragraph(str(row_val.get('Account No', '---')).strip(), td_norm),
                    Paragraph(str(row_val.get('Bank Name', '---')).strip(), td_norm),
                    Paragraph(str(row_val.get('Transaction ID', '---')).strip(), td_norm)
                ])
                
            col_widths_array = [35, 115, 115, 55, 87, 115, 140, 150]
            
            t_register = Table(reg_table_rows, colWidths=col_widths_array, repeatRows=1)
            t_style_rules = [('GRID', (0,0), (-1,-1), 0.8, colors.HexColor("#595959")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BACKGROUND', (0,0), (-1,0), TEAL_THEME), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('ALIGN', (1,1), (2,-1), 'LEFT'), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)]
            for i in range(1, len(reg_table_rows)):
                if i % 2 == 0: t_style_rules.append(('BACKGROUND', (0, i), (-1, i), LIGHT_TEAL))
            t_register.setStyle(TableStyle(t_style_rules))
            pdf_story.append(t_register); pdf_story.append(Spacer(1, 45))
            
            w_sig_panel = 390
            t_sig = Table([[Paragraph("________________________", td_bold), Paragraph("________________________", td_bold)], [Paragraph("DBT IN-CHARGE SIGNATURE", td_bold), Paragraph("HEADMASTER SEAL & SIGNATURE", td_bold)]], colWidths=[w_sig_panel, w_sig_panel])
            t_sig.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'BOTTOM'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            pdf_story.append(t_sig)
            
            def draw_dbt_canvas_decorations(canvas, document):
                canvas.saveState()
                if os.path.exists(get_exe_safe_path("basic.png")): canvas.drawImage(get_exe_safe_path("basic.png"), 25, 520, width=52, height=52, mask='auto')
                if os.path.exists(get_exe_safe_path("logo.png")):
                    canvas.drawImage(get_exe_safe_path("logo.png"), 765, 520, width=52, height=52, mask='auto')
                    canvas.saveState(); canvas.setFillAlpha(0.06); canvas.drawImage(get_exe_safe_path("logo.png"), 296, 145, width=250, height=250, mask='auto'); canvas.restoreState()
                canvas.restoreState()
                
            doc_pdf.build(pdf_story, onFirstPage=draw_dbt_canvas_decorations)
            self.popup('Report Hub', f"School Consolidated DBT Register Compiled!\nSaved as: {out_pdf_name}")
            open_file_cross_platform(out_pdf_name)
        except Exception as ex: self.popup('Print Error', f"Compilation Interrupt: {str(ex)}")

    def load_height_weight_view(self):
        self.content_area.clear_widgets(); self.current_view = 'height_weight'; self.hw_fields = {}
        is_mob = (kivy_platform != 'win')
        with self.content_area.canvas.before:
            Color(0.95, 0.95, 0.92, 1); self.c_bg = Rectangle(size=self.content_area.size, pos=self.content_area.pos)
        self.content_area.bind(size=lambda ins, val: setattr(self.c_bg, 'size', ins.size), pos=lambda ins, val: setattr(self.c_bg, 'pos', ins.pos))
        
        lbl_hw = Label(text='STUDENT HEIGHT & WEIGHT DASHBOARD', font_size=sp(17) if is_mob else 20, bold=True, color=(0,0.3,0.5,1), size_hint_y=None, height=dp(36) if is_mob else 40, halign='center', valign='middle')
        lbl_hw.bind(size=lbl_hw.setter('text_size'))
        self.content_area.add_widget(lbl_hw)
        
        top_bar = GridLayout(cols=2 if is_mob else 8, size_hint_y=None, height=dp(185) if is_mob else 50, spacing=dp(8) if is_mob else 10, padding=5)
        top_bar.add_widget(Label(text='Class:', color=(0,0,0,1), bold=True, font_size=sp(13) if is_mob else 13))
        self.hw_class_spinner = CustomSpinner(text='Class 1', values=('Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5'), size_hint_y=None, height=dp(42) if is_mob else 36)
        self.hw_class_spinner.bind(text=lambda sp, tx: self.refresh_hw_grid()); top_bar.add_widget(self.hw_class_spinner)
        
        top_bar.add_widget(Label(text='Month:', color=(0,0,0,1), bold=True, font_size=sp(13) if is_mob else 13))
        self.hw_month_spinner = CustomSpinner(text='April', values=('April', 'November'), size_hint_y=None, height=dp(42) if is_mob else 36)
        self.hw_month_spinner.bind(text=lambda sp, tx: self.refresh_hw_grid()); top_bar.add_widget(self.hw_month_spinner)
        
        top_bar.add_widget(Label(text='Year:', color=(0,0,0,1), bold=True, font_size=sp(13) if is_mob else 13))
        self.hw_year_spinner = CustomSpinner(text='2026', values=('2026', '2027', '2028', '2029', '2030'), size_hint_y=None, height=dp(42) if is_mob else 36)
        self.hw_year_spinner.bind(text=lambda sp, tx: self.refresh_hw_grid()); top_bar.add_widget(self.hw_year_spinner)
        
        btn_print_m_h = Button(text='PRINT MONTHLY PDF', background_color=(0.85, 0.45, 0.0, 1), bold=True, font_size=sp(12) if is_mob else 11, size_hint_y=None, height=dp(42) if is_mob else 36)
        btn_print_a_h = Button(text='PRINT ANNUAL PDF', background_color=(0.05, 0.35, 0.6, 1), bold=True, font_size=sp(12) if is_mob else 11, size_hint_y=None, height=dp(42) if is_mob else 36)
        top_bar.add_widget(btn_print_m_h); top_bar.add_widget(btn_print_a_h)
        self.content_area.add_widget(top_bar)
        
        self.hw_grid_box = BoxLayout(orientation='vertical', padding=5); self.content_area.add_widget(self.hw_grid_box)
        
        al = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 45, spacing=10)
        self.btn_save_hw = CustomButton(text='SAVE HEALTH DATA', background_color=(0.05, 0.45, 0.55, 1), bold=True)
        self.btn_save_hw.bind(on_press=self.save_hw_data)
        self.btn_back_hw = CustomButton(text='BACK', background_color=(0.7, 0.1, 0.1, 1), bold=True)
        self.btn_back_hw.bind(on_press=lambda x: self.show_welcome())
        al.add_widget(self.btn_save_hw); al.add_widget(self.btn_back_hw); self.content_area.add_widget(al)
        
        # 🖨️ ✨ [मास्टर हेल्थ ड्यूल पीडीएफ जनरेटर इंजन - क्रॉस-प्लेटफ़ॉर्म]
        def action_health_pdf_engine(is_annual_mode=False):
            cls = self.hw_class_spinner.text.strip()
            mn = self.hw_month_spinner.text.strip()
            yr = self.hw_year_spinner.text.strip()
            hw_file = 'Height_Weight_Database.xlsx'
            
            if not os.path.exists(EXCEL_FILE) or not os.path.exists(hw_file):
                self.popup('Alert', 'Required database files are missing!'); return
            try:
                st_df = pd.read_excel(EXCEL_FILE, dtype=str)
                class_students_list = []
                for _, r_st in st_df.iterrows():
                    if str(r_st.get('CLASS', '')).strip().lower() == cls.lower():
                        class_students_list.append(dict(r_st))
                if not class_students_list:
                    self.popup('No Data', f'No profiles found for {cls}'); return
                
                class_students_list.sort(key=lambda x: str(x.get('NAME', '')).upper())
                
                h_df = pd.read_excel(hw_file, dtype=str)
                hw_records_list = [dict(r_h) for _, r_h in h_df.iterrows()]
                
                from reportlab.lib.pagesizes import landscape, A4
                from reportlab.platypus import SimpleDocTemplate, TableStyle, Table, Paragraph, Spacer
                from reportlab.lib.styles import ParagraphStyle
                from reportlab.lib import colors
                
                GREEN_THEME = colors.HexColor("#1E5631"); LIGHT_GREEN = colors.HexColor("#E8F5E9")
                h_main = ParagraphStyle('H_M_H', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=GREEN_THEME, alignment=1)
                h_sub = ParagraphStyle('H_S_H', fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=colors.black, alignment=1)
                th_style = ParagraphStyle('T_H_H', fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.white, alignment=1)
                td_bold = ParagraphStyle('T_D_B_H', fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.black, alignment=1)
                td_norm = ParagraphStyle('T_D_N_H', fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.black, alignment=1)
                
                if is_annual_mode:
                    out_pdf = f"{cls.replace(' ', '_')}_Annual_Health_Register_{yr}.pdf"
                    doc = SimpleDocTemplate(out_pdf, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
                    pdf_story = []
                    
                    pdf_story.append(Spacer(1, 15))
                    pdf_story.append(Paragraph("<b>PRIMARY SCHOOL PANAUTA, WAZIRGANJ (BUDAUN)</b>", h_main))
                    pdf_story.append(Paragraph(f"<b>ANNUAL HEALTH REGISTER (APRIL vs NOVEMBER COMPARISON REGISTER) - YEAR: {yr} &nbsp;|&nbsp; CLASS: {cls.upper()}</b>", h_sub))
                    pdf_story.append(Spacer(1, 15))
                    
                    headers_list = [
                        Paragraph("<b>SR NO</b>", th_style), Paragraph("<b>STUDENT NAME</b>", th_style), Paragraph("<b>FATHER NAME</b>", th_style),
                        Paragraph("<b>HEIGHT (cm)<br/>[APRIL]</b>", th_style), Paragraph("<b>WEIGHT (kg)<br/>[APRIL]</b>", th_style),
                        Paragraph("<b>HEIGHT (cm)<br/>[NOV]</b>", th_style), Paragraph("<b>WEIGHT (kg)<br/>[NOV]</b>", th_style),
                        Paragraph("<b>NET HEIGHT<br/>GROWTH</b>", th_style), Paragraph("<b>NET WEIGHT<br/>GAIN</b>", th_style)
                    ]
                    table_data_matrix = [headers_list]
                    
                    for s_row in class_students_list:
                        sr = str(s_row.get('SR NO', '')).strip().split('.')
                        name = str(s_row.get('NAME', '')).strip().upper()
                        f_name = str(s_row.get("FATHER'S NAME", '')).strip().upper()
                        
                        ap_rec = next((r for r in hw_records_list if str(r.get('Class', '')).strip().lower() == cls.lower() and str(r.get('Month', '')).strip().lower() == 'april' and yr in str(r.get('Year', '')) and str(r.get('SR NO', '')).strip().split('.') == sr), None)
                        nv_rec = next((r for r in hw_records_list if str(r.get('Class', '')).strip().lower() == cls.lower() and str(r.get('Month', '')).strip().lower() == 'november' and yr in str(r.get('Year', '')) and str(r.get('SR NO', '')).strip().split('.') == sr), None)
                        
                        h_ap = str(ap_rec.get('Height_cm', '---')).strip() if ap_rec else "---"
                        w_ap = str(ap_rec.get('Weight_kg', '---')).strip() if ap_rec else "---"
                        h_nv = str(nv_rec.get('Height_cm', '---')).strip() if nv_rec else "---"
                        w_nv = str(nv_rec.get('Weight_kg', '---')).strip() if nv_rec else "---"
                        
                        try:
                            net_h = float(h_nv) - float(h_ap) if h_ap != "---" and h_nv != "---" else 0.0
                            net_w = float(w_nv) - float(w_ap) if w_ap != "---" and w_nv != "---" else 0.0
                            h_growth = f"+{net_h:.1f} cm" if net_h >= 0 else f"{net_h:.1f} cm"
                            w_growth = f"+{net_w:.1f} kg" if net_w >= 0 else f"{net_w:.1f} kg"
                        except:
                            h_growth, w_growth = "---", "---"
                            
                        table_data_matrix.append([
                            Paragraph(sr, td_norm), Paragraph(name, td_bold), Paragraph(f_name, td_norm),
                            Paragraph(h_ap, td_norm), Paragraph(w_ap, td_norm),
                            Paragraph(h_nv, td_norm), Paragraph(w_nv, td_norm),
                            Paragraph(f"<font color='green'><b>{h_growth}</b></font>" if '+' in h_growth else h_growth, td_bold),
                            Paragraph(f"<font color='green'><b>{w_growth}</b></font>" if '+' in w_growth else w_growth, td_bold)
                        ])
                    w_sr, w_nm, w_fn, w_box = 40, 140, 140, 70
                    col_widths_array = [w_sr, w_nm, w_fn, w_box, w_box, w_box, w_box, w_box, w_box]
                    
                # 📅 [भाग बी]: मासिक रिपोर्ट इंजन (अप्रैल या नवंबर wise - Windows + Android क्रॉस-प्लेटफ़ॉर्म)
                else:
                    out_pdf = f"{cls.replace(' ', '_')}_{mn}_Health_Register_{yr}.pdf"
                    doc = SimpleDocTemplate(out_pdf, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
                    pdf_story = []
                    
                    pdf_story.append(Spacer(1, 15))
                    pdf_story.append(Paragraph("<b>PRIMARY SCHOOL PANAUTA, WAZIRGANJ (BUDAUN)</b>", h_main))
                    pdf_story.append(Paragraph(f"<b>PHYSICAL DEVELOPMENT REGISTER  •  MONTH: {mn.upper()} {yr} &nbsp;|&nbsp; CLASS: {cls.upper()}</b>", h_sub))
                    pdf_story.append(Spacer(1, 15))
                    
                    headers_list = [Paragraph("<b>SR NO</b>", th_style), Paragraph("<b>STUDENT NAME</b>", th_style), Paragraph("<b>FATHER NAME</b>", th_style), Paragraph("<b>HEIGHT (in Centimeters)</b>", th_style), Paragraph("<b>WEIGHT (in Kilograms)</b>", th_style), Paragraph("<b>GROWTH REMARK / STATUS</b>", th_style)]
                    table_data_matrix = [headers_list]
                    
                    for s_row in class_students_list:
                        sr = str(s_row.get('SR NO', '')).strip().split('.')
                        name = str(s_row.get('NAME', '')).strip().upper()
                        f_name = str(s_row.get("FATHER'S NAME", '')).strip().upper()
                        
                        rec = next((r for r in hw_records_list if str(r.get('Class', '')).strip().lower() == cls.lower() and str(r.get('Month', '')).strip().lower() == mn.lower() and yr in str(r.get('Year', '')) and str(r.get('SR NO', '')).strip().split('.') == sr), None)
                        
                        h_val = str(rec.get('Height_cm', '---')).strip() if rec else "---"
                        w_val = str(rec.get('Weight_kg', '---')).strip() if rec else "---"
                        
                        try: remark = "NORMAL / HEALTHY" if float(w_val) > 15 else "UNDERWEIGHT" if w_val != "---" else "---"
                        except: remark = "---"
                        
                        table_data_matrix.append([Paragraph(sr, td_norm), Paragraph(name, td_bold), Paragraph(f_name, td_norm), Paragraph(h_val, td_norm), Paragraph(w_val, td_norm), Paragraph(remark, td_bold)])
                    
                    w_sr, w_nm, w_fn, w_val_b, w_rem = 45, 160, 160, 110, 137
                    col_widths_array = [w_sr, w_nm, w_fn, w_val_b, w_val_b, w_rem]
           
                t_register = Table(table_data_matrix, colWidths=col_widths_array, repeatRows=1)
                t_style_rules = [('GRID', (0,0), (-1,-1), 0.8, colors.HexColor("#595959")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BACKGROUND', (0,0), (-1,0), GREEN_THEME), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('ALIGN', (1,1), (2,-1), 'LEFT'), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]
                for i in range(1, len(table_data_matrix)):
                    if i % 2 == 0: t_style_rules.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GREEN))
                t_register.setStyle(TableStyle(t_style_rules))
                pdf_story.append(t_register); pdf_story.append(Spacer(1, 45))
                
                w_sig_panel = 390
                t_sig = Table([[Paragraph("________________________", td_bold), Paragraph("________________________", td_bold)], [Paragraph("CLASS TEACHER SIGNATURE", td_bold), Paragraph("MEDICAL OFFICER / HEADMASTER SIGN", td_bold)]], colWidths=[w_sig_panel, w_sig_panel])
                t_sig.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'BOTTOM'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
                pdf_story.append(t_sig)
                
                def draw_health_decorations(canvas, document):
                    canvas.saveState()
                    if os.path.exists(get_exe_safe_path("basic.png")): canvas.drawImage(get_exe_safe_path("basic.png"), 25, 520, width=52, height=52, mask='auto')
                    logo_p = get_exe_safe_path('logo.png')
                    if os.path.exists(logo_p):
                        canvas.drawImage(logo_p, 765, 520, width=52, height=52, mask='auto')
                        canvas.saveState(); canvas.setFillAlpha(0.06); canvas.drawImage(logo_p, 296, 145, width=250, height=250, mask='auto'); canvas.restoreState()
                    canvas.restoreState()
                    
                doc.build(pdf_story, onFirstPage=draw_health_decorations)
                self.popup('Success', f"PDF Health Register successfully compiled!\nSaved: {out_pdf}")
                open_file_cross_platform(out_pdf)
            except Exception as e: self.popup('Print Error', str(e))

        btn_print_m_h.bind(on_press=lambda x: action_health_pdf_engine(is_annual_mode=False))
        btn_print_a_h.bind(on_press=lambda x: action_health_pdf_engine(is_annual_mode=True))
        self.hw_tab_index = 0
        self.refresh_hw_grid()

    def refresh_hw_grid(self):
        self.hw_grid_box.clear_widgets(); self.hw_fields = {}; dynamic_inputs = []
        is_mob = (kivy_platform != 'win')
        sel_class = self.hw_class_spinner.text.strip().lower(); class_num = sel_class.replace('class', '').strip()
        m_name = self.hw_month_spinner.text.strip()
        y_name = self.hw_year_spinner.text.strip()
        current_period = f"{m_name}-{y_name}".lower().strip()
        hw_file = 'Height_Weight_Database.xlsx'
        
        scroll = ScrollView(do_scroll_x=True, do_scroll_y=True)
        grid_table = GridLayout(cols=4, spacing=(1, 1), size_hint_x=None if is_mob else 1, size_hint_y=None, padding=(2, 2, 2, 10))
        grid_table.bind(minimum_height=grid_table.setter('height'))
        
        col_w = [dp(60), dp(180), dp(125), dp(125)] if is_mob else [60, 220, 120, 120]
        if is_mob:
            grid_table.width = sum(col_w)
        grid_table.cols_minimum = {i: col_w[i] for i in range(4)}
        
        with grid_table.canvas.before:
            Color(0.35, 0.35, 0.35, 1)
            self.gt_hw_bg = Rectangle(size=grid_table.size, pos=grid_table.pos)
        grid_table.bind(size=lambda ins, val: setattr(self.gt_hw_bg, 'size', ins.size), pos=lambda ins, val: setattr(self.gt_hw_bg, 'pos', ins.pos))
        
        def make_hw_hdr_cell(txt, idx):
            lbl = Label(text=txt, color=(1,1,1,1), bold=True, font_size=sp(12) if is_mob else 11, size_hint_x=None if is_mob else 1, width=col_w[idx], size_hint_y=None, height=dp(42) if is_mob else 38, halign='center', valign='middle')
            with lbl.canvas.before:
                Color(0, 0.3, 0.5, 1)
                lbl.rect = Rectangle(size=lbl.size, pos=lbl.pos)
            lbl.bind(size=lambda ins, val: setattr(lbl.rect, 'size', ins.size), pos=lambda ins, val: setattr(lbl.rect, 'pos', ins.pos))
            return lbl

        headers_hw = ['SR NO', 'STUDENT NAME', 'HEIGHT (cm)', 'WEIGHT (kg)']
        for i, h in enumerate(headers_hw): 
            grid_table.add_widget(make_hw_hdr_cell(h, i))
            
        def make_hw_data_cell(txt, bg_col, idx):
            lbl = Label(text=str(txt), color=(0,0,0,1), font_size=sp(12) if is_mob else 11.5, size_hint_x=None if is_mob else 1, width=col_w[idx], size_hint_y=None, height=dp(42) if is_mob else 36, halign='center', valign='middle')
            with lbl.canvas.before:
                Color(*bg_col)
                lbl.rect = Rectangle(size=lbl.size, pos=lbl.pos)
            lbl.bind(size=lambda ins, val: setattr(lbl.rect, 'size', ins.size), pos=lambda ins, val: setattr(lbl.rect, 'pos', ins.pos))
            return lbl

        current_data = {}
        if os.path.exists(hw_file):
            try:
                df_old = pd.read_excel(hw_file, dtype=str)
                for _, r in df_old.iterrows():
                    s_id = str(r.get('SR NO', '')).strip().split('.')
                    r_class = str(r.get('Class', '')).strip().lower()
                    r_period = str(r.get('Month-Year', '')).strip().lower()
                    if r_class == sel_class and r_period == current_period:
                        current_data[s_id] = {'h': str(r.get('Height_cm', '')).strip(), 'w': str(r.get('Weight_kg', '')).strip()}
            except: pass
            
        if os.path.exists(EXCEL_FILE):
            try:
                df = pd.read_excel(EXCEL_FILE, dtype=str)
                r_idx = 0
                for idx, row in df.iterrows():
                    r_cls_raw = str(row.get('CLASS', '')).strip().lower()
                    r_cls_num = r_cls_raw.replace('class', '').strip()
                    if r_cls_raw != sel_class and r_cls_num != class_num:
                        continue

                    raw_sr = str(row.get('SR NO', '')).strip()
                    sr_val = raw_sr.split('.') if '.' in raw_sr else raw_sr
                    if not raw_sr or raw_sr == 'nan': sr_val = str(idx+1)
                    
                    name_val = str(row.get('NAME', '')).strip().upper() if pd.notna(row.get('NAME')) else "Unknown"
                    
                    initial_h = current_data.get(sr_val, {'h': '', 'w': ''})['h']
                    initial_w = current_data.get(sr_val, {'h': '', 'w': ''})['w']
                    
                    c_bg = (0.98, 0.98, 0.98, 1) if r_idx % 2 == 0 else (0.92, 0.94, 0.96, 1)
                    
                    grid_table.add_widget(make_hw_data_cell(sr_val, c_bg, 0))
                    grid_table.add_widget(make_hw_data_cell(name_val, c_bg, 1))
                    
                    h_in = CustomText(text=initial_h, size_hint_x=None if is_mob else 1, width=col_w[2], size_hint_y=None, height=dp(42) if is_mob else 36, halign='center', only_digits=True, hint_text="112")
                    w_in = CustomText(text=initial_w, size_hint_x=None if is_mob else 1, width=col_w[3], size_hint_y=None, height=dp(42) if is_mob else 36, halign='center', only_digits=True, hint_text="18")
                    
                    grid_table.add_widget(h_in); grid_table.add_widget(w_in)
                    dynamic_inputs = dynamic_inputs + [h_in, w_in]
                    self.hw_fields[sr_val] = (name_val, h_in, w_in)
                    r_idx += 1
            except Exception as e: print("Health Grid Loader Error:", str(e))
            
        scroll.add_widget(grid_table); self.hw_grid_box.add_widget(scroll)
        self.hw_master_tabs = [self.hw_class_spinner, self.hw_month_spinner, self.hw_year_spinner] + dynamic_inputs + [self.btn_save_hw, self.btn_back_hw]

    def save_hw_data(self, instance):
        if not self.hw_fields: return
        cls = self.hw_class_spinner.text.strip(); mn = self.hw_month_spinner.text.strip(); yr = self.hw_year_spinner.text.strip(); full_period = f"{mn}-{yr}"; hw_list = []
        
        for sr, widgets_tuple in self.hw_fields.items():
            name_val = str(widgets_tuple[0]).strip()
            h_text = str(widgets_tuple[1].text).strip()
            w_text = str(widgets_tuple[2].text).strip()
            
            hw_list.append({'Class': cls, 'Month': mn, 'Year': yr, 'SR NO': str(sr).strip(), 'NAME': name_val, 'Height_cm': h_text, 'Weight_kg': w_text, 'Month-Year': full_period})
        try:
            hw_file = 'Height_Weight_Database.xlsx'; new_df = pd.DataFrame(hw_list)
            if not os.path.exists(hw_file): 
                new_df.to_excel(hw_file, index=False)
            else:
                old_df = pd.read_excel(hw_file, dtype=str)
                kept_rows = []
                for _, r_old in old_df.iterrows():
                    r_c = str(r_old.get('Class', '')).strip().lower()
                    r_p = str(r_old.get('Month-Year', '')).strip().lower()
                    if not (r_c == cls.lower() and r_p == full_period.lower()):
                        kept_rows.append(dict(r_old))
                cleaned_old = pd.DataFrame(kept_rows, columns=old_df.columns)
                pd.concat([cleaned_old, new_df], ignore_index=True).to_excel(hw_file, index=False)
                
            self.popup('Success', f"{cls} का {full_period} स्वास्थ्य मापन रिकॉर्ड सफलतापूर्वक अपडेट सुरक्षित!"); self.refresh_hw_grid()
        except Exception as e: self.popup('Error', str(e))
  
    def load_attendance_view(self):
        self.content_area.clear_widgets(); self.current_view = 'attendance'; self.attendance_fields = {}
        is_mob = (kivy_platform != 'win')
        with self.content_area.canvas.before: Color(0.92, 0.92, 0.95, 1); self.c_bg = Rectangle(size=self.content_area.size, pos=self.content_area.pos)
        self.content_area.bind(size=lambda ins, val: setattr(self.c_bg, 'size', ins.size), pos=lambda ins, val: setattr(self.c_bg, 'pos', ins.pos))
        
        lbl_att = Label(text='STUDENT MONTHLY ATTENDANCE REGISTER', font_size=sp(17) if is_mob else 20, bold=True, color=(0,0.4,0.2,1), size_hint_y=None, height=dp(36) if is_mob else 40, halign='center', valign='middle')
        lbl_att.bind(size=lbl_att.setter('text_size'))
        self.content_area.add_widget(lbl_att)
        
        top_bar = GridLayout(cols=2 if is_mob else 8, size_hint_y=None, height=dp(185) if is_mob else 50, spacing=dp(8) if is_mob else 10, padding=5)
        top_bar.add_widget(Label(text='Select Class:', color=(0,0,0,1), bold=True, font_size=sp(13) if is_mob else 13))
        self.att_class_spinner = CustomSpinner(text='Class 1', values=('Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5'), size_hint_y=None, height=dp(42) if is_mob else 36)
        self.att_class_spinner.bind(text=lambda spinner, text: self.refresh_attendance_grid()); top_bar.add_widget(self.att_class_spinner)
        
        top_bar.add_widget(Label(text='Select Month:', color=(0,0,0,1), bold=True, font_size=sp(13) if is_mob else 13))
        self.att_month_spinner = CustomSpinner(text='September', values=('April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'January', 'February', 'March'), size_hint_y=None, height=dp(42) if is_mob else 36)
        self.att_month_spinner.bind(text=lambda spinner, text: self.refresh_attendance_grid()); top_bar.add_widget(self.att_month_spinner)
        
        top_bar.add_widget(Label(text='Select Year:', color=(0,0,0,1), bold=True, font_size=sp(13) if is_mob else 13))
        self.att_year_spinner = CustomSpinner(text='2026', values=('2026', '2027', '2028', '2029', '2030'), size_hint_y=None, height=dp(42) if is_mob else 36)
        self.att_year_spinner.bind(text=lambda spinner, text: self.refresh_attendance_grid()); top_bar.add_widget(self.att_year_spinner)
        
        btn_print_monthly_pdf = Button(text='PRINT MONTHLY', background_color=(0.85, 0.45, 0.0, 1), bold=True, font_size=sp(12) if is_mob else 11, size_hint_y=None, height=dp(42) if is_mob else 36)
        btn_print_annual_pdf = Button(text='PRINT ANNUAL', background_color=(0.05, 0.35, 0.6, 1), bold=True, font_size=sp(12) if is_mob else 11, size_hint_y=None, height=dp(42) if is_mob else 36)
        top_bar.add_widget(btn_print_monthly_pdf); top_bar.add_widget(btn_print_annual_pdf)
        
        self.content_area.add_widget(top_bar)
        self.attendance_grid_box = BoxLayout(orientation='vertical', padding=5); self.content_area.add_widget(self.attendance_grid_box)
        
        al = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 45, spacing=10)
        self.btn_save_att = CustomButton(text='SAVE ATTENDANCE RECORD', background_color=(0.05, 0.55, 0.25, 1), bold=True)
        self.btn_save_att.bind(on_press=self.save_attendance_data)
        self.btn_back_att = CustomButton(text='BACK', background_color=(0.7, 0.1, 0.1, 1), bold=True)
        self.btn_back_att.bind(on_press=lambda x: self.show_welcome()); al.add_widget(self.btn_save_att); al.add_widget(self.btn_back_att); self.content_area.add_widget(al)

        # 🖨️ 📈 [अचूक न्यूमेरिक-सिंक अटेंडेंस पीडीएफ इंजन - क्रॉस-प्लेटफ़ॉर्म]
        def action_attendance_pdf_engine(is_annual=False):
            sel_class = self.att_class_spinner.text.strip()
            sel_month = self.att_month_spinner.text.strip()
            sel_year = self.att_year_spinner.text.strip()
            
            student_file = 'Student_Database.xlsx'
            attendance_file = 'Attendance_Database.xlsx'
            if not os.path.exists(student_file) or not os.path.exists(attendance_file):
                self.popup('Alert', 'Student Database or Attendance Database file missing!'); return
            try:
                st_df = pd.read_excel(student_file, dtype=str)
                class_students_list = []
                for _, r_st in st_df.iterrows():
                    if str(r_st.get('CLASS', '')).strip().lower() == sel_class.lower():
                        class_students_list.append(dict(r_st))
                if not class_students_list:
                    self.popup('No Data', f'No student profiles found for {sel_class}'); return
                
                class_students_list.sort(key=lambda x: str(x.get('NAME', '')).upper())
                att_df = pd.read_excel(attendance_file, dtype=str)
                
                # 📅 सत्रवार एवं माहवार लाइव एक्सेल फ़िल्टर लॉजिक (Windows + Android क्रॉस-प्लेटफ़ॉर्म)
                filtered_att_rows = []
                if is_annual:
                    next_year = str(int(sel_year) + 1)
                    for _, r_att in att_df.iterrows():
                        r_c = str(r_att.get('Class', '')).strip().lower()
                        r_my = str(r_att.get('Month-Year', '')).strip()
                        if r_c == sel_class.lower() and (sel_year in r_my or next_year in r_my):
                            filtered_att_rows.append(dict(r_att))
                    heading_title_text = f"ANNUAL CONSOLIDATED ATTENDANCE LEDGER (SESSION : {sel_year}-{next_year})"
                    out_pdf_filename = f"{sel_class.replace(' ', '_')}_Annual_Attendance_{sel_year}_{next_year}.pdf"
                else:
                    target_my = f"{sel_month}-{sel_year}".lower().strip()
                    for _, r_att in att_df.iterrows():
                        r_c = str(r_att.get('Class', '')).strip().lower()
                        r_my = str(r_att.get('Month-Year', '')).strip().lower()
                        if r_c == sel_class.lower() and r_my == target_my:
                            filtered_att_rows.append(dict(r_att))
                    heading_title_text = f"MONTHLY ATTENDANCE REGISTER - {sel_month.upper()} {sel_year}"
                    out_pdf_filename = f"{sel_class.replace(' ', '_')}_Monthly_Attendance_{sel_month}_{sel_year}.pdf"
                
                attendance_rows_list = []
                for st_row in class_students_list:

                    raw_st_sr = str(st_row.get('SR NO', '')).strip()
                    clean_st_sr = raw_st_sr.split('.') if '.' in raw_st_sr else raw_st_sr
                    
                    raw_st_name = st_row.get('NAME', '')
                    name = str(raw_st_name).strip().upper() if not hasattr(raw_st_name, 'text') else "STUDENT"
                    
                    raw_f_name = st_row.get("FATHER'S NAME", '')
                    f_name = str(raw_f_name).strip().upper() if not hasattr(raw_f_name, 'text') else "FATHER"
                    
                    total_working_days = 0
                    present_count = 0
                    
                    if filtered_att_rows:
                        for r_rec in filtered_att_rows:
                            raw_rec_sr = str(r_rec.get('SR NO', r_rec.get('SR No', r_rec.get('sr no', '')))).strip()
                            clean_rec_sr = raw_rec_sr.split('.') if '.' in raw_rec_sr else raw_rec_sr
                            if clean_rec_sr == clean_st_sr:
                                w_val = r_rec.get('Month Working Days', r_rec.get('month working days', 0))
                                p_val = r_rec.get('Month Presents', r_rec.get('month presents', 0))
                                try:
                                    w_num = int(float(str(w_val).strip())) if pd.notna(w_val) and str(w_val).strip() != '' else 0
                                    p_num = int(float(str(p_val).strip())) if pd.notna(p_val) and str(p_val).strip() != '' else 0
                                    total_working_days += w_num
                                    present_count += p_num
                                except Exception:
                                    pass
                    
                    if total_working_days == 0:
                        if is_annual:
                            total_working_days, present_count = 72, 66
                        else:
                            try:
                                if clean_st_sr in self.attendance_fields and isinstance(self.attendance_fields[clean_st_sr], (tuple, list)):
                                    total_working_days = int(str(self.attendance_fields[clean_st_sr][1].text).strip()) if self.attendance_fields[clean_st_sr][1].text.strip() else 24
                                    present_count = int(str(self.attendance_fields[clean_st_sr][2].text).strip()) if self.attendance_fields[clean_st_sr][2].text.strip() else 22
                                else:
                                    total_working_days, present_count = 24, 22
                            except Exception:
                                total_working_days, present_count = 24, 22
                        
                    absent_count = total_working_days - present_count
                    if absent_count < 0: absent_count = 0
                    
                    per_val = (present_count / total_working_days) * 100 if total_working_days > 0 else 0
                    
                    attendance_rows_list.append({
                        "SR": clean_st_sr, "NAME": name, "FATHER": f_name,
                        "WORKING": str(total_working_days), "PRESENT": str(present_count),
                        "ABSENT": str(absent_count), "PER": f"{per_val:.1f}%"
                    })
                
                from reportlab.lib.pagesizes import landscape, A4
                from reportlab.platypus import SimpleDocTemplate, TableStyle, Table, Paragraph, Spacer
                from reportlab.lib.styles import ParagraphStyle
                from reportlab.lib import colors
                
                doc_pdf = SimpleDocTemplate(out_pdf_filename, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
                pdf_story = []
                
                BLUE_THEME = colors.HexColor("#0F4C81")
                LIGHT_BLUE = colors.HexColor("#EBF3FA")
                
                h_style_main = ParagraphStyle('H_M_A', fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=BLUE_THEME, alignment=1)
                h_style_sub = ParagraphStyle('H_S_A', fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=colors.black, alignment=1)
                th_style = ParagraphStyle('T_H_A', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.white, alignment=1)
                td_bold = ParagraphStyle('T_D_B_A', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.black, alignment=1)
                td_norm = ParagraphStyle('T_D_N_A', fontName='Helvetica', fontSize=9, leading=12, textColor=colors.black, alignment=1)
                
                pdf_story.append(Spacer(1, 15))
                pdf_story.append(Paragraph("<b>PRIMARY SCHOOL PANAUTA, WAZIRGANJ (BUDAUN)</b>", h_style_main))
                pdf_story.append(Paragraph(f"<b>{heading_title_text} &nbsp;|&nbsp; CLASS : {sel_class.upper()}</b>", h_style_sub))
                pdf_story.append(Spacer(1, 20))
                
                reg_headers = [Paragraph("<b>SR NO</b>", th_style), Paragraph("<b>STUDENT NAME</b>", th_style), Paragraph("<b>FATHER NAME</b>", th_style), Paragraph("<b>TOTAL WORKING DAYS</b>", th_style), Paragraph("<b>TOTAL PRESENT</b>", th_style), Paragraph("<b>TOTAL ABSENT</b>", th_style), Paragraph("<b>ATTENDANCE %</b>", th_style)]
                reg_table_rows = [reg_headers]
                
                for r_data in attendance_rows_list:
                    reg_table_rows.append([
                        Paragraph(r_data["SR"], td_norm), Paragraph(r_data["NAME"], td_bold), Paragraph(r_data["FATHER"], td_norm),
                        Paragraph(r_data["WORKING"], td_norm), Paragraph(f"<font color='green'><b>{r_data['PRESENT']}</b></font>", td_bold),
                        Paragraph(f"<font color='red'><b>{r_data['ABSENT']}</b></font>", td_norm), Paragraph(f"<b>{r_data['PER']}</b>", td_bold)
                    ])
                
                w_att_sr = 45
                w_att_name = 160
                w_att_father = 160
                w_att_work = 120
                w_att_pres = 100
                w_att_abs = 100
                w_att_per = 100
                col_w_list = [w_att_sr, w_att_name, w_att_father, w_att_work, w_att_pres, w_att_abs, w_att_per]
                
                t_register = Table(reg_table_rows, colWidths=col_w_list, repeatRows=1)
                t_reg_style = [('GRID', (0,0), (-1,-1), 0.8, colors.HexColor("#595959")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BACKGROUND', (0,0), (-1,0), BLUE_THEME), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('ALIGN', (1,1), (2,-1), 'LEFT'), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]
                
                for i in range(1, len(reg_table_rows)):
                    if i % 2 == 0: 
                        t_reg_style.append(('BACKGROUND', (0, i), (-1, i), LIGHT_BLUE))
                        
                t_register.setStyle(TableStyle(t_reg_style))
                pdf_story.append(t_register)
                pdf_story.append(Spacer(1, 45))
          
                w_sig_block = 390
                t_reg_sig = Table([
                    [Paragraph("________________________", td_bold), Paragraph("________________________", td_bold)], 
                    [Paragraph("CLASS TEACHER SIGNATURE", td_bold), Paragraph("HEADMASTER SEAL & SIGNATURE", td_bold)]
                ], colWidths=[w_sig_block, w_sig_block])
                
                t_reg_sig.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'BOTTOM'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
                pdf_story.append(t_reg_sig)
                
                def draw_attendance_canvas_decorations(canvas, document):
                    canvas.saveState()
                    if os.path.exists(get_exe_safe_path("basic.png")):
                        try: canvas.drawImage(get_exe_safe_path("basic.png"), 25, 520, width=52, height=52, mask='auto')
                        except: pass
                    logo_p = get_exe_safe_path("logo.png")
                    if os.path.exists(logo_p):
                        try: canvas.drawImage(logo_p, 765, 520, width=52, height=52, mask='auto')
                        except: pass
                        try:
                            canvas.saveState()
                            canvas.setFillAlpha(0.06) 
                            canvas.drawImage(logo_p, 296, 145, width=250, height=250, mask='auto')
                            canvas.restoreState()
                        except: pass
                    canvas.restoreState()
                
                doc_pdf.build(pdf_story, onFirstPage=draw_attendance_canvas_decorations)
                self.popup('Report Hub', f"Attendance Register PDF Generated Successfully!\nSaved as: {out_pdf_filename}")
                open_file_cross_platform(out_pdf_filename)
            except Exception as e: 
                self.popup('Print Error', str(e))

        btn_print_monthly_pdf.bind(on_press=lambda x: action_attendance_pdf_engine(is_annual=False))
        btn_print_annual_pdf.bind(on_press=lambda x: action_attendance_pdf_engine(is_annual=True))
        
        self.refresh_attendance_grid()

    def refresh_attendance_grid(self):
        self.attendance_grid_box.clear_widgets(); self.attendance_fields = {}; dynamic_inputs = []
        is_mob = (kivy_platform != 'win')
        selected_class = self.att_class_spinner.text.strip().lower(); class_num = selected_class.replace('class', '').strip()
        m_name = self.att_month_spinner.text.strip()
        y_name = self.att_year_spinner.text.strip()
        current_period = f"{m_name}-{y_name}".lower().strip()
        
        scroll = ScrollView(do_scroll_x=True, do_scroll_y=True)
        grid = GridLayout(cols=6, spacing=(dp(6), dp(6)) if is_mob else (8, 8), size_hint_x=None if is_mob else 1, size_hint_y=None, padding=dp(6) if is_mob else 10)
        grid.bind(minimum_height=grid.setter('height'))
        
        col_w_att = [dp(60), dp(175), dp(105), dp(105), dp(115), dp(115)] if is_mob else [60, 180, 110, 110, 120, 120]
        if is_mob:
            grid.width = sum(col_w_att)
        grid.cols_minimum = {i: col_w_att[i] for i in range(6)}

        headers = ['SR NO', 'STUDENT NAME', 'WORK DAYS', 'PRESENTS', 'CUM. WORK', 'CUM. PRES']
        for i, h in enumerate(headers):
            lbl_h = Label(text=h, bold=True, color=(0,0,0,1), size_hint_x=None if is_mob else 1, width=col_w_att[i], size_hint_y=None, height=dp(40) if is_mob else 36, font_size=sp(12) if is_mob else 11, halign='center', valign='middle')
            lbl_h.bind(size=lbl_h.setter('text_size'))
            grid.add_widget(lbl_h)
        
        prev_data = {}
        current_data = {}
        
        if os.path.exists(ATTENDANCE_FILE):
            try:
                df_old = pd.read_excel(ATTENDANCE_FILE, dtype=str)
                for _, r in df_old.iterrows():
                    s_id = str(r.get('SR NO', '')).strip().split('.')
                    r_class = str(r.get('Class', '')).strip().lower()
                    r_period = str(r.get('Month-Year', '')).strip().lower()
                    
                    try:
                        mw_val = int(float(str(r.get('Month Working Days', 0)).strip() or 0))
                        mp_val = int(float(str(r.get('Month Presents', 0)).strip() or 0))
                    except Exception:
                        mw_val, mp_val = 0, 0
                    
                    if r_class == selected_class and r_period == current_period:
                        current_data[s_id] = {'w': str(mw_val), 'p': str(mp_val)}
                        continue
                    if r_class == selected_class:
                        if s_id not in prev_data:
                            prev_data[s_id] = {'w': 0, 'p': 0}
                        prev_data[s_id]['w'] += mw_val
                        prev_data[s_id]['p'] += mp_val
            except Exception as e:
                print("UI History Reader Log:", str(e))
                
        if os.path.exists(EXCEL_FILE):
            try:
                df = pd.read_excel(EXCEL_FILE, dtype=str)
                for idx, row in df.iterrows():
                    r_cls_raw = str(row.get('CLASS', '')).strip().lower()
                    r_cls_num = r_cls_raw.replace('class', '').strip()
                    if r_cls_raw != selected_class and r_cls_num != class_num:
                        continue

                    raw_sr = str(row.get('SR NO', '')).strip()
                    sr_val = raw_sr.split('.')[0] if '.' in raw_sr else raw_sr
                    if not raw_sr or raw_sr == 'nan': sr_val = str(idx+1)
                    name_val = str(row.get('NAME', '')).strip().upper() if pd.notna(row.get('NAME')) else "Unknown"

                    lbl_sr = Label(text=sr_val, color=(0,0,0,1), size_hint_x=None if is_mob else 1, width=col_w_att[0], size_hint_y=None, height=dp(42) if is_mob else 36, font_size=sp(13) if is_mob else 13)
                    lbl_nm = Label(text=name_val, color=(0,0,0,1), size_hint_x=None if is_mob else 1, width=col_w_att[1], size_hint_y=None, height=dp(42) if is_mob else 36, font_size=sp(13) if is_mob else 13, halign='left', valign='middle')
                    lbl_nm.bind(size=lbl_nm.setter('text_size'))
                    grid.add_widget(lbl_sr); grid.add_widget(lbl_nm)
                    
                    if sr_val in current_data:
                        initial_mw = current_data[sr_val]['w']
                        initial_mp = current_data[sr_val]['p']
                    else:
                        initial_mw = ""
                        initial_mp = ""
                    
                    m_work = CustomText(text=initial_mw, size_hint_x=None if is_mob else 1, width=col_w_att[2], size_hint_y=None, height=dp(42) if is_mob else 36, font_size=sp(14) if is_mob else 14, halign='center', hint_text="0", only_digits=True)
                    m_pres = CustomText(text=initial_mp, size_hint_x=None if is_mob else 1, width=col_w_att[3], size_hint_y=None, height=dp(42) if is_mob else 36, font_size=sp(14) if is_mob else 14, halign='center', hint_text="0", only_digits=True)
                    
                    p_w = prev_data.get(sr_val, {'w': 0, 'p': 0})['w']
                    p_p = prev_data.get(sr_val, {'w': 0, 'p': 0})['p']
                    
                    try: curr_w_val = int(initial_mw) if initial_mw else 0
                    except: curr_w_val = 0
                    try: curr_p_val = int(initial_mp) if initial_mp else 0
                    except: curr_p_val = 0
                    
                    c_work = TextInput(text=str(p_w + curr_w_val), readonly=True, background_color=(0.95,1,0.95,1), halign='center', size_hint_x=None if is_mob else 1, width=col_w_att[4], size_hint_y=None, height=dp(42) if is_mob else 36, font_size=sp(14) if is_mob else 14)
                    c_pres = TextInput(text=str(p_p + curr_p_val), readonly=True, background_color=(0.95,1,0.95,1), halign='center', size_hint_x=None if is_mob else 1, width=col_w_att[5], size_hint_y=None, height=dp(42) if is_mob else 36, font_size=sp(14) if is_mob else 14)
                    
                    def make_update(mw=m_work, mp=m_pres, cw=c_work, cp=c_pres, pw=p_w, pp=p_p):
                        def up_func(instance, value):
                            try: val_w = int(mw.text.strip()) if mw.text.strip() else 0
                            except: val_w = 0
                            try: val_p = int(mp.text.strip()) if mp.text.strip() else 0
                            except: val_p = 0
                            cw.text = str(pw + val_w); cp.text = str(pp + val_p)
                        return up_func
                        
                    m_work.bind(text=make_update()); m_pres.bind(text=make_update())
                    grid.add_widget(m_work); grid.add_widget(m_pres); grid.add_widget(c_work); grid.add_widget(c_pres)
                    
                    dynamic_inputs = dynamic_inputs + [m_work, m_pres]
                    self.attendance_fields[sr_val] = (name_val, m_work, m_pres, c_work, c_pres)
            except Exception as grid_err:
                print("Grid View Creation Interruption:", str(grid_err))
                
        scroll.add_widget(grid); self.attendance_grid_box.add_widget(scroll)
        self.attendance_master_tabs = [self.att_class_spinner, self.att_month_spinner, self.att_year_spinner] + dynamic_inputs + [self.btn_save_att, self.btn_back_att]

    def save_attendance_data(self, instance):
        if not self.attendance_fields: return
        cls_name = str(self.att_class_spinner.text).strip()
        m_name = str(self.att_month_spinner.text).strip()
        y_name = str(self.att_year_spinner.text).strip()
        full_period = f"{m_name}-{y_name}"
        att_list = []
        
        for sr, widgets_tuple in self.attendance_fields.items():
            try:
                name_val = str(widgets_tuple[0]).strip()
                mw_text = str(widgets_tuple[1].text).strip()
                mp_text = str(widgets_tuple[2].text).strip()
                cw_text = str(widgets_tuple[3].text).strip()
                cp_text = str(widgets_tuple[4].text).strip()
            except Exception:
                name_val = "STUDENT"; mw_text = "24"; mp_text = "22"; cw_text = "24"; cp_text = "22"
            
            att_list.append({
                'Month': m_name,
                'SR NO': str(sr).strip(), 
                'NAME': name_val, 
                'Month Working Days': mw_text, 
                'Month Presents': mp_text, 
                'Cumulative Work Days': cw_text, 
                'Cumulative Presents': cp_text,
                'Class': cls_name,
                'Month-Year': full_period
            })       
        try:
            new_df = pd.DataFrame(att_list)
            
            if not os.path.exists(ATTENDANCE_FILE): 
                new_df.to_excel(ATTENDANCE_FILE, index=False)
            else:
                old_df = pd.read_excel(ATTENDANCE_FILE, dtype=str)
                target_class = cls_name.lower().strip()
                target_period = full_period.lower().strip()
                target_month = m_name.lower().strip()

                kept_rows = []
                for _, r_old in old_df.iterrows():
                    r_c = str(r_old.get('Class', '')).strip().lower()
                    r_my = str(r_old.get('Month-Year', '')).strip().lower()
                    r_m = str(r_old.get('Month', '')).strip().lower()

                    is_match_new = (r_c == target_class and r_my == target_period)
                    is_match_old = (r_m == target_month and (r_c == target_class or r_c in ['', 'nan', 'none']))
                    if not (is_match_new or is_match_old):
                        kept_rows.append(dict(r_old))

                cleaned_old_df = pd.DataFrame(kept_rows, columns=old_df.columns)
                pd.concat([cleaned_old_df, new_df], ignore_index=True).to_excel(ATTENDANCE_FILE, index=False)
                
            self.popup('Success', f"{cls_name} का {full_period} उपस्थिति रिकॉर्ड सफलतापूर्वक अपडेट सुरक्षित!")
            self.refresh_attendance_grid()
        except Exception as e: 
            self.popup('Error', f"Database Update Interruption: {str(e)}")

    def load_marks_entry_view(self):
        self.content_area.clear_widgets(); self.current_view = 'marks'
        is_mob = (kivy_platform != 'win')
        with self.content_area.canvas.before: Color(0.85, 0.95, 1.0, 1); self.c_bg = Rectangle(size=self.content_area.size, pos=self.content_area.pos)
        self.content_area.bind(size=lambda ins, val: setattr(self.c_bg, 'size', ins.size), pos=lambda ins, val: setattr(self.c_bg, 'pos', ins.pos))
        
        lbl_mk = Label(text='STUDENT MARKS ENTRY DASHBOARD', font_size=sp(17) if is_mob else 24, bold=True, color=(0,0,0.5,1), size_hint_y=None, height=dp(36) if is_mob else 40, halign='center', valign='middle')
        lbl_mk.bind(size=lbl_mk.setter('text_size'))
        self.content_area.add_widget(lbl_mk)
        
        top_bar = GridLayout(cols=2 if is_mob else 6, size_hint_y=None, height=dp(145) if is_mob else 60, spacing=dp(8) if is_mob else 10, padding=5)
        top_bar.add_widget(Label(text='SR No:', color=(0,0,0,1), bold=True, font_size=sp(13) if is_mob else 13))
        self.marks_sr = CustomText(multiline=False, size_hint_y=None, height=dp(42) if is_mob else 36, font_size=sp(15) if is_mob else 16, only_digits=True); top_bar.add_widget(self.marks_sr)
        
        top_bar.add_widget(Label(text='Select Class:', color=(0,0,0,1), bold=True, font_size=sp(13) if is_mob else 13))
        self.class_spinner = CustomSpinner(text='Choose Class', values=('Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5'), size_hint_y=None, height=dp(42) if is_mob else 36)
        self.class_spinner.bind(text=self.on_marks_setup_change); top_bar.add_widget(self.class_spinner)
        
        top_bar.add_widget(Label(text='Exam Type:', color=(0,0,0,1), bold=True, font_size=sp(13) if is_mob else 13))
        self.exam_spinner = CustomSpinner(text='Choose Exam', values=('Satra Pariksha 1', 'Half Yearly', 'Satra Pariksha 2', 'Annual Exam'), size_hint_y=None, height=dp(42) if is_mob else 36)
        self.exam_spinner.bind(text=self.on_marks_setup_change); top_bar.add_widget(self.exam_spinner); self.content_area.add_widget(top_bar)
        
        self.dynamic_marks_box = BoxLayout(orientation='vertical', padding=dp(5) if is_mob else 10); self.content_area.add_widget(self.dynamic_marks_box)
        
        al = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 45, spacing=10)
        self.btn_save_marks = CustomButton(text='SAVE MARKS', background_color=(0.9, 0.1, 0.1, 1), bold=True)
        self.btn_save_marks.bind(on_press=self.save_student_marks)
        self.btn_back_marks = CustomButton(text='BACK', background_color=(0.0, 0.0, 0.8, 1), bold=True)
        self.btn_back_marks.bind(on_press=lambda x: self.show_welcome()); al.add_widget(self.btn_save_marks); al.add_widget(self.btn_back_marks); self.content_area.add_widget(al)
        self.marks_master_tabs = [self.marks_sr, self.class_spinner, self.exam_spinner, self.btn_save_marks, self.btn_back_marks]; self.marks_tab_index = 0
        Window.unbind(on_key_down=self.on_keyboard_down) if hasattr(self, 'on_key_down') else None; Window.bind(on_key_down=self.on_keyboard_down)
        Clock.schedule_once(lambda dt: self.marks_master_tabs[0].set_visual_focus(True) if self.marks_master_tabs else None, 0.2)

    def on_marks_setup_change(self, spinner, text):
        cls_txt = self.class_spinner.text; ex_txt = self.exam_spinner.text
        if cls_txt == 'Choose Class' or ex_txt == 'Choose Exam': return
        is_mob = (kivy_platform != 'win')
        self.dynamic_marks_box.clear_widgets(); self.marks_fields = {}; dynamic_inputs = []
        o_max, w_max = 0, 0
        if ex_txt in ['Satra Pariksha 1', 'Satra Pariksha 2']:
            if cls_txt == 'Class 1': o_max, w_max = 10, 0
            elif cls_txt == 'Class 2': o_max, w_max = 5, 5
            else: o_max, w_max = 3, 7
        elif ex_txt == 'Half Yearly':
            if cls_txt == 'Class 1': o_max, w_max = 30, 0
            elif cls_txt == 'Class 2': o_max, w_max = 15, 15
            else: o_max, w_max = 9, 21
        elif ex_txt == 'Annual Exam':
            if cls_txt == 'Class 1': o_max, w_max = 50, 0
            elif cls_txt == 'Class 2': o_max, w_max = 25, 25
            else: o_max, w_max = 15, 35
            
        scroll = ScrollView(do_scroll_x=True, do_scroll_y=True)
        grid = GridLayout(cols=4, spacing=(dp(8), dp(10)) if is_mob else (12, 12), size_hint_y=None, padding=dp(6) if is_mob else 10)
        grid.bind(minimum_height=grid.setter('height'))
        
        hdr_h = dp(40) if is_mob else 36
        hdr_fs = sp(11.5) if is_mob else 13
        grid.add_widget(Label(text='SUBJECT', bold=True, color=(0,0,0,1), size_hint_y=None, height=hdr_h, font_size=hdr_fs))
        grid.add_widget(Label(text=f'ORAL ({o_max})', bold=True, color=(0,0,0,1), size_hint_y=None, height=hdr_h, font_size=hdr_fs))
        grid.add_widget(Label(text=f'WRIT ({w_max})', bold=True, color=(0,0,0,1), size_hint_y=None, height=hdr_h, font_size=hdr_fs))
        grid.add_widget(Label(text='TOTAL', bold=True, color=(0,0,0,1), size_hint_y=None, height=hdr_h, font_size=hdr_fs))
        
        subjects = ['Hindi', 'English', 'Maths'] if cls_txt in ['Class 1', 'Class 2'] else ['Hindi', 'English', 'Maths', 'EVS', 'Sanskrit', 'Art', 'Naitik Shiksha']
        row_h = dp(44) if is_mob else 36
        for sub in subjects:
            lbl_s = Label(text=sub, color=(0,0.2,0.4,1), bold=True, size_hint_y=None, height=row_h, font_size=sp(12.5) if is_mob else 13, halign='left', valign='middle')
            lbl_s.bind(size=lbl_s.setter('text_size'))
            grid.add_widget(lbl_s)
            
            oral_in = CustomText(multiline=False, text='0', size_hint_y=None, height=row_h, halign='center')
            writ_in = CustomText(multiline=False, text='0', size_hint_y=None, height=row_h, halign='center')
            total_box = TextInput(multiline=False, text='0', readonly=True, background_color=(0.90, 0.98, 0.92, 1), halign='center', size_hint_y=None, height=row_h, font_size=sp(14) if is_mob else 14)
            
            def update_total(instance, value, o=oral_in, w=writ_in, t=total_box):
                try: t.text = str(int((float(o.text) if o.text.strip() else 0)+(float(w.text) if w.text.strip() and w.text!='N/A' else 0)))
                except: t.text = '0'
            oral_in.bind(text=update_total); dynamic_inputs.append(oral_in)
            if cls_txt == 'Class 1': writ_in.text = 'N/A'; writ_in.disabled = True; writ_in.background_color = (0.85, 0.85, 0.85, 1)
            else: writ_in.bind(text=update_total); dynamic_inputs.append(writ_in)
            grid.add_widget(oral_in); grid.add_widget(writ_in); grid.add_widget(total_box); self.marks_fields[f"{sub}_Oral"] = oral_in; self.marks_fields[f"{sub}_Written"] = writ_in
        scroll.add_widget(grid); self.dynamic_marks_box.add_widget(scroll)
        self.marks_master_tabs = [self.marks_sr, self.class_spinner, self.exam_spinner] + dynamic_inputs + [self.btn_save_marks, self.btn_back_marks]
        try: self.marks_tab_index = self.marks_master_tabs.index(spinner)
        except: self.marks_tab_index = 0

    def save_student_marks(self, instance):
        if self.marks_sr.text.strip() == "" or self.class_spinner.text == 'Choose Class': return
        marks_data = {'SR No': [self.marks_sr.text], 'Class': [self.class_spinner.text], 'Exam Type': [self.exam_spinner.text]}
        for k, v in self.marks_fields.items(): marks_data[k] = [v.text]
        try:
            new_df = pd.DataFrame(marks_data)
            if not os.path.exists(MARKS_FILE): new_df.to_excel(MARKS_FILE, index=False)
            else: pd.concat([pd.read_excel(MARKS_FILE), new_df], ignore_index=True).to_excel(MARKS_FILE, index=False)
            self.popup('Success', 'Student exam marks have been saved to Excel database!'); self.load_marks_entry_view()
        except Exception as e: self.popup('Error', str(e))

    # 🍱 [भाग 1]: मुख्य एमडीएम व्यू लॉन्चर (मोबाइल Portrait स्क्रॉल बार सहित)
    def load_mdm_view(self):
        self.content_area.clear_widgets(); self.current_view = 'mdm'; self.mdm_fields = {}
        is_mob = (kivy_platform != 'win')
        with self.content_area.canvas.before:
            Color(0.95, 0.94, 0.91, 1); self.c_bg = Rectangle(size=self.content_area.size, pos=self.content_area.pos)
        self.content_area.bind(size=lambda ins, val: setattr(self.c_bg, 'size', ins.size), pos=lambda ins, val: setattr(self.c_bg, 'pos', ins.pos))
        
        top_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 45, spacing=dp(8) if is_mob else 10, padding=4)
        if is_mob:
            top_bar.size_hint_x = None
            top_bar.bind(minimum_width=top_bar.setter('width'))

        self.btn_daily_food = Button(text='🍱 OPTION 1: DAILY FOOD', background_color=(0.1, 0.45, 0.3, 1), bold=True, font_size=sp(12.5) if is_mob else 13.5, size_hint_x=None if is_mob else 1, width=dp(185))
        self.btn_bank_ledger = Button(text='💰 OPTION 2: BANK LEDGER', background_color=(0.6, 0.35, 0.05, 1), bold=True, font_size=sp(12.5) if is_mob else 13.5, size_hint_x=None if is_mob else 1, width=dp(195))
        self.btn_ration_stock = Button(text='🌾 OPTION 3: RATION STOCK', background_color=(0.1, 0.4, 0.6, 1), bold=True, font_size=sp(12.5) if is_mob else 13.5, size_hint_x=None if is_mob else 1, width=dp(195))
        
        self.btn_daily_food.bind(on_press=lambda x: self.switch_mdm_sub_view('daily'))
        self.btn_bank_ledger.bind(on_press=lambda x: self.switch_mdm_sub_view('ledger'))
        self.btn_ration_stock.bind(on_press=lambda x: self.switch_mdm_sub_view('ration'))
        
        top_bar.add_widget(self.btn_daily_food); top_bar.add_widget(self.btn_bank_ledger); top_bar.add_widget(self.btn_ration_stock)
        if is_mob:
            top_scroll = ScrollView(size_hint=(1, None), height=dp(52), do_scroll_x=True, do_scroll_y=False)
            top_scroll.add_widget(top_bar)
            self.content_area.add_widget(top_scroll)
        else:
            self.content_area.add_widget(top_bar)
        
        self.mdm_sub_box = BoxLayout(orientation='vertical', padding=5)
        self.content_area.add_widget(self.mdm_sub_box)
        self.switch_mdm_sub_view('daily')

    def switch_mdm_sub_view(self, view_type):
        self.current_mdm_sub_view_type = str(view_type).strip().lower()
        self.mdm_sub_box.clear_widgets()
        is_mob = (kivy_platform != 'win')
        
        if view_type == 'daily':
            ctrl_bar = GridLayout(cols=2 if is_mob else 5, size_hint_y=None, height=dp(145) if is_mob else 50, spacing=dp(8) if is_mob else 10, padding=5)
            ctrl_bar.add_widget(Label(text='Select Month:', color=(0,0,0,1), bold=True, font_size=sp(13) if is_mob else 13))
            self.mdm_month_spinner = CustomSpinner(text='February', values=('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'), size_hint_y=None, height=dp(42) if is_mob else 36)
            self.mdm_month_spinner.bind(text=lambda sp, tx: [setattr(self, 'mdm_popup_focus_index', 3), self.refresh_mdm_grid()]); ctrl_bar.add_widget(self.mdm_month_spinner)
            
            ctrl_bar.add_widget(Label(text='Select Year:', color=(0,0,0,1), bold=True, font_size=sp(13) if is_mob else 13))
            self.mdm_year_spinner = CustomSpinner(text='2026', values=[str(x) for x in range(2020, 2036)], size_hint_y=None, height=dp(42) if is_mob else 36)
            self.mdm_year_spinner.bind(text=lambda sp, tx: [setattr(self, 'mdm_popup_focus_index', 4), self.refresh_mdm_grid()]); ctrl_bar.add_widget(self.mdm_year_spinner)
            
            self.btn_print_m_food = Button(text='🖨️ PRINT FOOD MPR', background_color=(0.85, 0.45, 0.0, 1), bold=True, font_size=sp(12) if is_mob else 11, size_hint_y=None, height=dp(42) if is_mob else 36)
            btn_print_m_food_func = getattr(self, 'generate_mdm_monthly_mpr_pdf', None) or getattr(self, 'generate_mdm_pdf_report', lambda: None)
            self.btn_print_m_food.bind(on_press=lambda x: btn_print_m_food_func())
            ctrl_bar.add_widget(self.btn_print_m_food); self.mdm_sub_box.add_widget(ctrl_bar)
            
            self.mdm_grid_box = BoxLayout(orientation='vertical', padding=5); self.mdm_sub_box.add_widget(self.mdm_grid_box)
            
            al = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 45, spacing=10)
            self.btn_save_mdm = CustomButton(text='LOCK & SAVE MDM', background_color=(0.02, 0.45, 0.2, 1), bold=True)
            self.btn_save_mdm.bind(on_press=self.save_mdm_data)
            self.btn_back_mdm = CustomButton(text='BACK', background_color=(0.7, 0.1, 0.1, 1), bold=True)
            self.btn_back_mdm.bind(on_press=lambda x: self.show_welcome())
            al.add_widget(self.btn_save_mdm); al.add_widget(self.btn_back_mdm)
            self.mdm_sub_box.add_widget(al)
            
            self.refresh_mdm_grid()
            
        elif view_type == 'ledger':
            self.load_mdm_financial_ledger_ui()
            for child in self.mdm_sub_box.children:
                if isinstance(child, BoxLayout) and len(child.children) == 3:
                    self.btn_print_m_ledg = child.children[2]
                    self.btn_print_a_ledg = child.children[1]
                    self.btn_save_tx = child.children[0]
            
        elif view_type == 'ration':
            self.load_mdm_ration_stock_ui()
            for child in self.mdm_sub_box.children:
                if isinstance(child, BoxLayout) and len(child.children) == 1:
                    self.btn_save_rat = child.children[0]
        # ====================================================================
        mdm_all_controls_chain = []
        
        # 1️⃣ सबसे पहले टॉप नेविगेशन बार के ३ मुख्य ऑप्शन्स हुक
        if hasattr(self, 'btn_daily_food') and self.btn_daily_food: mdm_all_controls_chain.append(self.btn_daily_food)
        if hasattr(self, 'btn_bank_ledger') and self.btn_bank_ledger: mdm_all_controls_chain.append(self.btn_bank_ledger)
        if hasattr(self, 'btn_ration_stock') and self.btn_ration_stock: mdm_all_controls_chain.append(self.btn_ration_stock)
        
        # 🔷 केस ए: यदि दैनिक भोजन वितरण (Option 1) सक्रिय है
        if self.current_mdm_sub_view_type == 'daily':
            if hasattr(self, 'mdm_month_spinner'): mdm_all_controls_chain.append(self.mdm_month_spinner)
            if hasattr(self, 'mdm_year_spinner'): mdm_all_controls_chain.append(self.mdm_year_spinner)
            if hasattr(self, 'btn_print_m_food'): mdm_all_controls_chain.append(self.btn_print_m_food)
            if hasattr(self, 'mdm_seq') and self.mdm_seq:
                # डुप्लीकेट क्लीनर फ़िल्टर
                for item_w in self.mdm_seq:
                    if item_w not in mdm_all_controls_chain and item_w != getattr(self,'btn_save_mdm',None) and item_w != getattr(self,'btn_back_mdm',None):
                        mdm_all_controls_chain.append(item_w)
            if hasattr(self, 'btn_save_mdm'): mdm_all_controls_chain.append(self.btn_save_mdm)
            if hasattr(self, 'btn_back_mdm'): mdm_all_controls_chain.append(self.btn_back_mdm)
            
        # 🔷 केस बी: यदि बैंक पासबुक वित्तीय लेज़र (Option 2) सक्रिय है
        elif self.current_mdm_sub_view_type == 'ledger':
            if hasattr(self, 'f_tx_type') and self.f_tx_type: mdm_all_controls_chain.append(self.f_tx_type)
            if hasattr(self, 'f_rec_date') and self.f_rec_date: mdm_all_controls_chain.append(self.f_rec_date)
            if hasattr(self, 'f_open_bal') and self.f_open_bal: mdm_all_controls_chain.append(self.f_open_bal)
            if hasattr(self, 'f_rec_amt') and self.f_rec_amt: mdm_all_controls_chain.append(self.f_rec_amt)
            if hasattr(self, 'f_exp_date') and self.f_exp_date: mdm_all_controls_chain.append(self.f_exp_date)
            if hasattr(self, 'f_exp_amt') and self.f_exp_amt: mdm_all_controls_chain.append(self.f_exp_amt)
            if hasattr(self, 'f_cheque') and self.f_cheque: mdm_all_controls_chain.append(self.f_cheque)
            if hasattr(self, 'btn_print_m_ledg') and self.btn_print_m_ledg: mdm_all_controls_chain.append(self.btn_print_m_ledg)
            if hasattr(self, 'btn_print_a_ledg') and self.btn_print_a_ledg: mdm_all_controls_chain.append(self.btn_print_a_ledg)
            if hasattr(self, 'btn_save_tx') and self.btn_save_tx: mdm_all_controls_chain.append(self.btn_save_tx)
            
        # 🔷 केस सी: यदि राशन स्टॉक बहीखाता (Option 3) सक्रिय है
        elif self.current_mdm_sub_view_type == 'ration':
            if hasattr(self, 'r_month') and self.r_month: mdm_all_controls_chain.append(self.r_month)
            if hasattr(self, 'r_year') and self.r_year: mdm_all_controls_chain.append(self.r_year)
            if hasattr(self, 'r_op_wheat') and self.r_op_wheat: mdm_all_controls_chain.append(self.r_op_wheat)
            if hasattr(self, 'r_op_rice') and self.r_op_rice: mdm_all_controls_chain.append(self.r_op_rice)
            if hasattr(self, 'r_rec_wheat') and self.r_rec_wheat: mdm_all_controls_chain.append(self.r_rec_wheat)
            if hasattr(self, 'r_rec_rice') and self.r_rec_rice: mdm_all_controls_chain.append(self.r_rec_rice)
            if hasattr(self, 'r_con_wheat') and self.r_con_wheat: mdm_all_controls_chain.append(self.r_con_wheat)
            if hasattr(self, 'r_con_rice') and self.r_con_rice: mdm_all_controls_chain.append(self.r_con_rice)
            if hasattr(self, 'btn_save_rat') and self.btn_save_rat: mdm_all_controls_chain.append(self.btn_save_rat)

                    # 👑 [डायनामिक फ़ोकस मेन्टेन पैच]: स्पिनर बदलने पर कर्सर को पीछे भागने से रोकने का शत-प्रतिशत अचूक फिक्स
        self.mdm_seq = mdm_all_controls_chain
        
        # वर्तमान खुले विजेट को ढूंढना कि पहले कर्सर कहाँ था
        old_focused_text = ""
        if hasattr(self, 'current_mdm_focused_widget_type'):
            old_focused_text = self.current_mdm_focused_widget_type
            
        # डिफ़ॉल्ट रूप से शुरुआत 0
        target_restore_idx = 0
        
        # यदि यूज़र ने महीना बदला था, तो कर्सर को वापस महीना (Index 3) या साल (Index 4) पर ही रोक कर रखना
        for idx, w in enumerate(self.mdm_seq):
            if old_focused_text == "month" and ('Spinner' in str(type(w)) or 'CustomSpinner' in str(type(w))) and getattr(w, 'values', []) and 'January' in str(w.values):
                target_restore_idx = idx; break
            elif old_focused_text == "year" and ('Spinner' in str(type(w)) or 'CustomSpinner' in str(type(w))) and getattr(w, 'values', []) and '2026' in str(w.values):
                target_restore_idx = idx; break
                
                # ✨ [अल्टीमेट री-डायरेक्टर बाईपास पैच]: मान बदलने पर यह इंडेक्स को स्थिर रखेगा जिससे लगातार महीने बदलेंगे!
        if hasattr(self, 'mdm_popup_focus_index') and self.mdm_popup_focus_index is not None:
            if self.mdm_popup_focus_index >= len(self.mdm_seq):
                self.mdm_popup_focus_index = 3 if self.current_mdm_focused_widget_type == "month" else (4 if self.current_mdm_focused_widget_type == "year" else 0)
        else:
            self.mdm_popup_focus_index = 0

        def update_mdm_global_view_colors():
            for w in self.mdm_seq:
                if hasattr(w, 'background_color'): w.background_color = (1, 1, 1, 1)
                if hasattr(w, 'set_visual_focus'): w.set_visual_focus(False)
                elif hasattr(w, 'state'): w.state = 'normal'
                if ('Spinner' in str(type(w)) or 'CustomSpinner' in str(type(w))) and hasattr(w, 'dismiss'):
                    w.dismiss(); w.is_open = False
                    
            if self.mdm_popup_focus_index < len(self.mdm_seq):
                target_w = self.mdm_seq[self.mdm_popup_focus_index]
                target_type = str(type(target_w))
                if hasattr(target_w, 'set_visual_focus'): target_w.set_visual_focus(True)
                if 'CustomText' in target_type or 'TextInput' in target_type:
                    target_w.background_color = (0.9, 1.0, 0.9, 1); target_w.focus = True
                elif 'Button' in target_type or 'CustomButton' in target_type: target_w.state = 'down'

        def mdm_universal_keyboard_hook(window_instance, key, scancode, codepoint, modifiers):
            if self.current_view != 'mdm': return False
            num_w = len(self.mdm_seq)
            current_w = self.mdm_seq[self.mdm_popup_focus_index] if self.mdm_popup_focus_index < num_w else None
            
            if key in (273, 274, 275, 276):
                if current_w and ('CustomSpinner' in str(type(current_w)) or 'Spinner' in str(type(current_w))):
                    vals = current_w.values
                    s_idx = vals.index(current_w.text) if current_w.text in vals else -1
                    shift_val = -1 if key in (273, 276) else 1
                    current_w.text = vals[(s_idx + shift_val) % len(vals)]; return True
                shift = -1 if key in (273, 276) else 1
                self.mdm_popup_focus_index = (self.mdm_popup_focus_index + shift) % num_w
                update_mdm_global_view_colors(); return True
                
            elif key in (9, 13, 271):
                if key in (13, 271) and current_w:
                    btn_txt = getattr(current_w, 'text', '').upper()
                    if 'OPTION 1' in btn_txt: 
                        self.switch_mdm_sub_view('daily'); return True
                    elif 'OPTION 2' in btn_txt: 
                        self.switch_mdm_sub_view('ledger'); return True
                    elif 'OPTION 3' in btn_txt: 
                        self.switch_mdm_sub_view('ration'); return True
                
                if current_w and ('Button' in str(type(current_w)) or 'CustomButton' in str(type(current_w))):
                    current_w.state = 'normal'
                    if key in (13, 271): 
                        current_w.trigger_action(); return True
                
                shift = -1 if 'shift' in modifiers else 1
                self.mdm_popup_focus_index = (self.mdm_popup_focus_index + shift) % num_w
                update_mdm_global_view_colors(); return True
            return False

        from kivy.core.window import Window
        Window.bind(on_key_down=mdm_universal_keyboard_hook)
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: update_mdm_global_view_colors(), 0.05)

    def refresh_mdm_grid(self):
        self.mdm_grid_box.clear_widgets(); self.mdm_fields = {}; dynamic_inputs = []
        is_mob = (kivy_platform != 'win')
        m_name = self.mdm_month_spinner.text; y_val = int(self.mdm_year_spinner.text)
        
        months_days = {'January':31, 'February':29 if (y_val%4==0 and (y_val%100!=0 or y_val%400==0)) else 28, 'March':31, 'April':30, 'May':31, 'June':30, 'July':31, 'August':31, 'September':30, 'October':31, 'November':30, 'December':31}
        total_days = months_days.get(m_name, 31)
        months_num = {'January':1, 'February':2, 'March':3, 'April':4, 'May':5, 'June':6, 'July':7, 'August':8, 'September':9, 'October':10, 'November':11, 'December':12}
        m_num = months_num[m_name]
        
        scroll = ScrollView(do_scroll_x=True, do_scroll_y=True)
        grid = GridLayout(cols=11, spacing=(dp(4), dp(6)) if is_mob else (4, 6), size_hint_x=None if is_mob else 1, size_hint_y=None, padding=5)
        grid.bind(minimum_height=grid.setter('height'))
        
        col_w_mdm = [dp(80), dp(145), dp(75), dp(75), dp(75), dp(75), dp(75), dp(75), dp(80), dp(80), dp(85)] if is_mob else [75, 130, 65, 65, 65, 65, 65, 65, 70, 70, 80]
        if is_mob:
            grid.width = sum(col_w_mdm)
        grid.cols_minimum = {i: col_w_mdm[i] for i in range(11)}

        headers = ['DATE/DAY', 'MDM MENU\nCHART', 'TOTAL\nPRES', 'MDM\nOPTED', 'HAND\nWASH', 'WEDS\nMILK', 'MON\nFRUITS', 'SUPPL\nRCVD', 'WHEAT\n(KG)', 'RICE\n(KG)', 'CONV\nCOST']
        for i, h in enumerate(headers):
            lbl_h = Label(text=h, bold=True, color=(0,0,0,1), size_hint_x=None if is_mob else 1, width=col_w_mdm[i], size_hint_y=None, height=dp(48) if is_mob else 45, font_size=sp(11.5) if is_mob else 11, halign='center', valign='middle')
            lbl_h.bind(size=lbl_h.setter('text_size'))
            grid.add_widget(lbl_h)
            
        menu_chart_map = {0: 'Roti + Veg + Fruits', 1: 'Rice + Daal', 2: 'Tahri + Milk', 3: 'Roti + Veg', 4: 'Tahri', 5: 'Rice + Daal'}
        self.t_pres_list, self.m_opt_list, self.h_wash_list, self.fruits_list, self.suppl_list = [], [], [], [], []
        self.wheat_list, self.rice_list, self.cost_list = [], [], []
        row_h_mdm = dp(42) if is_mob else 38

        for d in range(1, total_days + 1):
            from datetime import datetime
            try: dt_obj = datetime(y_val, m_num, d); day_name = dt_obj.strftime('%A'); w_day = dt_obj.weekday()
            except: day_name = "Sunday"; w_day = 6
            if w_day == 6:
                grid.add_widget(Label(text=f"{d} (Sun)", color=(0.8,0.1,0.1,1), size_hint_x=None if is_mob else 1, width=col_w_mdm[0], size_hint_y=None, height=row_h_mdm, font_size=sp(12) if is_mob else 11, bold=True))
                grid.add_widget(Label(text='SUNDAY - CLOSED', color=(0.4,0.4,0.4,1), size_hint_x=None if is_mob else 1, width=col_w_mdm[1], size_hint_y=None, height=row_h_mdm, font_size=sp(12) if is_mob else 14, bold=True))
                for i in range(2, 11): grid.add_widget(Label(text='---', color=(0.7,0.7,0.7,1), size_hint_x=None if is_mob else 1, width=col_w_mdm[i], size_hint_y=None, height=row_h_mdm))
                continue
            
            grid.add_widget(Label(text=f"{d} ({day_name[:3]})", color=(0,0,0,1), size_hint_x=None if is_mob else 1, width=col_w_mdm[0], size_hint_y=None, height=row_h_mdm, font_size=sp(12) if is_mob else 11, bold=True))
            lbl_menu = Label(text=menu_chart_map.get(w_day, 'Special Meal'), color=(0.02, 0.3, 0.6, 1), size_hint_x=None if is_mob else 1, width=col_w_mdm[1], size_hint_y=None, height=row_h_mdm, font_size=sp(11.5) if is_mob else 11, bold=True, halign='center', valign='middle')
            lbl_menu.bind(size=lbl_menu.setter('text_size'))
            grid.add_widget(lbl_menu)
            
            t_pres = CustomText(text='0', size_hint_x=None if is_mob else 1, width=col_w_mdm[2], size_hint_y=None, height=row_h_mdm, halign='center', only_digits=True, max_chars=4)
            m_opt = CustomText(text='0', size_hint_x=None if is_mob else 1, width=col_w_mdm[3], size_hint_y=None, height=row_h_mdm, halign='center', only_digits=True, max_chars=4)
            h_wash = CustomText(text='0', size_hint_x=None if is_mob else 1, width=col_w_mdm[4], size_hint_y=None, height=row_h_mdm, halign='center', only_digits=True, max_chars=4)
            
            if w_day==2:
                milk_chk = CustomButton(text='YES', background_color=(0.7,0.1,0.1,1), size_hint_x=None if is_mob else 1, width=col_w_mdm[5], size_hint_y=None, height=row_h_mdm, font_size=sp(12) if is_mob else 11, bold=True)
            else:
                milk_chk = Label(text='---', size_hint_x=None if is_mob else 1, width=col_w_mdm[5], size_hint_y=None, height=row_h_mdm)
                
            fruit_lbl = Label(text='70' if w_day==0 else '0', color=(0,0,0,1), bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[6], size_hint_y=None, height=row_h_mdm)

            if w_day==3:
                suppl_in = CustomText(text='0', size_hint_x=None if is_mob else 1, width=col_w_mdm[7], size_hint_y=None, height=row_h_mdm, halign='center', only_digits=True, max_chars=4)
            else:
                suppl_in = CustomText(text='---', disabled=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[7], size_hint_y=None, height=row_h_mdm, halign='center')

            wheat_lbl = Label(text='0.00', color=(0,0,0,1), bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[8], size_hint_y=None, height=row_h_mdm)
            rice_lbl = Label(text='0.00', color=(0,0,0,1), bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[9], size_hint_y=None, height=row_h_mdm)
            cost_lbl = Label(text='0.00', color=(0,0,0,1), bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[10], size_hint_y=None, height=row_h_mdm)
            
            if w_day == 2:
                milk_chk.bind(on_press=lambda btn: [setattr(btn, 'text', 'YES' if btn.text=='NO' else 'NO'), setattr(btn, 'background_color', (0.05,0.5,0.1,1) if btn.text=='YES' else (0.7,0.1,0.1,1))])

            def make_live_calc(tp=t_pres, mo=m_opt, hw=h_wash, sp=suppl_in, fl=fruit_lbl, wl=wheat_lbl, rl=rice_lbl, cl=cost_lbl, wd=w_day):
                def calc_func(instance, value):
                    if tp.text.strip() == "0":
                        mo.text = "HOLIDAY"; hw.text = "0"; wl.text = "0.00"; rl.text = "0.00"; cl.text = "0.00"
                        if hasattr(sp, 'text'): sp.text = "0"
                        if wd == 0: fl.text = "0"
                        self.update_mdm_grand_totals(); return
                    if mo.text == "HOLIDAY": mo.text = "0"
                    try: count = int(mo.text.strip()) if mo.text.strip() else 0
                    except: count = 0
                    if wd == 0: fl.text = str(count)
                    total_grain = (count * 100) / 1000.0
                    if wd == 0 or wd == 3: wl.text = f"{total_grain:.2f}"; rl.text = "0.00"
                    else: wl.text = "0.00"; rl.text = f"{total_grain:.2f}"
                    cl.text = f"{(count * 6.78):.2f}"
                    self.update_mdm_grand_totals()
                return calc_func
                
            m_opt.bind(text=make_live_calc()); t_pres.bind(text=make_live_calc()); h_wash.bind(text=make_live_calc())
            grid.add_widget(t_pres); grid.add_widget(m_opt); grid.add_widget(h_wash); grid.add_widget(milk_chk)
            grid.add_widget(fruit_lbl); grid.add_widget(suppl_in); grid.add_widget(wheat_lbl); grid.add_widget(rice_lbl); grid.add_widget(cost_lbl)
            
            dynamic_inputs.append(t_pres)
            dynamic_inputs.append(m_opt)
            dynamic_inputs.append(h_wash)
            if w_day == 2: dynamic_inputs.append(milk_chk)
            if w_day == 3: dynamic_inputs.append(suppl_in)
            
            self.mdm_fields[str(d)] = (t_pres, m_opt, h_wash, milk_chk, fruit_lbl, wheat_lbl, rice_lbl, cost_lbl, day_name, suppl_in)
            self.t_pres_list.append(t_pres); self.m_opt_list.append(m_opt); self.h_wash_list.append(h_wash)
            self.fruits_list.append(fruit_lbl); self.suppl_list.append(suppl_in)
            self.wheat_list.append(wheat_lbl); self.rice_list.append(rice_lbl); self.cost_list.append(cost_lbl)
            
        grid.add_widget(Label(text="TOTAL", color=(0.8,0.1,0.1,1), font_size=sp(12) if is_mob else 12, bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[0], size_hint_y=None, height=row_h_mdm))
        grid.add_widget(Label(text="Monthly Sum", color=(0,0,0,1), font_size=sp(11.5) if is_mob else 11, bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[1], size_hint_y=None, height=row_h_mdm))
        self.tot_pres_lbl = Label(text="0", color=(0,0,0,1), bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[2], size_hint_y=None, height=row_h_mdm)
        self.tot_opt_lbl = Label(text="0", color=(0,0,0,1), bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[3], size_hint_y=None, height=row_h_mdm)
        self.tot_wash_lbl = Label(text="0", color=(0,0,0,1), bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[4], size_hint_y=None, height=row_h_mdm)
        grid.add_widget(self.tot_pres_lbl); grid.add_widget(self.tot_opt_lbl); grid.add_widget(self.tot_wash_lbl)
        grid.add_widget(Label(text="---", size_hint_x=None if is_mob else 1, width=col_w_mdm[5], size_hint_y=None, height=row_h_mdm))
        self.tot_fruit_lbl = Label(text="0", color=(0,0,0,1), bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[6], size_hint_y=None, height=row_h_mdm)
        self.tot_suppl_lbl = Label(text="0", color=(0,0,0,1), bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[7], size_hint_y=None, height=row_h_mdm)
        self.tot_wheat_lbl = Label(text="0.00", color=(0,0,0,1), bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[8], size_hint_y=None, height=row_h_mdm)
        self.tot_rice_lbl = Label(text="0.00", color=(0,0,0,1), bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[9], size_hint_y=None, height=row_h_mdm)
        self.tot_cost_lbl = Label(text="0.00", color=(0.8,0.1,0.1,1), bold=True, size_hint_x=None if is_mob else 1, width=col_w_mdm[10], size_hint_y=None, height=row_h_mdm)

        grid.add_widget(self.tot_fruit_lbl)
        grid.add_widget(self.tot_suppl_lbl)
        grid.add_widget(self.tot_wheat_lbl)
        grid.add_widget(self.tot_rice_lbl)
        grid.add_widget(self.tot_cost_lbl)
        
        scroll.add_widget(grid)
        self.mdm_grid_box.add_widget(scroll)
        self.update_mdm_grand_totals()
        
        mdm_all_controls_chain = []
        if not hasattr(self, 'current_mdm_sub_view_type'):
            self.current_mdm_sub_view_type = 'daily'
            
        if self.current_mdm_sub_view_type == 'daily':
            if hasattr(self, 'btn_daily_food'): mdm_all_controls_chain.append(self.btn_daily_food)
            if hasattr(self, 'btn_bank_ledger'): mdm_all_controls_chain.append(self.btn_bank_ledger)
            if hasattr(self, 'btn_ration_stock'): mdm_all_controls_chain.append(self.btn_ration_stock)
            if hasattr(self, 'mdm_month_spinner'): mdm_all_controls_chain.append(self.mdm_month_spinner)
            if hasattr(self, 'mdm_year_spinner'): mdm_all_controls_chain.append(self.mdm_year_spinner)
            if hasattr(self, 'btn_print_m_food'): mdm_all_controls_chain.append(self.btn_print_m_food)
            mdm_all_controls_chain.extend(dynamic_inputs)
            if hasattr(self, 'btn_save_mdm'): mdm_all_controls_chain.append(self.btn_save_mdm)
            if hasattr(self, 'btn_back_mdm'): mdm_all_controls_chain.append(self.btn_back_mdm)
            
        elif self.current_mdm_sub_view_type == 'ledger':
            if hasattr(self, 'btn_daily_food'): mdm_all_controls_chain.append(self.btn_daily_food)
            if hasattr(self, 'btn_bank_ledger'): mdm_all_controls_chain.append(self.btn_bank_ledger)
            if hasattr(self, 'btn_ration_stock'): mdm_all_controls_chain.append(self.btn_ration_stock)
            if hasattr(self, 'f_tx_type'): mdm_all_controls_chain.append(self.f_tx_type)
            if hasattr(self, 'f_rec_date'): mdm_all_controls_chain.append(self.f_rec_date)
            if hasattr(self, 'f_open_bal'): mdm_all_controls_chain.append(self.f_open_bal)
            if hasattr(self, 'f_rec_amt'): mdm_all_controls_chain.append(self.f_rec_amt)
            if hasattr(self, 'f_exp_date'): mdm_all_controls_chain.append(self.f_exp_date)
            if hasattr(self, 'f_exp_amt'): mdm_all_controls_chain.append(self.f_exp_amt)
            if hasattr(self, 'f_cheque'): mdm_all_controls_chain.append(self.f_cheque)
            if hasattr(self, 'btn_print_m_ledg'): mdm_all_controls_chain.append(self.btn_print_m_ledg)
            if hasattr(self, 'btn_print_a_ledg'): mdm_all_controls_chain.append(self.btn_print_a_ledg)
            if hasattr(self, 'btn_save_tx'): mdm_all_controls_chain.append(self.btn_save_tx)
            
        elif self.current_mdm_sub_view_type == 'ration':
            if hasattr(self, 'btn_daily_food'): mdm_all_controls_chain.append(self.btn_daily_food)
            if hasattr(self, 'btn_bank_ledger'): mdm_all_controls_chain.append(self.btn_bank_ledger)
            if hasattr(self, 'btn_ration_stock'): mdm_all_controls_chain.append(self.btn_ration_stock)
            if hasattr(self, 'r_month'): mdm_all_controls_chain.append(self.r_month)
            if hasattr(self, 'r_year'): mdm_all_controls_chain.append(self.r_year)
            if hasattr(self, 'r_op_wheat'): mdm_all_controls_chain.append(self.r_op_wheat)
            if hasattr(self, 'r_op_rice'): mdm_all_controls_chain.append(self.r_op_rice)
            if hasattr(self, 'r_rec_wheat'): mdm_all_controls_chain.append(self.r_rec_wheat)
            if hasattr(self, 'r_rec_rice'): mdm_all_controls_chain.append(self.r_rec_rice)
            if hasattr(self, 'r_con_wheat'): mdm_all_controls_chain.append(self.r_con_wheat)
            if hasattr(self, 'r_con_rice'): mdm_all_controls_chain.append(self.r_con_rice)
            if hasattr(self, 'btn_save_rat'): mdm_all_controls_chain.append(self.btn_save_rat)
            
        self.mdm_seq = mdm_all_controls_chain
        self.mdm_popup_focus_index = 0

        def update_mdm_local_widget_colors():
            for w in self.mdm_seq:
                if hasattr(w, 'background_color'): w.background_color = (1, 1, 1, 1)
                if hasattr(w, 'set_visual_focus'): w.set_visual_focus(False)
                elif hasattr(w, 'state'): w.state = 'normal'
                if ('Spinner' in str(type(w)) or 'CustomSpinner' in str(type(w))) and hasattr(w, 'dismiss'):
                    w.dismiss(); w.is_open = False
                    
            if self.mdm_popup_focus_index < len(self.mdm_seq):
                target_w = self.mdm_seq[self.mdm_popup_focus_index]
                target_type = str(type(target_w))
                if hasattr(target_w, 'set_visual_focus'): 
                    target_w.set_visual_focus(True)
                if 'CustomText' in target_type or 'TextInput' in target_type:
                    target_w.background_color = (0.9, 1.0, 0.9, 1); target_w.focus = True
                elif 'Button' in target_type or 'CustomButton' in target_type: 
                    target_w.state = 'down'

        def mdm_local_keyboard_hook(window_instance, key, scancode, codepoint, modifiers):
            if self.current_view != 'mdm': return False
            num_w = len(self.mdm_seq)
            current_w = self.mdm_seq[self.mdm_popup_focus_index] if self.mdm_popup_focus_index < num_w else None
            
            if key in (273, 274, 275, 276):
                if current_w and ('CustomSpinner' in str(type(current_w)) or 'Spinner' in str(type(current_w))):
                    vals = current_w.values
                    s_idx = vals.index(current_w.text) if current_w.text in vals else -1
                    shift_val = -1 if key in (273, 276) else 1
                    current_w.text = vals[(s_idx + shift_val) % len(vals)]
                    return True
                shift = -1 if key in (273, 276) else 1
                self.mdm_popup_focus_index = (self.mdm_popup_focus_index + shift) % num_w
                update_mdm_local_widget_colors(); return True
                
            elif key in (9, 13, 271):
                # यदि यूज़र टॉप नेविगेशन बार के ३ मुख्य विकल्पों पर खड़े होकर Enter दबाता है, तो रीयल-टाइम व्यू मोड को स्विच करना
                if key in (13, 271) and current_w:
                    btn_txt = getattr(current_w, 'text', '').upper()
                    if 'OPTION 1' in btn_txt:
                        self.current_mdm_sub_view_type = 'daily'; self.switch_mdm_sub_view('daily'); return True
                    elif 'OPTION 2' in btn_txt:
                        self.current_mdm_sub_view_type = 'ledger'; self.switch_mdm_sub_view('ledger'); return True
                    elif 'OPTION 3' in btn_txt:
                        self.current_mdm_sub_view_type = 'ration'; self.switch_mdm_sub_view('ration'); return True
                
                if current_w and ('Button' in str(type(current_w)) or 'CustomButton' in str(type(current_w))):
                    current_w.state = 'normal'
                    if key in (13, 271): current_w.trigger_action(); return True
                
                shift = -1 if 'shift' in modifiers else 1
                self.mdm_popup_focus_index = (self.mdm_popup_focus_index + shift) % num_w
                update_mdm_local_widget_colors(); return True
            return False

        from kivy.core.window import Window
        Window.bind(on_key_down=mdm_local_keyboard_hook)
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: update_mdm_local_widget_colors(), 0.05)

        self.update_mdm_grand_totals()

    def update_mdm_grand_totals(self):
        try:
            self.tot_pres_lbl.text = str(sum(int(x.text.strip()) for x in self.t_pres_list if x.text.strip() and x.text != "HOLIDAY"))
            self.tot_opt_lbl.text = str(sum(int(x.text.strip()) for x in self.m_opt_list if x.text.strip() and x.text != "HOLIDAY"))
            self.tot_wash_lbl.text = str(sum(int(x.text.strip()) for x in self.h_wash_list if x.text.strip() and x.text != "HOLIDAY"))
            self.tot_suppl_lbl.text = str(sum(int(x.text.strip()) for x in self.suppl_list if hasattr(x, 'text') and x.text.strip() and x.text != "---" and x.text != "HOLIDAY"))
            self.tot_fruit_lbl.text = str(sum(int(x.text.strip()) for x in self.fruits_list if x.text.strip() and x.text != "HOLIDAY"))
            self.tot_wheat_lbl.text = f"{sum(float(x.text.strip()) for x in self.wheat_list if x.text.strip() and x.text != 'HOLIDAY'):.2f}"
            self.tot_rice_lbl.text = f"{sum(float(x.text.strip()) for x in self.rice_list if x.text.strip() and x.text != 'HOLIDAY'):.2f}"
            self.tot_cost_lbl.text = f"Rs.{sum(float(x.text.strip()) for x in self.cost_list if x.text.strip() and x.text != 'HOLIDAY'):.2f}"
        except: pass

    def save_mdm_data(self, instance):
        if not self.mdm_fields: return
        m_name = self.mdm_month_spinner.text; y_name = self.mdm_year_spinner.text; mdm_records = []
        for d, (tp, mo, hw, mk, fl, wl, rl, cl, dy, sp) in self.mdm_fields.items():
            if dy == "Sunday": continue
            m_text = mk.text if hasattr(mk, 'text') else "NO"
            mdm_records.append({'Month-Year': f"{m_name}-{y_name}", 'Date': d, 'Day': dy, 'Total Present': tp.text, 'MDM Opted': mo.text, 'Hand Wash': hw.text, 'Milk Distributed': m_text, 'Fruit Distributed': fl.text, 'Wheat_KG': wl.text, 'Rice_KG': rl.text, 'Conversion Cost': cl.text.replace('Rs.', '')})
        try:
            mdm_file = 'MDM_Database.xlsx'; new_df = pd.DataFrame(mdm_records)
            if not os.path.exists(mdm_file): new_df.to_excel(mdm_file, index=False)
            else: pd.concat([pd.read_excel(mdm_file), new_df], ignore_index=True).to_excel(mdm_file, index=False)
            self.popup('Success', f'MDM Register saved successfully!'); self.show_welcome()
        except Exception as e: self.popup('Storage Error', str(e))
    
    def load_mdm_financial_ledger_ui(self):
        self.mdm_sub_box.clear_widgets()
        MDM_ACC_FILE = os.path.join(os.getcwd(), 'MDM_Account_Database.xlsx')
        
        from kivy.uix.widget import Widget
        from kivy.graphics import Color, Rectangle
        
        last_final_balance = 0.00
        if os.path.exists(MDM_ACC_FILE):
            try:
                df_b = pd.read_excel(MDM_ACC_FILE, dtype=str)
                for _, r_b in df_b.iterrows():
                    val_fb = str(r_b.get('Final Balance', '')).strip()
                    if val_fb and val_fb.lower() != 'nan':
                        last_final_balance = float(val_fb)
            except Exception: 
                pass

        is_mob = (kivy_platform != 'win')
        from datetime import datetime
        current_date_str = datetime.now().strftime("%d-%m-%Y")

        # 📝 [भाग ए]: वित्तीय ट्रांजैक्शन इनपुट फॉर्म पैनल (मोबाइल पर 2 कॉलम ताकि बॉक्स न पिचकें)
        form_grid = GridLayout(cols=2 if is_mob else 4, size_hint_y=None, height=dp(365) if is_mob else 155, spacing=dp(8) if is_mob else 14, padding=dp(6) if is_mob else 10)
        
        lbl_fs = sp(12.5) if is_mob else 13
        inp_h = dp(42) if is_mob else 36
        inp_fs = sp(14) if is_mob else 14
        inp_pad = [dp(6), dp(6)] if is_mob else [6, 6]

        form_grid.add_widget(Label(text='Transaction Type:', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.f_tx_type = CustomSpinner(text='Conversion Cost', values=('Conversion Cost', 'Fruits Cost', 'MME', 'Nutrition Supplement Cost', 'Interest', 'LPG Subsidy', 'Others'), size_hint_y=None, height=inp_h)
        form_grid.add_widget(self.f_tx_type)
        
        form_grid.add_widget(Label(text='Amount Received Date:', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.f_rec_date = TextInput(text=current_date_str, multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, padding=inp_pad)
        form_grid.add_widget(self.f_rec_date)
        
        form_grid.add_widget(Label(text='Opening Balance (Rs):', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.f_open_bal = TextInput(text=f"{last_final_balance:.2f}", multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, padding=inp_pad)
        form_grid.add_widget(self.f_open_bal)
        
        form_grid.add_widget(Label(text='Amount Received (Rs):', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.f_rec_amt = TextInput(text='0.00', multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, padding=inp_pad)
        form_grid.add_widget(self.f_rec_amt)
        
        form_grid.add_widget(Label(text='Expenditure Date:', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.f_exp_date = TextInput(text=current_date_str, multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, padding=inp_pad)
        form_grid.add_widget(self.f_exp_date)
        
        form_grid.add_widget(Label(text='Expenditure Amount (Rs):', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.f_exp_amt = TextInput(text='0.00', multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, padding=inp_pad)
        form_grid.add_widget(self.f_exp_amt)
        
        form_grid.add_widget(Label(text='Cheque / Reference No:', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.f_cheque = TextInput(text='', multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, padding=inp_pad, hint_text="Enter Number Here")
        form_grid.add_widget(self.f_cheque)
        self.mdm_sub_box.add_widget(form_grid)
        
        self.mdm_sub_box.add_widget(Widget(size_hint_y=None, height=dp(10) if is_mob else 50))
        
        # 🎛️ ३ मुख्य बटन्स एक्शन बार पैनल
        btn_action_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 45, spacing=dp(10) if is_mob else 15, padding=(dp(4), 0) if is_mob else (20, 0, 20, 0))
        if is_mob:
            btn_action_bar.size_hint_x = None
            btn_action_bar.bind(minimum_width=btn_action_bar.setter('width'))

        btn_print_m_ledg = Button(text='🖨️ PRINT MONTHLY', background_color=(0.1, 0.55, 0.4, 1), bold=True, font_size=sp(12) if is_mob else 12, size_hint_x=None if is_mob else 1, width=dp(165))
        btn_print_a_ledg = Button(text='🏛️ PRINT ANNUAL', background_color=(0.05, 0.35, 0.6, 1), bold=True, font_size=sp(12) if is_mob else 12, size_hint_x=None if is_mob else 1, width=dp(165))
        btn_save_tx = Button(text='💾 LOCK & SAVE', background_color=(0.05, 0.55, 0.2, 1), bold=True, font_size=sp(12) if is_mob else 12, size_hint_x=None if is_mob else 1, width=dp(165))
        
        btn_print_m_ledg.bind(on_press=lambda x: self.generate_mdm_ledger_report_pdf(is_annual=False))
        btn_print_a_ledg.bind(on_press=lambda x: self.generate_mdm_ledger_report_pdf(is_annual=True))
        btn_save_tx.bind(on_press=self.action_process_and_save_mdm_ledger)
        
        btn_action_bar.add_widget(btn_print_m_ledg); btn_action_bar.add_widget(btn_print_a_ledg); btn_action_bar.add_widget(btn_save_tx)
        if is_mob:
            act_scroll = ScrollView(size_hint=(1, None), height=dp(52), do_scroll_x=True, do_scroll_y=False)
            act_scroll.add_widget(btn_action_bar)
            self.mdm_sub_box.add_widget(act_scroll)
        else:
            self.mdm_sub_box.add_widget(btn_action_bar)
        
        self.mdm_sub_box.add_widget(Widget(size_hint_y=None, height=dp(8) if is_mob else 30))
        self.f_tx_type.bind(text=lambda spinner, text: self.refresh_mdm_head_opening_balance(text))
        
        # 📜 [भाग बी - लाइव ग्रिड लाइन्स फिक्स तालिका]
        scroll = ScrollView(do_scroll_x=True, do_scroll_y=True)
        grid_table = GridLayout(cols=10, spacing=(1, 1), size_hint_x=None if is_mob else 1, size_hint_y=None, padding=(5, 5, 5, 6))
        grid_table.bind(minimum_height=grid_table.setter('height'))
        
        col_w_ledg = [dp(140), dp(95), dp(90), dp(95), dp(95), dp(95), dp(95), dp(105), dp(95), dp(60)] if is_mob else [130, 85, 80, 85, 85, 85, 85, 95, 85, 50]
        if is_mob:
            grid_table.width = sum(col_w_ledg)
        grid_table.cols_minimum = {i: col_w_ledg[i] for i in range(10)}

        with grid_table.canvas.before:
            Color(0.35, 0.35, 0.35, 1)
            self.gt_bg = Rectangle(size=grid_table.size, pos=grid_table.pos)
        grid_table.bind(size=lambda ins, val: setattr(self.gt_bg, 'size', ins.size), pos=lambda ins, val: setattr(self.gt_bg, 'pos', ins.pos))
        
        def make_cell_lbl(txt, bg_col, col_idx, is_bold=False, txt_col=(0,0,0,1)):
            lbl = Label(text=txt, color=txt_col, bold=is_bold, font_size=sp(11.5) if is_mob else 11, size_hint_x=None if is_mob else 1, width=col_w_ledg[col_idx], size_hint_y=None, height=dp(38) if is_mob else 36, halign='center', valign='middle')
            with lbl.canvas.before:
                Color(*bg_col)
                lbl.rect = Rectangle(size=lbl.size, pos=lbl.pos)
            lbl.bind(size=lambda ins, val: setattr(lbl.rect, 'size', ins.size), pos=lambda ins, val: setattr(lbl.rect, 'pos', ins.pos))
            return lbl

        headers_ledger = ['TX TYPE', 'REC DATE', 'OPENING', 'RECEIVED', 'TOTAL BAL', 'EXP DATE', 'EXPENSE', 'CHEQUE NO', 'FINAL BAL', 'ACTION']
        for i, h in enumerate(headers_ledger): 
            grid_table.add_widget(make_cell_lbl(h, (0.05, 0.25, 0.45, 1), i, is_bold=True, txt_col=(1,1,1,1)))
            
        if os.path.exists(MDM_ACC_FILE):
            try:
                df_ledger = pd.read_excel(MDM_ACC_FILE, dtype=str)
                for idx, row in df_ledger.iterrows():
                    c_bg = (0.98, 0.97, 0.94, 1) if idx % 2 == 0 else (0.94, 0.95, 0.92, 1)
                    
                    grid_table.add_widget(make_cell_lbl(str(row.get('Transaction Type','')), c_bg, 0))
                    grid_table.add_widget(make_cell_lbl(str(row.get('Received Date','')), c_bg, 1))
                    grid_table.add_widget(make_cell_lbl(f"{float(row.get('Opening Balance',0) or 0):.2f}", c_bg, 2))
                    grid_table.add_widget(make_cell_lbl(f"+{float(row.get('Amount Received',0) or 0):.2f}", c_bg, 3, is_bold=True, txt_col=(0, 0.5, 0, 1)))
                    grid_table.add_widget(make_cell_lbl(f"{float(row.get('Total Balance',0) or 0):.2f}", c_bg, 4))
                    grid_table.add_widget(make_cell_lbl(str(row.get('Expenditure Date','')), c_bg, 5))
                    grid_table.add_widget(make_cell_lbl(f"-{float(row.get('Expenditure Amount',0) or 0):.2f}", c_bg, 6, is_bold=True, txt_col=(0.75, 0, 0, 1)))
                    grid_table.add_widget(make_cell_lbl(str(row.get('Cheque No','')), c_bg, 7))
                    grid_table.add_widget(make_cell_lbl(f"{float(row.get('Final Balance',0) or 0):.2f}", c_bg, 8, is_bold=True, txt_col=(0, 0.35, 0.7, 1)))
                    
                    btn_cell = BoxLayout(size_hint_x=None if is_mob else 1, width=col_w_ledg[9], size_hint_y=None, height=dp(38) if is_mob else 36, padding=3)
                    with btn_cell.canvas.before:
                        Color(*c_bg)
                        btn_cell.rect = Rectangle(size=btn_cell.size, pos=btn_cell.pos)
                    btn_cell.bind(size=lambda ins, val: setattr(btn_cell.rect, 'size', ins.size), pos=lambda ins, val: setattr(btn_cell.rect, 'pos', ins.pos))
                    
                    btn_del = Button(text='🗑', size_hint=(1, 1), background_color=(0.75, 0.1, 0.1, 1))
                    btn_del.bind(on_press=lambda x, row_idx=idx: self.delete_mdm_ledger_row(row_idx))
                    btn_cell.add_widget(btn_del)
                    grid_table.add_widget(btn_cell)
            except Exception: 
                pass
            
        scroll.add_widget(grid_table); self.mdm_sub_box.add_widget(scroll)
        self.refresh_mdm_head_opening_balance(self.f_tx_type.text)

    def refresh_mdm_head_opening_balance(self, selected_head):
        MDM_ACC_FILE = 'MDM_Account_Database.xlsx'
        head_balance = 0.00
        if os.path.exists(MDM_ACC_FILE):
            try:
                df_b = pd.read_excel(MDM_ACC_FILE, dtype=str)
                for _, r_b in df_b.iterrows():
                    if str(r_b.get('Transaction Type', '')).strip().lower() == selected_head.strip().lower():
                        val_fb = str(r_b.get('Final Balance', '')).strip()
                        if val_fb and val_fb.lower() != 'nan':
                            head_balance = float(val_fb)
            except Exception: pass
        self.f_open_bal.text = f"{head_balance:.2f}"

    def action_process_and_save_mdm_ledger(self, instance):
        MDM_ACC_FILE = 'MDM_Account_Database.xlsx'
        try:
            tx_type = self.f_tx_type.text.strip(); r_date = self.f_rec_date.text.strip(); o_bal = self.f_open_bal.text.strip(); r_amt = self.f_rec_amt.text.strip(); e_date = self.f_exp_date.text.strip(); e_amt = self.f_exp_amt.text.strip(); chk_no = self.f_cheque.text.strip() if self.f_cheque.text.strip() else "---"
            opening_bal = round(float(o_bal) if o_bal else 0.00, 2); received_amt = round(float(r_amt) if r_amt else 0.00, 2); expenditure_amt = round(float(e_amt) if e_amt else 0.00, 2)
            total_balance = round(opening_bal + received_amt, 2); final_balance = round(total_balance - expenditure_amt, 2)
            new_row = {'Transaction Type': str(tx_type), 'Received Date': str(r_date), 'Opening Balance': opening_bal, 'Amount Received': received_amt, 'Total Balance': total_balance, 'Expenditure Date': str(e_date), 'Expenditure Amount': expenditure_amt, 'Cheque No': str(chk_no), 'Final Balance': final_balance}
            new_df = pd.DataFrame([new_row])
            if not os.path.exists(MDM_ACC_FILE): new_df.to_excel(MDM_ACC_FILE, index=False)
            else:
                old_df = pd.read_excel(MDM_ACC_FILE); pd.concat([old_df, new_df], ignore_index=True).to_excel(MDM_ACC_FILE, index=False)
            self.popup('Success', 'Transaction successfully locked into Passbook!'); self.load_mdm_financial_ledger_ui()
        except Exception as e: self.popup('System Block Error', f"File writing error: {str(e)}")

    def delete_mdm_ledger_row(self, row_index):
        MDM_ACC_FILE = 'MDM_Account_Database.xlsx'
        try:
            if os.path.exists(MDM_ACC_FILE):
                df = pd.read_excel(MDM_ACC_FILE); df = df.drop(df.index[row_index]); df.to_excel(MDM_ACC_FILE, index=False); self.load_mdm_financial_ledger_ui()
        except: pass

    # 🌾 ✨ [OPTION 3: RATION GRAIN STOCK LEDGER COMPILER ENGINE] - मोबाइल + डेस्कटॉप सिंक
    def load_mdm_ration_stock_ui(self):
        self.mdm_sub_box.clear_widgets()
        RATION_FILE = 'MDM_Ration_Stock_Database.xlsx'
        is_mob = (kivy_platform != 'win')
        from kivy.uix.widget import Widget
        from kivy.graphics import Color, Rectangle
        
        last_w_bal, last_r_bal = 0.00, 0.00
        if os.path.exists(RATION_FILE):
            try:
                df_r = pd.read_excel(RATION_FILE, dtype=str)
                for _, r_row in df_r.iterrows():
                    vw = str(r_row.get('Final Wheat Stock', '')).strip()
                    vr = str(r_row.get('Final Rice Stock', '')).strip()
                    if vw and vw.lower() != 'nan': last_w_bal = float(vw)
                    if vr and vr.lower() != 'nan': last_r_bal = float(vr)
            except Exception: pass
            
        # 📦 [लेयर 1]: शुद्ध इनपुट फॉर्म ग्रिड (मोबाइल पर 2 कॉलम ताकि डिब्बे बड़े दिखें)
        form_grid = GridLayout(cols=2 if is_mob else 4, size_hint_y=None, height=dp(415) if is_mob else 165, spacing=dp(8) if is_mob else 12, padding=dp(6) if is_mob else 8)
        
        lbl_fs = sp(12.5) if is_mob else 13
        inp_h = dp(42) if is_mob else 36
        inp_fs = sp(14) if is_mob else 14
        inp_pad = [dp(6), dp(6)] if is_mob else [6, 6]

        form_grid.add_widget(Label(text='Select Month:', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.r_month = CustomSpinner(text='April', values=('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'), size_hint_y=None, height=inp_h)
        form_grid.add_widget(self.r_month)
        
        form_grid.add_widget(Label(text='Select Year:', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.r_year = CustomSpinner(text='2026', values=[str(x) for x in range(2020, 2036)], size_hint_y=None, height=inp_h)
        form_grid.add_widget(self.r_year)
        
        form_grid.add_widget(Label(text='Opening Wheat (KG):', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.r_op_wheat = TextInput(text=f"{last_w_bal:.2f}", multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, padding=inp_pad)
        form_grid.add_widget(self.r_op_wheat)
        
        form_grid.add_widget(Label(text='Opening Rice (KG):', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.r_op_rice = TextInput(text=f"{last_r_bal:.2f}", multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, padding=inp_pad)
        form_grid.add_widget(self.r_op_rice)
        
        form_grid.add_widget(Label(text='Wheat Received (KG):', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.r_rec_wheat = TextInput(text='0.00', multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, padding=inp_pad)
        form_grid.add_widget(self.r_rec_wheat)
        
        form_grid.add_widget(Label(text='Rice Received (KG):', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.r_rec_rice = TextInput(text='0.00', multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, padding=inp_pad)
        form_grid.add_widget(self.r_rec_rice)
        
        form_grid.add_widget(Label(text='Wheat Consumed (KG):', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.r_con_wheat = TextInput(text='0.00', multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, padding=inp_pad)
        form_grid.add_widget(self.r_con_wheat)
        
        form_grid.add_widget(Label(text='Rice Consumed (KG):', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.r_con_rice = TextInput(text='0.00', multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, padding=inp_pad)
        form_grid.add_widget(self.r_con_rice)
        self.mdm_sub_box.add_widget(form_grid)
        
        self.mdm_sub_box.add_widget(Widget(size_hint_y=None, height=dp(10) if is_mob else 40))
        
        btn_center_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 45, padding=(dp(20), 0) if is_mob else (240, 0, 240, 0))
        btn_save_rat = Button(text='💾 LOCK & SAVE RATION STOCK', background_color=(0.1, 0.45, 0.65, 1), bold=True, font_size=sp(13.5) if is_mob else 13, size_hint_y=None, height=dp(44) if is_mob else 38)
        btn_save_rat.bind(on_press=self.action_process_and_save_ration_stock)
        btn_center_box.add_widget(btn_save_rat)
        self.mdm_sub_box.add_widget(btn_center_box)
        
        self.mdm_sub_box.add_widget(Widget(size_hint_y=None, height=dp(8) if is_mob else 35))
        
        # 📜 [भाग बी - लाइव ग्रिड लाइन्स फिक्स तालिका]: ९ कॉलम्स (मोबाइल पर दाएँ-बाएँ स्क्रॉल सहित)
        scroll = ScrollView(do_scroll_x=True, do_scroll_y=True)
        grid_table = GridLayout(cols=9, spacing=(1, 1), size_hint_x=None if is_mob else 1, size_hint_y=None, padding=(5, 5, 5, 6))
        grid_table.bind(minimum_height=grid_table.setter('height'))
        
        col_w_rat = [dp(110), dp(95), dp(95), dp(95), dp(95), dp(95), dp(95), dp(95), dp(95)] if is_mob else [105, 85, 85, 85, 85, 85, 85, 85, 85]
        if is_mob:
            grid_table.width = sum(col_w_rat)
        grid_table.cols_minimum = {i: col_w_rat[i] for i in range(9)}

        with grid_table.canvas.before:
            Color(0.35, 0.35, 0.35, 1)
            self.rt_bg = Rectangle(size=grid_table.size, pos=grid_table.pos)
        grid_table.bind(size=lambda ins, val: setattr(self.rt_bg, 'size', ins.size), pos=lambda ins, val: setattr(self.rt_bg, 'pos', ins.pos))
        
        def make_ration_lbl(txt, bg_col, col_idx, is_bold=False, txt_col=(0,0,0,1)):
            lbl = Label(text=txt, color=txt_col, bold=is_bold, font_size=sp(11.5) if is_mob else 11, size_hint_x=None if is_mob else 1, width=col_w_rat[col_idx], size_hint_y=None, height=dp(38) if is_mob else 36, halign='center', valign='middle')
            with lbl.canvas.before:
                Color(*bg_col)
                lbl.rect = Rectangle(size=lbl.size, pos=lbl.pos)
            lbl.bind(size=lambda ins, val: setattr(lbl.rect, 'size', ins.size), pos=lambda ins, val: setattr(lbl.rect, 'pos', ins.pos))
            return lbl

        headers_ration = ['MONTH-YEAR', 'OPEN WHEAT', 'OPEN RICE', 'REC WHEAT', 'REC RICE', 'CONS WHEAT', 'CONS RICE', 'FINAL WHEAT', 'FINAL RICE']
        for i, h in enumerate(headers_ration): 
            grid_table.add_widget(make_ration_lbl(h, (0.05, 0.25, 0.45, 1), i, is_bold=True, txt_col=(1,1,1,1)))
        
        if os.path.exists(RATION_FILE):
            try:
                df_ledger = pd.read_excel(RATION_FILE, dtype=str)
                for idx, row in df_ledger.iterrows():
                    c_bg = (0.98, 0.97, 0.94, 1) if idx % 2 == 0 else (0.94, 0.95, 0.92, 1)
                    
                    grid_table.add_widget(make_ration_lbl(str(row.get('Month-Year','')), c_bg, 0))
                    grid_table.add_widget(make_ration_lbl(f"{float(row.get('Opening Wheat Stock',0) or 0):.2f} kg", c_bg, 1))
                    grid_table.add_widget(make_ration_lbl(f"{float(row.get('Opening Rice Stock',0) or 0):.2f} kg", c_bg, 2))
                    grid_table.add_widget(make_ration_lbl(f"+{float(row.get('Wheat Received',0) or 0):.2f} kg", c_bg, 3, is_bold=True, txt_col=(0, 0.5, 0, 1)))
                    grid_table.add_widget(make_ration_lbl(f"+{float(row.get('Rice Received',0) or 0):.2f} kg", c_bg, 4, is_bold=True, txt_col=(0, 0.5, 0, 1)))
                    grid_table.add_widget(make_ration_lbl(f"-{float(row.get('Wheat Consumed',0) or 0):.2f} kg", c_bg, 5, is_bold=True, txt_col=(0.75, 0, 0, 1)))
                    grid_table.add_widget(make_ration_lbl(f"-{float(row.get('Rice Consumed',0) or 0):.2f} kg", c_bg, 6, is_bold=True, txt_col=(0.75, 0, 0, 1)))
                    grid_table.add_widget(make_ration_lbl(f"{float(row.get('Final Wheat Stock',0) or 0):.2f} kg", c_bg, 7, is_bold=True, txt_col=(0, 0.3, 0.6, 1)))
                    grid_table.add_widget(make_ration_lbl(f"{float(row.get('Final Rice Stock',0) or 0):.2f} kg", c_bg, 8, is_bold=True, txt_col=(0, 0.3, 0.6, 1)))
            except Exception: pass
            
        scroll.add_widget(grid_table); self.mdm_sub_box.add_widget(scroll)

    # 💾 ✨ [सुधार 3]: 100% वर्किंग लाइव राशन डेटा राइटिंग इंजन (Windows + Android क्रॉस-प्लेटफ़ॉर्म)
    def action_process_and_save_ration_stock(self, instance):
        import os
        RATION_FILE = 'MDM_Ration_Stock_Database.xlsx'
        try:
            m_p = self.r_month.text.strip()
            y_p = self.r_year.text.strip()
            full_period = f"{m_p}-{y_p}"
            
            op_w = float(self.r_op_wheat.text.strip()) if self.r_op_wheat.text.strip() else 0.0
            op_r = float(self.r_op_rice.text.strip()) if self.r_op_rice.text.strip() else 0.0
            rc_w = float(self.r_rec_wheat.text.strip()) if self.r_rec_wheat.text.strip() else 0.0
            rc_r = float(self.r_rec_rice.text.strip()) if self.r_rec_rice.text.strip() else 0.0
            cn_w = float(self.r_con_wheat.text.strip()) if self.r_con_wheat.text.strip() else 0.0
            cn_r = float(self.r_con_rice.text.strip()) if self.r_con_rice.text.strip() else 0.0
            
            final_w = round((op_w + rc_w) - cn_w, 2)
            final_r = round((op_r + rc_r) - cn_r, 2)
            
            new_row = {
                'Month-Year': full_period, 'Opening Wheat Stock': op_w, 'Opening Rice Stock': op_r, 
                'Wheat Received': rc_w, 'Rice Received': rc_r, 'Wheat Consumed': cn_w, 'Rice Consumed': cn_r, 
                'Final Wheat Stock': final_w, 'Final Rice Stock': final_r
            }
            new_df = pd.DataFrame([new_row])
            
            if not os.path.exists(RATION_FILE): 
                new_df.to_excel(RATION_FILE, index=False)
            else:
                old_df = pd.read_excel(RATION_FILE, dtype=str)
                kept_rows = []
                for _, r_old in old_df.iterrows():
                    if str(r_old.get('Month-Year', '')).strip().lower() != full_period.lower():
                        kept_rows.append(dict(r_old))
                cleaned_old = pd.DataFrame(kept_rows, columns=old_df.columns)
                pd.concat([cleaned_old, new_df], ignore_index=True).to_excel(RATION_FILE, index=False)
                
            self.popup('Success', f'Ration stock record locked safely for {full_period}!')
            self.load_mdm_ration_stock_ui()
        except Exception as e: 
            self.popup('Error', f"Ration Storage Blocked: {str(e)}")

    def load_staff_view(self):
        self.content_area.clear_widgets()
        self.current_view = 'staff_registration'
        is_mob = (kivy_platform != 'win')
        
        with self.content_area.canvas.before:
            Color(0.96, 0.96, 0.86, 1)
            self.s_bg = Rectangle(size=self.content_area.size, pos=self.content_area.pos)
        self.content_area.bind(size=lambda ins, val: setattr(self.s_bg, 'size', ins.size), pos=lambda ins, val: setattr(self.s_bg, 'pos', ins.pos))
        
        self.content_area.add_widget(Label(text='STAFF DETAIL', font_size=sp(18) if is_mob else 26, bold=True, color=(0,0,0,1), size_hint_y=None, height=dp(36) if is_mob else 45, halign='center'))
        
        form_body = BoxLayout(orientation='vertical' if is_mob else 'horizontal', spacing=dp(8) if is_mob else 15, padding=dp(6) if is_mob else 10)
        
        scroll = ScrollView(size_hint=(1, 0.72) if is_mob else (0.75, 1))
        grid = GridLayout(cols=1, spacing=dp(10) if is_mob else 10, size_hint_y=None, padding=5)
        grid.bind(minimum_height=grid.setter('height'))
        
        self.staff_fields_list = ['S NO', 'EHRMS ID', "TEACHER'S NAME", "DESIGNATION", "FATHER/HUSBAND'S NAME", "MOTHER'S NAME", 'GENDER (MALE/FEMALE)', 'DATE OF BIRTH', 'DATE OF BIRTH (IN WORDS)', 'AADHAR NUMBER', 'MOBILE NUMBER', 'EMAIL ID', 'ADDRESS', 'QUALIFICATION', 'FIRST JOINING DATE', 'CURRENT SCHOOL JOINING DATE']
        self.staff_fields = {}
        self.staff_master_tabs = []
        
        for f in self.staff_fields_list:
            box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44) if is_mob else 38, spacing=dp(8) if is_mob else 10)
            
            lbl = Label(text=f, size_hint_x=0.42 if is_mob else 0.38, color=(0.1, 0.3, 0.1, 1), font_size=sp(12) if is_mob else 13, bold=True, halign='left', valign='middle')
            lbl.bind(size=lbl.setter('text_size'))
            box.add_widget(lbl)
            
            if f == 'GENDER (MALE/FEMALE)':
                spin = CustomSpinner(text='Male', values=('Male', 'Female', 'Other'), size_hint_x=0.58 if is_mob else 0.62)
                self.staff_fields[f] = spin
                box.add_widget(spin)
                self.staff_master_tabs.append(spin)
                
            elif f == 'DESIGNATION':
                spin_des = CustomSpinner(
                    text='SELECT DESIGNATION',
                    values=('HEAD MASTER', 'ASSISTANT TEACHER', 'SHIKSHAMITRA'),
                    size_hint_x=0.58 if is_mob else 0.62,
                    background_color=(0.15, 0.15, 0.15, 1),
                    color=(1, 1, 1, 1),
                    bold=True
                )
                self.staff_fields[f] = spin_des
                box.add_widget(spin_des)
                self.staff_master_tabs.append(spin_des)
                
            else:
                limit, only_dig = None, False
                if f in ['S NO', 'EHRMS ID']: only_dig = True
                elif f in ['AADHAR NUMBER']: limit = 12; only_dig = True
                elif f in ['MOBILE NUMBER']: limit = 10; only_dig = True
                
                if 'DATE' in f and 'WORDS' not in f:
                    db_box = BoxLayout(orientation='horizontal', size_hint_x=0.58 if is_mob else 0.62, spacing=4)
                    txt = CustomText(multiline=False, hint_text='DD-MM-YYYY', size_hint_x=0.78 if is_mob else 0.82)
                    if f == 'DATE OF BIRTH':
                        def auto_staff_words(instance, value):
                            clean = value.replace('-','').replace('/','').strip()
                            if len(clean) == 8:
                                self.staff_fields['DATE OF BIRTH (IN WORDS)'].text = date_to_words_eng(clean)
                        txt.bind(text=auto_staff_words)
                    
                    btn_cal = Button(text='📅', size_hint_x=0.22 if is_mob else 0.18, background_color=(0.1, 0.5, 0.3, 1))
                    btn_cal.bind(on_press=lambda instance, target=txt: self.open_staff_calendar_popup(target))
                    db_box.add_widget(txt); db_box.add_widget(btn_cal)
                    self.staff_fields[f] = txt
                    self.staff_master_tabs.append(txt)
                    box.add_widget(db_box)
                else:
                    read_only_mode = True if 'WORDS' in f else False
                    txt = CustomText(max_chars=limit, only_digits=only_dig, multiline=False, size_hint_x=0.58 if is_mob else 0.62, readonly=read_only_mode)
                    self.staff_fields[f] = txt
                    self.staff_master_tabs.append(txt)
                    box.add_widget(txt)
            grid.add_widget(box)
        scroll.add_widget(grid)

        if is_mob:
            photo_panel = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(145), padding=(dp(8), dp(6)), spacing=dp(12))
            with photo_panel.canvas.before:
                Color(0.98, 0.92, 0.74, 1)
                self.p_rect = Rectangle(size=photo_panel.size, pos=photo_panel.pos)
            photo_panel.bind(size=lambda ins, val: setattr(self.p_rect, 'size', ins.size), pos=lambda ins, val: setattr(self.p_rect, 'pos', ins.pos))
            
            self.staff_photo = Image(source='', size_hint=(None, None), size=(dp(110), dp(132)), allow_stretch=True, keep_ratio=False)
            photo_panel.add_widget(self.staff_photo)
            
            right_stf_box = BoxLayout(orientation='vertical', spacing=dp(8), padding=(0, dp(4)))
            self.staff_photo_path = CustomText(text='', hint_text='Photo Path', multiline=False, size_hint_y=None, height=dp(38))
            right_stf_box.add_widget(self.staff_photo_path)
            self.staff_master_tabs.append(self.staff_photo_path)
            
            b_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(38), spacing=dp(8))
            btn_browse = CustomButton(text='GALLERY', size_hint_x=None, width=dp(95), background_color=(0.2, 0.2, 0.2, 1), bold=True)
            btn_browse.bind(on_press=self.browse_staff_photo_action)
            btn_cam = CustomButton(text='CAMERA', size_hint_x=None, width=dp(95), background_color=(0, 0.4, 0.6, 1), bold=True)
            btn_cam.bind(on_press=self.capture_staff_camera_action)
            b_box.add_widget(btn_browse); b_box.add_widget(btn_cam); right_stf_box.add_widget(b_box)
            right_stf_box.add_widget(BoxLayout())
            photo_panel.add_widget(right_stf_box)
            
            form_body.add_widget(photo_panel)
            form_body.add_widget(scroll)
        else:
            photo_panel = BoxLayout(orientation='vertical', size_hint_x=0.25, padding=(10, 5, 10, 10), spacing=10)
            with photo_panel.canvas.before:
                Color(0.98, 0.92, 0.74, 1)
                self.p_rect = Rectangle(size=photo_panel.size, pos=photo_panel.pos)
            photo_panel.bind(size=lambda ins, val: setattr(self.p_rect, 'size', ins.size), pos=lambda ins, val: setattr(self.p_rect, 'pos', ins.pos))
            
            self.staff_photo = Image(source='', size_hint=(None, None), size=(170, 190), pos_hint={'center_x': 0.5})
            photo_panel.add_widget(self.staff_photo)
            
            self.staff_photo_path = CustomText(text='', hint_text='Photo Path', multiline=False, size_hint_y=None, height=36)
            photo_panel.add_widget(self.staff_photo_path)
            self.staff_master_tabs.append(self.staff_photo_path)
            
            b_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=38, spacing=5)
            btn_browse = CustomButton(text='BROWSE', font_size=11, background_color=(0.2, 0.2, 0.2, 1), bold=True)
            btn_browse.bind(on_press=self.browse_staff_photo_action)
            btn_cam = CustomButton(text='CAMERA', font_size=11, background_color=(0, 0.4, 0.6, 1), bold=True)
            btn_cam.bind(on_press=self.capture_staff_camera_action)
            b_box.add_widget(btn_browse); b_box.add_widget(btn_cam); photo_panel.add_widget(b_box)
            photo_panel.add_widget(BoxLayout())
            
            form_body.add_widget(scroll)
            form_body.add_widget(photo_panel)
        self.content_area.add_widget(form_body)
        
        # --- 🛠️ सुधरा हुआ स्टाफ कंट्रोल बटन पैनल (मोबाइल पर स्क्रॉल करने योग्य पट्टी) ---
        al = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 48, spacing=8, padding=(0, 5, 0, 0))
        if is_mob:
            al.size_hint_x = None
            al.bind(minimum_width=al.setter('width'))
        
        self.btn_save_stf = CustomButton(text='ADD/SAVE', background_color=(1, 0, 0, 1), bold=True, size_hint_x=None if is_mob else 1, width=dp(115))
        self.btn_save_stf.bind(on_press=self.save_staff_data)
        
        self.btn_reset_stf = CustomButton(text='RESET', background_color=(0, 1, 0, 1), bold=True, color=(0,0,0,1), size_hint_x=None if is_mob else 1, width=dp(100))
        self.btn_reset_stf.bind(on_press=self.reset_staff_fields_action)
        
        self.btn_close_stf = CustomButton(text='CLOSE', background_color=(0, 0, 1, 1), bold=True, size_hint_x=None if is_mob else 1, width=dp(100))
        self.btn_close_stf.bind(on_press=lambda x: self.show_welcome())
        
        self.btn_search_stf = CustomButton(text='SEARCH', background_color=(1, 0, 1, 1), bold=True, size_hint_x=None if is_mob else 1, width=dp(110))
        self.btn_search_stf.bind(on_press=self.search_staff_data_action)
        
        self.btn_update_stf = CustomButton(text='UPDATE', background_color=(0.1, 0.4, 0.6, 1), bold=True, size_hint_x=None if is_mob else 1, width=dp(110))
        self.btn_update_stf.bind(on_press=self.save_staff_data)

        self.btn_delete_stf = CustomButton(text='DELETE', background_color=(0, 0.8, 0.8, 1), bold=True, color=(0,0,0,1), size_hint_x=None if is_mob else 1, width=dp(105))
        
        self.btn_print_stf = CustomButton(text='PRINT', background_color=(0.1, 0.3, 0.1, 1), bold=True, size_hint_x=None if is_mob else 1, width=dp(100))
        self.btn_print_stf.bind(on_press=self.generate_staff_form_pdf)

        for b_stf in [self.btn_save_stf, self.btn_reset_stf, self.btn_close_stf, self.btn_search_stf, self.btn_update_stf, self.btn_delete_stf, self.btn_print_stf]:
            al.add_widget(b_stf)
        
        if is_mob:
            stf_btn_scroll = ScrollView(size_hint=(1, None), height=dp(52), do_scroll_x=True, do_scroll_y=False)
            stf_btn_scroll.add_widget(al)
            self.content_area.add_widget(stf_btn_scroll)
        else:
            self.content_area.add_widget(al)
        
        self.staff_master_tabs = self.staff_master_tabs + [
            self.btn_save_stf, self.btn_reset_stf, self.btn_close_stf, 
            self.btn_search_stf, self.btn_update_stf, self.btn_delete_stf, self.btn_print_stf
        ]
        self.staff_tab_index = 0

    def open_staff_calendar_popup(self, target_input):
        is_mob = (kivy_platform != 'win')
        pl = BoxLayout(orientation='vertical', padding=dp(10) if is_mob else 10, spacing=dp(8) if is_mob else 10)
        selectors = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44) if is_mob else 40, spacing=dp(6) if is_mob else 5)
        month_spin = Spinner(text='January', values=('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'), font_size=sp(14) if is_mob else 14)
        year_spin = Spinner(text='1990', values=[str(x) for x in range(1950, 2030)], font_size=sp(14) if is_mob else 14)
        selectors.add_widget(month_spin); selectors.add_widget(year_spin); pl.add_widget(selectors)
        grid = GridLayout(cols=7, spacing=dp(5) if is_mob else 5)
        pop = Popup(title='Select Date', content=pl, size_hint=(0.94, 0.72) if is_mob else (0.6, 0.65))
        m_dict = {'January':'01','February':'02','March':'03','April':'04','May':'05','June':'06','July':'07','August':'08','September':'09','October':'10','November':'11','December':'12'}
        for d in range(1, 32):
            btn_d = Button(text=str(d), background_color=(0.05, 0.45, 0.2, 1), bold=True, font_size=sp(14) if is_mob else 14)
            def select_staff_date(ins, day_num=d):
                m_code = m_dict[month_spin.text]; target_input.text = f"{day_num:02d}-{m_code}-{year_spin.text}"; pop.dismiss()
            btn_d.bind(on_press=select_staff_date); grid.add_widget(btn_d)
        pl.add_widget(grid)
        btn_close = Button(text='CLOSE', size_hint_y=None, height=dp(44) if is_mob else 40, background_color=(0.7,0,0,1), bold=True, font_size=sp(14) if is_mob else 14)
        btn_close.bind(on_press=pop.dismiss); pl.add_widget(btn_close); pop.open()

    def _get_staff_photo_filename(self):
        ehrms_val = self.staff_fields['EHRMS ID'].text.strip().replace('.0', '') if 'EHRMS ID' in self.staff_fields else ''
        t_nm = self.staff_fields["TEACHER'S NAME"].text.strip().replace(' ', '_') if "TEACHER'S NAME" in self.staff_fields else ''
        clean_nm = ''.join(c for c in t_nm if c.isalnum() or c == '_')
        if ehrms_val:
            return f"{ehrms_val}.jpg"
        elif clean_nm:
            return f"Staff_{clean_nm}.jpg"
        return "staff_temp.jpg"

    def browse_staff_photo_action(self, instance):
        def on_staff_photo_picked(fp):
            if fp and os.path.exists(fp):
                fname = self._get_staff_photo_filename()
                dest_p = os.path.abspath(os.path.join(STAFF_PHOTO_DIR, fname))
                comp_p = compress_image_under_30kb(fp, dest_p, max_kb=28)
                self.selected_staff_photo_path = comp_p
                self.staff_photo_path.text = fname
                self.staff_photo.source = comp_p
                self.staff_photo.reload()

        select_file_cross_platform(
            "Select Staff Photo",
            [("Images", "*.png *.jpg *.jpeg *.bmp")],
            on_staff_photo_picked
        )

    def capture_staff_camera_action(self, instance):
        fname = self._get_staff_photo_filename()
        dest_path = os.path.abspath(os.path.join(STAFF_PHOTO_DIR, fname))

        if kivy_platform == 'win':
            try:
                import cv2
                cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                ret, frame = cap.read()
                if ret:
                    cv2.imwrite(dest_path, frame)
                    comp_p = compress_image_under_30kb(dest_path, dest_path, max_kb=28)
                    self.selected_staff_photo_path = comp_p
                    self.staff_photo_path.text = fname
                    self.staff_photo.source = comp_p
                    self.staff_photo.reload()
                    self.popup('Camera', f'Staff Photo saved as {fname}!')
                else:
                    self.popup('Camera Error', 'Could not access active webcam!')
                cap.release()
            except Exception as e:
                self.popup('Error', str(e))
        else:
            def on_stf_cam_ok(fp):
                self.selected_staff_photo_path = fp
                self.staff_photo_path.text = os.path.basename(fp)
                self.staff_photo.source = fp
                self.staff_photo.reload()
                self.popup('Camera', f'Staff Photo saved as {os.path.basename(fp)}!')

            capture_mobile_camera_safe(dest_path, on_stf_cam_ok, self.popup)

    def reset_staff_fields_action(self, instance):
        for k, v in self.staff_fields.items():
            if not isinstance(v, Spinner): v.text = ''
        self.staff_photo_path.text = ''
        self.staff_photo.source = ''

    def save_staff_data(self, instance):
        import shutil
        import os
        
        stf_file = 'Staff_Database.xlsx'
        ehrms_id_val = self.staff_fields['EHRMS ID'].text.strip()
        teacher_name_val = self.staff_fields["TEACHER'S NAME"].text.strip()
        
        if not ehrms_id_val:
            self.popup('Validation Error', 'Error: EHRMS ID cannot be blank!'); return
        if not teacher_name_val:
            self.popup('Validation Error', 'Error: Teacher Name cannot be blank!'); return
            
        current_staff_data = {k: str(v.text.strip()) for k, v in self.staff_fields.items()}
        
        ordered_columns = [
            'S NO', 'EHRMS ID', "TEACHER'S NAME", 
            'DESIGNATION',
            "FATHER/HUSBAND'S NAME", "MOTHER'S NAME", 'GENDER (MALE/FEMALE)',
            'DATE OF BIRTH', 'DATE OF BIRTH (IN WORDS)', 'AADHAR NUMBER', 'MOBILE NUMBER',
            'EMAIL ID', 'ADDRESS', 'QUALIFICATION', 'FIRST JOINING DATE', 
            'CURRENT SCHOOL JOINING DATE', 'PHOTO_PATH'
        ]
        
        try:
            photo_src = getattr(self, 'selected_staff_photo_path', None)
            if photo_src and os.path.exists(photo_src):
                _, ext = os.path.splitext(photo_src)
                dest_p = os.path.join(STAFF_PHOTO_DIR, f"{ehrms_id_val}{ext}")
                if os.path.abspath(photo_src) != os.path.abspath(dest_p):
                    shutil.copy(photo_src, dest_p)
                current_staff_data['PHOTO_PATH'] = dest_p
                self.selected_staff_photo_path = None
            else:
                if os.path.exists(stf_file):
                    old_df = pd.read_excel(stf_file, dtype=str)
                    clean_target = ehrms_id_val.replace('.0', '').strip().lower()
                    for _, r_old in old_df.iterrows():
                        if str(r_old.get('EHRMS ID', '')).strip().replace('.0', '').lower() == clean_target:
                            old_p = str(r_old.get('PHOTO_PATH', '')).strip()
                            if old_p and old_p.lower() != 'nan':
                                current_staff_data['PHOTO_PATH'] = old_p

            clean_target_id = str(ehrms_id_val).replace('.0', '').strip().lower()
            existing_rows = []
            updated_flag = False

            if os.path.exists(stf_file):
                old_df = pd.read_excel(stf_file, dtype=str)
                for idx, r_old in old_df.iterrows():
                    row_dict = {col: str(r_old.get(col, '')).strip().replace('.0', '').replace('nan', '') for col in ordered_columns}
                    row_ehrms = row_dict.get('EHRMS ID', '').lower()
                    if row_ehrms == clean_target_id or (hasattr(self, 'current_loaded_staff_index') and self.current_loaded_staff_index == idx):
                        if not updated_flag:
                            full_new = {col: current_staff_data.get(col, '') for col in ordered_columns}
                            existing_rows.append(full_new)
                            updated_flag = True
                    else:
                        if row_ehrms:
                            existing_rows.append(row_dict)

            if not updated_flag:
                full_new = {col: current_staff_data.get(col, '') for col in ordered_columns}
                existing_rows.append(full_new)

            final_ordered_df = pd.DataFrame(existing_rows, columns=ordered_columns)
            final_ordered_df.to_excel(stf_file, index=False)
            self.current_loaded_staff_index = None

            msg = f'Staff Profile (ID: {ehrms_id_val}) Updated Successfully!' if updated_flag else 'New Staff Profile Registered Successfully!'
            self.popup('System Message', msg)
            self.reset_staff_fields_action(None)
            return

        except Exception as e: 
            self.popup('Error', f"Saving Staff System Failed: {str(e)}")

    def search_staff_data_action(self, instance):
        from kivy.core.window import Window
        from kivy.clock import Clock
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.textinput import TextInput
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from kivy.uix.popup import Popup
        import os

        is_mob = (kivy_platform != 'win')

        pl = BoxLayout(orientation='vertical', padding=(dp(15), dp(12)) if is_mob else (22, 12, 22, 12), spacing=dp(12) if is_mob else 12)
        heading_label = Label(text="Enter Teacher's Name or EHRMS ID:", color=(1, 1, 1, 1), bold=True, font_size=sp(14) if is_mob else 13, size_hint_y=None, height=dp(28) if is_mob else 22)
        pl.add_widget(heading_label)
        
        s_in = TextInput(multiline=False, size_hint_y=None, height=dp(44) if is_mob else 34, halign='center', font_size=sp(15) if is_mob else 14, background_color=(0.95, 0.95, 0.95, 1), padding=[dp(8), dp(8)] if is_mob else (6, 6, 6, 6))
        pl.add_widget(s_in)
        
        b_box = BoxLayout(spacing=dp(15) if is_mob else 15, size_hint_y=None, height=dp(44) if is_mob else 34)
        btn_f = Button(text='FIND', background_color=(0, 0.5, 0.1, 1), bold=True, font_size=sp(14) if is_mob else 14)
        btn_c = Button(text='CANCEL', background_color=(0.6, 0.1, 0.1, 1), bold=True, font_size=sp(14) if is_mob else 14)
        b_box.add_widget(btn_f); b_box.add_widget(btn_c); pl.add_widget(b_box)
        
        if is_mob:
            pop = Popup(title='Search Staff Database Terminal', content=pl, size_hint=(0.94, 0.42), auto_dismiss=False, background='', background_color=(0.14, 0.14, 0.14, 0.98))
        else:
            pop = Popup(title='Search Staff Database Terminal', content=pl, size_hint=(None, None), size=(500, 200), auto_dismiss=False, background='', background_color=(0.14, 0.14, 0.14, 0.98))
        
        def close_popup_and_clean_hook(ins):
            try: Window.unbind(on_key_down=keyboard_hook)
            except: pass
            pop.dismiss()
            
        btn_c.bind(on_press=close_popup_and_clean_hook)
        
        def find_staff_logic():
            q = s_in.text.strip().lower()
            stf_file = 'Staff_Database.xlsx'
            if not q:
                self.popup('Alert', 'Please enter a search query!'); return
            if not os.path.exists(stf_file):
                self.popup('File Error', f'Database file ({stf_file}) not found!'); return
                
            try:
                df = pd.read_excel(stf_file, dtype=str)
                matched_row = None
                matched_idx = None

                for r_idx, r_item in df.iterrows():
                    t_name = str(r_item.get("TEACHER'S NAME", '')).strip().lower()
                    e_id = str(r_item.get('EHRMS ID', '')).strip().replace('.0', '').lower()
                    if t_name == q or e_id == q.replace('.0', ''):
                        matched_row = r_item
                        matched_idx = r_idx
                        break
                    
                if matched_row is not None:
                    self.current_loaded_staff_index = matched_idx
                    row = matched_row
                    
                    for f in self.staff_fields_list:
                        if f in df.columns and f in self.staff_fields:
                            val = row.get(f, '')
                            self.staff_fields[f].text = str(val).replace('.0', '').strip() if pd.notna(val) and str(val).lower() != 'nan' else ""
                                
                    ehrms_id_loaded = str(row.get('EHRMS ID', '')).strip().replace('.0', '')
                    photo_found = False
                    
                    for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                        potential_p = os.path.join(STAFF_PHOTO_DIR, f"{ehrms_id_loaded}{ext}")
                        if os.path.exists(potential_p):
                            self.staff_photo.source = potential_p
                            self.staff_photo.reload()
                            if hasattr(self, 'staff_photo_path'):
                                self.staff_photo_path.text = f"{ehrms_id_loaded}{ext}"
                            photo_found = True; break
                            
                    if not photo_found and 'PHOTO_PATH' in df.columns and pd.notna(row.get('PHOTO_PATH')):
                        old_p = str(row.get('PHOTO_PATH', '')).strip()
                        if os.path.exists(old_p) and old_p.lower() != 'nan':
                            self.staff_photo.source = old_p; self.staff_photo.reload()
                            if hasattr(self, 'staff_photo_path'): self.staff_photo_path.text = os.path.basename(old_p)
                            photo_found = True
                            
                    if not photo_found:
                        self.staff_photo.source = get_exe_safe_path("logo.png") if os.path.exists(get_exe_safe_path("logo.png")) else ''
                        self.staff_photo.reload()
                        if hasattr(self, 'staff_photo_path'): self.staff_photo_path.text = ""
                        
                    close_popup_and_clean_hook(None)
                    self.popup('Success', f'Staff record and image loaded successfully!')
                else:
                    self.popup('Not Found', f'No staff found matching "{s_in.text.strip()}"')
            except Exception as e:
                self.popup('Database Error', f'Error reading staff database: {str(e)}')

        btn_f.bind(on_press=lambda x: find_staff_logic())

        self.staff_popup_focus_index = 0
        focus_chain = [s_in, btn_f, btn_c]
        def update_button_colors():
            if self.staff_popup_focus_index == 0:
                s_in.focus = True; btn_f.background_color = (0, 0.5, 0.1, 1); btn_c.background_color = (0.6, 0.1, 0.1, 1)
            elif self.staff_popup_focus_index == 1:
                s_in.focus = False; btn_f.background_color = (0, 0.9, 0.2, 1); btn_c.background_color = (0.6, 0.1, 0.1, 1)
            elif self.staff_popup_focus_index == 2:
                s_in.focus = False; btn_f.background_color = (0, 0.5, 0.1, 1); btn_c.background_color = (1, 0, 0, 1)

        def keyboard_hook(window, key, scancode, codepoint, modifiers):
            if key == 13 or key == 271:
                if self.staff_popup_focus_index == 0 or self.staff_popup_focus_index == 1: find_staff_logic(); return True
                elif self.staff_popup_focus_index == 2: close_popup_and_clean_hook(None); return True
            elif key == 9:
                self.staff_popup_focus_index = (self.staff_popup_focus_index + 1) % 3
                update_button_colors(); return True
            return False

        Window.bind(on_key_down=keyboard_hook)
        Clock.schedule_once(lambda dt: [setattr(s_in, 'focus', True), update_button_colors()], 0.05)
        pop.open()

    def load_grant_details_view(self):
        self.content_area.clear_widgets()
        self.current_view = 'grant_details'
        is_mob = (kivy_platform != 'win')
        GRANT_FILE = 'School_Grant_Database.xlsx'
        from kivy.uix.widget import Widget
        from kivy.graphics import Color, Rectangle
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        import os
        
        last_final_balance = 0.00
        if os.path.exists(GRANT_FILE):
            try:
                df_b = pd.read_excel(GRANT_FILE, dtype=str)
                for _, r_b in df_b.iterrows():
                    val_fb = str(r_b.get('Final Balance', '')).strip()
                    if val_fb and val_fb.lower() != 'nan':
                        last_final_balance = float(val_fb)
            except Exception: pass
            
        form_grid = GridLayout(cols=2 if is_mob else 4, size_hint_y=None, height=dp(465) if is_mob else 195, spacing=dp(8) if is_mob else 12, padding=dp(6) if is_mob else 10)
        grant_master_tabs_list = []
        
        lbl_fs = sp(12.5) if is_mob else 13
        inp_h = dp(42) if is_mob else 36
        inp_fs = sp(14) if is_mob else 14

        form_grid.add_widget(Label(text='Grant Component / Head:', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.g_tx_type = CustomSpinner(text='Composite School Grant', values=('Composite School Grant', 'Library Grant', 'Sports & Physical Education', 'Self Defense Training', 'Balika Manch', 'SMC Training', 'Eco Club', 'TLM Grant', 'OoSC Grant', 'UDISE Grant', 'Annual Function Grant', 'PTM Grant', 'Others'), size_hint_y=None, height=inp_h)
        form_grid.add_widget(self.g_tx_type); grant_master_tabs_list.append(self.g_tx_type)
        
        form_grid.add_widget(Label(text='PFMS Component Code:', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.g_pfms_code = CustomSpinner(text='F.01.18 (Composite Grant)', values=('F.01.18 (Composite Grant)', 'F.01.19 (Library Grant)', 'F.01.20 (Sports Grant)', 'F.01.22 (Self Defense)', 'F.01.25 (Balika Manch)', 'F.01.23 (SMC Training)', 'F.01.27 (Eco Club)', 'F.01.15 (TLM Grant)', 'F.02.04 (OoSC Grant)', 'F.01.08 (UDISE Grant)', 'F.01.29 (Annual Function)', 'F.01.30 (PTM Grant)', 'General.Others'), size_hint_y=None, height=inp_h)
        form_grid.add_widget(self.g_pfms_code); grant_master_tabs_list.append(self.g_pfms_code)
        
        form_grid.add_widget(Label(text='Budget Received Date:', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        from datetime import datetime; current_date_str = datetime.now().strftime("%d-%m-%Y")
        self.g_rec_date = CustomText(text=current_date_str, multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, write_tab=False)
        form_grid.add_widget(self.g_rec_date); grant_master_tabs_list.append(self.g_rec_date)
        
        form_grid.add_widget(Label(text='Opening Balance (Rs):', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.g_open_bal = CustomText(text=f"{last_final_balance:.2f}", multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, write_tab=False)
        form_grid.add_widget(self.g_open_bal); grant_master_tabs_list.append(self.g_open_bal)
        
        form_grid.add_widget(Label(text='Budget Received (Rs):', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.g_rec_amt = CustomText(text='0.00', multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, write_tab=False)
        form_grid.add_widget(self.g_rec_amt); grant_master_tabs_list.append(self.g_rec_amt)
        
        form_grid.add_widget(Label(text='Expenditure Amount (Rs):', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.g_exp_amt = CustomText(text='0.00', multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, write_tab=False)
        form_grid.add_widget(self.g_exp_amt); grant_master_tabs_list.append(self.g_exp_amt)
        
        form_grid.add_widget(Label(text='Vendor / Firm Name:', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.g_vendor = CustomText(text='', multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, hint_text="e.g. Balaji Traders", write_tab=False)
        form_grid.add_widget(self.g_vendor); grant_master_tabs_list.append(self.g_vendor)
        
        form_grid.add_widget(Label(text='Payment Done Via:', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.g_pay_mode = CustomSpinner(text='PFMS E-Payment', values=('PFMS E-Payment', 'Cheque Payment', 'Cash / Voucher'), size_hint_y=None, height=inp_h)
        form_grid.add_widget(self.g_pay_mode); grant_master_tabs_list.append(self.g_pay_mode)
        
        form_grid.add_widget(Label(text='Voucher / PFMS No:', color=(0,0,0,1), bold=True, font_size=lbl_fs))
        self.g_voucher = CustomText(text='', multiline=False, halign='center', size_hint_y=None, height=inp_h, font_size=inp_fs, hint_text="Enter C-No. / Voucher", write_tab=False)
        form_grid.add_widget(self.g_voucher); grant_master_tabs_list.append(self.g_voucher)
        self.content_area.add_widget(form_grid)
        
        self.content_area.add_widget(Widget(size_hint_y=None, height=dp(10) if is_mob else 50))
        
        btn_action_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 35, spacing=dp(10) if is_mob else 15, padding=(dp(4), 0) if is_mob else (20, 0, 20, 0))
        if is_mob:
            btn_action_bar.size_hint_x = None
            btn_action_bar.bind(minimum_width=btn_action_bar.setter('width'))

        btn_print_m_grant = Button(text='🖨️ MONTHLY GRANT', background_color=(0.1, 0.55, 0.4, 1), bold=True, font_size=sp(12) if is_mob else 12.5, size_hint_x=None if is_mob else 1, width=dp(165))
        btn_print_a_grant = Button(text='🏛️ ANNUAL GRANT', background_color=(0.05, 0.35, 0.6, 1), bold=True, font_size=sp(12) if is_mob else 12.5, size_hint_x=None if is_mob else 1, width=dp(165))
        btn_save_grant = Button(text='💾 LOCK & SAVE', background_color=(0.05, 0.55, 0.2, 1), bold=True, font_size=sp(12) if is_mob else 12.5, size_hint_x=None if is_mob else 1, width=dp(165))
        
        btn_print_m_grant.bind(on_press=lambda x: self.generate_grant_report_pdf(is_annual=False))
        btn_print_a_grant.bind(on_press=lambda x: self.generate_grant_report_pdf(is_annual=True))
        btn_save_grant.bind(on_press=self.action_process_and_save_grant_details)
        
        btn_action_bar.add_widget(btn_print_m_grant); grant_master_tabs_list.append(btn_print_m_grant)
        btn_action_bar.add_widget(btn_print_a_grant); grant_master_tabs_list.append(btn_print_a_grant)
        btn_action_bar.add_widget(btn_save_grant); grant_master_tabs_list.append(btn_save_grant)
        
        if is_mob:
            g_btn_scroll = ScrollView(size_hint=(1, None), height=dp(52), do_scroll_x=True, do_scroll_y=False)
            g_btn_scroll.add_widget(btn_action_bar)
            self.content_area.add_widget(g_btn_scroll)
        else:
            self.content_area.add_widget(btn_action_bar)
            
        self.content_area.add_widget(Widget(size_hint_y=None, height=dp(8) if is_mob else 20))
        
        def auto_sync_pfms_code(spinner, selected_text):
            self.refresh_grant_head_opening_balance(selected_text)
            mapping_dict = {
                'Composite School Grant': 'F.01.18 (Composite Grant)', 'Library Grant': 'F.01.19 (Library Grant)',
                'Sports & Physical Education': 'F.01.20 (Sports Grant)', 'Self Defense Training': 'F.01.22 (Self Defense)',
                'Balika Manch': 'F.01.25 (Balika Manch)', 'SMC Training': 'F.01.23 (SMC Training)',
                'Eco Club': 'F.01.27 (Eco Club)', 'TLM Grant': 'F.01.15 (TLM Grant)',
                'OoSC Grant': 'F.02.04 (OoSC Grant)', 'UDISE Grant': 'F.01.08 (UDISE Grant)',
                'Annual Function Grant': 'F.01.29 (Annual Function)', 'PTM Grant': 'F.01.30 (PTM Grant)'
            }
            if selected_text in mapping_dict: self.g_pfms_code.text = mapping_dict[selected_text]
        self.g_tx_type.bind(text=auto_sync_pfms_code)
        
        scroll = ScrollView(do_scroll_x=True, do_scroll_y=True)
        grid_table = GridLayout(cols=12, spacing=(1, 1), size_hint_x=None if is_mob else 1, size_hint_y=None, padding=(5, 5, 5, 6))
        grid_table.bind(minimum_height=grid_table.setter('height'))
        
        col_w_grt = [dp(150), dp(85), dp(95), dp(90), dp(90), dp(90), dp(90), dp(130), dp(105), dp(105), dp(95), dp(60)] if is_mob else [135, 75, 85, 80, 80, 80, 80, 115, 95, 95, 85, 50]
        if is_mob:
            grid_table.width = sum(col_w_grt)
        grid_table.cols_minimum = {i: col_w_grt[i] for i in range(12)}

        with grid_table.canvas.before: Color(0.35, 0.35, 0.35, 1); self.grt_bg = Rectangle(size=grid_table.size, pos=grid_table.pos)
        grid_table.bind(size=lambda ins, val: setattr(self.grt_bg, 'size', ins.size), pos=lambda ins, val: setattr(self.grt_bg, 'pos', ins.pos))
        
        def make_grant_cell_lbl(txt, bg_col, col_idx, is_bold=False, txt_col=(0,0,0,1)):
            lbl = Label(text=txt, color=txt_col, bold=is_bold, font_size=sp(11.5) if is_mob else 10.5, size_hint_x=None if is_mob else 1, width=col_w_grt[col_idx], size_hint_y=None, height=dp(40) if is_mob else 38, halign='center', valign='middle')
            with lbl.canvas.before: Color(*bg_col); lbl.rect = Rectangle(size=lbl.size, pos=lbl.pos)
            lbl.bind(size=lambda ins, val: setattr(lbl.rect, 'size', ins.size), pos=lambda ins, val: setattr(lbl.rect, 'pos', ins.pos))
            return lbl

        headers_grant = ['GRANT HEAD', 'PFMS CODE', 'REC DATE', 'OPENING', 'RECEIVED', 'TOTAL BAL', 'EXPENSE', 'VENDOR / FIRM', 'PAY MODE', 'VOUCHER / PFMS', 'FINAL BAL', 'ACTION']
        for i, h in enumerate(headers_grant):
            grid_table.add_widget(make_grant_cell_lbl(h, (0.05, 0.25, 0.45, 1), i, is_bold=True, txt_col=(1,1,1,1)))
            
        if os.path.exists(GRANT_FILE):
            try:
                df_ledger = pd.read_excel(GRANT_FILE, dtype=str)
                for idx, row in df_ledger.iterrows():
                    c_bg = (0.98, 0.97, 0.94, 1) if idx % 2 == 0 else (0.94, 0.95, 0.92, 1)
                    grid_table.add_widget(make_grant_cell_lbl(str(row.get('Grant Head','')), c_bg, 0))
                    grid_table.add_widget(make_grant_cell_lbl(str(row.get('PFMS Code','F.01.18')), c_bg, 1, is_bold=True, txt_col=(0.4, 0.2, 0, 1)))
                    grid_table.add_widget(make_grant_cell_lbl(str(row.get('Received Date','')), c_bg, 2))
                    grid_table.add_widget(make_grant_cell_lbl(f"{float(row.get('Opening Balance',0) or 0):.2f}", c_bg, 3))
                    grid_table.add_widget(make_grant_cell_lbl(f"+{float(row.get('Amount Received',0) or 0):.2f}", c_bg, 4, is_bold=True, txt_col=(0, 0.5, 0, 1)))
                    grid_table.add_widget(make_grant_cell_lbl(f"{float(row.get('Total Balance',0) or 0):.2f}", c_bg, 5))
                    grid_table.add_widget(make_grant_cell_lbl(f"-{float(row.get('Expenditure Amount',0) or 0):.2f}", c_bg, 6, is_bold=True, txt_col=(0.75, 0, 0, 1)))
                    grid_table.add_widget(make_grant_cell_lbl(str(row.get('Vendor Name','---')), c_bg, 7))
                    grid_table.add_widget(make_grant_cell_lbl(str(row.get('Payment Mode','PFMS')), c_bg, 8))
                    grid_table.add_widget(make_grant_cell_lbl(str(row.get('Voucher No','')), c_bg, 9))
                    grid_table.add_widget(make_grant_cell_lbl(f"{float(row.get('Final Balance',0) or 0):.2f}", c_bg, 10, is_bold=True, txt_col=(0, 0.35, 0.7, 1)))
                    
                    btn_cell = BoxLayout(size_hint_x=None if is_mob else 1, width=col_w_grt, size_hint_y=None, height=dp(40) if is_mob else 38, padding=3)
                    with btn_cell.canvas.before: 
                        Color(*c_bg)
                        btn_cell.rect = Rectangle(size=btn_cell.size, pos=btn_cell.pos)
                    btn_cell.bind(size=lambda ins, val: setattr(btn_cell.rect, 'size', ins.size), pos=lambda ins, val: setattr(btn_cell.rect, 'pos', ins.pos))
                    
                    btn_del = Button(text='🗑', size_hint=(1, 1), background_color=(0.75, 0.1, 0.1, 1))
                    btn_del.bind(on_press=lambda x, row_idx=idx: self.delete_grant_ledger_row(row_idx))
                    btn_cell.add_widget(btn_del)
                    grid_table.add_widget(btn_cell)
            except Exception: 
                pass
                
        scroll.add_widget(grid_table)
        self.content_area.add_widget(scroll)
        auto_sync_pfms_code(self.g_tx_type, self.g_tx_type.text)
        
        self.grant_seq = grant_master_tabs_list
        self.grant_popup_focus_index = 0
        
        def update_grant_local_widget_colors():
            for w in self.grant_seq:
                if hasattr(w, 'background_color'): w.background_color = (1, 1, 1, 1)
                if hasattr(w, 'set_visual_focus'): w.set_visual_focus(False)
                elif hasattr(w, 'state'): w.state = 'normal'
                if ('Spinner' in str(type(w)) or 'CustomSpinner' in str(type(w))) and hasattr(w, 'dismiss'):
                    w.dismiss()
                    w.is_open = False
                    
            if self.grant_popup_focus_index < len(self.grant_seq):
                target_w = self.grant_seq[self.grant_popup_focus_index]
                target_type = str(type(target_w))
                
                if hasattr(target_w, 'set_visual_focus'):
                    target_w.set_visual_focus(True)
                    
                if 'CustomText' in target_type or 'TextInput' in target_type:
                    target_w.background_color = (0.9, 1.0, 0.9, 1)
                    target_w.focus = True
                elif 'CustomSpinner' in target_type or 'Spinner' in target_type:
                    pass
                elif 'Button' in target_type:
                    target_w.state = 'down'

        def grant_local_keyboard_hook(window_instance, key, scancode, codepoint, modifiers):
            if self.current_view != 'grant_details': return False
            num_w = len(self.grant_seq)
            current_w = self.grant_seq[self.grant_popup_focus_index] if self.grant_popup_focus_index < num_w else None
            
            if key in (273, 274, 275, 276):
                if current_w and ('CustomSpinner' in str(type(current_w)) or 'Spinner' in str(type(current_w))):
                    vals = current_w.values
                    s_idx = vals.index(current_w.text) if current_w.text in vals else -1
                    shift_val = -1 if key in (273, 276) else 1
                    current_w.text = vals[(s_idx + shift_val) % len(vals)]
                    return True
                
                shift = -1 if key in (273, 276) else 1
                self.grant_popup_focus_index = (self.grant_popup_focus_index + shift) % num_w
                update_grant_local_widget_colors(); return True
                
            elif key in (9, 13, 271):
                if current_w and ('Button' in str(type(current_w))):
                    current_w.state = 'normal'
                    if key in (13, 271): current_w.trigger_action(); return True
                
                shift = -1 if 'shift' in modifiers else 1
                self.grant_popup_focus_index = (self.grant_popup_focus_index + shift) % num_w
                update_grant_local_widget_colors(); return True
            return False

        from kivy.core.window import Window
        Window.bind(on_key_down=grant_local_keyboard_hook)
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: update_grant_local_widget_colors(), 0.05)

    def refresh_grant_head_opening_balance(self, selected_head):
        GRANT_FILE = 'School_Grant_Database.xlsx'
        head_balance = 0.00
        if os.path.exists(GRANT_FILE):
            try:
                df_b = pd.read_excel(GRANT_FILE, dtype=str)
                for _, r_b in df_b.iterrows():
                    if str(r_b.get('Grant Head', '')).strip().lower() == selected_head.strip().lower():
                        val_fb = str(r_b.get('Final Balance', '')).strip()
                        if val_fb and val_fb.lower() != 'nan':
                            head_balance = float(val_fb)
            except Exception: pass
        try: self.g_open_bal.text = f"{head_balance:.2f}"
        except Exception: pass

    def action_process_and_save_grant_details(self, instance):
        import os
        GRANT_FILE = 'School_Grant_Database.xlsx'
        try:
            tx_type = self.g_tx_type.text.strip()
            p_code = self.g_pfms_code.text.split(' ')[0].strip()
            r_date = self.g_rec_date.text.strip()
            o_bal = self.g_open_bal.text.strip()
            r_amt = self.g_rec_amt.text.strip()
            e_amt = self.g_exp_amt.text.strip()
            v_name = self.g_vendor.text.strip() if self.g_vendor.text.strip() else "---"
            p_mode = self.g_pay_mode.text.strip()
            v_no = self.g_voucher.text.strip() if self.g_voucher.text.strip() else "---"
            
            opening_bal = round(float(o_bal) if o_bal else 0.00, 2)
            received_amt = round(float(r_amt) if r_amt else 0.00, 2)
            expenditure_amt = round(float(e_amt) if e_amt else 0.00, 2)
            
            total_balance = round(opening_bal + received_amt, 2)
            final_balance = round(total_balance - expenditure_amt, 2)
            
            new_row = {
                'Grant Head': str(tx_type), 'PFMS Code': str(p_code), 'Received Date': str(r_date), 
                'Opening Balance': opening_bal, 'Amount Received': received_amt, 'Total Balance': total_balance, 
                'Expenditure Amount': expenditure_amt, 'Vendor Name': str(v_name), 'Payment Mode': str(p_mode), 
                'Voucher No': str(v_no), 'Final Balance': final_balance
            }
            new_df = pd.DataFrame([new_row])
            if not os.path.exists(GRANT_FILE): new_df.to_excel(GRANT_FILE, index=False)
            else:
                old_df = pd.read_excel(GRANT_FILE); pd.concat([old_df, new_df], ignore_index=True).to_excel(GRANT_FILE, index=False)
                
            self.popup('Success', f'Grant transaction locked successfully under PFMS Code {p_code}!')
            self.load_grant_details_view()
        except Exception as e: self.popup('System Block Error', f"File writing error: {str(e)}")

    def delete_grant_ledger_row(self, row_index):
        GRANT_FILE = 'School_Grant_Database.xlsx'
        try:
            if os.path.exists(GRANT_FILE):
                df = pd.read_excel(GRANT_FILE); df = df.drop(df.index[row_index]); df.to_excel(GRANT_FILE, index=False); self.load_grant_details_view()
        except Exception: pass

    def generate_grant_report_pdf(self, is_annual=False):
        import os
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, TableStyle, Table, Paragraph, Spacer
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib import colors
        from datetime import datetime
        current_dt = datetime.now()
        
        try:
            scr_date_parts = self.g_rec_date.text.strip().split('-')
            target_m_code = str(scr_date_parts[1]).strip()
            target_y_code = str(scr_date_parts[2]).strip()
        except Exception:
            target_m_code = current_dt.strftime('%m')
            target_y_code = current_dt.strftime('%Y')
            
        GRANT_FILE = 'School_Grant_Database.xlsx'
        if not os.path.exists(GRANT_FILE):
            self.popup('Alert', 'Grant Details Database is completely empty!'); return
            
        try:
            df_l = pd.read_excel(GRANT_FILE, dtype=str)
            rev_months_map = {'01':'JANUARY', '02':'FEBRUARY', '03':'MARCH', '04':'APRIL', '05':'MAY', '06':'JUNE', '07':'JULY', '08':'AUGUST', '09':'SEPTEMBER', '10':'OCTOBER', '11':'NOVEMBER', '12':'DECEMBER'}
            display_month_heading = rev_months_map.get(target_m_code, current_dt.strftime('%B').upper())
            
            valid_rows = []
            if is_annual:
                for _, r_item in df_l.iterrows():
                    if str(target_y_code) in str(r_item.get('Received Date', '')):
                        valid_rows.append(dict(r_item))
                heading_title_text = f"ANNUAL SCHOOL GRANT DETAILS PASSBOOK LEDGER (PFMS LOCK) • YEAR: {target_y_code}"
                out_pdf_name = f"School_Annual_Grant_Ledger_{target_y_code}.pdf"
            else:
                for _, r_item in df_l.iterrows():
                    raw_date_str = str(r_item.get('Received Date', '')).strip()
                    if '-' in raw_date_str:
                        date_parts = raw_date_str.split('-')
                        if len(date_parts) == 3:
                            if str(date_parts[1]).strip() == target_m_code and str(date_parts[2]).strip() == target_y_code:
                                valid_rows.append(dict(r_item))
                heading_title_text = f"MONTHLY SCHOOL GRANT DETAILS PASSBOOK LEDGER (PFMS LOCK) • PERIOD: {display_month_heading} {target_y_code}"
                out_pdf_name = f"School_Monthly_Grant_Ledger_{display_month_heading}_{target_y_code}.pdf"
            filtered_df = pd.DataFrame(valid_rows) if valid_rows else pd.DataFrame()
                
            if filtered_df.empty:
                self.popup('No Transactions', f'No registered grant records found for the selected period.'); return
                
            heads_to_track = ['Composite School Grant', 'Library Grant', 'Sports & Physical Education', 'Self Defense Training', 'Balika Manch', 'SMC Training', 'Eco Club', 'TLM Grant', 'OoSC Grant', 'UDISE Grant', 'Annual Function Grant', 'PTM Grant']
            summary_received_dict = {h: 0.00 for h in heads_to_track}
            summary_used_dict = {h: 0.00 for h in heads_to_track}
            summary_final_dict = {h: 0.00 for h in heads_to_track}
            
            for _, r_row in filtered_df.iterrows():
                t_type = str(r_row.get('Grant Head', '')).strip()
                if t_type in heads_to_track:
                    summary_received_dict[t_type] += float(r_row.get('Amount Received', 0.00))
                    summary_used_dict[t_type] += abs(float(r_row.get('Expenditure Amount', 0.00)))
                    summary_final_dict[t_type] = float(r_row.get('Final Balance', 0.00))
                    
            doc_pdf = SimpleDocTemplate(out_pdf_name, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
            pdf_story = []
            
            NAVY_THEME = colors.HexColor("#0A3663"); LIGHT_BLUE = colors.HexColor("#EBF3FA")
            h_main = ParagraphStyle('H_M_G', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=NAVY_THEME, alignment=1)
            h_sub = ParagraphStyle('H_S_G', fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=colors.black, alignment=1)
            
            # ✨ [सुधार]: मुख्य तालिका के हेडर और डेटा फ़ॉन्ट्स को बढ़ाकर बड़ा (fontSize=9) किया गया ताकि साफ़ दिखे
            th_style = ParagraphStyle('T_H_G', fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.white, alignment=1)
            td_bold = ParagraphStyle('T_D_B_G', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.black, alignment=1)
            td_norm = ParagraphStyle('T_D_N_G', fontName='Helvetica', fontSize=9, leading=12, textColor=colors.black, alignment=1)
            
            smry_title = ParagraphStyle('S_T_G', fontName='Helvetica-Bold', fontSize=6, leading=8, textColor=NAVY_THEME, alignment=1)
            smry_val_rcvd = ParagraphStyle('S_V_R', fontName='Helvetica', fontSize=7, leading=9, textColor=colors.HexColor("#1B5E20"), alignment=1)
            smry_val_used = ParagraphStyle('S_V_U', fontName='Helvetica', fontSize=7, leading=9, textColor=colors.HexColor("#B71C1C"), alignment=1)
            smry_val_bal = ParagraphStyle('S_V_B', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=colors.HexColor("#0D47A1"), alignment=1)
            
            pdf_story.append(Spacer(1, 15))
            pdf_story.append(Paragraph("<b>PRIMARY SCHOOL PANAUTA, WAZIRGANJ (BUDAUN)</b>", h_main))
            pdf_story.append(Paragraph(f"<b>{heading_title_text}</b>", h_sub))
            pdf_story.append(Spacer(1, 12))
            
            row_headers = [Paragraph(f"<b>{h.replace(' School', '').replace(' Education', '')}</b>", smry_title) for h in heads_to_track]
            row_rcvd = [Paragraph(f"Rcvd: {summary_received_dict[h]:.0f}", smry_val_rcvd) for h in heads_to_track]
            row_used = [Paragraph(f"Used: {summary_used_dict[h]:.0f}", smry_val_used) for h in heads_to_track]
            row_bal = [Paragraph(f"<b>Bal: {summary_final_dict[h]:.0f}</b>", smry_val_bal) for h in heads_to_track]
            
            summary_matrix = [row_headers, row_rcvd, row_used, row_bal]
            w_box_unit = 812.0 / 12.0
            t_summary = Table(summary_matrix, colWidths=[w_box_unit]*12)
            
            t_summary.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1.2, NAVY_THEME), ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F0F5FA")), 
                ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#E8F5E9")), ('BACKGROUND', (0,2), (-1,2), colors.HexColor("#FFEBEE")), ('BACKGROUND', (0,3), (-1,3), colors.HexColor("#E3F2FD")), 
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)
            ]))
            pdf_story.append(t_summary); pdf_story.append(Spacer(1, 15))
            
            reg_headers = [Paragraph("<b>GRANT HEAD</b>", th_style), Paragraph("<b>PFMS CODE</b>", th_style), Paragraph("<b>REC DATE</b>", th_style), Paragraph("<b>OPENING BAL</b>", th_style), Paragraph("<b>BUDGET RCVD</b>", th_style), Paragraph("<b>TOTAL BAL</b>", th_style), Paragraph("<b>EXPENDITURE</b>", th_style), Paragraph("<b>VENDOR / FIRM NAME</b>", th_style), Paragraph("<b>PAY MODE</b>", th_style), Paragraph("<b>VOUCHER / PFMS NO</b>", th_style), Paragraph("<b>FINAL BALANCE</b>", th_style)]
            reg_table_rows = [reg_headers]
            
            for idx, r in filtered_df.iterrows():
                reg_table_rows.append([
                    Paragraph(str(r.get('Grant Head','')), td_norm), Paragraph(str(r.get('PFMS Code','F.01.18')), td_bold), Paragraph(str(r.get('Received Date','')), td_norm),
                    Paragraph(f"{float(r.get('Opening Balance',0)):.2f}", td_norm), Paragraph(f"+{float(r.get('Amount Received',0)):.2f}", td_bold),
                    Paragraph(f"{float(r.get('Total Balance',0)):.2f}", td_norm), Paragraph(f"-{float(r.get('Expenditure Amount',0)):.2f}", td_bold),
                    Paragraph(str(r.get('Vendor Name','---')), td_norm), Paragraph(str(r.get('Payment Mode','PFMS')), td_norm),
                    Paragraph(str(r.get('Voucher No','')), td_norm), Paragraph(f"<b>{float(r.get('Final Balance',0)):.2f}</b>", td_bold)
                ])
                
            w_tx, w_pf, w_dt, w_box, w_vn = 110, 52, 60, 72, 86
            t_register = Table(reg_table_rows, colWidths=[w_tx, w_pf, w_dt, w_box, w_box, w_box, w_box, w_vn, w_box, w_box, w_box], repeatRows=1)
            t_style_rules = [('GRID', (0,0), (-1,-1), 0.8, colors.HexColor("#595959")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BACKGROUND', (0,0), (-1,0), NAVY_THEME), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]
            for i in range(1, len(reg_table_rows)):
                if i % 2 == 0: t_style_rules.append(('BACKGROUND', (0, i), (-1, i), LIGHT_BLUE))
            t_register.setStyle(TableStyle(t_style_rules))
            pdf_story.append(t_register); pdf_story.append(Spacer(1, 45))
            
            w_sig_panel = 390
            t_sig = Table([[Paragraph("________________________", td_bold), Paragraph("________________________", td_bold)], [Paragraph("SMC CHAIRMAN SIGNATURE", td_bold), Paragraph("HEADMASTER SEAL & SIGNATURE", td_bold)]], colWidths=[w_sig_panel, w_sig_panel])
            t_sig.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0, colors.white), ('VALIGN', (0,0), (-1,-1), 'BOTTOM'), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 10)]))
            pdf_story.append(t_sig)
            
            def draw_ledger_decorations(canvas, document):
                canvas.saveState()
                if os.path.exists(get_exe_safe_path("basic.png")):
                    canvas.drawImage(get_exe_safe_path("basic.png"), 25, 520, width=52, height=52, mask='auto')
                logo_p = get_exe_safe_path('logo.png')
                if os.path.exists(logo_p):
                    canvas.drawImage(logo_p, 765, 520, width=52, height=52, mask='auto')
                    canvas.saveState()
                    canvas.setFillAlpha(0.06)
                    canvas.drawImage(logo_p, 296, 145, width=250, height=250, mask='auto')
                    canvas.restoreState()
                canvas.restoreState()
                
            doc_pdf.build(pdf_story, onFirstPage=draw_ledger_decorations)
            self.popup('Report Hub', f"Grant Progress Report Compiled Successfully!\nSaved: {out_pdf_name}")
            open_file_cross_platform(out_pdf_name)
        except Exception as ex:
            self.popup('Print Error', f"Grant PDF Compilation Failed: {str(ex)}")

    # =========================================================================
    def load_smc_details_view(self):
        self.content_area.clear_widgets()
        self.current_view = 'smc_details'
        is_mob = (kivy_platform != 'win')
        from kivy.uix.widget import Widget
        
        ctrl_bar = GridLayout(cols=2, size_hint_y=None, height=dp(48) if is_mob else 50, spacing=dp(8) if is_mob else 12, padding=5)
        ctrl_bar.add_widget(Label(text='SMC Session:', color=(0,0,0,1), bold=True, font_size=sp(13.5) if is_mob else 13.5))
        
        self.smc_session_spinner = CustomSpinner(text='2026-2027', values=('2026-2027', '2027-2028', '2028-2029'), size_hint_y=None, height=dp(42) if is_mob else 36)
        self.smc_session_spinner.bind(text=lambda sp, tx: self.refresh_smc_members_grid())
        ctrl_bar.add_widget(self.smc_session_spinner)
        self.content_area.add_widget(ctrl_bar)
        self.content_area.add_widget(Widget(size_hint_y=None, height=dp(6) if is_mob else 10))
        
        main_scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
        self.smc_main_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(12) if is_mob else 15, padding=5)
        self.smc_main_layout.bind(minimum_height=self.smc_main_layout.setter('height'))
        
        main_scroll.add_widget(self.smc_main_layout)
        self.content_area.add_widget(main_scroll)
        self.refresh_smc_members_grid()
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: setattr(self, 'smc_popup_focus_index', 0) or (hasattr(self.smc_session_spinner, 'set_visual_focus') and self.smc_session_spinner.set_visual_focus(True)), 0.1)

    def refresh_smc_members_grid(self):
        self.smc_main_layout.clear_widgets()
        SMC_FILE = 'SMC_Members_Database.xlsx'
        is_mob = (kivy_platform != 'win')
        import os
        from kivy.graphics import Color, Rectangle
        from kivy.uix.widget import Widget
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from kivy.uix.spinner import Spinner
        
        current_session = self.smc_session_spinner.text.strip()
        existing_data_dict = {}
        
        if os.path.exists(SMC_FILE):
            try:
                df = pd.read_excel(SMC_FILE, dtype=str)
                for _, r in df.iterrows():
                    if str(r.get('Session', '')).strip() == current_session:
                        s_no_i = int(float(str(r.get('S.No.', 0)).strip()))
                        existing_data_dict[s_no_i] = (
                            str(r.get('Member Name', '')).replace('nan', '').strip(), 
                            str(r.get('Designation', '')).replace('nan', '').strip(), 
                            str(r.get('Gender', 'Male')).replace('nan', 'Male').strip(), 
                            str(r.get('Mobile No', '')).replace('nan', '').strip(), 
                            str(r.get('Photo Path', '')).replace('nan', '').strip()
                        )
            except Exception: pass

        def trigger_live_camera_capture(s_no_key, btn_target, img_preview_widget):
            os.makedirs('SMC_Photos', exist_ok=True)
            m_name_w = self.smc_inputs_map.get(s_no_key, (None,))[0]
            raw_m_nm = m_name_w.text.strip().replace(' ', '_') if hasattr(m_name_w, 'text') else ''
            clean_m_nm = ''.join(c for c in raw_m_nm if c.isalnum() or c == '_')
            name_part = f"_{clean_m_nm}" if clean_m_nm else ""
            dest_path = os.path.abspath(os.path.join('SMC_Photos', f"SMC_{current_session.replace('-','_')}_{s_no_key}{name_part}.jpg"))

            def _apply_smc_photo(final_p):
                if final_p and os.path.exists(final_p):
                    self.smc_photo_paths_map[s_no_key] = final_p
                    img_preview_widget.source = final_p
                    img_preview_widget.reload()
                    btn_target.text = "CHANGE"
                    btn_target.background_color = (0.02, 0.45, 0.2, 1)

            def on_smc_photo_picked(p_path):
                if p_path and os.path.exists(p_path):
                    try:
                        comp_p = compress_image_under_30kb(p_path, dest_path, max_kb=28)
                        _apply_smc_photo(comp_p)
                    except Exception:
                        pass

            if kivy_platform == 'win':
                try:
                    import cv2
                    cam = cv2.VideoCapture(0)
                    if not cam.isOpened():
                        raise Exception("Camera missing")
                    self.popup('Camera Guide', "LIVE WEBCAM ACTIVE!\n\n1. Look at camera\n2. Press 'SPACEBAR' to capture\n3. Press 'ESC' to exit")
                    while True:
                        ret, frame = cam.read()
                        if not ret: break
                        cv2.imshow("SMC MEMBER LIVE PHOTO CAPTURE", frame)
                        k = cv2.waitKey(1)
                        if k % 256 == 27: break
                        elif k % 256 == 32:
                            cv2.imwrite(dest_path, frame)
                            comp_p = compress_image_under_30kb(dest_path, dest_path, max_kb=28)
                            _apply_smc_photo(comp_p)
                            break
                    cam.release(); cv2.destroyAllWindows()
                except Exception:
                    select_file_cross_platform("Select SMC Member Photo", [("Image Files", "*.png *.jpg *.jpeg")], on_smc_photo_picked)
            else:
                pl_opt = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
                pl_opt.add_widget(Label(text=f"Member No. {s_no_key} Photo Option:", bold=True, font_size=sp(14), color=(1,1,1,1)))
                b_row = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(44))
                b_cam = Button(text="CAMERA", background_color=(0, 0.45, 0.65, 1), bold=True, font_size=sp(13.5))
                b_gal = Button(text="GALLERY", background_color=(0.1, 0.55, 0.25, 1), bold=True, font_size=sp(13.5))
                b_row.add_widget(b_cam); b_row.add_widget(b_gal)
                pl_opt.add_widget(b_row)
                pop_opt = Popup(title="SMC Photo Source", content=pl_opt, size_hint=(0.88, 0.32), background='', background_color=(0.14, 0.14, 0.14, 0.98))

                def _choose_cam(x):
                    pop_opt.dismiss()
                    capture_mobile_camera_safe(dest_path, _apply_smc_photo, self.popup)

                def _choose_gal(x):
                    pop_opt.dismiss()
                    select_file_cross_platform("Select SMC Member Photo", [("Image Files", "*.png *.jpg *.jpeg")], on_smc_photo_picked)

                b_cam.bind(on_press=_choose_cam)
                b_gal.bind(on_press=_choose_gal)
                pop_opt.open()

        lbl_smc_hdr = Label(text="SMC ELECTED & EX-OFFICIO MEMBERS", color=(0.05, 0.25, 0.45, 1), bold=True, font_size=sp(14) if is_mob else 15, size_hint_y=None, height=dp(32) if is_mob else 36, halign='left', valign='middle')
        lbl_smc_hdr.bind(size=lbl_smc_hdr.setter('text_size'))
        self.smc_main_layout.add_widget(lbl_smc_hdr)
        
        form_scroll = ScrollView(size_hint=(1, None), height=dp(460) if is_mob else 420, do_scroll_x=True, do_scroll_y=True)
        vertical_form_box = BoxLayout(orientation='vertical', spacing=dp(10) if is_mob else 14, size_hint_x=None if is_mob else 1, size_hint_y=None, padding=(10, 10, 10, 15))
        if is_mob:
            vertical_form_box.width = dp(860)
        vertical_form_box.bind(minimum_height=vertical_form_box.setter('height'))
        
        smc_master_tabs_list = [self.smc_session_spinner]
        self.smc_inputs_map = {}; self.smc_photo_paths_map = {}
        ex_officio_titles = {12: 'Secretary (H.M.)', 13: 'A.N.M.', 14: 'Lekhpal', 15: 'Ward Member'}

        for d in range(1, 16):
            is_govt_officer = (d >= 12)
            role_fixed_title = ex_officio_titles[d] if is_govt_officer else ""
            
            member_card = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(52) if is_mob else 46, spacing=dp(8) if is_mob else 10, padding=(5, 3, 5, 3))
            with member_card.canvas.before:
                Color(0.95, 0.96, 0.98, 1)
                member_card.rect = Rectangle(size=member_card.size, pos=member_card.pos)
            member_card.bind(size=lambda ins, val: setattr(ins.rect, 'size', ins.size), pos=lambda ins, val: setattr(ins.rect, 'pos', ins.pos))

            lbl_cap = f"No. {d}" if not is_govt_officer else f"Govt {d-11}"
            member_card.add_widget(Label(text=lbl_cap, size_hint_x=0.07, color=(0.05, 0.25, 0.45, 1), bold=True, font_size=sp(12) if is_mob else 12))
            
            old_tuple = existing_data_dict.get(d, ('', '', 'Male', '', ''))
            val_name, val_desig, val_gender, val_mob, val_p_path = old_tuple
            
            in_name = CustomText(text=str(val_name), multiline=False, size_hint_x=0.25, font_size=13, hint_text="Enter Member Name")
            member_card.add_widget(in_name); smc_master_tabs_list.append(in_name)
            
            if not is_govt_officer:
                default_role = val_desig if val_desig else ('Chairman' if d == 1 else ('Vice-Chairman' if d == 2 else 'Parent Member'))
                in_desig = CustomSpinner(text=str(default_role), values=('Chairman', 'Vice-Chairman', 'Parent Member', 'Teacher Member', 'Elected Member'), size_hint_x=0.19)
                member_card.add_widget(in_desig); smc_master_tabs_list.append(in_desig)
            else:
                in_desig = Label(text=str(role_fixed_title), size_hint_x=0.19, color=(0.4, 0.2, 0, 1), bold=True, font_size=sp(12) if is_mob else 12.5)
                member_card.add_widget(in_desig)
                
            current_gender = val_gender if val_gender else 'Male'
            in_gender = CustomSpinner(text=str(current_gender), values=('Male', 'Female'), size_hint_x=0.11)
            member_card.add_widget(in_gender); smc_master_tabs_list.append(in_gender)
            
            raw_val_str = str(val_mob).strip()
            raw_mob_str = raw_val_str.split('.')[0] if '.' in raw_val_str else raw_val_str
            if raw_mob_str == 'nan': raw_mob_str = ''

            in_mob = CustomText(text=raw_mob_str, max_chars=10, only_digits=True, multiline=False, size_hint_x=0.16, font_size=13, hint_text="10 Digits")
            member_card.add_widget(in_mob); smc_master_tabs_list.append(in_mob)
            
            p_exist = str(val_p_path).strip()
            has_valid_pic = bool(p_exist and p_exist.lower() != 'nan' and os.path.exists(p_exist))
            self.smc_photo_paths_map[d] = p_exist if has_valid_pic else ""

            img_box = Image(
                source=p_exist if has_valid_pic else get_exe_safe_path('logo.png'),
                size_hint=(None, None),
                size=(dp(40), dp(46)) if is_mob else (36, 40),
                allow_stretch=True,
                keep_ratio=False
            )
            member_card.add_widget(img_box)

            btn_pic = Button(
                text="CHANGE" if has_valid_pic else "PHOTO",
                font_size=sp(11) if is_mob else 11,
                bold=True,
                size_hint_x=0.12,
                background_color=(0.1, 0.45, 0.65, 1) if has_valid_pic else (0.3, 0.3, 0.3, 1)
            )
            btn_pic.bind(on_press=lambda instance, s_idx=d, im_w=img_box: trigger_live_camera_capture(s_idx, instance, im_w))
            member_card.add_widget(btn_pic)
            
            self.smc_inputs_map[d] = (in_name, in_desig, in_gender, in_mob)
            vertical_form_box.add_widget(member_card)
            
        form_scroll.add_widget(vertical_form_box)
        self.smc_main_layout.add_widget(form_scroll)
        self.smc_main_layout.add_widget(Widget(size_hint_y=None, height=dp(8) if is_mob else 10))
        
        bottom_btn_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 45, spacing=dp(10) if is_mob else 20, padding=(dp(6), 0) if is_mob else (40, 0, 40, 0))
        btn_print_report = Button(text='PRINT PDF' if is_mob else '🖨️ GENERATE & PRINT COMPREHENSIVE PDF REPORT', background_color=(0.85, 0.45, 0.0, 1), bold=True, font_size=sp(12.5) if is_mob else 12.5)
        btn_lock_save = Button(text='SAVE SMC DATA' if is_mob else '💾 LOCK & SAVE ALL MEMBERS DATA TO DATABASE', background_color=(0.02, 0.45, 0.2, 1), bold=True, font_size=sp(12.5) if is_mob else 12.5)
        
        btn_print_report.bind(on_press=lambda x: self.generate_smc_report_pdf())
        btn_lock_save.bind(on_press=self.action_save_smc_members_data)
        
        bottom_btn_layout.add_widget(btn_print_report)
        bottom_btn_layout.add_widget(btn_lock_save)
        self.smc_main_layout.add_widget(bottom_btn_layout)
        
        smc_master_tabs_list.extend([btn_print_report, btn_lock_save])
        self.smc_seq = smc_master_tabs_list
        self.smc_popup_focus_index = 0

        def update_smc_local_widget_colors():
            for w in self.smc_seq:
                if hasattr(w, 'background_color'): w.background_color = (1, 1, 1, 1)
                if hasattr(w, 'set_visual_focus'): w.set_visual_focus(False)
                elif hasattr(w, 'state'): w.state = 'normal'
                if ('Spinner' in str(type(w)) or 'CustomSpinner' in str(type(w))) and hasattr(w, 'dismiss'):
                    w.dismiss()
                    w.is_open = False
                
            if self.smc_popup_focus_index < len(self.smc_seq):
                target_w = self.smc_seq[self.smc_popup_focus_index]
                target_type = str(type(target_w))
                if hasattr(target_w, 'set_visual_focus'):
                    target_w.set_visual_focus(True)
                if 'CustomText' in target_type or 'TextInput' in target_type:
                    target_w.background_color = (0.9, 1.0, 0.9, 1)
                    target_w.focus = True
                elif 'CustomSpinner' in target_type or 'Spinner' in target_type:
                    pass 
                elif 'Button' in target_type:
                    target_w.state = 'down'

        def smc_local_keyboard_hook(window_instance, key, scancode, codepoint, modifiers):
            if self.current_view != 'smc_details': return False
            num_w = len(self.smc_seq)
            current_w = self.smc_seq[self.smc_popup_focus_index] if self.smc_popup_focus_index < num_w else None
            
            if key in (273, 274, 275, 276):
                if current_w and ('CustomSpinner' in str(type(current_w)) or 'Spinner' in str(type(current_w))):
                    vals = current_w.values
                    s_idx = vals.index(current_w.text) if current_w.text in vals else -1
                    shift_val = -1 if key in (273, 276) else 1
                    current_w.text = vals[(s_idx + shift_val) % len(vals)]
                    return True
                shift = -1 if key in (273, 276) else 1
                self.smc_popup_focus_index = (self.smc_popup_focus_index + shift) % num_w
                update_smc_local_widget_colors(); return True
                
            elif key in (9, 13, 271):
                if current_w and ('Button' in str(type(current_w))):
                    current_w.state = 'normal'
                    if "PHOTO" in getattr(current_w, 'text', '').upper() or "CHANGE" in getattr(current_w, 'text', '').upper():
                        if key in (13, 271): 
                            current_w.trigger_action(); return True
                    else:
                        if key in (13, 271): current_w.trigger_action(); return True
                
                shift = -1 if 'shift' in modifiers else 1
                self.smc_popup_focus_index = (self.smc_popup_focus_index + shift) % num_w
                update_smc_local_widget_colors()
                return True
            return False

        from kivy.core.window import Window
        Window.bind(on_key_down=smc_local_keyboard_hook)
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: update_smc_local_widget_colors(), 0.05)

    def action_save_smc_members_data(self, instance):
        SMC_FILE = 'SMC_Members_Database.xlsx'
        import os
        current_session = self.smc_session_spinner.text.strip()
        smc_records = []
        
        try:
            for s_no, (in_n, in_d, in_g, in_m) in self.smc_inputs_map.items():
                m_name = in_n.text.strip() if hasattr(in_n, 'text') else str(in_n)
                m_desig = in_d.text.strip() if hasattr(in_d, 'text') else str(in_d).strip()
                m_gender = in_g.text.strip() if hasattr(in_g, 'text') else str(in_g)
                m_mobile = in_m.text.strip() if hasattr(in_m, 'text') else str(in_m)
                p_path = self.smc_photo_paths_map.get(s_no, "")
                
                smc_records.append({
                    'Session': current_session,
                    'S.No.': s_no,
                    'Member Name': m_name,
                    'Designation': m_desig,
                    'Gender': m_gender,
                    'Mobile No': m_mobile,
                    'Photo Path': p_path
                })
                
            new_df = pd.DataFrame(smc_records)
            if not os.path.exists(SMC_FILE):
                new_df.to_excel(SMC_FILE, index=False)
            else:
                old_df = pd.read_excel(SMC_FILE, dtype=str)
                kept_rows = []
                for _, r_old in old_df.iterrows():
                    if str(r_old.get('Session', '')).strip() != current_session:
                        kept_rows.append(dict(r_old))
                cleaned_old = pd.DataFrame(kept_rows, columns=old_df.columns)
                pd.concat([cleaned_old, new_df], ignore_index=True).to_excel(SMC_FILE, index=False)
                
            self.popup('Success', f'SMC Committee Details saved safely for Session {current_session}!')
            self.refresh_smc_members_grid()
        except Exception as e:
            self.popup('Storage Failed', f"Storage Blocked: {str(e)}")

    def generate_smc_report_pdf(self):
        import os
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, TableStyle, Table, Paragraph, Spacer, Image
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib import colors
        
        current_session = self.smc_session_spinner.text.strip()
        SMC_FILE = 'SMC_Members_Database.xlsx'
        
        if not os.path.exists(SMC_FILE):
            self.popup('Alert', 'SMC Database is empty! Please fill and save data first.'); return
            
        try:
            df = pd.read_excel(SMC_FILE, dtype=str)
            filtered_rows = []
            for _, r_smc in df.iterrows():
                if str(r_smc.get('Session', '')).strip() == current_session:
                    filtered_rows.append(dict(r_smc))
            if not filtered_rows: 
                self.popup('No Data', f'No records found for Session {current_session}.'); return
                
            out_pdf_name = f"SMC_Committee_Report_Session_{current_session.replace('-','_')}.pdf"
            
            if os.path.exists(out_pdf_name):
                try: os.rename(out_pdf_name, out_pdf_name)
                except Exception:
                    import random; out_pdf_name = f"SMC_Committee_Report_Session_{current_session.replace('-','_')}_{random.randint(10,99)}.pdf"

            doc_pdf = SimpleDocTemplate(out_pdf_name, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=25)
            pdf_story = []
            
            NAVY_THEME = colors.HexColor("#0A3663"); LIGHT_BLUE = colors.HexColor("#F4F8FA")
            h_main = ParagraphStyle('H_M_S', fontName='Helvetica-Bold', fontSize=17, leading=21, textColor=NAVY_THEME, alignment=1)
            h_sub = ParagraphStyle('H_S_S', fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=colors.black, alignment=1)
            th_style = ParagraphStyle('T_H_S', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.white, alignment=1)
            td_bold = ParagraphStyle('T_D_B_S', fontName='Helvetica-Bold', fontSize=9, leading=13, textColor=colors.black, alignment=1)
            td_norm = ParagraphStyle('T_D_N_S', fontName='Helvetica', fontSize=9, leading=13, textColor=colors.black, alignment=1)
            
            pdf_story.append(Spacer(1, 15))
            pdf_story.append(Paragraph("<b>PRIMARY SCHOOL PANAUTA, WAZIRGANJ (BUDAUN)</b>", h_main))
            pdf_story.append(Paragraph(f"<b>SCHOOL MANAGEMENT COMMITTEE (SMC) MEMBERS DISCLOSURE REGISTER<br/>ACADEMIC SESSION: {current_session}</b>", h_sub))
            pdf_story.append(Spacer(1, 20))
            
            reg_headers = [Paragraph("<b>S.No.</b>", th_style), Paragraph("<b>NAME OF MEMBER</b>", th_style), Paragraph("<b>DESIGNATION ROLE</b>", th_style), Paragraph("<b>GENDER</b>", th_style), Paragraph("<b>MOBILE NO.</b>", th_style), Paragraph("<b>PHOTO</b>", th_style)]
            reg_table_rows = [reg_headers]
            
            def get_sno_int(r_item):
                try: return int(float(str(r_item.get('S.No.', 1)).strip()))
                except Exception: return 99

            sorted_rows = sorted(filtered_rows, key=get_sno_int)
            
            display_counter = 1
            for r in sorted_rows:
                s_no_actual = get_sno_int(r)
                if display_counter == 12:
                    reg_table_rows.append([Paragraph("<b>---</b>", td_bold), Paragraph("<b>EX-OFFICIO OFFICERS & GOVT MEMBERS LIST</b>", td_bold), Paragraph("<b>GOVT OFFICIALS</b>", td_bold), Paragraph("<b>---</b>", td_bold), Paragraph("<b>---</b>", td_bold), Paragraph("<b>---</b>", td_bold)])
                
                print_s_no = str(s_no_actual) if s_no_actual < 12 else str(s_no_actual - 11)
                is_vip_role = s_no_actual in [1, 12]
                
                raw_mob = str(r.get('Mobile No', '')).strip()
                if raw_mob.endswith('.0'): raw_mob = raw_mob[:-2]
                if not raw_mob or raw_mob == 'nan': raw_mob = '---'
                
                p_path = str(r.get('Photo Path', '')).strip()
                if p_path and os.path.exists(p_path):
                    try: img_widget = Image(p_path, width=32, height=36)
                    except Exception: img_widget = Paragraph("<i>No Pic</i>", td_norm)
                else:
                    img_widget = Paragraph("<i>No Pic</i>", td_norm)
                
                reg_table_rows.append([
                    Paragraph(print_s_no, td_bold),
                    Paragraph(str(r.get('Member Name', '')).upper() if str(r.get('Member Name', '')).strip() and str(r.get('Member Name', '')) != 'nan' else "<i>(VACANT)</i>", td_bold if is_vip_role else td_norm),
                    Paragraph(str(r.get('Designation', '')), td_bold if is_vip_role else td_norm),
                    Paragraph(str(r.get('Gender', 'Male')).upper(), td_norm),
                    Paragraph(raw_mob, td_norm),
                    img_widget
                ])
                display_counter += 1
                
            t_register = Table(reg_table_rows, colWidths=[32, 168, 130, 55, 105, 60], repeatRows=1)
            t_style_rules = [
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#4A4A4A")), ('BOX', (0,0), (-1,-1), 1.5, NAVY_THEME),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BACKGROUND', (0,0), (-1,0), NAVY_THEME), ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)
            ]
            
            for i in range(1, len(reg_table_rows)):
                try:
                    if "EX-OFFICIO" in str(reg_table_rows[i][1].text):
                        t_style_rules.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor("#E3F2FD"))); continue
                except Exception: pass
                if i % 2 == 0: t_style_rules.append(('BACKGROUND', (0, i), (-1, i), LIGHT_BLUE))
                    
            t_register.setStyle(TableStyle(t_style_rules))
            pdf_story.append(t_register); pdf_story.append(Spacer(1, 45))
            
            w_sig_panel = 275
            t_sig = Table([[Paragraph("________________________", td_bold), Paragraph("________________________", td_bold)], [Paragraph("SMC SECRETARY (H.M.)", td_bold), Paragraph("SMC CHAIRMAN SIGNATURE", td_bold)]], colWidths=[w_sig_panel, w_sig_panel])
            t_sig.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0, colors.white), ('VALIGN', (0,0), (-1,-1), 'BOTTOM'), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 10)]))
            pdf_story.append(t_sig)
            
            def draw_smc_decorations(canvas, document):
                canvas.saveState()
                if os.path.exists(get_exe_safe_path("basic.png")): canvas.drawImage(get_exe_safe_path("basic.png"), 20, 768, width=54, height=52, mask='auto')
                logo_p = get_exe_safe_path("logo.png")
                if os.path.exists(logo_p):
                    canvas.drawImage(logo_p, 520, 768, width=54, height=52, mask='auto')
                    canvas.saveState(); canvas.setFillAlpha(0.04); canvas.drawImage(logo_p, 172, 280, width=250, height=250, mask='auto'); canvas.restoreState()
                canvas.restoreState()
                
            doc_pdf.build(pdf_story, onFirstPage=draw_smc_decorations)
            self.popup('Report Hub', f"SMC Report Compiled Successfully under New Layout!\nSaved: {out_pdf_name}")
            open_file_cross_platform(out_pdf_name)
        except Exception as ex: self.popup('Print Error', f"PDF Compilation Failed: {str(ex)}")
    # =========================================================================
    # 🏛️ MASTER MODULE: COOK-CUM-HELPER DETAILS WITH LIVE WEBCAM & PURE WHITE UI
    # =========================================================================
    def load_cook_details_view(self):
        self.content_area.clear_widgets()
        self.current_view = 'cook_details'
        is_mob = (kivy_platform != 'win')
        from kivy.uix.widget import Widget
        
        ctrl_bar = GridLayout(cols=2, size_hint_y=None, height=dp(48) if is_mob else 50, spacing=dp(8) if is_mob else 12, padding=5)
        ctrl_bar.add_widget(Label(text='Cook Session:', color=(0,0,0,1), bold=True, font_size=sp(13.5) if is_mob else 13.5))
        
        session_values = [f"{year}-{year+1}" for year in range(2026, 2051)]
            
        self.cook_session_spinner = CustomSpinner(text='2026-2027', values=tuple(session_values), size_hint_y=None, height=dp(42) if is_mob else 36)
        self.cook_session_spinner.bind(text=lambda sp, tx: self.refresh_cook_members_grid())
        ctrl_bar.add_widget(self.cook_session_spinner)
        self.content_area.add_widget(ctrl_bar)
        self.content_area.add_widget(Widget(size_hint_y=None, height=dp(6) if is_mob else 10))
        
        main_scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
        self.cook_main_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(12) if is_mob else 15, padding=5)
        self.cook_main_layout.bind(minimum_height=self.cook_main_layout.setter('height'))
        
        main_scroll.add_widget(self.cook_main_layout)
        self.content_area.add_widget(main_scroll)
        
        self.refresh_cook_members_grid()

    def refresh_cook_members_grid(self):
        self.cook_main_layout.clear_widgets()
        COOK_FILE = 'Cook_Members_Database.xlsx'
        is_mob = (kivy_platform != 'win')
        import os
        from kivy.graphics import Color, Rectangle
        from kivy.uix.widget import Widget
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from kivy.uix.image import Image
        
        current_session = self.cook_session_spinner.text.strip()
        
        master_form_box = BoxLayout(orientation='vertical' if is_mob else 'horizontal', spacing=dp(10) if is_mob else 15, padding=5, size_hint_y=None, height=dp(520) if is_mob else 310)

        left_form = GridLayout(cols=2, spacing=(dp(8), dp(8)) if is_mob else (12, 10), size_hint=(1, None) if is_mob else (0.60, 1), height=dp(395) if is_mob else 300, padding=5)
        cook_master_tabs_list = [self.cook_session_spinner]
        self.cook_fields = {}

        fields_config = [
            ('Name of MDM Cook', 'text', 'Enter Cook Name', None),
            ('Gender / Sex', 'spinner', ('Female', 'Male'), None),
            ('Date of Birth', 'text', 'DD-MM-YYYY', 10),
            ('Bank Account No', 'text', 'Max 16 Digits', 16),
            ('Bank Name', 'text', 'State Bank of India', None),
            ('Bank IFSC Code', 'text', '11 Digit IFSC', 11),
            ('Aadhar Number', 'text', '12 Digit Aadhar', 12),
            ('Mobile Number', 'text', '10 Digit Mobile', 10)
        ]

        for label_text, f_type, placeholder, char_limit in fields_config:
            lbl_c = Label(text=label_text, color=(0,0,0,1), bold=True, font_size=sp(12.5) if is_mob else 13, halign='left', valign='middle')
            lbl_c.bind(size=lbl_c.setter('text_size'))
            left_form.add_widget(lbl_c)
            if f_type == 'spinner':
                spin = CustomSpinner(text=str(placeholder), values=placeholder, size_hint_y=None, height=dp(42) if is_mob else 36)
                left_form.add_widget(spin); cook_master_tabs_list.append(spin)
                self.cook_fields[label_text] = spin
            else:
                only_dig = (label_text in ['Bank Account No', 'Aadhar Number', 'Mobile Number'])
                txt = CustomText(max_chars=char_limit, only_digits=only_dig, multiline=False, hint_text=placeholder, halign='center', size_hint_y=None, height=dp(42) if is_mob else 36)
                left_form.add_widget(txt); cook_master_tabs_list.append(txt)
                self.cook_fields[label_text] = txt

        # 📸 [भाग 2]: फोटो पैनल (मोबाइल पर बड़ा फोटो बॉक्स और कॉम्पैक्ट बटन्स)
        right_photo_panel = BoxLayout(orientation='horizontal' if is_mob else 'vertical', size_hint=(1, None) if is_mob else (0.40, 1), height=dp(145) if is_mob else 300, padding=dp(8) if is_mob else 10, spacing=dp(12) if is_mob else 10)
        with right_photo_panel.canvas.before:
            Color(0.95, 0.96, 0.98, 1)
            right_photo_panel.rect = Rectangle(size=right_photo_panel.size, pos=right_photo_panel.pos)
        right_photo_panel.bind(size=lambda ins, val: setattr(right_photo_panel.rect, 'size', ins.size), pos=lambda ins, val: setattr(right_photo_panel.rect, 'pos', ins.pos))
        
        if not is_mob:
            right_photo_panel.add_widget(Label(text='📸 MDM COOK PHOTO CONTROLLER', font_size=13, bold=True, color=(0.05, 0.25, 0.45, 1), size_hint_y=None, height=25))
        
        self.cook_photo_widget = Image(source='', size_hint=(None, None), size=(dp(110), dp(132)) if is_mob else (110, 120), allow_stretch=True, keep_ratio=False, pos_hint={'center_x': 0.5, 'center_y': 0.5})
        right_photo_panel.add_widget(self.cook_photo_widget)
        
        self.cook_photo_path_str = ""

        def _get_cook_photo_path():
            os.makedirs('Cook_Photos', exist_ok=True)
            c_nm = self.cook_fields['Name of MDM Cook'].text.strip().replace(' ', '_')
            clean_c_nm = ''.join(c for c in c_nm if c.isalnum() or c == '_') or 'Cook'
            c_id = self.cook_fields['Aadhar Number'].text.strip() or self.cook_fields['Bank Account No'].text.strip()
            id_suffix = f"_{c_id[-4:]}" if len(c_id) >= 4 else (f"_{c_id}" if c_id else "")
            return os.path.abspath(os.path.join('Cook_Photos', f"Cook_{clean_c_nm}{id_suffix}.jpg"))
        
        btn_capture_live = Button(text="CAMERA" if is_mob else "📸 LIVE Snap Camera", font_size=sp(12) if is_mob else 11, bold=True, size_hint=(None, None) if is_mob else (1, None), width=dp(105), height=dp(38) if is_mob else 36, background_color=(0.1, 0.45, 0.65, 1))
        def local_snap_action(instance):
            dest_path = _get_cook_photo_path()

            if kivy_platform == 'win':
                try:
                    import cv2
                    cam = cv2.VideoCapture(0)
                    if not cam.isOpened():
                        raise Exception("Camera missing")
                    self.popup('Camera Guide', "LIVE WEBCAM ACTIVE!\n\n1. Look at camera\n2. Press 'SPACEBAR' to capture photo\n3. Press 'ESC' to exit")
                    while True:
                        ret, frame = cam.read()
                        if not ret: break
                        cv2.imshow("COOK MEMBER LIVE PHOTO CAPTURE", frame)
                        k = cv2.waitKey(1)
                        if k % 256 == 27: break
                        elif k % 256 == 32:
                            cv2.imwrite(dest_path, frame)
                            comp_p = compress_image_under_30kb(dest_path, dest_path, max_kb=28)
                            self.cook_photo_path_str = comp_p
                            self.cook_photo_widget.source = comp_p
                            self.cook_photo_widget.reload()
                            btn_capture_live.text = "✅ SNAP CAPTURED"
                            btn_capture_live.background_color = (0.02, 0.45, 0.2, 1)
                            break
                    cam.release(); cv2.destroyAllWindows()
                except Exception:
                    self.popup('Camera Error', 'Could not open live snapshot webcam feed!')
            else:
                def on_cook_cam_ok(fp):
                    self.cook_photo_path_str = fp
                    self.cook_photo_widget.source = fp
                    self.cook_photo_widget.reload()
                    btn_capture_live.text = "CAPTURED"
                    btn_capture_live.background_color = (0.02, 0.45, 0.2, 1)

                capture_mobile_camera_safe(dest_path, on_cook_cam_ok, self.popup)
        btn_capture_live.bind(on_press=local_snap_action)

        btn_browse_gallery = Button(text="GALLERY" if is_mob else "🖼️ BROWSE FROM GALLERY", font_size=sp(12) if is_mob else 11, bold=True, size_hint=(None, None) if is_mob else (1, None), width=dp(105), height=dp(38) if is_mob else 36, background_color=(0.2, 0.2, 0.2, 1))
        def local_browse_action(instance):
            def on_cook_photo_picked(p_path):
                if p_path and os.path.exists(p_path):
                    try:
                        dest_path = _get_cook_photo_path()
                        comp_p = compress_image_under_30kb(p_path, dest_path, max_kb=28)
                        self.cook_photo_path_str = comp_p
                        self.cook_photo_widget.source = comp_p
                        self.cook_photo_widget.reload()
                        btn_browse_gallery.text = "ATTACHED" if is_mob else "✅ ATTACHED"
                        btn_browse_gallery.background_color = (0.02, 0.45, 0.2, 1)
                    except Exception:
                        pass

            select_file_cross_platform(
                "Select Cook Photo",
                [("Image Files", "*.png *.jpg *.jpeg *.bmp")],
                on_cook_photo_picked
            )
        btn_browse_gallery.bind(on_press=local_browse_action)
        
        if is_mob:
            cam_btns_col = BoxLayout(orientation='vertical', spacing=dp(10), padding=(0, dp(12)))
            cam_btns_col.add_widget(btn_capture_live)
            cam_btns_col.add_widget(btn_browse_gallery)
            cam_btns_col.add_widget(BoxLayout())
            right_photo_panel.add_widget(cam_btns_col)
            master_form_box.add_widget(right_photo_panel)
            master_form_box.add_widget(left_form)
        else:
            right_photo_panel.add_widget(btn_capture_live)
            right_photo_panel.add_widget(btn_browse_gallery)
            right_photo_panel.add_widget(BoxLayout())
            master_form_box.add_widget(left_form)
            master_form_box.add_widget(right_photo_panel)

        self.cook_main_layout.add_widget(master_form_box)
        
        # 📑 [भाग 3]: ऐक्शन बटन्स बार (मोबाइल पर स्क्रॉल पट्टी सहित)
        action_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 45, spacing=dp(10) if is_mob else 15, padding=(dp(4), 0) if is_mob else (30, 0, 30, 0))
        if is_mob:
            action_bar.size_hint_x = None
            action_bar.bind(minimum_width=action_bar.setter('width'))

        btn_save = Button(text='💾 SAVE & ADD NEW COOK' if is_mob else '💾 SAVE & ADD NEW COOK RECORD', background_color=(0.02, 0.45, 0.2, 1), bold=True, font_size=sp(12.5) if is_mob else 12.5, size_hint_x=None if is_mob else 1, width=dp(185))
        btn_clear = Button(text='🧹 CLEAR FORM' if is_mob else '🧹 CLEAR FORM FIELDS', background_color=(0.6, 0.1, 0.1, 1), bold=True, font_size=sp(12.5) if is_mob else 12.5, size_hint_x=None if is_mob else 1, width=dp(135))
        btn_print = Button(text='🖨️ PRINT PDF REPORT' if is_mob else '🖨️ PRINT STAFF-STYLE COMPREHENSIVE PDF REPORT', background_color=(0.85, 0.45, 0.0, 1), bold=True, font_size=sp(12.5) if is_mob else 12.5, size_hint_x=None if is_mob else 1, width=dp(175))
        
        self.is_cook_update_mode_active = False
        self.target_update_account_no_key = ""

        def clear_cook_form_fields(instance=None):
            for field_w in self.cook_fields.values():
                if hasattr(field_w, 'text') and not isinstance(field_w, Spinner): field_w.text = ""
            self.cook_photo_path_str = ""
            self.cook_photo_widget.source = ""
            self.is_cook_update_mode_active = False
            self.target_update_account_no_key = ""
            btn_save.text = '💾 SAVE & ADD NEW COOK' if is_mob else '💾 SAVE & ADD NEW COOK RECORD'
            btn_save.background_color = (0.02, 0.45, 0.2, 1)
            btn_capture_live.text = "📸 CAMERA" if is_mob else "📸 LIVE Snap Camera"
            btn_capture_live.background_color = (0.1, 0.45, 0.65, 1)
            btn_browse_gallery.text = "🖼️ GALLERY" if is_mob else "🖼️ BROWSE FROM GALLERY"
            btn_browse_gallery.background_color = (0.2, 0.2, 0.2, 1)

        def save_or_update_cook_entry_to_database(instance):
            c_name = self.cook_fields['Name of MDM Cook'].text.strip()
            c_acc = self.cook_fields['Bank Account No'].text.strip()
            c_mob = self.cook_fields['Mobile Number'].text.strip()
            
            if not c_name: self.popup('Validation Error', 'Error: Cook Name cannot be blank!'); return
            if not c_acc: self.popup('Validation Error', 'Error: Bank Account Number is required!'); return
            if len(c_mob) != 10: self.popup('Validation Error', 'Error: Mobile Number must be 10 digits!'); return
            
            new_record = {
                'Session': current_session,
                'Cook Name': c_name.upper(),
                'Gender': self.cook_fields['Gender / Sex'].text.strip(),
                'DOB': self.cook_fields['Date of Birth'].text.strip(),
                'Account No': c_acc,
                'Bank Name': self.cook_fields['Bank Name'].text.strip().upper(),
                'IFSC Code': self.cook_fields['Bank IFSC Code'].text.strip().upper(),
                'Aadhar No': self.cook_fields['Aadhar Number'].text.strip(),
                'Mobile No': c_mob,
                'Photo Path': self.cook_photo_path_str
            }
            try:
                df_new = pd.DataFrame([new_record])
                if not os.path.exists(COOK_FILE):
                    df_new.to_excel(COOK_FILE, index=False)
                else:
                    df_old = pd.read_excel(COOK_FILE, dtype=str)
                    acc_to_drop = str(self.target_update_account_no_key if self.is_cook_update_mode_active else c_acc).strip()
                    kept_rows = []
                    for _, r_old in df_old.iterrows():
                        r_s = str(r_old.get('Session', '')).strip()
                        r_a = str(r_old.get('Account No', '')).strip().replace('.0', '')
                        if not (r_s == current_session and r_a == acc_to_drop):
                            kept_rows.append(dict(r_old))
                    cleaned_old = pd.DataFrame(kept_rows, columns=df_old.columns)
                    pd.concat([cleaned_old, df_new], ignore_index=True).to_excel(COOK_FILE, index=False)
                
                msg = f"Cook '{c_name}' successfully UPDATED in Database!" if self.is_cook_update_mode_active else f"Cook '{c_name}' successfully SAVED into Database!"
                self.popup('Success', msg)
                clear_cook_form_fields(); self.refresh_cook_members_grid()
            except Exception as e: 
                self.popup('Failed', f"Storage Blocked: {str(e)}")

        btn_save.bind(on_press=save_or_update_cook_entry_to_database)
        btn_clear.bind(on_press=clear_cook_form_fields)
        btn_print.bind(on_press=lambda x: self.generate_cook_report_pdf())
        
        action_bar.add_widget(btn_save); cook_master_tabs_list.append(btn_save)
        action_bar.add_widget(btn_clear); cook_master_tabs_list.append(btn_clear)
        action_bar.add_widget(btn_print); cook_master_tabs_list.append(btn_print)
        
        if is_mob:
            act_c_scroll = ScrollView(size_hint=(1, None), height=dp(52), do_scroll_x=True, do_scroll_y=False)
            act_c_scroll.add_widget(action_bar)
            self.cook_main_layout.add_widget(act_c_scroll)
        else:
            self.cook_main_layout.add_widget(action_bar)
            
        self.cook_main_layout.add_widget(Widget(size_hint_y=None, height=dp(10) if is_mob else 15))

         # 📑 [भाग 4]: नीचे लाइव डेटाबेस ग्रिड टेबल व्यू (मोबाइल पर फुल-पेज व स्क्रॉल सहित)
        lbl_cook_list = Label(text="📋 LIVE REGISTERED MDM COOK LIST (Tap Row to Edit)", color=(0.05, 0.25, 0.45, 1), bold=True, font_size=sp(13) if is_mob else 13.5, size_hint_y=None, height=dp(30) if is_mob else 25, halign='left', valign='middle')
        lbl_cook_list.bind(size=lbl_cook_list.setter('text_size'))
        self.cook_main_layout.add_widget(lbl_cook_list)
        
        db_scroll = ScrollView(size_hint=(1, None), height=dp(360) if is_mob else 240, do_scroll_x=True, do_scroll_y=True)
        grid_table = GridLayout(cols=10, spacing=(1, 1), size_hint_x=None, size_hint_y=None, padding=2)
        grid_table.bind(minimum_height=grid_table.setter('height'))
        col_w = [dp(50), dp(155), dp(80), dp(95), dp(145), dp(125), dp(105), dp(125), dp(110), dp(65)] if is_mob else [45, 140, 75, 85, 130, 110, 95, 110, 100, 60]
        grid_table.width = sum(col_w)
        for i, w_slot in enumerate(col_w): 
            grid_table.cols_minimum[i] = w_slot
            
        with grid_table.canvas.before:
            Color(0.35, 0.35, 0.35, 1)
            grid_table.rect = Rectangle(size=grid_table.size, pos=grid_table.pos)
        grid_table.bind(size=lambda ins, val: setattr(grid_table.rect, 'size', ins.size), pos=lambda ins, val: setattr(grid_table.rect, 'pos', ins.pos))
        
        def make_hdr_cell(txt, col_idx):
            lbl = Label(text=txt, color=(1,1,1,1), bold=True, font_size=sp(11.5) if is_mob else 11, size_hint_x=None, width=col_w[col_idx], size_hint_y=None, height=dp(40) if is_mob else 34, halign='center', valign='middle')
            with lbl.canvas.before: 
                Color(0.05, 0.25, 0.45, 1)
                lbl.rect = Rectangle(size=lbl.size, pos=lbl.pos)
            lbl.bind(size=lambda ins, val: setattr(lbl.rect, 'size', ins.size), pos=lambda ins, val: setattr(lbl.rect, 'pos', ins.pos))
            return lbl

        hdrs = ['S.No', 'Name of Cook', 'Gender', 'D.O.B', 'Account Number', 'Bank Name', 'IFSC Code', 'Aadhar Number', 'Mobile No', 'Action']
        for i, h in enumerate(hdrs): 
            grid_table.add_widget(make_hdr_cell(h, i))
            
        def select_cook_row_for_update_logic(row_data_dict):
            self.cook_fields['Name of MDM Cook'].text = str(row_data_dict.get('Cook Name', '')).replace('nan','').strip()
            self.cook_fields['Gender / Sex'].text = str(row_data_dict.get('Gender', 'Female')).replace('nan','Female').strip()
            self.cook_fields['Date of Birth'].text = str(row_data_dict.get('DOB', '')).replace('nan','').strip()
            self.cook_fields['Bank Account No'].text = str(row_data_dict.get('Account No', '')).replace('nan','').strip()
            self.cook_fields['Bank Name'].text = str(row_data_dict.get('Bank Name', '')).replace('nan','').strip()
            self.cook_fields['Bank IFSC Code'].text = str(row_data_dict.get('IFSC Code', '')).replace('nan','').strip()
            self.cook_fields['Aadhar Number'].text = str(row_data_dict.get('Aadhar No', '')).replace('nan','').strip()
            self.cook_fields['Mobile Number'].text = str(row_data_dict.get('Mobile No', '')).replace('nan','').strip()
            
            p_path = str(row_data_dict.get('Photo Path', '')).strip()
            if p_path and p_path != 'nan' and os.path.exists(p_path):
                self.cook_photo_path_str = p_path
                self.cook_photo_widget.source = p_path
                self.cook_photo_widget.reload()
            else:
                self.cook_photo_path_str = ""
                self.cook_photo_widget.source = ""
                
            self.is_cook_update_mode_active = True
            self.target_update_account_no_key = str(row_data_dict.get('Account No', '')).strip()
            btn_save.text = '🆙 UPDATE COOK RECORD' if is_mob else '🆙 UPDATE EXISTING COOK RECORD'
            btn_save.background_color = (0.1, 0.35, 0.7, 1)

        def make_clickable_data_cell(txt, bg_c, col_idx, row_full_data_dict, is_bold=False):
            lbl = Button(text=txt, color=(0,0,0,1), bold=is_bold, font_size=sp(12) if is_mob else 11.5, size_hint_x=None, width=col_w[col_idx], size_hint_y=None, height=dp(40) if is_mob else 34, background_normal='', background_down='')
            with lbl.canvas.before: 
                Color(*bg_c)
                lbl.rect = Rectangle(size=lbl.size, pos=lbl.pos)
            lbl.bind(size=lambda ins, val: setattr(lbl.rect, 'size', ins.size), pos=lambda ins, val: setattr(lbl.rect, 'pos', ins.pos))
            lbl.bind(on_press=lambda x: select_cook_row_for_update_logic(row_full_data_dict))
            return lbl

        if os.path.exists(COOK_FILE):
            try:
                df_db = pd.read_excel(COOK_FILE, dtype=str)
                raw_records = []
                for _, r_c in df_db.iterrows():
                    if str(r_c.get('Session', '')).strip() == current_session:
                        raw_records.append(dict(r_c))
                
                def delete_cook_row(target_acc, row_num_idx):
                    try:
                        df_old = pd.read_excel(COOK_FILE, dtype=str)
                        kept_rows = []
                        for idx_o, r_o in df_old.iterrows():
                            r_s = str(r_o.get('Session', '')).strip()
                            r_a = str(r_o.get('Account No', '')).strip().replace('.0', '')
                            if target_acc and str(target_acc).strip() not in ['', 'nan']:
                                if not (r_s == current_session and r_a == str(target_acc).strip()):
                                    kept_rows.append(dict(r_o))
                            else:
                                if idx_o != row_num_idx:
                                    kept_rows.append(dict(r_o))
                        df_purged = pd.DataFrame(kept_rows, columns=df_old.columns)
                        df_purged.to_excel(COOK_FILE, index=False)
                        self.popup('Purged', 'Cook Record deleted safely from Excel Database!')
                        clear_cook_form_fields()
                        self.refresh_cook_members_grid()
                    except Exception as ex: 
                        self.popup('Error', f"Purge Blocked: {str(ex)}")

                for r_idx, row in enumerate(raw_records):
                    c_bg = (0.98, 0.98, 0.98, 1) if r_idx % 2 == 0 else (0.92, 0.94, 0.96, 1)
                    
                    def clean_cell_text(val):
                        s = str(val).strip()
                        return "" if (s in ['None', 'nan', 'NaN'] or not s) else s

                    grid_table.add_widget(make_clickable_data_cell(str(r_idx + 1), c_bg, 0, row, is_bold=True))
                    grid_table.add_widget(make_clickable_data_cell(clean_cell_text(row.get('Cook Name', '')), c_bg, 1, row))
                    grid_table.add_widget(make_clickable_data_cell(clean_cell_text(row.get('Gender', 'Female')), c_bg, 2, row))
                    grid_table.add_widget(make_clickable_data_cell(clean_cell_text(row.get('DOB', '')), c_bg, 3, row))
                    grid_table.add_widget(make_clickable_data_cell(clean_cell_text(row.get('Account No', '')), c_bg, 4, row))
                    grid_table.add_widget(make_clickable_data_cell(clean_cell_text(row.get('Bank Name', '')), c_bg, 5, row))
                    grid_table.add_widget(make_clickable_data_cell(clean_cell_text(row.get('IFSC Code', '')), c_bg, 6, row))
                    grid_table.add_widget(make_clickable_data_cell(clean_cell_text(row.get('Aadhar No', '')), c_bg, 7, row))
                    grid_table.add_widget(make_clickable_data_cell(clean_cell_text(row.get('Mobile No', '')), c_bg, 8, row))
                    
                    btn_cell = BoxLayout(size_hint_x=None, width=col_w, size_hint_y=None, height=dp(40) if is_mob else 34, padding=2)
                    with btn_cell.canvas.before: 
                        Color(*c_bg)
                        btn_cell.rect = Rectangle(size=btn_cell.size, pos=btn_cell.pos)
                    btn_cell.bind(size=lambda ins, val: setattr(btn_cell.rect, 'size', ins.size), pos=lambda ins, val: setattr(btn_cell.rect, 'pos', ins.pos))
                    
                    curr_acc_number = clean_cell_text(row.get('Account No', ''))
                    btn_del = Button(text='🗑', background_color=(0.7, 0.1, 0.1, 1), font_size=sp(13) if is_mob else 11, bold=True)
                    btn_del.bind(on_press=lambda instance, acc=curr_acc_number, idx=r_idx: delete_cook_row(acc, idx))
                    
                    btn_cell.add_widget(btn_del)
                    grid_table.add_widget(btn_cell)
            except Exception as e: 
                pass
 
        db_scroll.add_widget(grid_table)
        self.cook_main_layout.add_widget(db_scroll)
        
        self.cook_popup_focus_index = 0
        self.cook_seq = cook_master_tabs_list
        
        def update_cook_local_widget_colors():
            for w in self.cook_seq:
                if hasattr(w, 'background_color'): w.background_color = (1, 1, 1, 1)
                if hasattr(w, 'set_visual_focus'): w.set_visual_focus(False)
                elif hasattr(w, 'state'): w.state = 'normal'
                if ('Spinner' in str(type(w)) or 'CustomSpinner' in str(type(w))) and hasattr(w, 'dismiss'):
                    w.dismiss()
                    w.is_open = False
            if self.cook_popup_focus_index < len(self.cook_seq):
                target_w = self.cook_seq[self.cook_popup_focus_index]
                target_type = str(type(target_w))
                if hasattr(target_w, 'set_visual_focus'): target_w.set_visual_focus(True)
                if 'CustomText' in target_type or 'TextInput' in target_type:
                    target_w.background_color = (0.9, 1.0, 0.9, 1)
                    target_w.focus = True
                elif 'Button' in target_type: 
                    target_w.state = 'down'

        def cook_local_keyboard_hook(window_instance, key, scancode, codepoint, modifiers):
            if self.current_view != 'cook_details': return False
            num_w = len(self.cook_seq)
            current_w = self.cook_seq[self.cook_popup_focus_index] if self.cook_popup_focus_index < num_w else None
            
            if key in (273, 274, 275, 276):
                if current_w and ('CustomSpinner' in str(type(current_w)) or 'Spinner' in str(type(current_w))):
                    vals = current_w.values
                    s_idx = vals.index(current_w.text) if current_w.text in vals else -1
                    shift_val = -1 if key in (273, 276) else 1
                    current_w.text = vals[(s_idx + shift_val) % len(vals)]
                    return True
                shift = -1 if key in (273, 276) else 1
                self.cook_popup_focus_index = (self.cook_popup_focus_index + shift) % num_w
                update_cook_local_widget_colors(); return True
                
            elif key in (9, 13, 271):
                if current_w and ('Button' in str(type(current_w))):
                    current_w.state = 'normal'
                    if key in (13, 271): current_w.trigger_action(); return True
                shift = -1 if 'shift' in modifiers else 1
                self.cook_popup_focus_index = (self.cook_popup_focus_index + shift) % num_w
                update_cook_local_widget_colors(); return True
            return False

        from kivy.core.window import Window
        Window.bind(on_key_down=cook_local_keyboard_hook)
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: update_cook_local_widget_colors(), 0.05)

    def action_save_cook_members_data(self, instance):
        COOK_FILE = 'Cook_Members_Database.xlsx'
        import os
        current_session = self.cook_session_spinner.text.strip()
        cook_records = []
        try:
            for s_no, (in_n, in_g, in_d, in_a, in_b, in_i, in_aa, in_m) in self.cook_inputs_map.items():
                cook_records.append({
                    'Session': current_session, 'S.No.': s_no, 'Cook Name': in_n.text.strip(),
                    'Gender': in_g.text.strip() if hasattr(in_g, 'text') else str(in_g),
                    'DOB': in_d.text.strip(), 'Account No': in_a.text.strip(),
                    'Bank Name': in_b.text.strip(), 'IFSC Code': in_i.text.strip(),
                    'Aadhar No': in_aa.text.strip(), 'Mobile No': in_m.text.strip(),
                    'Photo Path': self.cook_photo_paths_map.get(s_no, "")
                })
            new_df = pd.DataFrame(cook_records)
            if not os.path.exists(COOK_FILE): new_df.to_excel(COOK_FILE, index=False)
            else:
                old_df = pd.read_excel(COOK_FILE, dtype=str)
                kept_rows = [dict(r_o) for _, r_o in old_df.iterrows() if str(r_o.get('Session', '')).strip() != current_session]
                cleaned_old = pd.DataFrame(kept_rows, columns=old_df.columns)
                pd.concat([cleaned_old, new_df], ignore_index=True).to_excel(COOK_FILE, index=False)
            self.popup('Success', f'MDM Cook Committee details safely saved for Session {current_session}!')
            self.refresh_cook_members_grid()
        except Exception as e: self.popup('Storage Failed', str(e))

    # 🖨️ 🍱 [मास्टर पीडीएफ प्रिंटर - Windows + Android क्रॉस-प्लेटफ़ॉर्म]
    def generate_cook_report_pdf(self):
        import os
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, TableStyle, Table, Paragraph, Spacer, Image
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib import colors
        
        current_session = self.cook_session_spinner.text.strip()
        COOK_FILE = 'Cook_Members_Database.xlsx'
        
        if not os.path.exists(COOK_FILE):
            self.popup('Alert', 'Cook Database is empty! Please save data first.'); return
            
        try:
            df = pd.read_excel(COOK_FILE, dtype=str)
            filtered_rows = []
            for _, r_c in df.iterrows():
                if str(r_c.get('Session', '')).strip() == current_session:
                    filtered_rows.append(dict(r_c))
            if not filtered_rows:
                self.popup('No Data', 'No records found.'); return
                
            out_pdf_name = f"MDM_Cook_Helpers_Report_{current_session.replace('-','_')}.pdf"
            doc_pdf = SimpleDocTemplate(out_pdf_name, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=25)
            pdf_story = []
            
            BROWN_THEME = colors.HexColor("#7A3E00"); LIGHT_GOLD = colors.HexColor("#FFF8E7")
            h_main = ParagraphStyle('H_M_C', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=BROWN_THEME, alignment=1)
            h_sub = ParagraphStyle('H_S_C', fontName='Helvetica-Bold', fontSize=11, leading=15, textColor=colors.black, alignment=1)
            th_style = ParagraphStyle('T_H_C', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.white, alignment=1)
            td_bold = ParagraphStyle('T_D_B_C', fontName='Helvetica-Bold', fontSize=9, leading=13, textColor=colors.black, alignment=1)
            td_norm = ParagraphStyle('T_D_N_C', fontName='Helvetica', fontSize=9, leading=13, textColor=colors.black, alignment=1)
            
            pdf_story.append(Spacer(1, 15))
            pdf_story.append(Paragraph("<b>PRIMARY SCHOOL PANAUTA, WAZIRGANJ (BUDAUN)</b>", h_main))
            pdf_story.append(Paragraph(f"<b>MID-DAY MEAL (MDM) COOK-CUM-HELPERS OFFICIAL PASSPORT REGISTER<br/>ACADEMIC SESSION: {current_session}</b>", h_sub))
            pdf_story.append(Spacer(1, 20))
            
            reg_headers = [Paragraph("<b>S.No.</b>", th_style), Paragraph("<b>COOK NAME</b>", th_style), Paragraph("<b>GENDER</b>", th_style), Paragraph("<b>D.O.B.</b>", th_style), Paragraph("<b>ACCOUNT NO</b>", th_style), Paragraph("<b>BANK NAME</b>", th_style), Paragraph("<b>IFSC CODE</b>", th_style), Paragraph("<b>AADHAR NUMBER</b>", th_style), Paragraph("<b>MOBILE NUMBER</b>", th_style), Paragraph("<b>PHOTO</b>", th_style)]
            reg_table_rows = [reg_headers]
            
            for idx, r in enumerate(filtered_rows, start=1):
                raw_mob = str(r.get('Mobile No', '')).strip().split('.')
                raw_adh = str(r.get('Aadhar No', '')).strip().split('.')
                if raw_mob in ['', 'nan', 'None']: raw_mob = '---'
                if raw_adh in ['', 'nan', 'None']: raw_adh = '---'
                
                p_path = str(r.get('Photo Path', '')).strip()
                if p_path and os.path.exists(p_path):
                    try: img_widget = Image(p_path, width=32, height=36)
                    except Exception: img_widget = Paragraph("<i>No Pic</i>", td_norm)
                else:
                    img_widget = Paragraph("<i>No Pic</i>", td_norm)
                
                reg_table_rows.append([
                    Paragraph(str(idx), td_bold),
                    Paragraph(str(r.get('Cook Name', '')).strip().upper(), td_bold),
                    Paragraph(str(r.get('Gender', 'Female')).strip().upper(), td_norm),
                    Paragraph(str(r.get('DOB', '---')).strip(), td_norm),
                    Paragraph(str(r.get('Account No', '---')).strip().split('.'), td_norm),
                    Paragraph(str(r.get('Bank Name', '---')).strip().upper(), td_norm),
                    Paragraph(str(r.get('IFSC Code', '---')).strip().upper(), td_norm),
                    Paragraph(raw_adh, td_norm),
                    Paragraph(raw_mob, td_norm),
                    img_widget
                ])
                
            t_register = Table(reg_table_rows, colWidths=[30, 110, 60, 65, 100, 95, 75, 110, 105, 60], repeatRows=1)
            t_style_rules = [
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#4A4A4A")), ('BOX', (0,0), (-1,-1), 1.5, BROWN_THEME),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BACKGROUND', (0,0), (-1,0), BROWN_THEME), ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)
            ]
            for i in range(1, len(reg_table_rows)):
                if i % 2 == 0: t_style_rules.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GOLD))
            t_register.setStyle(TableStyle(t_style_rules))
            pdf_story.append(t_register); pdf_story.append(Spacer(1, 45))
            
            w_sig_panel = 395
            t_sig = Table([[Paragraph("________________________", td_bold), Paragraph("________________________", td_bold)], [Paragraph("MDM IN-CHARGE SIGNATURE", td_bold), Paragraph("HEADMASTER SEAL & SIGNATURE", td_bold)]], colWidths=[w_sig_panel, w_sig_panel])
            t_sig.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0, colors.white), ('VALIGN', (0,0), (-1,-1), 'BOTTOM'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            pdf_story.append(t_sig)
            
            def draw_cook_decorations(canvas, document):
                canvas.saveState()
                if os.path.exists(get_exe_safe_path("basic.png")): canvas.drawImage(get_exe_safe_path("basic.png"), 25, 520, width=54, height=52, mask='auto')
                logo_p = get_exe_safe_path('logo.png')
                if os.path.exists(logo_p):
                    canvas.drawImage(logo_p, 765, 520, width=54, height=52, mask='auto')
                    canvas.saveState(); canvas.setFillAlpha(0.04); canvas.drawImage(logo_p, 296, 145, width=250, height=250, mask='auto'); canvas.restoreState()
                canvas.restoreState()
                
            doc_pdf.build(pdf_story, onFirstPage=draw_cook_decorations)
            self.popup('Report Hub', f"MDM Cook Helpers Report Compiled Successfully!\nSaved: {out_pdf_name}")
            open_file_cross_platform(out_pdf_name)
        except Exception as ex: self.popup('Print Error', f"PDF Compilation Failed: {str(ex)}")

    def load_tc_view(self):
        self.content_area.clear_widgets()
        self.current_view = 'tc_module'
        self.tc_inputs = []
        is_mob = (kivy_platform != 'win')
        
        with self.content_area.canvas.before:
            Color(0.78, 0.78, 0.78, 1)
            self.tc_bg = Rectangle(size=self.content_area.size, pos=self.content_area.pos)
        self.content_area.bind(size=lambda ins, val: setattr(self.tc_bg, 'size', ins.size), pos=lambda ins, val: setattr(self.tc_bg, 'pos', ins.pos))
        
        lbl_tc = Label(text='TRANSFER CERTIFICATE (T.C.)', font_size=sp(18) if is_mob else 24, bold=True, color=(0,0,0,1), size_hint_y=None, height=dp(36) if is_mob else 45, halign='center', valign='middle')
        lbl_tc.bind(size=lbl_tc.setter('text_size'))
        self.content_area.add_widget(lbl_tc)
        
        scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
        grid = GridLayout(cols=1 if is_mob else 2, spacing=(dp(10), dp(10)) if is_mob else (20, 10), size_hint_y=None, padding=dp(6) if is_mob else 10)
        grid.bind(minimum_height=grid.setter('height'))
        
        self.tc_fields_list = [
            'TRANSFER CERTIFICATE NUMBER', 'CASTE',
            'ADMISSION NUMBER (SR NO)', 'RELION',
            'PEN NO', 'APAAR ID',
            'SCHOOL NAME', 'DURATION OF RESIDENCE IN UP',
            'PLACE', 'ADDRESS',
            'DISTRICT', 'TEHSIL',
            'ADMISSION DATE', 'LAST DATE OF SCHOOL',
            'SCHOOL LEAVING DATE', 'SCHOOL LEAVING REASON',
            'STUDENT\'S NAME', 'CHARACTER STATUS',
            'AADHAR NUMBER', 'HIGHEST EXAM PASSED',
            'DATE OF BIRTH (IN NUMBERS)', 'EXAM PASSED DATE',
            'DATE OF BIRTH (IN WORDS)', 'LANGUAGE',
            'FATHER\'S NAME', 'OCCUPATION',
            'MOTHER\'S NAME'
        ]
        self.tc_fields = {}
        
        for f in self.tc_fields_list:
            box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44) if is_mob else 36, spacing=5)
            lbl = Label(text=f, size_hint_x=0.44 if is_mob else 0.42, color=(0.12, 0.12, 0.12, 1), font_size=sp(12) if is_mob else 11, bold=True, halign='left', valign='middle')
            lbl.bind(size=lbl.setter('text_size'))
            box.add_widget(lbl)
            
            if f in ['CASTE', 'RELION', 'DURATION OF RESIDENCE IN UP', 'DISTRICT', 'TEHSIL', 'SCHOOL LEAVING REASON', 'CHARACTER STATUS', 'HIGHEST EXAM PASSED', 'LANGUAGE', 'OCCUPATION']:
                vals = ['General', 'OBC', 'SC', 'ST'] if f=='CASTE' else ['Hindu', 'Muslim', 'Sikh', 'Christian']
                if f == 'DURATION OF RESIDENCE IN UP': vals = ['By Birth', '1 Year', '2 Years', '5 Years', '10 Years']
                if f == 'CHARACTER STATUS': vals = ['Good', 'Excellent', 'Satisfactory']
                if f == 'LANGUAGE': vals = ['Hindi', 'English']
                if f == 'SCHOOL LEAVING REASON': vals = ['Class 5th Passed', 'Admission in Other School', 'Moved to Other Place']
                if f == 'HIGHEST EXAM PASSED': vals = ['Class 1st Passed', 'Class 2nd Passed', 'Class 3rd Passed', 'Class 4th Passed', 'Class 5th Passed']
                if f == 'OCCUPATION': vals = ['Agriculture', 'Labourer Work', 'Govt. Job', 'Private Job']
                if f == 'DISTRICT': vals = ['Budaun', 'Bareilly', 'Moradabad', 'Aligarh', 'Lucknow', 'Kanpur']
                if f == 'TEHSIL': vals = ['Select District First']
                
                spin = CustomSpinner(text=vals[0] if isinstance(vals, list) else str(vals), values=vals if isinstance(vals, list) else [str(vals)], size_hint_x=0.56 if is_mob else 0.58)

                if f == 'DISTRICT':
                    def sync_tehsils(instance, text):
                        if text == 'Budaun': self.tc_fields['TEHSIL'].values = ['Bisauli', 'Budaun', 'Dataganj', 'Bilsi', 'Sahaswan']; self.tc_fields['TEHSIL'].text = 'Budaun'
                        elif text == 'Bareilly': self.tc_fields['TEHSIL'].values = ['Aonla', 'Bareilly', 'Baheri', 'Faridpur']; self.tc_fields['TEHSIL'].text = 'Bareilly'
                        else: self.tc_fields['TEHSIL'].values = ['Sadar']; self.tc_fields['TEHSIL'].text = 'Sadar'
                    spin.bind(text=sync_tehsils)
                    
                self.tc_fields[f] = spin; box.add_widget(spin); self.tc_inputs.append(spin)
            else:
                limit, only_dig = None, False
                if f in ['TRANSFER CERTIFICATE NUMBER', 'ADMISSION NUMBER (SR NO)', 'PEN NO', 'APAAR ID']: only_dig = True
                if f == 'AADHAR NUMBER': limit = 12; only_dig = True
                
                if f in ['DATE OF BIRTH (IN NUMBERS)', 'ADMISSION DATE', 'LAST DATE OF SCHOOL', 'SCHOOL LEAVING DATE', 'EXAM PASSED DATE']:
                    db_box = BoxLayout(orientation='horizontal', size_hint_x=0.56 if is_mob else 0.58, spacing=3)
                    txt = CustomText(max_chars=10, hint_text='DD-MM-YYYY', multiline=False, size_hint_x=0.78 if is_mob else 0.80)
                    
                    if f == 'DATE OF BIRTH (IN NUMBERS)':
                        def auto_tc_words_converter(instance, value):
                            clean = value.replace('-','').replace('/','').replace('.','').strip()
                            if len(clean) == 8:
                                self.tc_fields['DATE OF BIRTH (IN WORDS)'].text = date_to_words_eng(clean)
                        txt.bind(text=auto_tc_words_converter)
                        
                    btn_cal = Button(text='📅', size_hint_x=0.22 if is_mob else 0.20, background_color=(0.02, 0.45, 0.2, 1))
                    btn_cal.bind(on_press=lambda instance, target=txt: self.open_staff_calendar_popup(target))
                    db_box.add_widget(txt); db_box.add_widget(btn_cal)
                    self.tc_fields[f] = txt; self.tc_inputs.append(txt); box.add_widget(db_box)
                else:
                    read_only_flag = True if 'WORDS' in f else False
                    txt = CustomText(max_chars=limit, only_digits=only_dig, multiline=False, size_hint_x=0.56 if is_mob else 0.58, readonly=read_only_flag)
                    
                    if f == 'ADMISSION NUMBER (SR NO)':
                        def trigger_student_lookup(instance, value):
                            s_id = value.strip()
                            if s_id and os.path.exists(EXCEL_FILE):
                                try:
                                    df = pd.read_excel(EXCEL_FILE, dtype=str)
                                    if 'SR NO' in df.columns:
                                        matched_row = None
                                        for _, r_st in df.iterrows():
                                            if str(r_st.get('SR NO', '')).strip().replace('.0', '') == str(s_id):
                                                matched_row = r_st
                                                break
                                        if matched_row is not None:
                                            row = matched_row
                                            mappings = {
                                                "STUDENT'S NAME": "NAME", "FATHER'S NAME": "FATHER'S NAME",
                                                "MOTHER'S NAME": "MOTHER'S NAME", "AADHAR NUMBER": "ST Aadhaar NO",
                                                "ADDRESS": "ADDRESS", "CASTE": "CATEGORY", "PEN NO": "PEN NO",
                                                "APAAR ID": "APAAR ID", "DATE OF BIRTH (IN NUMBERS)": "DATE OF BIRTH (DDMMYYYY)",
                                                "ADMISSION DATE": "ADMISSION DATE (DDMMYYYY)"                                           
                                            }
                                            
                                            for tc_f, excel_f in mappings.items():
                                                actual_excel_col = excel_f
                                                if "ADMISSION DATE" in excel_f:
                                                    if "ADMISSION DATE" in df.columns: actual_excel_col = "ADMISSION DATE"
                                                    elif "DATE OF ADMISSION" in df.columns: actual_excel_col = "DATE OF ADMISSION"
                                                    elif "ADMISSION DATE (DDMMYYYY)" in df.columns: actual_excel_col = "ADMISSION DATE (DDMMYYYY)"
                                                    elif "DOA" in df.columns: actual_excel_col = "DOA"
                                                
                                                if actual_excel_col in df.columns and tc_f in self.tc_fields:
                                                    local_val = str(row[actual_excel_col]).strip()
                                                    if local_val.endswith('.0'): local_val = local_val[:-2]
                                                    if local_val.lower() == 'nan': local_val = ""
                                                                                                        # Master Smart Date Formatter (Intelligent 7 & 8 Digit String Splitter Engine)
                                                    if tc_f in ["DATE OF BIRTH (IN NUMBERS)", "ADMISSION DATE"]:
                                                        clean_date_str = local_val.replace("-","").replace("/","").strip()
                                                        
                                                        # Case 1: If it's a standard 8-digit format (e.g., 25012018)
                                                        if len(clean_date_str) == 8:
                                                            val = f"{clean_date_str[0:2]}-{clean_date_str[2:4]}-{clean_date_str[4:8]}"
                                                            
                                                        # Case 2: If it's a 7-digit format missing a leading zero (e.g., 1042026 -> 01-04-2026)
                                                        elif len(clean_date_str) == 7:
                                                            d_year = clean_date_str[-4:]
                                                            d_month = clean_date_str[-6:-4]
                                                            d_day = "0" + clean_date_str[0]
                                                            val = f"{d_day}-{d_month}-{d_year}"
                                                            
                                                        # Case 3: If it's a 7-digit format with a double-digit day (e.g., 1042026 -> 10-04-2026)
                                                        elif len(clean_date_str) == 7 and clean_date_str[0:2] == "10":
                                                            val = f"10-{clean_date_str[2:4]}-{clean_date_str[3:]}"
                                                        
                                                        # Case 4: Smart positional slicer from end to fix any dynamic length leaks
                                                        else:
                                                            if len(clean_date_str) >= 6:
                                                                val = f"{clean_date_str[:-6].zfill(2)}-{clean_date_str[-6:-4]}-{clean_date_str[-4:]}"
                                                            else:
                                                                val = local_val
                                                    else:
                                                        val = local_val
                                                    
                                                    # 🟢 [सटीक संरेखण]: टेक्स्ट फ़ील्ड में मान असाइन करना (कड़ाई से 52-स्पेस गैप पर लॉक)
                                                    self.tc_fields[tc_f].text = val
                                                                                                        
                                                    # Dynamic Words Converter runs strictly on DOB field only
                                                    if tc_f == "DATE OF BIRTH (IN NUMBERS)":
                                                        clean_dob = val.replace("-","").strip()
                                                        if len(clean_dob) == 8 and "DATE OF BIRTH (IN WORDS)" in self.tc_fields:
                                                            self.tc_fields["DATE OF BIRTH (IN WORDS)"].text = date_to_words_eng(clean_dob)
                                                                                                                    
                                except Exception as e:
                                    print("Lookup Engine Error:", str(e))
                        txt.bind(text=trigger_student_lookup)
                    self.tc_fields[f] = txt; box.add_widget(txt); self.tc_inputs.append(txt)
            grid.add_widget(box)
            
        scroll.add_widget(grid); self.content_area.add_widget(scroll)
        
        # --- 🎛️ निचला बटन पैनल (मोबाइल पर स्क्रॉल करने योग्य पट्टी ताकि कोई भी बटन न कटे) ---
        al = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48) if is_mob else 48, spacing=8, padding=(0, 5, 0, 0))
        if is_mob:
            al.size_hint_x = None
            al.bind(minimum_width=al.setter('width'))
        
        self.btn_save_tc = CustomButton(text='ADD/SAVE', background_color=(1, 0, 0, 1), bold=True, font_size=11, size_hint_x=None if is_mob else 1, width=dp(115))
        self.btn_save_tc.bind(on_press=self.save_tc_data_action)
        
        self.btn_search_tc = CustomButton(text='SEARCH', background_color=(1, 0, 1, 1), bold=True, font_size=11, size_hint_x=None if is_mob else 1, width=dp(110))
        self.btn_search_tc.bind(on_press=self.search_tc_data_action)
        
        self.btn_update_tc = CustomButton(text='UPDATE', background_color=(1, 1, 0, 1), bold=True, color=(0,0,0,1), font_size=11, size_hint_x=None if is_mob else 1, width=dp(110))
        self.btn_update_tc.bind(on_press=self.update_tc_data_action)
        
        self.btn_delete_tc = CustomButton(text='DELETE', background_color=(0, 0.8, 0.8, 1), bold=True, color=(0,0,0,1), font_size=11, size_hint_x=None if is_mob else 1, width=dp(105))
        self.btn_delete_tc.bind(on_press=self.delete_tc_data_action)
        
        self.btn_print_tc = CustomButton(text='PRINT', background_color=(0.1, 0.3, 0.1, 1), bold=True, font_size=11, size_hint_x=None if is_mob else 1, width=dp(100))
        self.btn_print_tc.bind(on_press=self.generate_tc_pdf_report)

        self.btn_download_tc_fmt = CustomButton(text='📥 DOWNLOAD FORMAT', background_color=(0.45, 0.45, 0.45, 1), bold=True, font_size=10.5, size_hint_x=None if is_mob else 1, width=dp(145))
        self.btn_download_tc_fmt.bind(on_press=self.action_download_tc_excel_format if hasattr(self, 'action_download_tc_excel_format') else self.action_download_tc_format)
        
        self.btn_upload_tc_excel = CustomButton(text='📤 UPLOAD FROM EXCEL', background_color=(0.35, 0.05, 0.55, 1), bold=True, font_size=10.5, size_hint_x=None if is_mob else 1, width=dp(155))
        self.btn_upload_tc_excel.bind(on_press=self.action_upload_tc_excel_database)

        for b_tc in [self.btn_save_tc, self.btn_search_tc, self.btn_update_tc, self.btn_delete_tc, self.btn_print_tc, self.btn_download_tc_fmt, self.btn_upload_tc_excel]:
            al.add_widget(b_tc)

        if is_mob:
            tc_btn_scroll = ScrollView(size_hint=(1, None), height=dp(52), do_scroll_x=True, do_scroll_y=False)
            tc_btn_scroll.add_widget(al)
            self.content_area.add_widget(tc_btn_scroll)
        else:
            self.content_area.add_widget(al)
        
        self.tc_master_tabs = self.tc_inputs + [self.btn_save_tc, self.btn_search_tc, self.btn_update_tc, self.btn_delete_tc, self.btn_print_tc, self.btn_download_tc_fmt, self.btn_upload_tc_excel]
        self.tc_tab_index = 0

    def action_download_tc_excel_format(self, instance):
        import os, openpyxl
        TEMPLATE_FILE = 'TC_Upload_Template.xlsx'
        try:
            cols_tc = [
                'TRANSFER CERTIFICATE NUMBER', 'CASTE', 'ADMISSION NUMBER (SR NO)', 'RELION',
                'PEN NO', 'APAAR ID', 'SCHOOL NAME', 'DURATION OF RESIDENCE IN UP',
                'PLACE', 'ADDRESS', 'DISTRICT', 'TEHSIL', 'ADMISSION DATE', 'LAST DATE OF SCHOOL',
                'SCHOOL LEAVING DATE', 'SCHOOL LEAVING REASON', "STUDENT'S NAME", 'CHARACTER STATUS',
                'AADHAR NUMBER', 'HIGHEST EXAM PASSED', 'DATE OF BIRTH (IN NUMBERS)', 'EXAM PASSED DATE',
                'DATE OF BIRTH (IN WORDS)', 'LANGUAGE', "FATHER'S NAME", 'OCCUPATION', "MOTHER'S NAME"
            ]
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(cols_tc)
            wb.save(TEMPLATE_FILE)
            self.popup('Template Downloaded', f"✅ TC Upload Template Generated!\nFile: {TEMPLATE_FILE}")
            open_file_cross_platform(TEMPLATE_FILE)
        except Exception as e:
            self.popup('Export Failed', str(e))

    # 📥 [बैकएंड हेल्पर हुक]: फॉलबैक हुक ताकि वैकल्पिक नामकरण विरोधाभास भी हमेशा के लिए समाप्त हो जाए
    def action_download_tc_format(self, instance):
        self.action_download_tc_excel_format(instance)

       # 📤 [टीसी बैकएंड इंजन 2]: बल्क टीसी एक्सेल डेटा को १ सेकंड में डेटाबेस में मर्ज करने का मास्टर इंजन
    def action_upload_tc_excel_database(self, instance):
        import os

        def process_tc_excel_file(file_path):
            if not file_path:
                return
            try:
                df_up = pd.read_excel(file_path, dtype=str)
                
                # वैलिडेशन सुरक्षा: टीसी नंबर या कम से कम प्रवेशांक होना कड़ाई से अनिवार्य है
                if 'TRANSFER CERTIFICATE NUMBER' not in df_up.columns and 'ADMISSION NUMBER (SR NO)' not in df_up.columns:
                    self.popup('Validation Error', "Invalid Template Format!\n\nExcel must contain 'TRANSFER CERTIFICATE NUMBER' or 'ADMISSION NUMBER (SR NO)' columns.")
                    return
                    
                tc_file = 'TC_Database.xlsx'
                cols_tc = [
                    'TRANSFER CERTIFICATE NUMBER', 'CASTE', 'ADMISSION NUMBER (SR NO)', 'RELION',
                    'PEN NO', 'APAAR ID', 'SCHOOL NAME', 'DURATION OF RESIDENCE IN UP',
                    'PLACE', 'ADDRESS', 'DISTRICT', 'TEHSIL', 'ADMISSION DATE', 'LAST DATE OF SCHOOL',
                    'SCHOOL LEAVING DATE', 'SCHOOL LEAVING REASON', "STUDENT'S NAME", 'CHARACTER STATUS',
                    'AADHAR NUMBER', 'HIGHEST EXAM PASSED', 'DATE OF BIRTH (IN NUMBERS)', 'EXAM PASSED DATE',
                    'DATE OF BIRTH (IN WORDS)', 'LANGUAGE', "FATHER'S NAME", 'OCCUPATION', "MOTHER'S NAME"
                ]
                
                # स्ट्रिंग्स को साफ़ करना (Clean Cases)
                for c in df_up.columns:
                    df_up[c] = df_up[c].astype(str).str.strip().str.replace('nan', '', case=False).str.replace(r'\.0$', '', regex=True)
                    
                if not os.path.exists(tc_file):
                    for col in cols_tc:
                        if col not in df_up.columns: df_up[col] = ""
                    df_up[cols_tc].to_excel(tc_file, index=False)
                else:
                    df_old = pd.read_excel(tc_file, dtype=str)
                    for c in df_old.columns:
                        df_old[c] = df_old[c].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.replace('nan', '', case=False)
                    
                    # टीसी नंबर के आधार पर ओवरराइट/ड्रॉप फ़िल्टर लॉक
                    if 'TRANSFER CERTIFICATE NUMBER' in df_up.columns and 'TRANSFER CERTIFICATE NUMBER' in df_old.columns:
                        df_old = df_old.drop(df_old[df_old['TRANSFER CERTIFICATE NUMBER'].isin(df_up['TRANSFER CERTIFICATE NUMBER'])].index)
                    elif 'ADMISSION NUMBER (SR NO)' in df_up.columns and 'ADMISSION NUMBER (SR NO)' in df_old.columns:
                        df_old = df_old.drop(df_old[df_old['ADMISSION NUMBER (SR NO)'].isin(df_up['ADMISSION NUMBER (SR NO)'])].index)
                        
                    df_merged = pd.concat([df_old, df_up], ignore_index=True)
                    for col in cols_tc:
                        if col not in df_merged.columns: df_merged[col] = ""
                        
                    df_merged[cols_tc].to_excel(tc_file, index=False)
                    
                self.popup('Success', f"🎉 BULK TC DATA LOADED SUCCESSFULLY!\n\nTotal {len(df_up)} Transfer Certificate records merged into 'TC_Database.xlsx'.")
                if hasattr(self, 'reset_tc_fields_action'): self.reset_tc_fields_action(None)
            except Exception as ex:
                self.popup('Upload Interrupted', f"TC Excel import crashed: {str(ex)}")

        select_file_cross_platform(
            "Select TC Excel File",
            [("Excel Files", "*.xlsx *.xls")],
            process_tc_excel_file
        )

    def reset_tc_fields_action(self, instance):
        for k, v in self.tc_fields.items():
            if not isinstance(v, Spinner): v.text = ''

    def save_tc_data_action(self, instance):
        st_name = self.tc_fields["STUDENT'S NAME"].text.strip()
        if not st_name:
            self.popup('System Alert', "Student's Name cannot be blank!"); return
            
        sr_no_tc = self.tc_fields['ADMISSION NUMBER (SR NO)'].text.strip().replace('.0', '')
        tc_num = self.tc_fields['TRANSFER CERTIFICATE NUMBER'].text.strip()
        leaving_date = self.tc_fields['SCHOOL LEAVING DATE'].text.strip()
        leaving_reason = self.tc_fields['SCHOOL LEAVING REASON'].text.strip()
        
        tc_file = 'TC_Database.xlsx'
        data_dict = {k: [v.text.strip()] for k, v in self.tc_fields.items()}
        
        try:
            # 1. TC_Database.xlsx में रिकॉर्ड सेव करना
            new_df = pd.DataFrame(data_dict)
            if not os.path.exists(tc_file):
                new_df.to_excel(tc_file, index=False)
            else:
                old_tc = pd.read_excel(tc_file, dtype=str)
                kept_tc = []
                for _, r_tc in old_tc.iterrows():
                    if not (tc_num and str(r_tc.get('TRANSFER CERTIFICATE NUMBER', '')).strip() == tc_num):
                        kept_tc.append(dict(r_tc))
                cleaned_tc = pd.DataFrame(kept_tc, columns=old_tc.columns)
                pd.concat([cleaned_tc, new_df], ignore_index=True).to_excel(tc_file, index=False)
                
            # 2. मुख्य Student_Database.xlsx में बच्चे का स्टेटस 'Left School with TC' और TC विवरण अपडेट करना (Windows + Android सुरक्षित)
            if sr_no_tc and os.path.exists(EXCEL_FILE):
                st_df = pd.read_excel(EXCEL_FILE, dtype=str)
                tc_sess_yr = get_academic_session_start_year(leaving_date)
                tc_sess_col = f"SESSION_{tc_sess_yr}_{tc_sess_yr+1}"

                all_st_cols = list(st_df.columns)
                for extra_c in ['STUDENT STATUS', 'TC NUMBER', 'TERMINATION DATE', 'TC REASON', tc_sess_col]:
                    if extra_c not in all_st_cols:
                        all_st_cols.append(extra_c)

                updated_st_rows = []
                status_msg = f"Left School with TC ({tc_sess_yr}-{tc_sess_yr+1})"

                for _, r_st in st_df.iterrows():
                    row_d = {col: str(r_st.get(col, '')).strip().replace('nan', '') for col in all_st_cols}
                    r_sr = row_d.get('SR NO', '').replace('.0', '').strip()
                    if r_sr == sr_no_tc:
                        row_d['STUDENT STATUS'] = status_msg
                        row_d['TC NUMBER'] = tc_num
                        row_d['TERMINATION DATE'] = leaving_date
                        row_d['TC REASON'] = leaving_reason
                        row_d[tc_sess_col] = status_msg
                        row_d['CLASS'] = status_msg
                    updated_st_rows.append(row_d)

                pd.DataFrame(updated_st_rows, columns=all_st_cols).to_excel(EXCEL_FILE, index=False)
                
            self.popup('Success', f"TC Saved & Student (SR No: {sr_no_tc}) marked as 'Left School with TC' in Master Database!")
            self.reset_tc_fields_action(None)
        except Exception as e:
            self.popup('Error', f"TC Sync Error: {str(e)}")

    def search_tc_data_action(self, instance):
        # 1. Premium Dynamic Popup Window Grid Builder
        pl = BoxLayout(orientation='vertical', padding=15, spacing=10)
        pl.add_widget(Label(text="Enter TC Number or Admission (SR No) to Find:", color=(1,1,1,1), bold=True, font_size=13))
        s_in = TextInput(multiline=False, size_hint_y=None, height=40, font_size=16, halign='center')
        pl.add_widget(s_in)
        b_box = BoxLayout(spacing=10, size_hint_y=None, height=40)
        btn_f = Button(text='FIND RECORD', background_color=(0,0.6,0.1,1), bold=True)
        btn_c = Button(text='CANCEL', background_color=(0.7,0.1,0.1,1), bold=True)
        b_box.add_widget(btn_f); b_box.add_widget(btn_c); pl.add_widget(b_box)
        pop = Popup(title='Search TC Database Terminal', content=pl, size_hint=(0.55, 0.38))
        btn_c.bind(on_press=pop.dismiss)
        
        def find_tc_record(ins):
            q = s_in.text.strip().lower()
            tc_file = 'TC_Database.xlsx'
            if q and os.path.exists(tc_file):
                try:
                    df = pd.read_excel(tc_file)
                    # Inspector scans both string and numeric indexes securely
                    match = pd.DataFrame()
                    if 'TRANSFER CERTIFICATE NUMBER' in df.columns:
                        df['TC_STR'] = df['TRANSFER CERTIFICATE NUMBER'].astype(str).str.strip().str.replace('.0', '', regex=False).str.lower()
                        match = df[df['TC_STR'] == q]
                    if match.empty and 'ADMISSION NUMBER (SR NO)' in df.columns:
                        df['SR_STR'] = df['ADMISSION NUMBER (SR NO)'].astype(str).str.strip().str.replace('.0', '', regex=False).str.lower()
                        match = df[df['SR_STR'] == q]
                        
                    if not match.empty:
                        row = match.iloc[0]
                        # Auto-maps stored columns seamlessly back to your screen inputs
                        for f in self.tc_fields_list:
                            if f in df.columns and f in self.tc_fields:
                                val = str(row[f]).strip()
                                if val.endswith('.0'): val = val[:-2]
                                if val.lower() == 'nan': val = ""
                                self.tc_fields[f].text = val
                        pop.dismiss()
                        self.popup('Search Engine', "Transfer Certificate Record Loaded Successfully!")
                    else:
                        self.popup('System Alert', "No matching TC Record found in database!")
                except Exception as e:
                    self.popup('Search Error', f"Excel Stream Interruption: {str(e)}")
            else:
                self.popup('System Alert', "TC Database File (TC_Database.xlsx) does not exist yet!")
        btn_f.bind(on_press=find_tc_record)
        pop.open()

    def update_tc_data_action(self, instance):
        # 2. Strict Core Auditor: Lock matching rows and over-writes data records safely
        tc_num = self.tc_fields['TRANSFER CERTIFICATE NUMBER'].text.strip()
        if not tc_num:
            self.popup('System Alert', "Transfer Certificate Number is required for updating records!"); return
            
        tc_file = 'TC_Database.xlsx'
        if os.path.exists(tc_file):
            try:
                df = pd.read_excel(tc_file)
                if 'TRANSFER CERTIFICATE NUMBER' in df.columns:
                    df['TC_STR'] = df['TRANSFER CERTIFICATE NUMBER'].astype(str).str.strip().str.replace('.0', '', regex=False)
                    # Filter isolates and drops old matching target index row
                    if str(tc_num) in df['TC_STR'].values:
                        df = df[df['TC_STR'] != str(tc_num)]
                        if 'TC_STR' in df.columns: df.drop(columns=['TC_STR'], inplace=True)
                        if 'SR_STR' in df.columns: df.drop(columns=['SR_STR'], inplace=True)
                        
                        # Generates fresh single-row DataFrame array matrix from active inputs
                        data_dict = {k: [v.text.strip()] for k, v in self.tc_fields.items()}
                        updated_df = pd.DataFrame(data_dict)
                        
                        # Re-appends and synchronizes back to active spreadsheet stream
                        final_df = pd.concat([df, updated_df], ignore_index=True)
                        final_df.to_excel(tc_file, index=False)
                        self.popup('Success', f"TC Number {tc_num} Updated and Synchronized Successfully!")
                    else:
                        self.popup('System Alert', f"TC Number {tc_num} not found in database to update!")
            except Exception as e:
                self.popup('Update Error', f"Write Permission Interruption: {str(e)}")

    def delete_tc_data_action(self, instance):
        # 3. Secure Target Deletion Engine
        tc_num = self.tc_fields['TRANSFER CERTIFICATE NUMBER'].text.strip()
        if not tc_num:
            self.popup('System Alert', "Enter or Search a TC Record first to trigger deletion!"); return
            
        tc_file = 'TC_Database.xlsx'
        if os.path.exists(tc_file):
            try:
                df = pd.read_excel(tc_file)
                if 'TRANSFER CERTIFICATE NUMBER' in df.columns:
                    df['TC_STR'] = df['TRANSFER CERTIFICATE NUMBER'].astype(str).str.strip().str.replace('.0', '', regex=False)
                    if str(tc_num) in df['TC_STR'].values:
                        # Purges old target line completely out of Excel records matrix
                        df = df[df['TC_STR'] != str(tc_num)]
                        if 'TC_STR' in df.columns: df.drop(columns=['TC_STR'], inplace=True)
                        if 'SR_STR' in df.columns: df.drop(columns=['SR_STR'], inplace=True)
                        
                        df.to_excel(tc_file, index=False)
                        self.reset_tc_fields_action(None)
                        self.popup('Success', f"TC Number {tc_num} Deleted permanently from database records!")
                    else:
                        self.popup('System Alert', f"TC Number {tc_num} not found in database records!")
            except Exception as e:
                self.popup('Deletion Error', f"Excel Matrix Conflict: {str(e)}")

    def generate_tc_pdf_report(self, instance):
        import os
        st_name = self.tc_fields["STUDENT'S NAME"].text.strip()
        if not st_name:
            self.popup('System Alert', "Student's Name is blank! Kindly fetch or enter data first."); return
            
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors

            pdf_filename = f"TC_Official_{self.tc_fields['ADMISSION NUMBER (SR NO)'].text.strip()}_{st_name.replace(' ', '_')}.pdf"
            
            doc = SimpleDocTemplate(pdf_filename, pagesize=A4, rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
            story = []
            
            HEADER_MAROON = colors.HexColor("#8B0000")
            OFFICIAL_BLUE = colors.HexColor("#0F4C81")
            STRIP_GREY = colors.HexColor("#A6A6A6")
            GRID_LINE = colors.HexColor("#595959")
            
            styles = getSampleStyleSheet()
            
            board_style = ParagraphStyle('BoardHead', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=HEADER_MAROON, alignment=1)
            sch_style = ParagraphStyle('SchHead', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=OFFICIAL_BLUE, alignment=1)
            sub_style = ParagraphStyle('SubHead', fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=colors.black, alignment=1)
            strip_style = ParagraphStyle('StripTxt', fontName='Helvetica-Bold', fontSize=11, leading=12, textColor=colors.white, alignment=1)
            
            cell_bold = ParagraphStyle('CellB', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.black)
            cell_norm = ParagraphStyle('CellN', fontName='Helvetica', fontSize=9, leading=11, textColor=colors.black)
            
            story.append(Spacer(1, 5))
            story.append(Paragraph("<b>UTTAR PRADESH BASIC SHIKSHA PARISHAD, PRAYAGRAJ</b>", board_style))
            story.append(Spacer(1, 2))
            story.append(Paragraph(f"<b>{self.tc_fields['SCHOOL NAME'].text.strip()}</b>", sch_style))
            story.append(Paragraph(f"BLOCK - WAZIRGANJ, DISTRICT - {self.tc_fields['DISTRICT'].text.strip().upper()}", sub_style))
            story.append(Spacer(1, 4))
            story.append(Paragraph("<b>TRANSFER CERTIFICATE (स्थानांतरण प्रमाण पत्र)</b>", ParagraphStyle('TcTitle', fontName='Helvetica-Bold', fontSize=12, leading=14, textColor=OFFICIAL_BLUE, alignment=1)))
            story.append(Spacer(1, 4))
            
            story.append(Paragraph("<b>SESSION - 2026-2027</b>", sub_style))
            story.append(Spacer(1, 6))
            
            s1_data = [[Paragraph("<b>FOR OFFICE USE ONLY</b>", strip_style)]]
            t_s1 = Table(s1_data, colWidths=[565], rowHeights=[20])
            t_s1.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), STRIP_GREY), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            story.append(t_s1)
            
            office_grid = [
                [Paragraph("<b>TRANSFER CERTIFICATE NO.</b>", cell_bold), Paragraph(self.tc_fields['TRANSFER CERTIFICATE NUMBER'].text.strip(), cell_bold),
                 Paragraph("<b>PEN NUMBER</b>", cell_bold), Paragraph(self.tc_fields['PEN NO'].text.strip(), cell_norm)],
                [Paragraph("<b>APAAR ID</b>", cell_bold), Paragraph(self.tc_fields["APAAR ID"].text.strip(), cell_norm),
                 Paragraph("<b>SR NUMBER (ADMISSION NO.)</b>", cell_bold), Paragraph(self.tc_fields['ADMISSION NUMBER (SR NO)'].text.strip(), cell_norm)]
            ]
            t_office = Table(office_grid, colWidths=[120, 162, 140, 143], rowHeights=[22, 22])
            t_office.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, GRID_LINE),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F2F2F2")),
                ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#F2F2F2")),
                ('LEFTPADDING', (0,0), (-1,-1), 6)
            ]))
            story.append(t_office)
            story.append(Spacer(1, 4))
            
            s2_data = [[Paragraph("<b>STUDENT DETAIL</b>", strip_style)]]
            t_s2 = Table(s2_data, colWidths=[565], rowHeights=[20])
            t_s2.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), STRIP_GREY), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            story.append(t_s2)
            
            student_grid = [
                [Paragraph("<b>STUDENT'S FULL NAME</b>", cell_bold), Paragraph(self.tc_fields["STUDENT'S NAME"].text.strip().upper(), cell_bold)],
                [Paragraph("<b>FATHER'S NAME / GUARDIAN</b>", cell_bold), Paragraph(self.tc_fields["FATHER'S NAME"].text.strip().upper(), cell_norm)],
                [Paragraph("<b>MOTHER'S NAME</b>", cell_bold), Paragraph(self.tc_fields["MOTHER'S NAME"].text.strip().upper(), cell_norm)],
                [Paragraph("<b>DATE OF BIRTH (IN NUMBERS)</b>", cell_bold), Paragraph(self.tc_fields["DATE OF BIRTH (IN NUMBERS)"].text.strip(), cell_bold)],
                [Paragraph("<b>DATE OF BIRTH (IN WORDS)</b>", cell_bold), Paragraph(self.tc_fields["DATE OF BIRTH (IN WORDS)"].text.strip().upper(), cell_norm)],
                [Paragraph("<b>CATEGORY / CASTE</b>", cell_bold), Paragraph(self.tc_fields["CASTE"].text.strip(), cell_norm)],
                [Paragraph("<b>RELIGION</b>", cell_bold), Paragraph(self.tc_fields["RELION"].text.strip(), cell_norm)],
                [Paragraph("<b>AADHAR NUMBER (STUDENT)</b>", cell_bold), Paragraph(self.tc_fields["AADHAR NUMBER"].text.strip(), cell_norm)],
                [Paragraph("<b>PERMANENT ADDRESS</b>", cell_bold), Paragraph(self.tc_fields["ADDRESS"].text.strip(), cell_norm)],
                [Paragraph("<b>PLACE OF BIRTH</b>", cell_bold), Paragraph(self.tc_fields["PLACE"].text.strip(), cell_norm)],
                [Paragraph("<b>TEHSIL</b>", cell_bold), Paragraph(self.tc_fields["TEHSIL"].text.strip(), cell_norm)],
                [Paragraph("<b>ADMISSION DATE</b>", cell_bold), Paragraph(self.tc_fields['ADMISSION DATE'].text.strip(), cell_norm)],
                [Paragraph("<b>DURATION OF RESIDENCE IN UP</b>", cell_bold), Paragraph(self.tc_fields["DURATION OF RESIDENCE IN UP"].text.strip(), cell_norm)]
            ]
            t_student = Table(student_grid, colWidths=[200, 365], rowHeights=[21]*13)
            t_student.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, GRID_LINE),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F9F9F9")),
                ('LEFTPADDING', (0,0), (-1,-1), 8)
            ]))
            story.append(t_student)
            story.append(Spacer(1, 4))
                       
            # --- SECTION 3: ACADEMIC DETAIL STRIP ---
            s3_data = [[Paragraph("<b>ACADEMIC DETAIL</b>", strip_style)]]
            t_s3 = Table(s3_data, colWidths=[565], rowHeights=[20])
            t_s3.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), STRIP_GREY), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            story.append(t_s3)
            
            # School Leaving Parameters Matrix Array
            bank_grid = [
                [Paragraph("<b>HIGHEST CLASS EXAM PASSED</b>", cell_bold), Paragraph(self.tc_fields["HIGHEST EXAM PASSED"].text.strip(), cell_norm),
                 Paragraph("<b>EXAM PASSED DATE</b>", cell_bold), Paragraph(self.tc_fields["EXAM PASSED DATE"].text.strip(), cell_norm)],
                [Paragraph("<b>LAST DATE OF SCHOOL</b>", cell_bold), Paragraph(self.tc_fields["LAST DATE OF SCHOOL"].text.strip(), cell_norm),
                 Paragraph("<b>SCHOOL LEAVING DATE</b>", cell_bold), Paragraph(self.tc_fields["SCHOOL LEAVING DATE"].text.strip(), cell_norm)],
                [Paragraph("<b>SCHOOL LEAVING REASON</b>", cell_bold), Paragraph(self.tc_fields["SCHOOL LEAVING REASON"].text.strip(), cell_norm),
                 Paragraph("<b>LANGUAGE MEDIUM</b>", cell_bold), Paragraph(self.tc_fields["LANGUAGE"].text.strip(), cell_norm)],
                [Paragraph("<b>STUDENT CHARACTER</b>", cell_bold), Paragraph(self.tc_fields["CHARACTER STATUS"].text.strip(), cell_norm),
                 Paragraph("<b>GUARDIAN OCCUPATION</b>", cell_bold), Paragraph(self.tc_fields["OCCUPATION"].text.strip(), cell_norm)]
            ]
            t_bank = Table(bank_grid, colWidths=[180, 115, 150, 120], rowHeights=[21]*4)
            t_bank.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, GRID_LINE),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F9F9F9")),
                ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#F9F9F9")),
                ('LEFTPADDING', (0,0), (-1,-1), 6)
            ]))
            story.append(t_bank)
            story.append(Spacer(1, 120))
            
            # --- SECTION 4: OFFICIAL TRI-SIGNATURES FRAMEWORK ROW ---
            current_date_text = datetime.today().strftime('%d-%m-%Y')
            sig_data = [
                [Paragraph(f"<b>DATE -</b> {current_date_text}", cell_bold),
                 Paragraph("<b>PRINCIPAL'S SIGNATURE</b><br/>(With Official School Stamp)", ParagraphStyle('H_Sig', fontName='Helvetica-Bold', fontSize=10, alignment=2))]
            ]
            t_sig = Table(sig_data, colWidths=[250, 315], rowHeights=40)
            t_sig.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('ALIGN', (0,0), (0,0), 'LEFT'),   # Strict Table Cell Alignment Lock
                ('ALIGN', (1,0), (1,0), 'RIGHT')   # Pulls Principal Sign to extreme right corner

            ]))
            story.append(t_sig)
            
            # --- CANVAS DRAW HOOK FOR THICK BORDER, WATERMARK & LOGO ---
            def draw_page_border_frame(canvas, document):
                import os
                canvas.saveState()
                
                # 1. Double Line Premium Border Frame (Locks offset padding margins)
                canvas.setStrokeColor(HEADER_MAROON)
                canvas.setLineWidth(2)
                canvas.rect(8, 8, 579, 826) 
                canvas.setStrokeColor(OFFICIAL_BLUE)
                canvas.setLineWidth(0.8)
                canvas.rect(11, 11, 573, 820)
                
                # 2. Top Right Corner Logo Placement
                if os.path.exists(get_exe_safe_path("logo.png")):
                    try:
                        # Draws a sharp 55x55 pixel official emblem at top-right corner
                        canvas.drawImage(get_exe_safe_path("logo.png"), 510, 750, width=55, height=55, mask='auto')
                    except:
                        pass
                
                # 3. Center Page Soft Watermark Shading
                if os.path.exists(get_exe_safe_path("logo.png")):
                    try:
                        # Sets transparency fill to 8% (0.08) so text stays highly readable
                        canvas.setFillAlpha(0.08) 
                        # Positioned precisely at dead center of A4 sheet (250x250)
                        canvas.drawImage(get_exe_safe_path("logo.png"), 172, 296, width=250, height=250, mask='auto')
                    except:
                        pass
                
                # Restore state must strictly happen at the very end to protect text fonts opacity
                canvas.restoreState()
                
            # Compiles document elements into ReportLab flowable stream architecture
            doc.build(story, onFirstPage=draw_page_border_frame)
            self.popup('Print Engine', f"UP Government Format TC PDF Generated on Single Page!\nSaved as: {pdf_filename}")
            
            import platform
            if platform.system() == "Windows":
                open_file_cross_platform(pdf_filename)
                try:
                    open_file_cross_platform(pdf_filename, "print")
                except Exception as print_err:
                    print("Printer Hardware Connection Check:", str(print_err))
            else:
                open_file_cross_platform(pdf_filename)

        except Exception as e:
            self.popup('Print Error', f"ReportLab Compiler Interruption: {str(e)}")

    def generate_admission_form_pdf(self, instance):
        import os
        PHOTO_DIR = 'student_photos'
        
        # 1. Flexible Student Name Fetcher Lock
        st_name = ""
        name_keys = ["NAME", "STUDENT NAME", "NAME OF STUDENT", "STUDENT'S NAME"]
        for nk in name_keys:
            if nk in self.fields and self.fields[nk].text.strip():
                st_name = self.fields[nk].text.strip(); break
        if not st_name:
            for k, v in self.fields.items():
                if "name" in k.lower() and "father" not in k.lower() and "mother" not in k.lower():
                    st_name = v.text.strip(); break
                    
        if not st_name or st_name.lower() == "student":
            self.popup('System Alert', "Student's Name is blank! Kindly enter or search details first."); return
            
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import mm
            
            pdf_filename = f"Admission_Form_{st_name.replace(' ', '_')}.pdf"
            doc = SimpleDocTemplate(pdf_filename, pagesize=A4, rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
            story = []
            
            HEADER_MAROON = colors.HexColor("#8B0000") 
            OFFICIAL_BLUE = colors.HexColor("#0F4C81") 
            STRIP_GREY = colors.HexColor("#A6A6A6")    
            GRID_LINE = colors.HexColor("#595959")     
            
            styles = getSampleStyleSheet()
            board_style = ParagraphStyle('B_Head', fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=HEADER_MAROON, alignment=1)
            sch_style = ParagraphStyle('S_Head', fontName='Helvetica-Bold', fontSize=17, leading=20, textColor=OFFICIAL_BLUE, alignment=1)
            sub_style = ParagraphStyle('Sub_Head', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.black, alignment=1)
            strip_style = ParagraphStyle('Str_Txt', fontName='Helvetica-Bold', fontSize=11, leading=13, textColor=colors.white, alignment=1)
            
            cell_bold = ParagraphStyle('C_B', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.black)
            cell_norm = ParagraphStyle('C_N', fontName='Helvetica', fontSize=9, leading=11, textColor=colors.black)
            
            # --- ✨ 2. SMART LOGO HEADER GRID MATRIX ENGINE ---
            # Top Left: basic.png (48x48 mm/points)
            if os.path.exists(get_exe_safe_path("basic.png")):
                left_logo = Image(get_exe_safe_path("basic.png"), width=48, height=48)
            else:
                left_logo = Paragraph("", sub_style)
                
            # --- ✨ 2. SMART LOGO HEADER GRID MATRIX ENGINE ---
            # Top Left: basic.png (बिना कटे परफेक्ट फिट करने के लिए 45x45 साइज)
            if os.path.exists(get_exe_safe_path("basic.png")):
                left_logo = Image(get_exe_safe_path("basic.png"), width=45, height=45)
            else:
                left_logo = Paragraph("", sub_style)
                
            # Top Right: School Logo 
            if os.path.exists(get_exe_safe_path("logo.png")):
                right_logo = Image(get_exe_safe_path("logo.png"), width=45, height=45)
            else:
                right_logo = Paragraph("", sub_style)
                
            # Center Text Layout
            center_text_block = [
                Paragraph("<b>UTTAR PRADESH BASIC SHIKSHA PARISHAD, PRAYAGRAJ</b>", board_style),
                Spacer(1, 1),
                Paragraph("<b>PRIMARY SCHOOL PANAUTA</b>", sch_style),
                Paragraph("BLOCK - WAZIRGANJ, DISTRICT - BUDAUN, 243601", sub_style),
                Spacer(1, 2),
                Paragraph("<b>ADMISSION FORM (प्रवेश पत्र)</b>", ParagraphStyle('FormT', fontName='Helvetica-Bold', fontSize=12, leading=14, textColor=OFFICIAL_BLUE, alignment=1)),
                Spacer(1, 1),
                Paragraph("<b>SESSION - 2026-2027</b>", sub_style)
            ]
            
            # ✨ फिक्स चौड़ाई: बाईं तरफ 60, बीच में 445 और दाईं तरफ 60 पॉइंट का स्पेस अलॉट कर दिया गया है
            header_table_data = [[left_logo, center_text_block, right_logo]]
            t_master_header = Table(header_table_data, colWidths=[60, 445, 60])
            t_master_header.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (0,0), (0,0), 'LEFT'),
                ('ALIGN', (2,0), (2,0), 'RIGHT'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0)
            ]))
            story.append(t_master_header)
            story.append(Spacer(1, 6))
            
            # --- SECTION 1: OFFICE USE STRIP ---
            s1_data = [[Paragraph("<b>FOR OFFICE USE ONLY</b>", strip_style)]]
            t_s1 = Table(s1_data, colWidths=565, rowHeights=18)
            t_s1.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), STRIP_GREY), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            story.append(t_s1)
            
            def f_txt(keywords_list, default=""):
                for kw in keywords_list:
                    if kw in self.fields: return self.fields[kw].text.strip()
                    for screen_key, widget in self.fields.items():
                        clean_sk = screen_key.lower().replace("'", "").replace("’", "").strip()
                        clean_kw = kw.lower().replace("'", "").replace("’", "").strip()
                        if clean_kw in clean_sk:
                            return widget.text.strip()
                return default
            
            # 👑 [क्लीन डेट्स फॉर्मेटर एवं PRESENT CLASS लॉक - Windows + Android क्रॉस-प्लेटफ़ॉर्म]
            adm_date = format_date_dd_mm_yyyy(f_txt(['ADMISSION DATE', 'DATE OF ADMISSION', 'DOA']))
            dob_num = format_date_dd_mm_yyyy(f_txt(['DATE OF BIRTH (DDMMYYYY)', 'DATE OF BIRTH', 'DOB']))
            
            sr_for_check = f_txt(['SR NO', 'SR NUMBER', 'ADMISSION NO']).replace('.0', '')
            selected_cls_on_screen = f_txt(['CLASS'])
            
            present_class_val = selected_cls_on_screen
            if sr_for_check and os.path.exists(EXCEL_FILE):
                try:
                    df_chk = pd.read_excel(EXCEL_FILE, dtype=str)
                    if 'CLASS' in df_chk.columns and 'SR NO' in df_chk.columns:
                        for _, r_chk in df_chk.iterrows():
                            if str(r_chk.get('SR NO', '')).strip().replace('.0', '') == sr_for_check:
                                db_cls = str(r_chk.get('CLASS', '')).strip()
                                if db_cls and db_cls.lower() != 'nan':
                                    present_class_val = db_cls
                except Exception:
                    pass
            else:
                present_class_val, _ = calculate_promoted_class_history(adm_date, selected_cls_on_screen)
            
            office_grid = [
                [Paragraph("<b>PEN NUMBER</b>", cell_bold), Paragraph(f_txt(['PEN NO', 'PEN NUMBER']), cell_norm),
                 Paragraph("<b>SR NUMBER</b>", cell_bold), Paragraph(sr_for_check, cell_bold)],
                [Paragraph("<b>ADMISSION DATE</b>", cell_bold), Paragraph(adm_date, cell_norm),
                 Paragraph("<b>PRESENT CLASS</b>", cell_bold), Paragraph(present_class_val, cell_bold)]
            ]
            t_office = Table(office_grid, colWidths=[120, 162, 143, 140], rowHeights=[20]*2)
            t_office.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, GRID_LINE), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F2F2F2")), ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#F2F2F2")),
                ('LEFTPADDING', (0,0), (-1,-1), 6)
            ]))
            story.append(t_office)
            story.append(Spacer(1, 4))
            
            # --- SECTION 2: STUDENT DETAIL STRIP ---
            s2_data = [[Paragraph("<b>STUDENT DETAIL</b>", strip_style)]]
            t_s2 = Table(s2_data, colWidths=565, rowHeights=18)
            t_s2.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), STRIP_GREY), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            story.append(t_s2)
            
            student_left_fields = [
                [Paragraph("<b>NAME OF STUDENT</b>", cell_bold), Paragraph(st_name.upper(), cell_bold)],
                [Paragraph("<b>FATHER'S NAME</b>", cell_bold), Paragraph(f_txt(["FATHER'S NAME", "FATHER NAME", "FATHERS NAME"]).upper(), cell_norm)],
                [Paragraph("<b>MOTHER'S NAME</b>", cell_bold), Paragraph(f_txt(["MOTHER'S NAME", "MOTHER NAME", "MOTHERS NAME"]).upper(), cell_norm)],
                [Paragraph("<b>FATHER/MOTHER's NAME AS PER STUDENT'S AADHAR</b>", cell_bold), Paragraph(f_txt(["FATHER'S NAME AS PER STUDENT'S Aadhaar", "FATHER'S NAME AS PER STUDENT'S AADHAAR", "AADHAR NAME"]).upper(), cell_norm)],
                [Paragraph("<b>DATE OF BIRTH (IN NUMBERS)</b>", cell_bold), Paragraph(dob_num, cell_bold)],
                [Paragraph("<b>DATE OF BIRTH (IN WORDS)</b>", cell_bold), Paragraph(f_txt(['DATE OF BIRTH (IN WORDS)', 'WORDS', 'IN WORD']).upper(), cell_norm)],
                [Paragraph("<b>ADDRESS</b>", cell_bold), Paragraph(f_txt(['ADDRESS']).upper(), cell_norm)],
                [Paragraph("<b>GENDER</b>", cell_bold), Paragraph(f_txt(['GENDER']), cell_norm)],
                [Paragraph("<b>MOBILE NUMBER</b>", cell_bold), Paragraph(f_txt(['MOBILE NUMBER', 'MOBILE NO']), cell_norm)],
                [Paragraph("<b>CATEGORY / CASTE</b>", cell_bold), Paragraph(f_txt(['CATEGORY', 'CASTE']), cell_norm)],
                [Paragraph("<b>STUDENT'S AADHAR NUMBER</b>", cell_bold), Paragraph(f_txt(["ST Aadhaar NO", "STUDENT'S AADHAR NUMBER", "ST AADHAR"]), cell_norm)],
                [Paragraph("<b>FATHER'S AADHAR NUMBER</b>", cell_bold), Paragraph(f_txt(['FATHER Aadhaar NO', 'FATHER AADHAR']), cell_norm)],
                [Paragraph("<b>MOTHER'S AADHAR NUMBER</b>", cell_bold), Paragraph(f_txt(['MOTHER Aadhaar NO', 'MOTHER AADHAR']), cell_norm)]
            ]
            
            t_st_left = Table(student_left_fields, colWidths=[180, 250], rowHeights=[20]*13)
            t_st_left.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, GRID_LINE), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F9F9F9")), ('LEFTPADDING', (0,0), (-1,-1), 6)
            ]))
            
            st_block = [[t_st_left, Spacer(1, 1)]]
            t_st_main = Table(st_block, colWidths=[430, 135])
            t_st_main.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'), 
                ('LEFTPADDING', (0,0), (-1,-1), 0), 
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0)
            ]))
            story.append(t_st_main)
            story.append(Spacer(1, 4))
            
            # --- SECTION 3: BANK DETAIL STRIP ---
            s3_data = [[Paragraph("<b>BANK DETAIL</b>", strip_style)]]
            t_s3 = Table(s3_data, colWidths=565, rowHeights=18)
            t_s3.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), STRIP_GREY), 
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), 
                ('ALIGN', (0,0), (-1,-1), 'CENTER')
            ]))
            story.append(t_s3)
            story.append(Spacer(1, 4))
            
            bank_grid = [
                [Paragraph("<b>BANK NAME</b>", cell_bold), Paragraph(f_txt(['BANK NAME', 'BANK']), cell_norm),
                 Paragraph("<b>BANK IFSC CODE</b>", cell_bold), Paragraph(f_txt(['BANK IFSC CODE', 'IFSC']), cell_norm)],
                [Paragraph("<b>BANK ACCOUNT NUMBER</b>", cell_bold), Paragraph(f_txt(['A/C NUMBER', 'ACCOUNT NUMBER']), cell_norm),
                 Paragraph("<b>ACCOUNT HOLDER NAME</b>", cell_bold), Paragraph(f_txt(['A/C HOLDER NAME', 'ACCOUNT HOLDER NAME']), cell_norm)],
                [Paragraph("<b>RELATION WITH STUDENT</b>", cell_bold), Paragraph(f_txt(['RELATION OF A/C HOLDER WITH STUDENT', 'RELATION']), cell_norm),
                 Paragraph("<b>A/C HOLDER AADHAR</b>", cell_bold), Paragraph(f_txt(['A/C HOLDER Aadhaar NUMBER', 'A/C HOLDER AADHAR NUMBER', 'HOLDER AADHAR']), cell_norm)],
                [Paragraph("<b>SAME FAMILY MEMBER</b>", cell_bold), Paragraph(f_txt(['SAME FAMILY']), cell_norm),
                 Paragraph("<b>CWSN (YES/NO)</b>", cell_bold), Paragraph(f_txt(['CWSN (YES/NO)', 'CWSN']), cell_norm)]
            ]
            t_bank = Table(bank_grid, colWidths=[120, 160, 150, 135], rowHeights=[20]*4)
            t_bank.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, GRID_LINE), 
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F9F9F9")), 
                ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#F9F9F9")),
                ('LEFTPADDING', (0,0), (-1,-1), 6)
            ]))
            story.append(t_bank)
            story.append(Spacer(1, 4))
            
            # --- SECTION 4: ENCLOSED ATTACHMENTS STRIP ---
            s4_data = [[Paragraph("<b>ENCLOSED ATTACHMENTS</b>", strip_style)]]
            t_s4 = Table(s4_data, colWidths=[565], rowHeights=[18])
            t_s4.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), STRIP_GREY), 
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), 
                ('ALIGN', (0,0), (-1,-1), 'CENTER')
            ]))
            story.append(t_s4)
            story.append(Spacer(1, 4))
            
            enclosed_grid = [
                [Paragraph("1 - STUDENT'S AADHAR COPY", cell_norm), Paragraph("[  ]", ParagraphStyle('Chk', fontName='Helvetica', fontSize=10, alignment=2))],
                [Paragraph("2 - FATHER/MOTHER'S AADHAR COPY", cell_norm), Paragraph("[  ]", ParagraphStyle('Chk', fontName='Helvetica', fontSize=10, alignment=2))],
                [Paragraph("3 - BANK PASSBOOK COPY", cell_norm), Paragraph("[  ]", ParagraphStyle('Chk', fontName='Helvetica', fontSize=10, alignment=2))],
                [Paragraph("4 - STUDENT'S PHOTOGRAPH", cell_norm), Paragraph("[  ]", ParagraphStyle('Chk', fontName='Helvetica', fontSize=10, alignment=2))]
            ]
            t_enc = Table(enclosed_grid, colWidths=[450, 115], rowHeights=[18]*4)
            t_enc.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey), 
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), 
                ('LEFTPADDING', (0,0), (-1,-1), 8), 
                ('RIGHTPADDING', (1,0), (1,-1), 15)
            ]))
            story.append(t_enc)
            story.append(Spacer(1, 35))
            
            # --- SECTION 5: SIGNATURE MATRIX ROW ---
            from datetime import datetime
            current_date_text = datetime.today().strftime('%d-%m-%Y')
            sig_data = [
                [Paragraph(f"<b>DATE - {current_date_text}</b>", ParagraphStyle('D_L', fontName='Helvetica-Bold', fontSize=10, alignment=0)),
                 Paragraph("<b>PARENT'S SIGNATURE</b>", ParagraphStyle('P_C', fontName='Helvetica-Bold', fontSize=10, alignment=1)),
                 Paragraph("<b>PRINCIPAL'S SIGNATURE</b><br/>(With School Seal)", ParagraphStyle('Pr_R', fontName='Helvetica-Bold', fontSize=10, alignment=2))]
            ]
            t_sig = Table(sig_data, colWidths=[150, 220, 195], rowHeights=[35])
            t_sig.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'BOTTOM')]))
            story.append(t_sig)
            
            # --- CANVAS DRAW HOOK FOR BORDER, WATERMARK & ACTIVE PHOTO TRACKER ---
            def draw_registration_border_watermark(canvas, document):
                import os
                canvas.saveState()
                canvas.setStrokeColor(HEADER_MAROON); canvas.setLineWidth(2); canvas.rect(8, 8, 579, 826) 
                canvas.setStrokeColor(OFFICIAL_BLUE); canvas.setLineWidth(0.8); canvas.rect(11, 11, 573, 820)
                
                if os.path.exists(get_exe_safe_path("logo.png")):
                    try:
                        canvas.setFillAlpha(0.08) 
                        canvas.drawImage(get_exe_safe_path("logo.png"), 172, 296, width=250, height=250, mask='auto')
                        canvas.setFillAlpha(1.0)
                    except: pass
                    
                # 📸 पासपोर्ट आकार का फिक्स अलाइनमेंट हुक (35mm × 45mm)
                try:
                    photo_file_path = ""
                    sr_widget_val = ""
                    
                    for k, v in self.fields.items():
                        if "sr" in k.lower() or "admission" in k.lower():
                            sr_widget_val = v.text.strip().replace('.0', ''); break
                            
                    if sr_widget_val:
                        extensions = ['.jpg', '.png', '.jpeg', '.bmp']
                        possible_paths = []
                        for ext in extensions:
                            possible_paths.append(os.path.join(PHOTO_DIR, f"{sr_widget_val}{ext}"))
                            possible_paths.append(os.path.join(PHOTO_DIR, f"student_{sr_widget_val}{ext}"))
                            possible_paths.append(os.path.join(os.getcwd(), f"{sr_widget_val}{ext}"))
                            
                        for path in possible_paths:
                            if os.path.exists(path):
                                photo_file_path = path; break
                                
                    if (not photo_file_path or not os.path.exists(photo_file_path)):
                        if hasattr(self, 'selected_photo_path') and self.selected_photo_path and os.path.exists(str(self.selected_photo_path).strip()):
                            photo_file_path = str(self.selected_photo_path).strip()
                        elif hasattr(self, 'image_path') and self.image_path and os.path.exists(str(self.image_path).strip()):
                            photo_file_path = str(self.image_path).strip()
                    
                    # 📐 पासपोर्ट आकार ग्रिड पैरामीटर्स (X=455, Y=430 पर एकदम सुरक्षित लॉक)
                    box_x = 455
                    box_y = 430
                    box_w = 35 * mm  # ~99.2 pt
                    box_h = 45 * mm  # ~127.5 pt
                    
                    # पहले काला पासपोर्ट बॉक्स बॉर्डर बनाएं
                    canvas.setStrokeColor(colors.black)
                    canvas.setLineWidth(1.2)
                    canvas.rect(box_x, box_y, box_w, box_h)
                    
                    if photo_file_path and os.path.exists(photo_file_path):
                        # बॉक्स के ठीक अंदर असली फ़ोटो ड्रा करें
                        canvas.drawImage(photo_file_path, box_x + 1, box_y + 1, width=box_w - 2, height=box_h - 2, mask='auto')
                    else:
                        # यदि फ़ोटो नहीं है, तो बॉक्स के अंदर टेक्स्ट लिखें
                        canvas.setFont("Helvetica-Bold", 8)
                        canvas.setFillColor(colors.HexColor("#666655"))
                        canvas.drawCentredString(box_x + (box_w/2), box_y + (box_h/2) + 5, "PASSPORT")
                        canvas.drawCentredString(box_x + (box_w/2), box_y + (box_h/2) - 5, "PHOTO")
                except Exception as img_err:
                    print("Admission Canvas Photo Sync Error:", str(img_err))
                    
                canvas.restoreState()
                
            doc.build(story, onFirstPage=draw_registration_border_watermark)
            self.popup('Print Engine', f"परिषदीय स्कूल एडमिशन फॉर्म सफलतापूर्वक तैयार!\nसहेजा गया: {pdf_filename}")
            
            import platform
            if platform.system() == "Windows":
                open_file_cross_platform(pdf_filename)
                try:
                    open_file_cross_platform(pdf_filename, "print") 
                except Exception as print_hardware_err:
                    print("Printer Hardware Connection Check Log:", str(print_hardware_err))
            else:
                open_file_cross_platform(pdf_filename)
        except Exception as e:
            self.popup('Print Error', f"ReportLab Interruption: {str(e)}")

    def generate_staff_form_pdf(self, instance):
        import os
        pass
        import platform
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        
        STAFF_PHOTO_DIR = 'staff_photos'
        teacher_name = self.staff_fields["TEACHER'S NAME"].text.strip()
        ehrms_id_val = self.staff_fields['EHRMS ID'].text.strip()
        
        if not teacher_name or teacher_name.lower() == "teacher":
            self.popup('System Alert', "Teacher's Name is blank! Kindly search or enter staff details first."); return
            
        try:
            pdf_filename = f"Staff_Profile_{teacher_name.replace(' ', '_')}.pdf"
            doc = SimpleDocTemplate(pdf_filename, pagesize=A4, rightMargin=15, leftMargin=15, topMargin=135, bottomMargin=15)
            story = []
            
            HEADER_MAROON = colors.HexColor("#8B0000") 
            OFFICIAL_BLUE = colors.HexColor("#0F4C81") 
            STRIP_GREY = colors.HexColor("#808080")    
            GRID_LINE = colors.HexColor("#595959")     
            
            cell_bold = ParagraphStyle('C_B', fontName=MY_PROJECT_FONT, fontSize=10, leading=13, textColor=colors.black)
            cell_norm = ParagraphStyle('C_N', fontName=MY_PROJECT_FONT, fontSize=10, leading=13, textColor=colors.black)
            strip_style = ParagraphStyle('Str_Txt', fontName=MY_PROJECT_FONT, fontSize=11, leading=13, textColor=colors.white, alignment=1)
            
            # --- SECTION 1: OFFICIAL USE STRIP ---
            s1_data = [[Paragraph("<b>OFFICIAL EHRMS RECORD PANEL</b>", strip_style)]]
            t_s1 = Table(s1_data, colWidths=565, rowHeights=20)
            t_s1.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), STRIP_GREY), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            story.append(t_s1)
            story.append(Spacer(1, 6))
            
            def f_txt(kw):
                if kw in self.staff_fields: return self.staff_fields[kw].text.strip()
                return ""

            office_grid = [
                [Paragraph("<b>S NO</b>", cell_bold), Paragraph(f_txt('S NO'), cell_norm),
                 Paragraph("<b>EHRMS ID</b>", cell_bold), Paragraph(ehrms_id_val, cell_bold)],
                [Paragraph("<b>DESIGNATION</b>", cell_bold), Paragraph(f_txt('DESIGNATION'), cell_bold),
                 Paragraph("<b>MOBILE NUMBER</b>", cell_bold), Paragraph(f_txt('MOBILE NUMBER'), cell_norm)]
            ]
            t_office = Table(office_grid, colWidths=(100, 182.5, 100, 182.5), rowHeights=(26, 26))
            t_office.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, GRID_LINE), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F2F2F2")), ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#F2F2F2")),
                ('LEFTPADDING', (0,0), (-1,-1), 6)
            ]))
            story.append(t_office)
            story.append(Spacer(1, 6))
            
            # --- SECTION 2: STAFF PERSONAL DETAIL STRIP ---
            s2_data = [[Paragraph("<b>STAFF PERSONAL AND JOINING DETAILS</b>", strip_style)]]
            t_s2 = Table(s2_data, colWidths=565, rowHeights=20)
            t_s2.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), STRIP_GREY), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            story.append(t_s2)
            story.append(Spacer(1, 6))
            
            # 📸 ✨ [फ़ोटो पाथ डिटेक्टर हुक]: स्टोरी टेबल के अंदर इमेज डालने के लिए पाथ निकालना
            photo_file_path = ""
            if ehrms_id_val:
                clean_id = ehrms_id_val.replace('.0', '').strip()
                for ext in ('.jpg', '.png', '.jpeg', '.bmp'):
                    p_path = os.path.join(STAFF_PHOTO_DIR, f"{clean_id}{ext}")
                    if os.path.exists(p_path):
                        photo_file_path = p_path; break
                        
            if not photo_file_path or not os.path.exists(photo_file_path):
                if hasattr(self, 'selected_staff_photo_path') and self.selected_staff_photo_path and os.path.exists(str(self.selected_staff_photo_path).strip()):
                    photo_file_path = str(self.selected_staff_photo_path).strip()
            
            # अंतरराष्ट्रीय पासपोर्ट आकार (35mm × 45mm = ~99pt × ~127pt) विजेट बनाना
            if photo_file_path and os.path.exists(photo_file_path):
                staff_img_widget = Image(photo_file_path, width=35*mm, height=45*mm)
            else:
                staff_img_widget = Paragraph("<font size=8 color='#666655'><b>PASSPORT<br/>PHOTO</b></font>", cell_bold)

            # ✨ [मास्टर अलाइनमेंट फिक्स]: तीसरे कॉलम की रो नंबर 1 पर फ़ोटो विजेट लॉक कर दिया, बाकी रोज़ खाली रहेंगी
            staff_left_fields = [
                [Paragraph("<b>TEACHER'S NAME</b>", cell_bold), Paragraph(teacher_name.upper(), cell_bold), staff_img_widget],
                [Paragraph("<b>FATHER/HUSBAND'S NAME</b>", cell_bold), Paragraph(f_txt("FATHER/HUSBAND'S NAME").upper(), cell_norm), ""],
                [Paragraph("<b>MOTHER'S NAME</b>", cell_bold), Paragraph(f_txt("MOTHER'S NAME").upper(), cell_norm), ""],
                [Paragraph("<b>GENDER (MALE/FEMALE)</b>", cell_bold), Paragraph(f_txt('GENDER (MALE/FEMALE)'), cell_norm), ""],
                [Paragraph("<b>DATE OF BIRTH</b>", cell_bold), Paragraph(f_txt('DATE OF BIRTH'), cell_bold), ""],
                [Paragraph("<b>DATE OF BIRTH (IN WORDS)</b>", cell_bold), Paragraph(f_txt('DATE OF BIRTH (IN WORDS)').upper(), cell_norm), ""],
                [Paragraph("<b>AADHAR NUMBER</b>", cell_bold), Paragraph(f_txt('AADHAR NUMBER'), cell_norm), ""],
                [Paragraph("<b>EMAIL ID</b>", cell_bold), Paragraph(f_txt('EMAIL ID').lower(), cell_norm), ""],
                [Paragraph("<b>QUALIFICATION</b>", cell_bold), Paragraph(f_txt('QUALIFICATION').upper(), cell_norm), ""],
                [Paragraph("<b>FIRST JOINING DATE</b>", cell_bold), Paragraph(f_txt('FIRST JOINING DATE'), cell_norm), ""],
                [Paragraph("<b>CURRENT SCHOOL JOINING</b>", cell_bold), Paragraph(f_txt('CURRENT SCHOOL JOINING DATE'), cell_norm), ""],
                [Paragraph("<b>ADDRESS</b>", cell_bold), Paragraph(f_txt('ADDRESS').upper(), cell_norm), ""]
            ]
            
            t_st_left = Table(staff_left_fields, colWidths=(165, 250, 150), rowHeights=(28,28,28,28,28,28,28,28,28,28,28,28))
            t_st_left.setStyle(TableStyle([
                # ग्रिड लाइन्स को सिर्फ पहले दो कॉलम (0 और 1) तक ही सीमित रखा, तीसरे कॉलम (फोटो एरिया) में ग्रिड लाइन बंद!
                ('GRID', (0,0), (1,-1), 1, GRID_LINE), 
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F9F9F9")), 
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                
                # 🛡️ तीसरे कॉलम (फोटो एरिया) को पूरी तरह से एक बड़ा ब्लैंक बॉक्स (Span) बनाकर साफ़ करना
                ('SPAN', (2,0), (2,-1)), 
                ('ALIGN', (2,0), (2,-1), 'CENTER'),
                ('VALIGN', (2,0), (2,-1), 'MIDDLE'),
                ('BACKGROUND', (2,0), (2,-1), colors.white),
                ('BOX', (2,0), (2,-1), 1.2, colors.black), # फोटो के चारों तरफ एक साफ़ आउटलाइन बॉक्स
            ]))
            
            st_block = [[t_st_left, Spacer(1, 1)]]
            t_st_main = Table(st_block, colWidths=(565, 0))
            t_st_main.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0)
            ]))
            story.append(t_st_main)
            story.append(Spacer(1, 95))
            
            # --- SIGNATURE BLOCK ---
            sig_right_style = ParagraphStyle('S_R', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.black, alignment=2)
            sig_data = [
                [Paragraph("<b>________________________<br/><br/>Teacher's Signature</b>", cell_bold),
                 Paragraph("<b>________________________<br/><br/>Headmaster Signature</b>", sig_right_style)]
            ]
            t_sig = Table(sig_data, colWidths=(282.5, 282.5))
            t_sig.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'BOTTOM'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)
            ]))
            story.append(t_sig)
            
            # --- CANVAS DECORATIONS (BORDERS, LOGOS, WATERMARK) ---
            def draw_staff_canvas_decorations(canvas, document):
                canvas.saveState()
                canvas.setStrokeColor(HEADER_MAROON); canvas.setLineWidth(2); canvas.rect(8, 8, 579, 826) 
                canvas.setStrokeColor(OFFICIAL_BLUE); canvas.setLineWidth(0.8); canvas.rect(11, 11, 573, 820)
                
                if os.path.exists(get_exe_safe_path("basic.png")):
                    try: canvas.drawImage(get_exe_safe_path("basic.png"), 20, 756, width=46, height=46, mask='auto')
                    except: pass
                    
                if os.path.exists(get_exe_safe_path("logo.png")):
                    try: canvas.drawImage(get_exe_safe_path("logo.png"), 528, 756, width=46, height=46, mask='auto')
                    except: pass

                canvas.setFillColor(HEADER_MAROON); canvas.setFont("Helvetica-Bold", 12)
                canvas.drawCentredString(297, 792, "UTTAR PRADESH BASIC SHIKSHA PARISHAD, PRAYAGRAJ")
                
                canvas.setFillColor(OFFICIAL_BLUE); canvas.setFont("Helvetica-Bold", 16)
                canvas.drawCentredString(297, 773, "PRIMARY SCHOOL PANAUTA")
                canvas.setFillColor(colors.black)
                canvas.setFont(MY_PROJECT_FONT, 12)
                canvas.drawCentredString(297, 760, "BLOCK - WAZIRGANJ, DISTRICT - BUDAUN, 243601")
                
                canvas.setFillColor(OFFICIAL_BLUE)
                canvas.setFont("Helvetica-Bold", 11)
                canvas.drawCentredString(297, 742, "STAFF BIODATA FORM")
                canvas.setFillColor(colors.black)
                canvas.setFont("Helvetica-Bold", 9)
                canvas.drawCentredString(297, 729, "SESSION - 2026-2027")

                if os.path.exists(get_exe_safe_path("logo.png")):
                    try:
                        canvas.saveState()
                        canvas.setFillAlpha(0.06) 
                        canvas.drawImage(get_exe_safe_path("logo.png"), 172, 296, width=250, height=250, mask='auto')
                        canvas.restoreState()
                    except:
                        pass
                canvas.restoreState()
                
            doc.build(story, onFirstPage=draw_staff_canvas_decorations)
            self.popup('Print Engine', f"STAFF BIODATA FORM IS READY!\nSAVED: {pdf_filename}")
            open_file_cross_platform(pdf_filename)
        except Exception as e:
            self.popup('Print Error', f"ReportLab Interruption: {str(e)}")

    def generate_student_report_card_pdf(self, instance):
        import os
        pass
        import platform
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.platypus import Image as RLImage
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        # --- 🔤 [ग्लोबल हिंदी-इंग्लिश फॉन्ट सिंक] ---
        HINDI_FONT_NAME = MY_PROJECT_FONT

        st_profile = getattr(self, 'current_report_student_profile', {})
        compiled_marks = getattr(self, 'student_marks_summary', {})
        
        st_name = st_profile.get('NAME', '')
        sr_no_val = st_profile.get('SR NO', '')
        class_val = str(st_profile.get('CLASS', '')).strip()
        
        if not st_name:
            self.popup('System Alert', "Student details could not be loaded!"); return
            
        try:
            pdf_filename = f"Report_Card_SR_{sr_no_val.replace(' ', '_')}.pdf"
            doc = SimpleDocTemplate(pdf_filename, pagesize=A4, rightMargin=15, leftMargin=15, topMargin=112, bottomMargin=15)
            story = []
            
            PURPLE_THEME = colors.HexColor("#3F2583")  
            LIGHT_PURPLE = colors.HexColor("#F1EEF9")  
            BORDER_GOLD = colors.HexColor("#D4AF37")   
            GRID_LINE = colors.HexColor("#595959")     
            
            styles = getSampleStyleSheet()
            cell_bold = ParagraphStyle('C_B', fontName=HINDI_FONT_NAME, fontSize=10, leading=13, textColor=colors.black)
            cell_norm = ParagraphStyle('C_N', fontName=HINDI_FONT_NAME, fontSize=10, leading=13, textColor=colors.black)
            
            center_bold = ParagraphStyle('C_Bold', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.black, alignment=1)
            center_norm = ParagraphStyle('C_Norm', fontName='Helvetica', fontSize=10, leading=13, textColor=colors.black, alignment=1)
            
            table_header_style = ParagraphStyle('T_H', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.white, alignment=1)
            strip_style = ParagraphStyle('Str_Txt', fontName='Helvetica-Bold', fontSize=12, leading=14, textColor=colors.white, alignment=1)
            sub_strip_style = ParagraphStyle('SubStr', fontName=HINDI_FONT_NAME, fontSize=10, leading=13, textColor=colors.white, alignment=1)
            
            # --- 🗂️ SECTION 1: REPORT CARD BANNER ---
            banner_width_val = 565
            banner_width_total = [banner_width_val]
            banner_data = [
                [Paragraph("<b>REPORT CARD</b>", strip_style)],
                [Paragraph("Academic Session  •  2025-2026", sub_strip_style)]
            ]
            t_banner = Table(banner_data, colWidths=banner_width_total, rowHeights=20)
            t_banner.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), PURPLE_THEME),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2), ('TOPPADDING', (0,0), (-1,-1), 2)
            ]))
            story.append(t_banner)
            story.append(Spacer(1, 6))
            
            # --- 📸 SECTION 2: STUDENT PROFILE GRID WITH PASSPORT PHOTO ---
            photo_file_path = ""
            if sr_no_val:
                clean_id = sr_no_val.replace('.0', '').strip()
                for ext in ['.jpg', '.png', '.jpeg', '.bmp']:
                    p_path = os.path.join('student_photos', f"{clean_id}{ext}")
                    if os.path.exists(p_path):
                        photo_file_path = p_path; break
                        
            if not photo_file_path or not os.path.exists(photo_file_path):
                if hasattr(self, 'selected_photo_path') and self.selected_photo_path and os.path.exists(str(self.selected_photo_path).strip()):
                    photo_file_path = str(self.selected_photo_path).strip()
            
            if photo_file_path and os.path.exists(photo_file_path):
                try: student_img_widget = RLImage(photo_file_path, width=35*mm, height=40*mm)
                except: student_img_widget = Paragraph("<font size=8 color='#777777'><b>PHOTO ERROR</b></font>", cell_bold)
            else:
                student_img_widget = Paragraph("<font size=8 color='#777777'><b>PASSPORT<br/>PHOTO</b></font>", cell_bold)

            w_label_1 = 95
            w_value_1 = 130
            w_label_2 = 95
            w_value_2 = 145
            w_photo_column = 100
            profile_column_widths_list = [w_label_1, w_value_1, w_label_2, w_value_2, w_photo_column]
            profile_row_heights_list = [22.5, 22.5, 22.5, 22.5, 22.5]

            raw_dob = st_profile.get('DATE OF BIRTH', '---')
            dob_words = date_to_words_eng(raw_dob) if raw_dob != '---' else '---'
            # ✨ [सुधार फिक्स 1]: नंबर और शब्दों को आपस में कंबाइन किया गया
            full_dob_combined = f"{raw_dob} &nbsp;({dob_words.upper()})" if raw_dob != '---' else '---'

            # ✨ [सुधार फिक्स 2]: सभी फील्ड्स के आगे विसर्ग (:) लगा दिया गया है
            profile_grid = [
                [Paragraph("Student Name :", cell_norm), Paragraph(f"<b>{st_name.upper()}</b>", cell_bold),
                 Paragraph("Class :", cell_norm), Paragraph(class_val if class_val else "Class 1", cell_bold), student_img_widget],
                [Paragraph("Admission No :", cell_norm), Paragraph(sr_no_val, cell_bold),
                 Paragraph("Session :", cell_norm), Paragraph("2025-2026", cell_norm), ""],
                [Paragraph("Father's Name :", cell_norm), Paragraph(st_profile.get("FATHER'S NAME", '').upper(), cell_norm),
                 Paragraph("Mother's Name :", cell_norm), Paragraph(st_profile.get("MOTHER'S NAME", '').upper(), cell_norm), ""],
                [Paragraph("Date of Birth :", cell_norm), Paragraph(f"<font size=8.5><b>{full_dob_combined}</b></font>", cell_bold), "", "", ""],
                [Paragraph("PEN No :", cell_norm), Paragraph(st_profile.get('PEN NO', '---'), cell_norm),
                 Paragraph("APAAR ID :", cell_norm), Paragraph(st_profile.get('APAAR ID', '---'), cell_norm), ""]
            ]
            
            t_profile = Table(profile_grid, colWidths=profile_column_widths_list, rowHeights=profile_row_heights_list)
            t_profile.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LINEBELOW', (0,0), (3,4), 0.5, colors.HexColor("#D3D3D3")),
                ('SPAN', (4,0), (4,4)), 
                ('SPAN', (1,3), (3,3)), # कंबाइन DOB को पूरे ३ खानों तक क्षैतिज मर्ज किया
                ('ALIGN', (4,0), (4,4), 'CENTER'),
                ('VALIGN', (4,0), (4,4), 'MIDDLE'),
                ('BOX', (4,0), (4,4), 1.2, PURPLE_THEME), 
                ('TOPPADDING', (0,0), (-1,-1), 1), ('BOTTOMPADDING', (0,0), (-1,-1), 1)
            ]))
            story.append(t_profile)
            story.append(Spacer(1, 10))
            
            # --- 📊 SECTION 3: STATEMENT OF MARKS ---
            story.append(Paragraph("<font color='#3F2583'><b>STATEMENT OF MARKS</b></font>", ParagraphStyle('SecT', fontName='Helvetica-Bold', fontSize=10.5, leading=13)))
            story.append(Spacer(1, 4))
            
            is_class_1_or_2 = any(x in class_val.lower() for x in ['1', '2', 'one', 'two'])
            subjects_list = ["HINDI", "ENGLISH", "MATHS"] if is_class_1_or_2 else ["HINDI", "ENGLISH", "SANSKRIT", "MATHS", "HAMARA PARIVESH", "ART", "PHYSICAL EDUCATION", "ENVIRONMENT", "WORK EXPERIENCE", "NAITIK SHIKSHA"]
            max_subjects = len(subjects_list)

            # ✨ [क्रिटिकल फिक्स]: फ़ंक्शन को लूप से ठीक पहले डिक्लेअर किया गया ताकि अनफाइंड एरर जड़ से ख़त्म हो जाए
            def calculate_grade(score):
                if score >= 91: return 'A'
                elif score >= 76: return 'B'
                elif score >= 56: return 'C'
                elif score >= 41: return 'D'
                return 'E'

            total_st1, total_st2, total_half, total_annual, total_grand = 0, 0, 0, 0, 0
            valid_subject_count = 0 
            
            w_col_idx = 25
            w_col_sub = 270
            w_col_mark = 54
            master_marks_table_widths = [w_col_idx, w_col_sub, w_col_mark, w_col_mark, w_col_mark, w_col_mark, w_col_mark]
            
            marks_rows = [
                [
                    Paragraph("<b>#</b>", table_header_style), Paragraph("<b>SUBJECT</b>", table_header_style),
                    Paragraph("<b>ST1</b>", table_header_style), Paragraph("<b>HALF</b>", table_header_style),
                    Paragraph("<b>ST2</b>", table_header_style), Paragraph("<b>ANNUAL</b>", table_header_style),
                    Paragraph("<b>TOTAL</b>", table_header_style)
                ],
                [
                    Paragraph("", table_header_style), Paragraph("", table_header_style),
                    Paragraph("<b>(10)</b>", table_header_style), Paragraph("<b>YEARLY (30)</b>", table_header_style),
                    Paragraph("<b>(10)</b>", table_header_style), Paragraph("<b>(50)</b>", table_header_style),
                    Paragraph("<b>(100)</b>", table_header_style)
                ]
            ]
            
            for idx, sub in enumerate(subjects_list, start=1):
                st1 = compiled_marks.get(f"{sub}_ST1", 0)
                half = compiled_marks.get(f"{sub}_HALF", 0)
                st2 = compiled_marks.get(f"{sub}_ST2", 0)
                annual = compiled_marks.get(f"{sub}_ANNUAL", 0)
                sub_total = st1 + half + st2 + annual
                
                if sub_total > 0:
                    valid_subject_count += 1
                    total_st1 += st1; total_st2 += st2; total_half += half; total_annual += annual; total_grand += sub_total
                    temp_row = [
                        Paragraph(str(idx), center_norm), Paragraph(f"<b>{sub}</b>", cell_bold),
                        Paragraph(str(st1), center_norm), Paragraph(str(half), center_norm),
                        Paragraph(str(st2), center_norm), Paragraph(str(annual), center_norm),
                        Paragraph(f"<b>{sub_total}</b>", center_bold)
                    ]
                else:
                    temp_row = [Paragraph(str(idx), center_norm), Paragraph(sub, cell_norm), Paragraph("-", center_norm), Paragraph("-", center_norm), Paragraph("-", center_norm), Paragraph("-", center_norm), Paragraph("-", center_norm)]
                marks_rows.append(temp_row)
                
            if valid_subject_count == 0: valid_subject_count = max_subjects

            marks_rows.append([
                Paragraph("", center_norm), Paragraph("<b>Grand Total</b>", cell_bold),
                Paragraph(f"<b>{total_st1}</b>", center_bold), Paragraph(f"<b>{total_half}</b>", center_bold),
                Paragraph(f"<b>{total_st2}</b>", center_bold), Paragraph(f"<b>{total_annual}</b>", center_bold),
                Paragraph(f"<font color='#3F2583'><b>{total_grand} / {valid_subject_count*100}</b></font>", center_bold)
            ])

            t_matrix = Table(marks_rows, colWidths=master_marks_table_widths)
            t_style = [
                ('GRID', (0,0), (-1,-1), 0.8, GRID_LINE),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (-1,1), PURPLE_THEME), 
                ('SPAN', (0,0), (0,1)), 
                ('SPAN', (1,0), (1,1)), 
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('BACKGROUND', (0,-1), (-1,-1), LIGHT_PURPLE),
                ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)
            ]
            
            for i in range(2, max_subjects + 2):
                if i % 2 == 1: 
                    t_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor("#F7F5FB")))
                else:
                    t_style.append(('BACKGROUND', (0, i), (-1, i), colors.white))
                    
            t_matrix.setStyle(TableStyle(t_style))
            story.append(t_matrix)
            story.append(Spacer(1, 10))
            
            # --- 📈 SECTION 4: PROGRESS BOXES ---
            perc_val = (total_grand / (valid_subject_count * 100)) * 100 if total_grand > 0 else 0
            final_grade = calculate_grade(perc_val) if total_grand > 0 else "-"
            
            box_style_title = ParagraphStyle('BT', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor("#333333"), alignment=1)
            box_style_score = ParagraphStyle('BS', fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=PURPLE_THEME, alignment=1)
            
            cards_grid = [
                [Paragraph("TOTAL MARKS", box_style_title), Paragraph("PERCENTAGE", box_style_title), Paragraph("OVERALL GRADE", box_style_title), Paragraph("CLASS RANK", box_style_title), Paragraph("RESULT STATUS", box_style_title)],
                [Paragraph(f"<b>{total_grand} / {valid_subject_count*100}</b>", box_style_score), Paragraph(f"<b>{perc_val:.1f}%</b>", box_style_score), Paragraph(f"<b>{final_grade}</b>", box_style_score), Paragraph("<b>#1</b>", box_style_score), Paragraph("<b>PASS</b>" if perc_val >= 40 else "<b>---</b>", box_style_score)]
            ]
            
            w_card_single = 113
            cards_columns_widths_list = [w_card_single, w_card_single, w_card_single, w_card_single, w_card_single]
            
            t_cards = Table(cards_grid, colWidths=cards_columns_widths_list)
            t_cards.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, PURPLE_THEME),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (-1,0), LIGHT_PURPLE),
                ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('BACKGROUND', (4,1), (4,1), colors.HexColor("#2E7D32")) if perc_val >= 40 else ('BACKGROUND', (4,1), (4,1), colors.white),
                ('TEXTCOLOR', (4,1), (4,1), colors.white) if perc_val >= 40 else ('TEXTCOLOR', (4,1), (4,1), colors.black)
            ]))
            story.append(t_cards)
            story.append(Spacer(1, 10))
            
                       # --- 📝 SECTION 5: GRADE SCALE PANEL ---
            scale_style = ParagraphStyle('GS', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.black, alignment=1)
            g_scale_data = [[Paragraph("GRADE SCALE : &nbsp;&nbsp;&nbsp;&nbsp; A (100%-91%) &nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp; B (90%-76%) &nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp; C (75%-56%) &nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp; D (55%-41%) &nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp; E (Below 40% Fail)", scale_style)]]
            
            t_g_box = Table(g_scale_data, colWidths=banner_width_total, rowHeights=20)
            t_g_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), LIGHT_PURPLE), 
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), 
                ('GRID', (0,0), (-1,-1), 1, PURPLE_THEME)
            ]))
            story.append(t_g_box)
            
            # --- 🎨 MASTER CANVAS DECORATIONS ---
            def draw_premium_canvas_decorations(canvas, document):
                canvas.saveState()
                
                canvas.setStrokeColor(PURPLE_THEME); canvas.setLineWidth(1.5); canvas.rect(8, 8, 579, 826) 
                canvas.setStrokeColor(BORDER_GOLD); canvas.setLineWidth(0.6); canvas.rect(10, 10, 575, 822)
                
                if os.path.exists(get_exe_safe_path("basic.png")):
                    try: canvas.drawImage(get_exe_safe_path("basic.png"), 18, 742, width=55, height=55, mask='auto')
                    except: pass
                if os.path.exists(get_exe_safe_path("logo.png")):
                    try: canvas.drawImage(get_exe_safe_path("logo.png"), 522, 742, width=55, height=55, mask='auto')
                    except: pass

                canvas.setFillColor(PURPLE_THEME); canvas.setFont("Helvetica-Bold", 22)
                canvas.drawCentredString(297, 778, "PRIMARY SCHOOL PANAUTA")
                
                canvas.setFillColor(colors.black); canvas.setFont("Helvetica-Bold", 10.5)
                canvas.drawCentredString(297, 762, "BLOCK - WAZIRGANJ, DISTRICT - BUDAUN, UDISE - 09191204201")
                
                canvas.setFillColor(colors.black); canvas.setFont("Helvetica-Bold", 9.5)
                canvas.drawCentredString(297, 748, "Phone: 9458500800  |  Email: pspanauta1@gmail.com")

                if os.path.exists(get_exe_safe_path("logo.png")):
                    try:
                        canvas.saveState()
                        canvas.setFillAlpha(0.06) 
                        canvas.drawImage(get_exe_safe_path("logo.png"), 172, 260, width=250, height=250, mask='auto')
                        canvas.restoreState()
                    except: pass
                    
                sig_y_pos = 38
                canvas.setStrokeColor(colors.black); canvas.setLineWidth(1)
                
                canvas.line(30, sig_y_pos + 15, 180, sig_y_pos + 15)
                canvas.line(222, sig_y_pos + 15, 372, sig_y_pos + 15)
                canvas.line(415, sig_y_pos + 15, 565, sig_y_pos + 15)
                
                canvas.setFillColor(colors.black); canvas.setFont("Helvetica-Bold", 9.5)
                canvas.drawCentredString(105, sig_y_pos, "CLASS TEACHER")
                canvas.drawCentredString(297, sig_y_pos, "EXAM CONTROLLER")
                canvas.drawCentredString(490, sig_y_pos, "PRINCIPAL")
                
                canvas.restoreState()
                
            doc.build(story, onFirstPage=draw_premium_canvas_decorations)
            self.popup('Report Hub', f"Report Card generated successfully!\nSaved as: {pdf_filename}")
            open_file_cross_platform(pdf_filename)
        except Exception as e:
            self.popup('Print Error', f"ReportLab Engine Interruption: {str(e)}")

    # 🖨️ 🍱 [भाग ए]: मासिक खाद्यान्न प्रोग्रेस रिपोर्ट (MPR) जनरेट करने का इंजन (Windows + Android क्रॉस-प्लेटफ़ॉर्म)
    def generate_mdm_monthly_mpr_pdf(self):
        import os
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, TableStyle, Table, Paragraph, Spacer
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib import colors
        
        m_name = self.mdm_month_spinner.text.strip()
        y_name = self.mdm_year_spinner.text.strip()
        target_period = f"{m_name}-{y_name}".lower().strip()
        mdm_file = 'MDM_Database.xlsx'
        
        if not os.path.exists(mdm_file):
            self.popup('Alert', 'MDM Database is empty! Please save data first.'); return
            
        try:
            df_m = pd.read_excel(mdm_file, dtype=str)
            filtered_rows = []
            for _, r_m in df_m.iterrows():
                if str(r_m.get('Month-Year', '')).strip().lower() == target_period:
                    filtered_rows.append(dict(r_m))
            
            if not filtered_rows:
                self.popup('No Data', f'No food distribution data found for {m_name}-{y_name}'); return
                
            working_rows = []
            for r_w in filtered_rows:
                opt_s = str(r_w.get('MDM Opted', '')).strip().upper()
                if opt_s != 'HOLIDAY' and opt_s not in ['', '0', 'NAN']:
                    working_rows.append(r_w)

            total_working_days = len(working_rows)
            
            def get_safe_sum(column_name):
                s_val = 0
                for rw in working_rows:
                    try: s_val += int(float(str(rw.get(column_name, 0)).strip() or 0))
                    except Exception: pass
                return s_val
                
            total_mdm_served = get_safe_sum('MDM Opted')
            total_fruits_served = get_safe_sum('Fruit Distributed')
            total_suppl_served = get_safe_sum('Hand Wash')
            
            total_wheat_used = 0.0
            total_rice_used = 0.0
            for rw in working_rows:
                try: total_wheat_used += float(str(rw.get('Wheat_KG', 0)).strip() or 0)
                except Exception: pass
                try: total_rice_used += float(str(rw.get('Rice_KG', 0)).strip() or 0)
                except Exception: pass
            filtered_df = pd.DataFrame(filtered_rows)
            
            # ✨ [गुणा लागत गणना फ़ॉर्मूला इंजन Lock]
            calc_total_conv_cost = total_mdm_served * 6.78
            calc_total_fruit_cost = total_fruits_served * 4.00
            calc_total_suppl_cost = total_suppl_served * 5.00
            
            out_pdf_name = f"MDM_Monthly_MPR_{m_name}_{y_name}.pdf"
            doc_pdf = SimpleDocTemplate(out_pdf_name, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
            pdf_story = []
            
            BROWN_THEME = colors.HexColor("#7A3E00"); LIGHT_GOLD = colors.HexColor("#FFF8E7")
            h_main = ParagraphStyle('H_M_M', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=BROWN_THEME, alignment=1)
            h_sub = ParagraphStyle('H_S_M', fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=colors.black, alignment=1)
            th_style = ParagraphStyle('T_H_M', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=colors.white, alignment=1)
            td_bold = ParagraphStyle('T_D_B_M', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=colors.black, alignment=1)
            td_norm = ParagraphStyle('T_D_N_M', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.black, alignment=1)
            
            smry_title = ParagraphStyle('S_T_M', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=BROWN_THEME, alignment=1)
            smry_val = ParagraphStyle('S_V_M', fontName='Helvetica-Bold', fontSize=11, leading=13, textColor=colors.black, alignment=1)
            
            pdf_story.append(Spacer(1, 15))
            pdf_story.append(Paragraph("<b>PRIMARY SCHOOL PANAUTA, WAZIRGANJ (BUDAUN)</b>", h_main))
            pdf_story.append(Paragraph(f"<b>MID-DAY MEAL (MDM) MONTHLY PROGRESS REPORT (MPR)  •  PERIOD: {m_name.upper()} {y_name}</b>", h_sub))
            pdf_story.append(Spacer(1, 12))
            
                        # ✨ [क्रिटिकल फिक्स 1]: हेडर रो को शुद्ध स्ट्रिंग टेक्स्ट में बदला गया ताकि INNERGRID शत-प्रतिशत रेंडर हो सके!
            row_headers = ["TOTAL DAYS", "CONVERSION COST", "FRUITS COST", "SUPPLEMENT COST", "WHEAT REGISTER", "RICE REGISTER"]
            
            row_data_composite = [
                Paragraph(f"<b>{total_working_days} Days</b>", smry_val), 
                Paragraph(f"Fed: {total_mdm_served}<br/><font color='green'><b>Rs.{calc_total_conv_cost:.2f}</b></font>", smry_val), 
                Paragraph(f"Fed: {total_fruits_served}<br/><font color='green'><b>Rs.{calc_total_fruit_cost:.2f}</b></font>", smry_val), 
                Paragraph(f"Served: {total_suppl_served}<br/><font color='green'><b>Rs.{calc_total_suppl_cost:.2f}</b></font>", smry_val), 
                Paragraph(f"<b>{total_wheat_used:.2f} KG</b>", smry_val), 
                Paragraph(f"<b>{total_rice_used:.2f} KG</b>", smry_val)
            ]
            
            summary_table_data = [row_headers, row_data_composite]
            
            # 📐 [क्रिटिकल फिक्स 2]: निचली मुख्य तालिका की कुल चौड़ाई (36+46+73*9 = 812 पॉइंट्स) के एकदम बराबर आवंटन फिक्स
            w_box_unit = 812.0 / 6.0
            
            t_summary = Table(summary_table_data, colWidths=[w_box_unit]*6)
            
            # ✨ [क्रिटिकल फिक्स 3]: 'GRID' और 'BOX' दोनों को एक साथ लगाकर लाइनों को 100% कड़ाई से लॉक किया गया
            t_summary.setStyle(TableStyle([
                ('TEXTCOLOR', (0,0), (-1,0), BROWN_THEME),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 10.5),
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#FAF0E6")), 
                ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#FFFDE7")), 
                ('GRID', (0,0), (-1,-1), 1.2, BROWN_THEME), 
                ('BOX', (0,0), (-1,-1), 1.5, BROWN_THEME),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), 
                ('ALIGN', (0,0), (-1,-1), 'CENTER'), 
                ('TOPPADDING', (0,0), (-1,-1), 7), 
                ('BOTTOMPADDING', (0,0), (-1,-1), 7)
            ]))
            pdf_story.append(t_summary); pdf_story.append(Spacer(1, 15))

            # ✨ [सुधार 4]: पूरे महीने की सभी तारीखें (All Dates) क्रमानुसार स्वतः मैप करने का लूप इंजन
            reg_headers = [Paragraph("<b>DATE</b>", th_style), Paragraph("<b>DAY</b>", th_style), Paragraph("<b>TOTAL PRES</b>", th_style), Paragraph("<b>MDM OPTED</b>", th_style), Paragraph("<b>HAND WASH</b>", th_style), Paragraph("<b>MILK DIST</b>", th_style), Paragraph("<b>FRUIT DIST</b>", th_style), Paragraph("<b>SUPPL RCVD</b>", th_style), Paragraph("<b>WHEAT (KG)</b>", th_style), Paragraph("<b>RICE (KG)</b>", th_style), Paragraph("<b>CONV COST</b>", th_style)]
            reg_table_rows = [reg_headers]
            
            y_val = int(y_name); months_num_map = {'January':1, 'February':2, 'March':3, 'April':4, 'May':5, 'June':6, 'July':7, 'August':8, 'September':9, 'October':10, 'November':11, 'December':12}
            m_num = months_num_map[m_name]
            months_days_count = {'January':31, 'February':29 if (y_val%4==0 and (y_val%100!=0 or y_val%400==0)) else 28, 'March':31, 'April':30, 'May':31, 'June':30, 'July':31, 'August':31, 'September':30, 'October':31, 'November':30, 'December':31}
            max_days = months_days_count.get(m_name, 31)
            
            for d in range(1, max_days + 1):
                try:
                    from datetime import datetime
                    dt_obj = datetime(y_val, m_num, d); day_name = dt_obj.strftime('%A'); w_day = dt_obj.weekday()
                except Exception: day_name = "Sunday"; w_day = 6
                
                row_val = None
                for r_item in filtered_rows:
                    if str(r_item.get('Date', '')).strip().split('.') == str(d):
                        row_val = r_item
                
                if w_day == 6:
                    reg_table_rows.append([Paragraph(f"{d}", td_norm), Paragraph("Sunday", td_norm), Paragraph("---", td_norm), Paragraph("<font color='red'>HOLIDAY</font>", td_bold), Paragraph("---", td_norm), Paragraph("---", td_norm), Paragraph("---", td_norm), Paragraph("---", td_norm), Paragraph("---", td_norm), Paragraph("---", td_norm), Paragraph("Rs.0.00", td_norm)])
                    continue
                    
                if row_val is not None:
                    opt_txt = str(row_val.get('MDM Opted', '0')).strip()
                    is_h = 'HOLIDAY' in opt_txt.upper() or opt_txt in ['', '0', 'nan']
                    opt_html = f"<font color='red'>HOLIDAY</font>" if is_h else opt_txt
                    
                    reg_table_rows.append([
                        Paragraph(str(d), td_norm), Paragraph(day_name[:3], td_norm),
                        Paragraph('---' if is_h else str(row_val.get('Total Present', '0')), td_norm),
                        Paragraph(opt_html, td_bold if is_h else td_norm),
                        Paragraph('---' if is_h else str(row_val.get('Hand Wash', '0')), td_norm),
                        Paragraph('---' if is_h else str(row_val.get('Milk Distributed', 'NO')), td_norm),
                        Paragraph('---' if is_h else str(row_val.get('Fruit Distributed', '0')), td_norm),
                        Paragraph('---' if is_h else str(row_val.get('Supplement Served', '0')), td_norm),
                        Paragraph('---' if is_h else f"{float(row_val.get('Wheat_KG',0) or 0):.2f}", td_norm),
                        Paragraph('---' if is_h else f"{float(row_val.get('Rice_KG',0) or 0):.2f}", td_norm),
                        Paragraph('---' if is_h else f"Rs.{float(row_val.get('Conversion Cost',0) or 0):.2f}", td_bold)
                    ])
                else:
                    reg_table_rows.append([Paragraph(str(d), td_norm), Paragraph(day_name[:3], td_norm), Paragraph("0", td_norm), Paragraph("Not Fed", td_norm), Paragraph("0", td_norm), Paragraph("NO", td_norm), Paragraph("0", td_norm), Paragraph("0", td_norm), Paragraph("0.00", td_norm), Paragraph("0.00", td_norm), Paragraph("Rs.0.00", td_norm)])
                    
            t_register = Table(reg_table_rows, colWidths=[50, 65, 75, 80, 70, 70, 75, 80, 80, 80, 85], repeatRows=1)
            t_style_rules = [('GRID', (0,0), (-1,-1), 0.8, colors.HexColor("#595959")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BACKGROUND', (0,0), (-1,0), BROWN_THEME), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)]
            for i in range(1, len(reg_table_rows)):
                if i % 2 == 0: t_style_rules.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GOLD))
            t_register.setStyle(TableStyle(t_style_rules))
            pdf_story.append(t_register); pdf_story.append(Spacer(1, 45))
            
            w_sig_panel = 390
            t_sig = Table([[Paragraph("________________________", td_bold), Paragraph("________________________", td_bold)], [Paragraph("MDM IN-CHARGE SIGNATURE", td_bold), Paragraph("HEADMASTER SEAL & SIGNATURE", td_bold)]], colWidths=[w_sig_panel, w_sig_panel])
            t_sig.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0, colors.white), ('VALIGN', (0,0), (-1,-1), 'BOTTOM'), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 10)]))
            pdf_story.append(t_sig)
            
            def draw_ledger_decorations(canvas, document):
                canvas.saveState()
                if os.path.exists(get_exe_safe_path("basic.png")): canvas.drawImage(get_exe_safe_path("basic.png"), 25, 520, width=52, height=52, mask='auto')
                logo_p = get_exe_safe_path('logo.png')
                if os.path.exists(logo_p):
                    canvas.drawImage(logo_p, 765, 520, width=52, height=52, mask='auto')
                    canvas.saveState(); canvas.setFillAlpha(0.06); canvas.drawImage(logo_p, 296, 145, width=250, height=250, mask='auto'); canvas.restoreState()
                canvas.restoreState()
                
            doc_pdf.build(pdf_story, onFirstPage=draw_ledger_decorations)
            self.popup('Report Hub', f"MDM Monthly MPR Report Compiled Successfully!\nSaved: {out_pdf_name}")
            open_file_cross_platform(out_pdf_name)
        except Exception as ex: self.popup('Print Error', f"MPR PDF Compilation Failed: {str(ex)}")

    ### 🛠️ भाग 2: पूर्ण संरेखित एवं ग्रिड लाइन्स युक्त वित्तीय लेज़र इंजन (`generate_mdm_ledger_report_pdf`)
    def generate_mdm_ledger_report_pdf(self, is_annual=False):
        import os
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, TableStyle, Table, Paragraph, Spacer
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib import colors
        
        m_name = self.mdm_month_spinner.text.strip()
        y_name = self.mdm_year_spinner.text.strip()
        MDM_ACC_FILE = 'MDM_Account_Database.xlsx'
        
        if not os.path.exists(MDM_ACC_FILE):
            self.popup('Alert', 'Financial Ledger Database is completely empty!'); return
            
        try:
            df_l = pd.read_excel(MDM_ACC_FILE, dtype=str)
            
            rev_months_map = {'01':'JANUARY', '02':'FEBRUARY', '03':'MARCH', '04':'APRIL', '05':'MAY', '06':'JUNE', '07':'JULY', '08':'AUGUST', '09':'SEPTEMBER', '10':'OCTOBER', '11':'NOVEMBER', '12':'DECEMBER'}
            display_month_heading = m_name.upper()
            
            valid_rows = []
            if is_annual:
                for _, r_item in df_l.iterrows():
                    if str(y_name) in str(r_item.get('Received Date', '')):
                        valid_rows.append(dict(r_item))
                heading_title_text = f"ANNUAL COOPERATIVE FINANCIAL PASSBOOK LEDGER  •  YEAR: {y_name}"
                out_pdf_name = f"MDM_Annual_Financial_Ledger_{y_name}.pdf"
            else:
                try:
                    scr_date_parts = self.f_rec_date.text.strip().split('-')
                    target_m_code = str(scr_date_parts[1]).strip()
                    target_y_code = str(scr_date_parts[2]).strip()
                    display_month_heading = rev_months_map.get(target_m_code, m_name.upper())
                except Exception:
                    months_numeric_indices = {'January':'01', 'February':'02', 'March':'03', 'April':'04', 'May':'05', 'June':'06', 'July':'07', 'August':'08', 'September':'09', 'October':'10', 'November':'11', 'December':'12'}
                    target_m_code = months_numeric_indices.get(m_name, '10')
                    target_y_code = str(y_name)
                    display_month_heading = m_name.upper()
                
                for _, r_item in df_l.iterrows():
                    raw_date_str = str(r_item.get('Received Date', '')).strip()
                    if '-' in raw_date_str:
                        date_parts = raw_date_str.split('-')
                        if len(date_parts) == 3:
                            c_month = str(date_parts[1]).strip()
                            c_year = str(date_parts[2]).strip()
                            if c_month == target_m_code and c_year == target_y_code:
                                valid_rows.append(dict(r_item))
                                
                heading_title_text = f"MONTHLY PASSBOOK FINANCIAL LEDGER  •  PERIOD: {display_month_heading} {target_y_code}"
                out_pdf_name = f"MDM_Monthly_Financial_Ledger_{display_month_heading}_{target_y_code}.pdf"
                
            if not valid_rows:
                self.popup('No Transactions', 'No financial ledger records found for the selected period.'); return
            filtered_df = pd.DataFrame(valid_rows)
                   
            heads_to_track = ['Conversion Cost', 'Fruits Cost', 'MME', 'Nutrition Supplement Cost', 'Interest', 'LPG Subsidy', 'Others']
            summary_received_dict = {h: 0.00 for h in heads_to_track}
            summary_used_dict = {h: 0.00 for h in heads_to_track}
            summary_final_dict = {h: 0.00 for h in heads_to_track}
            
            for r_row in valid_rows:
                t_type = str(r_row.get('Transaction Type', '')).strip()
                if t_type in heads_to_track:
                    try: summary_received_dict[t_type] += float(str(r_row.get('Amount Received', 0)).strip() or 0)
                    except Exception: pass
                    try: summary_used_dict[t_type] += abs(float(str(r_row.get('Expenditure Amount', 0)).strip() or 0))
                    except Exception: pass
                    try: summary_final_dict[t_type] = float(str(r_row.get('Final Balance', 0)).strip() or 0)
                    except Exception: pass
                    
            doc_pdf = SimpleDocTemplate(out_pdf_name, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
            pdf_story = []
            
            NAVY_THEME = colors.HexColor("#0A3663"); LIGHT_BLUE = colors.HexColor("#EBF3FA")
            h_main = ParagraphStyle('H_M_L', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=NAVY_THEME, alignment=1)
            h_sub = ParagraphStyle('H_S_L', fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=colors.black, alignment=1)
            th_style = ParagraphStyle('T_H_L', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white, alignment=1)
            td_bold = ParagraphStyle('T_D_B_L', fontName='Helvetica-Bold', fontSize=8, leading=10.5, textColor=colors.black, alignment=1)
            td_norm = ParagraphStyle('T_D_N_L', fontName='Helvetica', fontSize=8, leading=10.5, textColor=colors.black, alignment=1)
            
            smry_title = ParagraphStyle('S_T_L', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=NAVY_THEME, alignment=1)
            smry_val_rcvd = ParagraphStyle('S_V_R', fontName='Helvetica', fontSize=9, leading=12, textColor=colors.HexColor("#1B5E20"), alignment=1)
            smry_val_used = ParagraphStyle('S_V_U', fontName='Helvetica', fontSize=9, leading=12, textColor=colors.HexColor("#B71C1C"), alignment=1)
            smry_val_bal = ParagraphStyle('S_V_B', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=colors.HexColor("#0D47A1"), alignment=1)
            
            pdf_story.append(Spacer(1, 15))
            pdf_story.append(Paragraph("<b>PRIMARY SCHOOL PANAUTA, WAZIRGANJ (BUDAUN)</b>", h_main))
            pdf_story.append(Paragraph(f"<b>{heading_title_text}</b>", h_sub))
            pdf_story.append(Spacer(1, 12))
            
            # ✨ [महा-सुधार]: 4-कतारों का मैट्रिक्स बनाया गया ताकि Received, Used और Balance के बीच ग्रिड लाइन्स आ सकें
            row_heads = [Paragraph(f"<b>{h.upper()}</b>", smry_title) for h in heads_to_track]
            row_rcvd = [Paragraph(f"Rcvd: {summary_received_dict[h]:.0f}", smry_val_rcvd) for h in heads_to_track]
            row_used = [Paragraph(f"Used: {summary_used_dict[h]:.0f}", smry_val_used) for h in heads_to_track]
            row_bal = [Paragraph(f"<b>Bal: {summary_final_dict[h]:.1f}</b>", smry_val_bal) for h in heads_to_track]
            
            summary_matrix = [row_heads, row_rcvd, row_used, row_bal]
            
            # निचली टेबल के बिल्कुल बराबर ८१० पॉइंट्स की एब्सोल्यूट चौड़ाई सिंक
            w_box_unit = 810 / 7
            t_summary = Table(summary_matrix, colWidths=[140, 110, 110, 120, 110, 110, 110])
            
            # ✨ [ग्रिड लाइन्स सिंक फिक्स]: समरी मैट्रिक्स की प्रत्येक आंतरिक कतार के बीच डार्क ग्रिड बॉर्डर लॉक
            t_summary.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1.2, NAVY_THEME), 
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F0F5FA")), 
                ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#E8F5E9")), # Received रो हल्का हरा बैकग्राउंड
                ('BACKGROUND', (0,2), (-1,2), colors.HexColor("#FFEBEE")), # Used रो हल्का लाल बैकग्राउंड
                ('BACKGROUND', (0,3), (-1,3), colors.HexColor("#E3F2FD")), # Balance रो हल्का नीला बैकग्राउंड
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), 
                ('ALIGN', (0,0), (-1,-1), 'CENTER'), 
                ('TOPPADDING', (0,0), (-1,-1), 5), 
                ('BOTTOMPADDING', (0,0), (-1,-1), 5)
            ]))
            pdf_story.append(t_summary); pdf_story.append(Spacer(1, 15))
            
            # 📜 निचली दिनांकवार लेज़र तालिका
            reg_headers = [Paragraph("<b>TX TYPE</b>", th_style), Paragraph("<b>REC DATE</b>", th_style), Paragraph("<b>OPENING BAL</b>", th_style), Paragraph("<b>AMT RECEIVED</b>", th_style), Paragraph("<b>TOTAL BAL</b>", th_style), Paragraph("<b>EXP DATE</b>", th_style), Paragraph("<b>EXPENDITURE</b>", th_style), Paragraph("<b>CHEQUE NO</b>", th_style), Paragraph("<b>FINAL BALANCE</b>", th_style)]
            reg_table_rows = [reg_headers]
            
            for idx, r in filtered_df.iterrows():
                reg_table_rows.append([
                    Paragraph(str(r.get('Transaction Type','')), td_norm), Paragraph(str(r.get('Received Date','')), td_norm),
                    Paragraph(f"{float(r.get('Opening Balance',0)):.2f}", td_norm), Paragraph(f"+{float(r.get('Amount Received',0)):.2f}", td_bold),
                    Paragraph(f"{float(r.get('Total Balance',0)):.2f}", td_norm), Paragraph(str(r.get('Expenditure Date','')), td_norm),
                    Paragraph(f"-{float(r.get('Expenditure Amount',0)):.2f}", td_bold), Paragraph(str(r.get('Cheque No','')), td_norm),
                    Paragraph(f"<b>{float(r.get('Final Balance',0)):.2f}</b>", td_bold)
                ])
                
            w_tx, w_dt, w_box = 130, 75, 85
            t_register = Table(reg_table_rows, colWidths=[130, 75, 80, 85, 85, 75, 85, 85, 110], repeatRows=1)
            t_style_rules = [('GRID', (0,0), (-1,-1), 0.8, colors.HexColor("#595959")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BACKGROUND', (0,0), (-1,0), NAVY_THEME), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]
            for i in range(1, len(reg_table_rows)):
                if i % 2 == 0: t_style_rules.append(('BACKGROUND', (0, i), (-1, i), LIGHT_BLUE))
            t_register.setStyle(TableStyle(t_style_rules))
            pdf_story.append(t_register); pdf_story.append(Spacer(1, 45))
            
            w_sig_panel = 390
            t_sig = Table([[Paragraph("________________________", td_bold), Paragraph("________________________", td_bold)], [Paragraph("MDM IN-CHARGE SIGNATURE", td_bold), Paragraph("HEADMASTER SEAL & SIGNATURE", td_bold)]], colWidths=[w_sig_panel, w_sig_panel])
            t_sig.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0, colors.white), ('VALIGN', (0,0), (-1,-1), 'BOTTOM'), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 10)]))
            pdf_story.append(t_sig)
            
            def draw_ledger_decorations(canvas, document):
                canvas.saveState()
                if os.path.exists(get_exe_safe_path("basic.png")):
                    canvas.drawImage(get_exe_safe_path("basic.png"), 25, 520, width=52, height=52, mask='auto')
                logo_p = get_exe_safe_path('logo.png')
                if os.path.exists(logo_p):
                    canvas.drawImage(logo_p, 765, 520, width=52, height=52, mask='auto')
                    canvas.saveState()
                    canvas.setFillAlpha(0.06)
                    canvas.drawImage(logo_p, 296, 145, width=250, height=250, mask='auto')
                    canvas.restoreState()
                canvas.restoreState()
                
            doc_pdf.build(pdf_story, onFirstPage=draw_ledger_decorations)
            self.popup('Report Hub', f"MDM Financial Passbook Report Compiled Successfully!\nSaved: {out_pdf_name}")
            open_file_cross_platform(out_pdf_name)
        except Exception as ex:
            self.popup('Print Error', f"Ledger PDF Compilation Failed: {str(ex)}")
    
def load_photo_gallery_view(self):
        self.content_area.clear_widgets()
        self.current_view = 'photo_gallery'
        is_mob = (kivy_platform != 'win')
        GALLERY_DIR = 'School_Photo_Gallery'
        GALLERY_DB = 'Photo_Gallery_Database.xlsx'
        os.makedirs(GALLERY_DIR, exist_ok=True)

        hdr = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46) if is_mob else 44, spacing=dp(8), padding=dp(4))
        hdr.add_widget(Label(text='SCHOOL PHOTO GALLERY (<30KB)', font_size=sp(15) if is_mob else 20, bold=True, color=(0.02, 0.35, 0.2, 1)))
        btn_cam = Button(text='CAMERA', size_hint_x=None, width=dp(85), background_color=(0.05, 0.45, 0.7, 1), bold=True, font_size=sp(12))
        btn_gal = Button(text='GALLERY', size_hint_x=None, width=dp(85), background_color=(0.05, 0.55, 0.25, 1), bold=True, font_size=sp(12))
        hdr.add_widget(btn_cam); hdr.add_widget(btn_gal)
        self.content_area.add_widget(hdr)

        def _save_gallery_photo(src_fp):
            if not src_fp or not os.path.exists(src_fp): return
            import random
            fname = f"Gallery_{datetime.now().strftime('%Y%m%d')}_{random.randint(100,999)}.jpg"
            dest_p = os.path.abspath(os.path.join(GALLERY_DIR, fname))
            comp_p = compress_image_under_30kb(src_fp, dest_p, max_kb=28)

            pl = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))
            pl.add_widget(Label(text='Enter Photo Title / Event Name:', bold=True, color=(1,1,1,1), font_size=sp(14)))
            cap_in = CustomText(hint_text='e.g. Annual Function 2026', multiline=False, size_hint_y=None, height=dp(42))
            pl.add_widget(cap_in)
            btn_ok = Button(text='SAVE TO GALLERY', background_color=(0.05, 0.55, 0.25, 1), bold=True, size_hint_y=None, height=dp(42))
            pl.add_widget(btn_ok)
            pop = Popup(title='Photo Caption', content=pl, size_hint=(0.90, 0.38) if is_mob else (0.45, 0.35), background='', background_color=(0.14, 0.14, 0.14, 0.98))

            def _commit_gal(x):
                title_t = cap_in.text.strip().upper() or 'SCHOOL EVENT'
                df_n = pd.DataFrame([{'Date': datetime.now().strftime('%d-%m-%Y'), 'Title': title_t, 'Path': comp_p}])
                if not os.path.exists(GALLERY_DB):
                    df_n.to_excel(GALLERY_DB, index=False)
                else:
                    pd.concat([pd.read_excel(GALLERY_DB, dtype=str), df_n], ignore_index=True).to_excel(GALLERY_DB, index=False)
                pop.dismiss()
                self.popup('Saved', 'Compressed Photo (<30KB) added to Gallery!')
                self.load_photo_gallery_view()

            btn_ok.bind(on_press=_commit_gal)
            pop.open()

        def _cam_gal(x):
            import random
            tmp_p = os.path.abspath(os.path.join(GALLERY_DIR, f"tmp_{random.randint(1000,9999)}.jpg"))
            if kivy_platform == 'win':
                select_file_cross_platform("Select Photo", [("Images", "*.png *.jpg *.jpeg")], _save_gallery_photo)
            else:
                capture_mobile_camera_safe(tmp_p, _save_gallery_photo, self.popup)

        btn_cam.bind(on_press=_cam_gal)
        btn_gal.bind(on_press=lambda x: select_file_cross_platform("Select Photo", [("Images", "*.png *.jpg *.jpeg")], _save_gallery_photo))

        sc = ScrollView(do_scroll_x=False, do_scroll_y=True)
        grid = GridLayout(cols=2 if is_mob else 4, spacing=dp(10), padding=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        from kivy.uix.behaviors import ButtonBehavior
        class GalImg(ButtonBehavior, Image): pass

        def _zoom_gal_img(p, t):
            box = BoxLayout(orientation='vertical', padding=10, spacing=10)
            box.add_widget(Image(source=p, allow_stretch=True, keep_ratio=True, size_hint=(1, 0.88)))
            bc = Button(text='CLOSE', size_hint=(1, 0.12), background_color=(0.75, 0.15, 0.15, 1), bold=True)
            box.add_widget(bc)
            pp = Popup(title=t, content=box, size_hint=(0.94, 0.82) if is_mob else (0.8, 0.82))
            bc.bind(on_press=pp.dismiss); pp.open()

        items = []
        if os.path.exists(GALLERY_DB):
            try:
                df_g = pd.read_excel(GALLERY_DB, dtype=str)
                items = [dict(r) for _, r in df_g.iterrows()]
            except Exception: pass

        if not items:
            grid.add_widget(Label(text='No photos uploaded yet. Tap CAMERA or GALLERY above.', color=(0.2, 0.2, 0.2, 1), size_hint_y=None, height=dp(60)))
        else:
            for it in reversed(items):
                p_img = str(it.get('Path', '')).strip()
                t_img = str(it.get('Title', 'PHOTO')).strip()
                d_img = str(it.get('Date', '')).strip()
                if os.path.exists(p_img):
                    card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(175), padding=4, spacing=3)
                    with card.canvas.before:
                        Color(1, 1, 1, 1)
                        card.bg = Rectangle(size=card.size, pos=card.pos)
                    card.bind(size=lambda ins, val: setattr(ins.bg, 'size', ins.size), pos=lambda ins, val: setattr(ins.bg, 'pos', ins.pos))
                    im = GalImg(source=p_img, allow_stretch=True, keep_ratio=False, size_hint=(1, 0.76))
                    im.bind(on_release=lambda x, fp=p_img, ft=t_img: _zoom_gal_img(fp, ft))
                    card.add_widget(im)
                    lbl_t = Label(text=f"{t_img}\n({d_img})", color=(0, 0.2, 0.4, 1), font_size=sp(11), bold=True, halign='center', size_hint=(1, 0.24))
                    lbl_t.bind(size=lbl_t.setter('text_size'))
                    card.add_widget(lbl_t)
                    grid.add_widget(card)

        sc.add_widget(grid)
        self.content_area.add_widget(sc)

    def open_google_drive_sync_popup(self):
        is_mob = (kivy_platform != 'win')
        CFG_FILE = 'Drive_Sync_Config.txt'
        saved_url = open(CFG_FILE, 'r').read().strip() if os.path.exists(CFG_FILE) else ''

        pl = BoxLayout(orientation='vertical', padding=dp(14) if is_mob else 18, spacing=dp(10))
        lbl = Label(text='Centralized School Data Sync (Google Drive Web App URL):\nAll teachers using the same Drive URL share live school data.', color=(1,1,1,1), font_size=sp(12.5) if is_mob else 13, size_hint_y=None, height=dp(55))
        lbl.bind(size=lambda ins, val: setattr(ins, 'text_size', (ins.width - dp(8), None)))
        pl.add_widget(lbl)

        in_url = CustomText(text=saved_url, hint_text='Paste Google Apps Script Web App URL here...', multiline=False, size_hint_y=None, height=dp(44))
        pl.add_widget(in_url)

        btn_push = Button(text='1. UPLOAD / BACKUP DATA TO GOOGLE DRIVE', background_color=(0.05, 0.55, 0.25, 1), bold=True, font_size=sp(13), size_hint_y=None, height=dp(44))
        btn_pull = Button(text='2. DOWNLOAD / SYNC DATA FROM GOOGLE DRIVE', background_color=(0.08, 0.42, 0.78, 1), bold=True, font_size=sp(13), size_hint_y=None, height=dp(44))
        btn_cls = Button(text='CLOSE', background_color=(0.75, 0.15, 0.15, 1), bold=True, font_size=sp(13), size_hint_y=None, height=dp(42))
        pl.add_widget(btn_push); pl.add_widget(btn_pull); pl.add_widget(btn_cls)

        pop = Popup(title='Google Drive Centralized Database Sync', content=pl, size_hint=(0.94, 0.65) if is_mob else (0.52, 0.55), background='', background_color=(0.14, 0.14, 0.14, 0.98))
        btn_cls.bind(on_press=pop.dismiss)

        db_files = ['Student_Database.xlsx', 'Marks_Database.xlsx', 'Attendance_Database.xlsx', 'DBT_Database.xlsx', 'MDM_Database.xlsx', 'MDM_Account_Database.xlsx', 'MDM_Ration_Stock_Database.xlsx', 'Staff_Database.xlsx', 'SMC_Members_Database.xlsx', 'Cook_Members_Database.xlsx', 'School_Grant_Database.xlsx', 'TC_Database.xlsx', 'Bulletin_Database.xlsx', 'Users_Database.xlsx', 'Photo_Gallery_Database.xlsx']

        def _push_drive(x):
            url = in_url.text.strip()
            if not url.startswith('http'):
                self.popup('URL Required', 'Please paste your valid Google Drive Apps Script Web App URL first!'); return
            open(CFG_FILE, 'w').write(url)
            try:
                import base64, json, urllib.request
                payload = {'action': 'upload', 'files': {}}
                for f in db_files:
                    if os.path.exists(f):
                        with open(f, 'rb') as fp:
                            payload['files'][f] = base64.b64encode(fp.read()).decode('utf-8')
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
                urllib.request.urlopen(req, timeout=15)
                pop.dismiss()
                self.popup('Drive Backup Complete', f"{len(payload['files'])} Database files uploaded to Google Drive!")
            except Exception as ex:
                self.popup('Sync Error', f'Drive Upload Failed: {str(ex)}')

        def _pull_drive(x):
            url = in_url.text.strip()
            if not url.startswith('http'):
                self.popup('URL Required', 'Please paste your valid Google Drive Apps Script Web App URL first!'); return
            open(CFG_FILE, 'w').write(url)
            try:
                import base64, json, urllib.request
                req = urllib.request.Request(url, data=json.dumps({'action': 'download'}).encode('utf-8'), headers={'Content-Type': 'application/json'})
                resp = json.loads(urllib.request.urlopen(req, timeout=15).read().decode('utf-8'))
                files_map = resp.get('files', {})
                for fname, b64_data in files_map.items():
                    with open(fname, 'wb') as fp:
                        fp.write(base64.b64decode(b64_data))
                pop.dismiss()
                self.popup('Drive Sync Complete', f"{len(files_map)} Database files synced from Google Drive!")
            except Exception as ex:
                self.popup('Sync Error', f'Drive Download Failed: {str(ex)}')

        btn_push.bind(on_press=_push_drive)
        btn_pull.bind(on_press=_pull_drive)
        pop.open()


class SplashLoadingScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        is_mob = (kivy_platform != 'win')
        root = BoxLayout(orientation='vertical', padding=dp(24) if is_mob else 40, spacing=dp(16) if is_mob else 20)
        with root.canvas.before:
            Color(0.01, 0.28, 0.12, 1)
            self.bg_rect = Rectangle(size=Window.size, pos=root.pos)
        root.bind(size=lambda ins, val: setattr(self.bg_rect, 'size', ins.size), pos=lambda ins, val: setattr(self.bg_rect, 'pos', ins.pos))

        root.add_widget(BoxLayout(size_hint_y=0.18))

        logo_p = get_exe_safe_path('logo.png')
        if os.path.exists(logo_p):
            root.add_widget(Image(source=logo_p, size_hint=(None, None), size=(dp(135), dp(135)) if is_mob else (150, 150), pos_hint={'center_x': 0.5}))

        lbl_title = Label(text='PRIMARY SCHOOL PANAUTA', font_size=sp(22) if is_mob else 28, bold=True, color=(1, 0.9, 0, 1), size_hint_y=None, height=dp(36) if is_mob else 40, halign='center')
        lbl_sub = Label(text='UDISE: 09191204201  |  Wazirganj, Budaun', font_size=sp(14) if is_mob else 16, bold=True, color=(0.9, 1, 0.9, 1), size_hint_y=None, height=dp(26) if is_mob else 30, halign='center')
        root.add_widget(lbl_title)
        root.add_widget(lbl_sub)

        boxes_row = BoxLayout(orientation='horizontal', spacing=dp(10) if is_mob else 12, size_hint=(None, None), size=(dp(190), dp(28)) if is_mob else (220, 32), pos_hint={'center_x': 0.5})
        self.load_boxes = []
        for _ in range(5):
            b = Button(text='', disabled=True, background_disabled_normal='', background_color=(0.15, 0.55, 0.3, 1))
            boxes_row.add_widget(b)
            self.load_boxes.append(b)
        root.add_widget(boxes_row)

        from kivy.uix.progressbar import ProgressBar
        self.pbar = ProgressBar(max=100, value=10, size_hint=(0.82, None) if is_mob else (0.5, None), height=dp(14) if is_mob else 16, pos_hint={'center_x': 0.5})
        root.add_widget(self.pbar)

        self.status_lbl = Label(text='Loading School ERP System... 10%', font_size=sp(13.5) if is_mob else 14, bold=True, color=(1, 1, 1, 1), size_hint_y=None, height=dp(28) if is_mob else 30, halign='center')
        root.add_widget(self.status_lbl)
        root.add_widget(BoxLayout(size_hint_y=0.22))

        self.add_widget(root)
        self.step = 0
        Clock.schedule_interval(self._animate_loading, 0.18)

    def _animate_loading(self, dt):
        self.step += 1
        active_idx = (self.step - 1) % len(self.load_boxes)
        for i, box in enumerate(self.load_boxes):
            box.background_color = (1, 0.85, 0, 1) if i == active_idx else (0.15, 0.55, 0.3, 1)

        if self.step == 2:
            self.pbar.value = 40
            self.status_lbl.text = 'Preparing Student & Staff Modules... 40%'
            if not self.manager.has_screen('login'):
                self.manager.add_widget(LoginScreen(name='login'))
        elif self.step == 4:
            self.pbar.value = 75
            self.status_lbl.text = 'Loading Attendance, MDM & Reports... 75%'
            if not self.manager.has_screen('dashboard'):
                self.manager.add_widget(DashboardScreen(name='dashboard'))
        elif self.step >= 6:
            self.pbar.value = 100
            self.status_lbl.text = 'Ready! Opening Login Screen... 100%'
            Clock.unschedule(self._animate_loading)
            Clock.schedule_once(lambda d: setattr(self.manager, 'current', 'login'), 0.2)


class SchoolERPApp(App):
    def build(self):
        self.icon = get_exe_safe_path('logo.png')
        Window.bind(on_key_down=self.universal_keyboard_navigation_handler)
        
        sm = ScreenManager()
        sm.add_widget(SplashLoadingScreen(name='splash'))
        return sm

    def universal_keyboard_navigation_handler(self, window, key, scancode, codepoint, modifiers):
        from kivy.uix.textinput import TextInput
        from kivy.uix.spinner import Spinner
        from kivy.uix.button import Button
        from kivy.uix.scrollview import ScrollView
        
        current_focus = window.focus
        if not current_focus or isinstance(current_focus, bool):
            if hasattr(self, 'current_keyboard_active_widget') and self.current_keyboard_active_widget:
                current_focus = self.current_keyboard_active_widget
            else:
                return False
                
        if not hasattr(current_focus, 'parent') or not current_focus.parent:
            return False
            
        parent_layout = current_focus.parent
        if isinstance(parent_layout, ScrollView) and hasattr(parent_layout, 'children'):
            if parent_layout.children:
                parent_layout = parent_layout.children[0]
        elif hasattr(parent_layout, 'parent') and isinstance(parent_layout.parent, ScrollView):
            if parent_layout.parent.children:
                parent_layout = parent_layout.parent.children[0]
                
        if not hasattr(parent_layout, 'children'):
            return False
            
        all_widgets = []
        for w in parent_layout.children:
            if isinstance(w, (TextInput, Spinner, Button)) or 'CustomText' in str(type(w)) or 'CustomSpinner' in str(type(w)) or 'CustomButton' in str(type(w)):
                all_widgets.append(w)
                
        all_widgets.reverse()
        if current_focus not in all_widgets:
            return False
            
        idx = all_widgets.index(current_focus)
        num_widgets = len(all_widgets)
        
        def switch_focus_to_target(target_widget, current_widget):
            if isinstance(current_widget, Button) or 'Button' in str(type(current_widget)):
                current_widget.state = 'normal'
            if hasattr(current_widget, 'is_open') and current_widget.is_open:
                current_widget.is_open = False
                
            self.current_keyboard_active_widget = target_widget
            if isinstance(target_widget, Spinner) or 'Spinner' in str(type(target_widget)) or 'CustomSpinner' in str(type(target_widget)):
                if hasattr(window, 'focus'): window.focus = None
                target_widget.is_open = True
            elif isinstance(target_widget, Button) or 'Button' in str(type(target_widget)) or 'CustomButton' in str(type(target_widget)):
                if hasattr(window, 'focus'): window.focus = None
                target_widget.state = 'down'
            else:
                self.current_keyboard_active_widget = None
                target_widget.focus = True

        if key == 9 and not modifiers:
            next_idx = (idx + 1) % num_widgets
            switch_focus_to_target(all_widgets[next_idx], current_focus)
            return True
        elif key == 9 and 'shift' in modifiers:
            prev_idx = (idx - 1 + num_widgets) % num_widgets
            switch_focus_to_target(all_widgets[prev_idx], current_focus)
            return True
        elif key == 13:
            if isinstance(current_focus, Button) or 'Button' in str(type(current_focus)) or 'CustomButton' in str(type(current_focus)):
                current_focus.state = 'normal'
                current_focus.trigger_action()
                return True
            elif (isinstance(current_focus, Spinner) or 'Spinner' in str(type(current_focus)) or 'CustomSpinner' in str(type(current_focus))) and getattr(current_focus, 'is_open', False):
                current_focus.is_open = False
                return True
            next_idx = (idx + 1) % num_widgets
            switch_focus_to_target(all_widgets[next_idx], current_focus)
            return True
        elif key in (274, 275):
            if (isinstance(current_focus, Spinner) or 'Spinner' in str(type(current_focus)) or 'CustomSpinner' in str(type(current_focus))) and getattr(current_focus, 'is_open', False):
                return False
            if isinstance(current_focus, TextInput) and current_focus.cursor_index() != len(current_focus.text):
                return False 
            next_idx = (idx + 1) % num_widgets
            switch_focus_to_target(all_widgets[next_idx], current_focus)
            return True
        elif key in (273, 276):
            if (isinstance(current_focus, Spinner) or 'Spinner' in str(type(current_focus)) or 'CustomSpinner' in str(type(current_focus))) and getattr(current_focus, 'is_open', False):
                return False 
            if isinstance(current_focus, TextInput) and current_focus.cursor_index() != 0:
                return False 
            prev_idx = (idx - 1 + num_widgets) % num_widgets
            switch_focus_to_target(all_widgets[prev_idx], current_focus)
            return True
            
        return False

if __name__ == '__main__':
    try:
        SchoolERPApp().run()
    except Exception as master_err:
        import traceback
        err_msg = traceback.format_exc()
        from kivy.app import App
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.label import Label

        class CrashLogApp(App):
            def build(self):
                sv = ScrollView()
                lbl = Label(
                    text=f"APP STARTUP LOG:\n\n{err_msg}",
                    size_hint_y=None,
                    text_size=(800, None),
                    color=(1, 0.3, 0.3, 1)
                )
                lbl.bind(texture_size=lbl.setter('size'))
                sv.add_widget(lbl)
                return sv

        CrashLogApp().run()

