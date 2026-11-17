import sys
import os
import re
import base64
from bs4 import BeautifulSoup
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QTextEdit, QLabel, QPushButton, QHeaderView, QMessageBox, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont

# --- Google API Kütüphaneleri ---
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['']

# --- ANOMALİ TESPİT MOTORU ---
class AnomalyDetector:
    def __init__(self):
        self.suspicious_keywords = {
            "acil": 2, "askıya alındı": 3, "hesabınız": 1, "kazandınız": 3,
            "bedava": 2, "tıkla": 1, "ödül": 2, "şifre": 2, "doğrula": 2,
            "suspended": 3, "verify": 2, "urgent": 2, "winner": 3, "click here": 2
        }
        self.suspicious_links = ["bit.ly", "tinyurl", "goo.gl", "t.co", "ow.ly"]

    def analyze_email(self, subject, sender, body):
        score = 0
        reasons = []
        subject_lower = subject.lower()
        body_lower = body.lower()

        for word, points in self.suspicious_keywords.items():
            if word in subject_lower or word in body_lower:
                score += points
                reasons.append(f"Şüpheli kelime: '{word}'")

        links = re.findall(r'(https?://[^\s]+)', body)
        for link in links:
            for sus_link in self.suspicious_links:
                if sus_link in link:
                    score += 3
                    reasons.append(f"Kısaltılmış şüpheli link: {link}")
        
        if re.search(r'\.(xyz|top|club|online|tk)$', sender.lower()):
            score += 3
            reasons.append("Şüpheli gönderici uzantısı")

        is_anomaly = score >= 3
        return is_anomaly, score, reasons

# --- GMAIL VERİ ÇEKME THREAD'İ ---
class GmailFetcherThread(QThread):
    data_fetched = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            creds = None
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists('credentials.json'):
                        self.error_occurred.emit("HATA: 'credentials.json' dosyası bulunamadı!")
                        return
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())

            service = build('gmail', 'v1', credentials=creds)
            results = service.users().messages().list(userId='me', maxResults=20).execute()
            messages = results.get('messages', [])

            detector = AnomalyDetector()
            email_data_list = []

            for msg in messages:
                msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
                payload = msg_data['payload']
                headers = payload.get('headers', [])

                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "Konu Yok")
                sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Bilinmeyen Gönderici")
                date = next((h['value'] for h in headers if h['name'].lower() == 'date'), "Tarih Yok")
                snippet = msg_data.get('snippet', '')

                body = ""
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part['mimeType'] in ['text/plain', 'text/html'] and 'data' in part['body']:
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                            break
                elif 'body' in payload and 'data' in payload['body']:
                    body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')

                if body:
                    soup = BeautifulSoup(body, "html.parser")
                    body_text = soup.get_text(separator=' ')
                else:
                    body_text = snippet

                is_anomaly, score, reasons = detector.analyze_email(subject, sender, body_text)
                
                email_data_list.append({
                    'sender': sender, 'subject': subject, 'date': date,
                    'is_anomaly': is_anomaly, 'score': score, 'reasons': reasons, 'snippet': snippet
                })

            self.data_fetched.emit(email_data_list)

        except Exception as e:
            self.error_occurred.emit(f"Bağlantı Hatası: {str(e)}")

# --- CYBERPUNK ARAYÜZ (GUI) ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NEON SENTINEL // Gmail Anomali Dedektörü")
        self.setGeometry(100, 100, 1200, 750)
        
        # Cyberpunk Renk Paleti
        self.bg_color = "#0a0a0f"       # Derin siyah/mor arka plan
        self.panel_color = "#12121a"    # Panel arka planı
        self.neon_pink = "#ff0055"      # Anomali Rengi
        self.neon_cyan = "#00f0ff"      # Ana Metin/Çizgi Rengi
        self.neon_yellow = "#fcee0a"    # Vurgu Rengi
        self.text_color = "#e0e0e0"

        self.setStyleSheet(f"background-color: {self.bg_color}; color: {self.text_color}; font-family: 'Consolas', 'Courier New', monospace;")
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # --- SOL PANEL ---
        left_layout = QVBoxLayout()
        
        # Başlık
        title_label = QLabel("> SYS.MAIL_SCAN_ACTIVE")
        title_label.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {self.neon_cyan}; border-bottom: 2px solid {self.neon_cyan}; padding-bottom: 5px;")
        
        # Glow Efekti Başlık
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(15)
        glow.setColor(QColor(self.neon_cyan))
        glow.setOffset(0, 0)
        title_label.setGraphicsEffect(glow)
        left_layout.addWidget(title_label)

        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["KAYNAK", "VERİ_PAKETİ (KONU)", "ZAMAN", "DURUM"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet(f"""
            QTableWidget {{ 
                background-color: {self.panel_color}; 
                border: 1px solid {self.neon_cyan}; 
                gridline-color: #333; 
                color: {self.text_color};
            }}
            QHeaderView::section {{ 
                background-color: #000; 
                color: {self.neon_yellow}; 
                border: 1px solid {self.neon_cyan};
                font-weight: bold;
                padding: 5px;
            }}
            QTableWidget::item {{ padding: 5px; border-bottom: 1px solid #222; }}
            QTableWidget::item:selected {{ background-color: rgba(0, 240, 255, 0.2); color: white; }}
        """)
        self.table.itemSelectionChanged.connect(self.show_details)
        left_layout.addWidget(self.table)

        # Buton
        self.scan_btn = QPushButton(">> SİSTEMİ TARA <<")
        self.scan_btn.setStyleSheet(f"""
            QPushButton {{ 
                background-color: transparent; 
                color: {self.neon_cyan}; 
                font-weight: bold; 
                font-size: 14px;
                padding: 12px; 
                border: 2px solid {self.neon_cyan}; 
                border-radius: 0px;
            }}
            QPushButton:hover {{ 
                background-color: {self.neon_cyan}; 
                color: #000; 
            }}
            QPushButton:disabled {{ 
                border-color: #555; 
                color: #555; 
            }}
        """)
        self.scan_btn.clicked.connect(self.start_scan)
        left_layout.addWidget(self.scan_btn)

        # --- SAĞ PANEL ---
        right_layout = QVBoxLayout()
        
        detail_title = QLabel("> DATA_INSPECTOR")
        detail_title.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        detail_title.setStyleSheet(f"color: {self.neon_pink}; border-bottom: 2px solid {self.neon_pink}; padding-bottom: 5px;")
        
        glow2 = QGraphicsDropShadowEffect()
        glow2.setBlurRadius(15)
        glow2.setColor(QColor(self.neon_pink))
        glow2.setOffset(0, 0)
        detail_title.setGraphicsEffect(glow2)
        right_layout.addWidget(detail_title)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet(f"""
            background-color: {self.panel_color}; 
            border: 1px solid {self.neon_pink}; 
            font-size: 14px; 
            padding: 15px;
            color: {self.text_color};
        """)
        right_layout.addWidget(self.detail_text)

        main_layout.addLayout(left_layout, 65)
        main_layout.addLayout(right_layout, 35)

    def start_scan(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(">> TARANIYOR...")
        self.table.setRowCount(0)
        self.detail_text.setHtml(f"<span style='color:{self.neon_yellow}'>Sistem taranıyor, lütfen bekleyin...</span>")

        self.thread = GmailFetcherThread()
        self.thread.data_fetched.connect(self.populate_table)
        self.thread.error_occurred.connect(self.show_error)
        self.thread.finished.connect(self.scan_finished)
        self.thread.start()

    def populate_table(self, emails):
        self.table.setRowCount(len(emails))
        for row, email in enumerate(emails):
            self.table.setItem(row, 0, QTableWidgetItem(email['sender']))
            self.table.setItem(row, 1, QTableWidgetItem(email['subject']))
            self.table.setItem(row, 2, QTableWidgetItem(email['date']))
            
            status_item = QTableWidgetItem("!! ANOMALİ !!" if email['is_anomaly'] else "TEMİZ")
            if email['is_anomaly']:
                status_item.setForeground(QColor(self.neon_pink))
                status_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            else:
                status_item.setForeground(QColor("#00ff00"))
            
            self.table.setItem(row, 3, status_item)
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, email)

    def show_details(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
        
        row = selected_items[0].row()
        email_data = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

        # Cyberpunk HTML Raporu
        report = f"<div style='font-family: Consolas;'>"
        report += f"<p style='color:{self.neon_cyan}'><b>[KAYNAK]</b> {email_data['sender']}</p>"
        report += f"<p style='color:{self.neon_cyan}'><b>[KONU]</b> {email_data['subject']}</p>"
        report += f"<p style='color:{self.neon_cyan}'><b>[ZAMAN]</b> {email_data['date']}</p>"
        report += f"<p style='color:#888;'><b>[ÖZET]</b> {email_data['snippet']}</p>"
        report += "<hr style='border: 1px solid #333;'>"
        
        if email_data['is_anomaly']:
            report += f"<h2 style='color: {self.neon_pink}; text-shadow: 0 0 10px {self.neon_pink};'>[!!] TEHDİT ALGILANDI [!!]</h2>"
            report += f"<p style='color: {self.neon_yellow};'>TEHDİT SEVİYESİ: {email_data['score']}</p>"
            report += f"<p style='color: {self.neon_pink};'><b>ANALİZ DETAYLARI:</b></p><ul>"
            for reason in email_data['reasons']:
                report += f"<li style='color: #ff8888;'>{reason}</li>"
            report += "</ul>"
        else:
            report += f"<h2 style='color: #00ff00;'>[OK] GÜVENLİ PAKET</h2>"
            report += f"<p style='color: #00ff00;'>TEHDİT SEVİYESİ: {email_data['score']}</p>"
            if email_data['reasons']:
                report += f"<p style='color: {self.neon_yellow};'><b>UYARILAR:</b></p><ul>"
                for reason in email_data['reasons']:
                    report += f"<li style='color: {self.neon_yellow};'>{reason}</li>"
                report += "</ul>"
        
        report += "</div>"
        self.detail_text.setHtml(report)

    def show_error(self, error_msg):
        QMessageBox.critical(self, "SİSTEM HATASI", f"<span style='color:red'>{error_msg}</span>")
        self.scan_finished()

    def scan_finished(self):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(">> SİSTEMİ TARA <<")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
