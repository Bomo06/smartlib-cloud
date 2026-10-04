import os
import io
import csv
import base64
from urllib.parse import quote
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)
app.secret_key = "smart_cloud_library_bomo_secret_key"

# Cloud DB Configuration (Neon PostgreSQL)
db_url = "postgresql://neondb_owner:npg_lg85vUsoYVGi@ep-dawn-mouse-b5zf4euu-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ----------------- DATABASE MODELS -----------------

class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    upi_id = db.Column(db.String(100), default="mohamedtharik@okaxis")
    upi_payee_name = db.Column(db.String(100), default="SmartLib College Library")
    custom_qr_base64 = db.Column(db.Text, nullable=True)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(150), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    tags = db.Column(db.String(200), nullable=False)
    total_copies = db.Column(db.Integer, default=3)
    available_copies = db.Column(db.Integer, default=3)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(30), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    student_phone = db.Column(db.String(20), default="9876543210")
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, default=datetime.utcnow)
    return_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default="Issued")

    book = db.relationship('Book', backref=db.backref('transactions', lazy=True))

    @property
    def overdue_days(self):
        end_time = self.return_date if self.return_date else datetime.utcnow()
        if end_time > self.due_date:
            return max(0, (end_time - self.due_date).days)
        return 0

    @property
    def days_remaining(self):
        if self.status == "Issued" and datetime.utcnow() <= self.due_date:
            return max(0, (self.due_date - datetime.utcnow()).days)
        return 0

    @property
    def current_fine(self):
        return self.overdue_days * 10

    @property
    def clean_phone(self):
        digits = "".join(ch for ch in (self.student_phone or "") if ch.isdigit())
        if len(digits) == 10:
            return "91" + digits
        elif len(digits) == 12 and digits.startswith("91"):
            return digits
        return digits

    @property
    def whatsapp_direct_url(self):
        if self.overdue_days > 0:
            msg = (
                f"📚 *SMARTLIB COLLEGE LIBRARY - OVERDUE NOTICE*\n\n"
                f"Hello *{self.student_name}* (Reg No: {self.student_id}),\n"
                f"Your 14-day borrowing period for the book *'{self.book.title}'* ({self.book.book_code}) expired on *{self.due_date.strftime('%d %b %Y')}*.\n\n"
                f"⚠️ *Overdue Days:* {self.overdue_days} Days\n"
                f"💳 *Pending Fine:* Rs. {self.current_fine} (@ Rs.10/day)\n\n"
                f"Please return the book or renew it online via the SmartLib Student Portal immediately."
            )
        else:
            msg = (
                f"📚 *SMARTLIB COLLEGE LIBRARY - DUE DATE REMINDER*\n\n"
                f"Hello *{self.student_name}* (Reg No: {self.student_id}),\n"
                f"Friendly reminder that your borrowed book *'{self.book.title}'* ({self.book.book_code}) is due on *{self.due_date.strftime('%d %b %Y')}* ({self.days_remaining} days remaining).\n\n"
                f"If you need extra time, you can use the +7 Days Self-Renewal option on the Student Portal."
            )
        phone_target = self.clean_phone
        if phone_target:
            return f"https://wa.me/{phone_target}?text={quote(msg)}"
        return f"https://wa.me/?text={quote(msg)}"

# ----------------- AUTO-MIGRATION & INITIAL SEED -----------------

def init_and_migrate_db():
    db.create_all()
    try:
        db.session.execute(text("ALTER TABLE transaction ADD COLUMN IF NOT EXISTS student_phone VARCHAR(20) DEFAULT '9876543210';"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    if SystemConfig.query.count() == 0:
        cfg = SystemConfig(upi_id="mohamedtharik@okaxis", upi_payee_name="SmartLib College Library")
        db.session.add(cfg)
        db.session.commit()

    if Book.query.count() == 0:
        sample_books = [
            Book(book_code="LIB-AI101", title="Hands-On Machine Learning", author="Aurelien Geron", category="AI & Data Science", tags="ai, ml, python, deep learning, neural networks", total_copies=5, available_copies=4),
            Book(book_code="LIB-AI102", title="Deep Learning with Python", author="Francois Chollet", category="AI & Data Science", tags="ai, deep learning, keras, neural networks", total_copies=3, available_copies=3),
            Book(book_code="LIB-CS201", title="Clean Code", author="Robert C. Martin", category="Software Engineering", tags="coding, software, architecture, programming", total_copies=4, available_copies=4),
            Book(book_code="LIB-CL301", title="Cloud Computing: Concepts, Technology & Architecture", author="Thomas Erl", category="Cloud Computing", tags="cloud, aws, distributed, microservices", total_copies=4, available_copies=3),
            Book(book_code="LIB-NW401", title="Computer Networking: A Top-Down Approach", author="James Kurose", category="Networking", tags="networks, tcp, udp, protocols, internet", total_copies=3, available_copies=3),
            Book(book_code="LIB-DS501", title="Python for Data Analysis", author="Wes McKinney", category="AI & Data Science", tags="pandas, data science, python, analytics", total_copies=5, available_copies=5),
        ]
        db.session.add_all(sample_books)
        db.session.commit()

        t1 = Transaction(
            student_id="730224243014",
            student_name="T. Mohammed Tharik",
            student_phone="9876543210",
            book_id=1,
            issue_date=datetime.utcnow() - timedelta(days=5),
            due_date=datetime.utcnow() + timedelta(days=9),
            status="Issued"
        )
        t2 = Transaction(
            student_id="26AIDS15",
            student_name="Karthik Raja",
            student_phone="9876543210",
            book_id=4,
            issue_date=datetime.utcnow() - timedelta(days=18),
            due_date=datetime.utcnow() - timedelta(days=4),
            status="Issued"
        )
        db.session.add_all([t1, t2])
        db.session.commit()

def get_ai_recommendations(query_interest):
    if not query_interest:
        return []
    keywords = [k.strip().lower() for k in query_interest.split() if len(k.strip()) > 1]
    all_books = Book.query.all()
    scored_books = []
    for book in all_books:
        score = 0
        text_pool = f"{book.title} {book.category} {book.tags} {book.author}".lower()
        for kw in keywords:
            if kw in text_pool:
                score += 2
        if score > 0:
            scored_books.append((score, book))
    scored_books.sort(key=lambda x: x[0], reverse=True)
    return [b for _, b in scored_books[:4]]

# ----------------- PREMIUM 3D CYBER-AURORA GLASSMORPHISM UI -----------------

PORTAL_HTML = """
<!DOCTYPE html>
<html lang="en" id="htmlRoot" class="theme-aurora">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartLib • Next-Gen Cloud Library System</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Outfit', sans-serif; overflow-x: hidden; transition: all 0.4s ease; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }

        /* THEME 1: CYBER AURORA DARK (DEFAULT) */
        html.theme-aurora body {
            background-color: #060919;
            background-image:
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.28) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(6, 182, 212, 0.25) 0px, transparent 50%),
                radial-gradient(at 50% 100%, rgba(168, 85, 247, 0.22) 0px, transparent 50%),
                linear-gradient(to right, rgba(255,255,255,0.02) 1px, transparent 1px),
                linear-gradient(to bottom, rgba(255,255,255,0.02) 1px, transparent 1px);
            background-size: 100% 100%, 100% 100%, 100% 100%, 40px 40px, 40px 40px;
            color: #F8FAFC;
        }
        html.theme-aurora .glass-panel {
            background: rgba(15, 23, 42, 0.68);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(148, 163, 184, 0.16);
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
        }
        html.theme-aurora .input-cyber {
            background: rgba(9, 13, 28, 0.85);
            border: 1px solid rgba(99, 102, 241, 0.35);
            color: #FFFFFF;
        }
        html.theme-aurora .input-cyber:focus {
            border-color: #38BDF8;
            box-shadow: 0 0 20px rgba(56, 189, 248, 0.25);
        }
        html.theme-aurora .heading-main { color: #FFFFFF; }
        html.theme-aurora .sub-text { color: #94A3B8; }
        html.theme-aurora .table-header { background: rgba(9, 13, 28, 0.9); color: #94A3B8; }
        html.theme-aurora .table-row-hover:hover { background: rgba(56, 189, 248, 0.07); }

        /* THEME 2: ROYAL CRYSTAL DAYLIGHT (SWITCHABLE) */
        html.theme-crystal body {
            background-color: #F0F4FF;
            background-image:
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.18) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(14, 165, 233, 0.18) 0px, transparent 50%),
                linear-gradient(to right, rgba(79, 70, 229, 0.04) 1px, transparent 1px),
                linear-gradient(to bottom, rgba(79, 70, 229, 0.04) 1px, transparent 1px);
            background-size: 100% 100%, 100% 100%, 40px 40px, 40px 40px;
            color: #0F172A;
        }
        html.theme-crystal .glass-panel {
            background: rgba(255, 255, 255, 0.88);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(99, 102, 241, 0.2);
            box-shadow: 0 20px 40px rgba(79, 70, 229, 0.08);
        }
        html.theme-crystal .input-cyber {
            background: #FFFFFF;
            border: 1px solid #CBD5E1;
            color: #0F172A;
        }
        html.theme-crystal .input-cyber:focus {
            border-color: #4F46E5;
            box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.15);
        }
        html.theme-crystal .heading-main { color: #0F172A; }
        html.theme-crystal .sub-text { color: #475569; }
        html.theme-crystal .table-header { background: #EEF2FF; color: #4338CA; }
        html.theme-crystal .table-row-hover:hover { background: rgba(79, 70, 229, 0.05); }

        .card-3d {
            transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease;
        }
        .card-3d:hover {
            transform: translateY(-6px) scale(1.01);
        }
        @keyframes pulseGlow {
            0%, 100% { opacity: 0.5; transform: scale(1); }
            50% { opacity: 0.9; transform: scale(1.08); }
        }
        .aurora-orb { animation: pulseGlow 6s infinite ease-in-out; }
    </style>
</head>
<body class="min-h-screen flex flex-col relative">

    <div class="fixed top-16 left-10 w-72 h-72 bg-indigo-500/20 rounded-full blur-[110px] pointer-events-none aurora-orb"></div>
    <div class="fixed bottom-10 right-10 w-80 h-80 bg-cyan-500/20 rounded-full blur-[120px] pointer-events-none aurora-orb"></div>

    <!-- Top Glassmorphic Command Navbar -->
    <header class="sticky top-0 z-50 bg-slate-950/80 backdrop-blur-2xl border-b border-indigo-500/30 shadow-2xl">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 py-3.5 flex flex-wrap justify-between items-center gap-3">
            <div class="flex items-center space-x-3.5">
                <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 via-violet-500 to-cyan-400 p-[2px] shadow-lg shadow-indigo-500/30">
                    <div class="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center text-2xl">
                        ⚡
                    </div>
                </div>
                <div>
                    <div class="flex items-center gap-2.5">
                        <h1 class="text-lg sm:text-xl font-black tracking-tight bg-gradient-to-r from-white via-cyan-200 to-indigo-300 bg-clip-text text-transparent">
                            SMARTLIB CLOUD AI
                        </h1>
                        <span class="hidden sm:inline-flex items-center gap-1 bg-gradient-to-r from-indigo-500/20 to-cyan-500/20 text-cyan-300 border border-cyan-400/30 text-[11px] font-bold px-2.5 py-0.5 rounded-full">
                            B.Tech AI & DS
                        </span>
                    </div>
                    <p class="text-xs text-slate-400">Next-Gen Cloud Library • Direct WhatsApp Messages • Live QR & Analytics</p>
                </div>
            </div>

            <div class="flex flex-wrap items-center gap-2.5">
                <div class="hidden lg:flex items-center gap-2 text-xs bg-emerald-500/10 text-emerald-300 px-3.5 py-1.5 rounded-full border border-emerald-500/30 font-semibold">
                    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                    <span>Neon PostgreSQL: Live</span>
                </div>

                <button type="button" onclick="toggleTheme()"
                        class="bg-slate-800/90 hover:bg-slate-700 text-cyan-300 border border-cyan-500/30 px-3.5 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-md">
                    <span id="themeIcon">☀️</span>
                    <span id="themeLabel">Crystal Mode</span>
                </button>

                <a href="/" class="px-4 py-2 rounded-xl text-xs font-extrabold transition shadow-lg {% if mode == 'student' %}bg-gradient-to-r from-cyan-400 via-blue-500 to-indigo-600 text-white shadow-cyan-500/25{% else %}bg-slate-900 text-slate-300 border border-slate-700 hover:border-cyan-400{% endif %}">
                    🎓 Student Hub
                </a>
                <a href="/admin" class="px-4 py-2 rounded-xl text-xs font-extrabold transition shadow-lg {% if mode == 'admin' %}bg-gradient-to-r from-fuchsia-500 via-purple-600 to-indigo-600 text-white shadow-purple-500/25{% else %}bg-slate-900 text-slate-300 border border-slate-700 hover:border-purple-400{% endif %}">
                    🔐 Admin Command
                </a>
                {% if mode == 'admin' and session.get('admin_logged_in') %}
                <a href="/logout" class="bg-rose-600 hover:bg-rose-500 text-white px-3.5 py-2 rounded-xl text-xs font-bold shadow-lg shadow-rose-600/30 transition">
                    Logout ({{ session.get('admin_user', 'Bomo') }})
                </a>
                {% endif %}
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto w-full px-4 sm:px-6 py-7 space-y-7 flex-1 relative z-10">

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <div class="space-y-2">
              {% for cat, msg in messages %}
                <div class="p-4 rounded-2xl text-sm font-bold shadow-xl flex items-center justify-between border {% if cat == 'error' %}bg-rose-950/90 border-rose-500 text-rose-200{% else %}bg-emerald-950/90 border-emerald-400 text-emerald-200{% endif %}">
                  <span>{{ msg }}</span>
                </div>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}

        <!-- HERO BANNER WITH LIVE CLOCK -->
        <div class="relative rounded-3xl overflow-hidden p-6 sm:p-8 bg-gradient-to-r from-indigo-950 via-blue-950 to-slate-900 border border-indigo-500/40 shadow-2xl text-white">
            <div class="absolute -right-10 -top-10 w-64 h-64 bg-cyan-500/20 rounded-full blur-3xl pointer-events-none"></div>
            <div class="relative z-10 flex flex-wrap justify-between items-center gap-6">
                <div class="max-w-2xl">
                    <div class="inline-flex items-center gap-2 bg-cyan-400/15 border border-cyan-400/30 text-cyan-300 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider mb-3">
                        <span>🚀 Automated Cloud Library Ecosystem</span>
                    </div>
                    <h2 class="text-2xl sm:text-3xl font-black tracking-tight leading-tight">
                        {% if mode == 'student' %}
                        Smart Book Discovery, Self-Issue & Instant QR Pass
                        {% else %}
                        Librarian Command Center, Live Analytics & Direct WhatsApp Alerts
                        {% endif %}
                    </h2>
                    <p class="text-xs sm:text-sm text-indigo-200 mt-2 leading-relaxed">
                        Powered by Neon Serverless PostgreSQL • Content-Based AI Recommender • 14-Day Due Date Tracker & Direct WhatsApp Student Messaging.
                    </p>
                </div>
                <div class="bg-slate-950/60 backdrop-blur-md border border-white/15 px-5 py-4 rounded-2xl text-right">
                    <p class="text-[11px] uppercase tracking-widest text-cyan-300 font-bold">Live Server Time</p>
                    <p id="liveClock" class="text-xl sm:text-2xl font-mono font-extrabold text-white mt-0.5">--:--:--</p>
                    <p class="text-xs text-slate-400 mt-0.5">Fine Rate: ₹10 / Overdue Day</p>
                </div>
            </div>
        </div>

        <!-- 4 3D NEON GRADIENT KPI CARDS -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
            <div class="card-3d rounded-3xl p-5 bg-gradient-to-br from-indigo-600 via-blue-600 to-blue-800 text-white shadow-xl shadow-indigo-600/25 border border-white/15">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="text-xs font-extrabold uppercase tracking-wider text-blue-100">Total Cloud Books</p>
                        <p class="text-3xl sm:text-4xl font-black mt-2">{{ stats.total_books }}</p>
                    </div>
                    <span class="bg-white/20 backdrop-blur-md p-3 rounded-2xl text-2xl shadow-inner">📚</span>
                </div>
                <div class="mt-3 pt-2 border-t border-white/15 flex justify-between text-[11px] text-blue-100 font-semibold">
                    <span>Catalog Status</span>
                    <span>100% Cloud Synced</span>
                </div>
            </div>

            <div class="card-3d rounded-3xl p-5 bg-gradient-to-br from-emerald-500 via-teal-600 to-emerald-800 text-white shadow-xl shadow-emerald-600/25 border border-white/15">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="text-xs font-extrabold uppercase tracking-wider text-emerald-100">Available Copies</p>
                        <p class="text-3xl sm:text-4xl font-black mt-2">{{ stats.available_books }}</p>
                    </div>
                    <span class="bg-white/20 backdrop-blur-md p-3 rounded-2xl text-2xl shadow-inner">✨</span>
                </div>
                <div class="mt-3 pt-2 border-t border-white/15 flex justify-between text-[11px] text-emerald-100 font-semibold">
                    <span>Ready to Issue</span>
                    <span>Instant QR Pass</span>
                </div>
            </div>

            <div class="card-3d rounded-3xl p-5 bg-gradient-to-br from-violet-600 via-purple-600 to-fuchsia-800 text-white shadow-xl shadow-purple-600/25 border border-white/15">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="text-xs font-extrabold uppercase tracking-wider text-purple-100">Active Borrowed</p>
                        <p class="text-3xl sm:text-4xl font-black mt-2">{{ stats.active_issues }}</p>
                    </div>
                    <span class="bg-white/20 backdrop-blur-md p-3 rounded-2xl text-2xl shadow-inner">🎓</span>
                </div>
                <div class="mt-3 pt-2 border-t border-white/15 flex justify-between text-[11px] text-purple-100 font-semibold">
                    <span>Borrow Window</span>
                    <span>14 Days Period</span>
                </div>
            </div>

            {% if mode == 'admin' %}
            <div class="card-3d rounded-3xl p-5 bg-gradient-to-br from-rose-600 via-pink-600 to-red-800 text-white shadow-xl shadow-rose-600/25 border border-white/15">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="text-xs font-extrabold uppercase tracking-wider text-rose-100">Pending Fines</p>
                        <p class="text-3xl sm:text-4xl font-black mt-2">₹{{ stats.total_fine }}</p>
                    </div>
                    <span class="bg-white/20 backdrop-blur-md p-3 rounded-2xl text-2xl shadow-inner">💳</span>
                </div>
                <div class="mt-3 pt-2 border-t border-white/15 flex justify-between text-[11px] text-rose-100 font-semibold">
                    <span>Overdue Students: {{ stats.overdue_count }}</span>
                    <span>UPI QR Active</span>
                </div>
            </div>
            {% else %}
            <div class="card-3d rounded-3xl p-5 bg-gradient-to-br from-cyan-500 via-sky-600 to-blue-700 text-white shadow-xl shadow-cyan-500/25 border border-white/15">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="text-xs font-extrabold uppercase tracking-wider text-cyan-100">Self Renewal</p>
                        <p class="text-3xl sm:text-4xl font-black mt-2">+7 Days</p>
                    </div>
                    <span class="bg-white/20 backdrop-blur-md p-3 rounded-2xl text-2xl shadow-inner">🔄</span>
                </div>
                <div class="mt-3 pt-2 border-t border-white/15 flex justify-between text-[11px] text-cyan-100 font-semibold">
                    <span>Zero Fine Extension</span>
                    <span>1-Click Online</span>
                </div>
            </div>
            {% endif %}
        </div>

        {% if mode == 'student' %}
        <!-- ================= STUDENT PORTAL VIEW ================= -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <!-- Left 6 Cols: Student Self-Service Book Borrow -->
            <div class="lg:col-span-6 glass-panel rounded-3xl p-6 sm:p-7 relative overflow-hidden">
                <div class="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-cyan-400 via-blue-500 to-indigo-600"></div>
                <div class="flex items-center justify-between pb-4 mb-5 border-b border-slate-500/20">
                    <div>
                        <span class="bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 text-[11px] font-extrabold uppercase px-3 py-1 rounded-full">
                            Instant Self-Issue Desk
                        </span>
                        <h2 class="text-xl font-black heading-main mt-2">📲 Borrow a Library Book</h2>
                    </div>
                    <span class="text-xs font-bold text-emerald-400 bg-emerald-500/15 border border-emerald-500/30 px-3 py-1 rounded-full">
                        Auto 14-Day Due Date
                    </span>
                </div>

                <form method="POST" action="/issue" class="space-y-4">
                    <input type="hidden" name="from_page" value="student">
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label class="text-xs font-bold sub-text block mb-1.5">Register Number *</label>
                            <input type="text" name="student_id" required placeholder="e.g., 730224243014"
                                   class="w-full input-cyber rounded-xl px-4 py-3 text-sm font-mono outline-none">
                        </div>
                        <div>
                            <label class="text-xs font-bold sub-text block mb-1.5">Student Full Name *</label>
                            <input type="text" name="student_name" required placeholder="e.g., T. Mohammed Tharik"
                                   class="w-full input-cyber rounded-xl px-4 py-3 text-sm outline-none">
                        </div>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label class="text-xs font-bold sub-text block mb-1.5">WhatsApp Mobile No (10 Digits) *</label>
                            <input type="tel" name="student_phone" required pattern="[0-9]{10}" maxlength="10" placeholder="e.g., 9876543210"
                                   class="w-full input-cyber rounded-xl px-4 py-3 text-sm font-mono outline-none">
                        </div>
                        <div>
                            <label class="text-xs font-bold sub-text block mb-1.5">Select Available Book *</label>
                            <select name="book_id" required class="w-full input-cyber rounded-xl px-4 py-3 text-sm outline-none">
                                <option value="">-- Choose Book --</option>
                                {% for b in books %}
                                    {% if b.available_copies > 0 %}
                                    <option value="{{ b.id }}">[{{ b.book_code }}] {{ b.title }} ({{ b.available_copies }} left)</option>
                                    {% endif %}
                                {% endfor %}
                            </select>
                        </div>
                    </div>

                    <button type="submit" class="w-full bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white font-black py-3.5 rounded-xl text-sm shadow-xl shadow-blue-600/30 transition transform hover:scale-[1.01]">
                        🚀 Confirm Book Borrow & Assign 14-Day Due Date
                    </button>
                </form>
            </div>

            <!-- Right 6 Cols: Check Due Status, +7d Renew & Original UPI Fine Scanner -->
            <div class="lg:col-span-6 glass-panel rounded-3xl p-6 sm:p-7 relative overflow-hidden flex flex-col justify-between">
                <div class="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-emerald-400 via-teal-500 to-cyan-500"></div>
                <div>
                    <div class="flex items-center justify-between pb-4 mb-5 border-b border-slate-500/20">
                        <div>
                            <span class="bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 text-[11px] font-extrabold uppercase px-3 py-1 rounded-full">
                                Student Account & Fine Desk
                            </span>
                            <h2 class="text-xl font-black heading-main mt-2">🔍 Check Due Date, Renew (+7d) or Pay Fine</h2>
                        </div>
                    </div>

                    <form method="GET" action="/" class="flex gap-2.5 mb-4">
                        <input type="text" name="my_reg" value="{{ my_reg }}" placeholder="Enter Reg No (e.g., 730224243014 or 26AIDS15) or Mobile..."
                               class="flex-1 input-cyber rounded-xl px-4 py-3 text-sm outline-none">
                        <button type="submit" class="bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-extrabold px-6 py-3 rounded-xl text-xs shadow-lg">
                            Search
                        </button>
                        {% if my_reg %}
                        <a href="/" class="bg-slate-700/60 text-slate-200 px-3.5 py-3 rounded-xl text-xs font-bold flex items-center">Clear</a>
                        {% endif %}
                    </form>

                    {% if my_reg %}
                    <div class="space-y-3 max-h-56 overflow-y-auto pr-1">
                        {% for mt in my_transactions %}
                        <div class="p-4 rounded-2xl border border-indigo-500/30 bg-indigo-950/20 flex flex-wrap justify-between items-center gap-3 text-xs">
                            <div>
                                <div class="font-extrabold heading-main text-sm">{{ mt.book.title }}</div>
                                <div class="sub-text mt-0.5">{{ mt.student_name }} (<span class="font-mono">{{ mt.student_id }}</span>) • 📱 {{ mt.student_phone }}</div>
                                <div class="mt-1.5 flex items-center gap-2">
                                    <span>Due Date: <strong class="{% if mt.overdue_days > 0 and mt.status == 'Issued' %}text-rose-400{% else %}text-cyan-400{% endif %}">{{ mt.due_date.strftime('%d %b %Y') }}</strong></span>
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                {% if mt.status == 'Returned' %}
                                    <span class="bg-slate-500/20 sub-text px-3 py-1 rounded-full font-bold">✔ Returned</span>
                                {% else %}
                                    {% if mt.current_fine > 0 %}
                                    <button type="button"
                                            onclick="openUpiModal('{{ mt.id }}','{{ mt.student_name }}','{{ mt.student_id }}','{{ mt.book.title }}','{{ mt.current_fine }}','student')"
                                            class="bg-gradient-to-r from-rose-600 to-pink-600 text-white px-3.5 py-2 rounded-xl font-extrabold shadow-lg">
                                        💳 Pay ₹{{ mt.current_fine }} QR
                                    </button>
                                    {% else %}
                                    <span class="bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-3 py-1 rounded-full font-bold">{{ mt.days_remaining }}d Left</span>
                                    {% endif %}
                                    <form method="POST" action="/renew/{{ mt.id }}">
                                        <input type="hidden" name="from_page" value="student">
                                        <input type="hidden" name="my_reg" value="{{ my_reg }}">
                                        <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold px-3.5 py-2 rounded-xl shadow-lg">
                                            🔄 +7d Renew
                                        </button>
                                    </form>
                                {% endif %}
                            </div>
                        </div>
                        {% else %}
                        <p class="text-xs text-rose-400 font-bold p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20">No borrowing records found for "{{ my_reg }}".</p>
                        {% endfor %}
                    </div>
                    {% else %}
                    <div class="p-4 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-xs sub-text space-y-2">
                        <p class="font-extrabold heading-main">✨ Try Quick Demo Lookup:</p>
                        <p>• Type <strong class="text-cyan-400 font-mono">730224243014</strong> (Active Student) or <strong class="text-rose-400 font-mono">26AIDS15</strong> (Overdue Student with ₹40 Fine QR).</p>
                        <p>• Extend your due date by <strong>+7 Days</strong> online or pay overdue fines using the library UPI QR scanner.</p>
                    </div>
                    {% endif %}
                </div>

                <div class="mt-4 pt-3 border-t border-slate-500/20 flex justify-between items-center text-xs sub-text">
                    <span>Automated 14-Day Due Tracker</span>
                    <a href="/admin" class="text-cyan-400 font-extrabold hover:underline">Librarian Command Center →</a>
                </div>
            </div>
        </div>

        <!-- AI Smart Recommender Banner -->
        <div class="glass-panel rounded-3xl p-6 sm:p-7 relative overflow-hidden border border-indigo-500/40">
            <div class="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-fuchsia-500 via-purple-500 to-indigo-500"></div>
            <div class="flex flex-wrap items-center justify-between gap-2 mb-4">
                <div>
                    <span class="bg-fuchsia-500/15 text-fuchsia-400 border border-fuchsia-500/30 text-[11px] font-extrabold uppercase px-3 py-1 rounded-full">
                        AI Content-Based Recommendation Engine
                    </span>
                    <h2 class="text-xl font-black heading-main mt-2">🤖 Smart Book Recommender & Instant Subject Filter</h2>
                </div>
                <span class="text-xs sub-text">Try keywords: <strong class="text-cyan-400">python ai</strong>, <strong class="text-cyan-400">cloud</strong>, <strong class="text-cyan-400">networks</strong></span>
            </div>
            <form method="GET" action="/" class="flex flex-col sm:flex-row gap-3">
                <input type="text" name="interest" value="{{ interest }}" placeholder="Ask AI: e.g., machine learning python, cloud computing, networking..."
                       class="flex-1 input-cyber rounded-2xl px-5 py-3.5 text-sm font-medium outline-none">
                <button type="submit" class="bg-gradient-to-r from-fuchsia-600 via-purple-600 to-indigo-600 hover:from-fuchsia-500 hover:to-indigo-500 text-white font-black px-8 py-3.5 rounded-2xl text-sm shadow-xl shadow-purple-600/30 transition">
                    ✨ Recommend Books
                </button>
                {% if interest %}
                <a href="/" class="bg-slate-800 text-slate-200 px-5 py-3.5 rounded-2xl text-sm font-bold text-center">Reset</a>
                {% endif %}
            </form>

            {% if recommendations %}
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-5 pt-5 border-t border-slate-500/20">
                {% for r in recommendations %}
                <div class="p-4 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 flex justify-between items-center">
                    <div>
                        <span class="text-xs font-mono font-bold bg-cyan-400/20 text-cyan-300 px-2.5 py-0.5 rounded-md">{{ r.book_code }}</span>
                        <h4 class="font-extrabold text-sm heading-main mt-1.5">{{ r.title }}</h4>
                        <p class="text-xs sub-text">{{ r.author }} • {{ r.category }}</p>
                    </div>
                    <span class="text-xs font-black px-3 py-1 rounded-full bg-emerald-400 text-slate-950">
                        {{ r.available_copies }} Left
                    </span>
                </div>
                {% endfor %}
            </div>
            {% endif %}
        </div>

        <!-- Cloud Book Inventory Table -->
        <div class="glass-panel rounded-3xl overflow-hidden">
            <div class="p-6 border-b border-slate-500/20 flex flex-wrap justify-between items-center gap-4">
                <div>
                    <h3 class="font-black text-lg heading-main">📚 Live Cloud Book Catalog & Dynamic QR Tags</h3>
                    <p class="text-xs sub-text">Scan any book's QR code with your phone camera to verify Book ID and stock</p>
                </div>
                <input type="text" id="catalogSearch" onkeyup="filterCatalog()" placeholder="🔍 Quick Filter Books..."
                       class="input-cyber rounded-xl px-4 py-2 text-xs w-60 outline-none">
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse text-sm">
                    <thead>
                        <tr class="table-header text-xs uppercase tracking-wider">
                            <th class="p-4">Smart QR</th>
                            <th class="p-4">Book Code</th>
                            <th class="p-4">Title & Author</th>
                            <th class="p-4">Department Category</th>
                            <th class="p-4">Availability</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-500/15">
                        {% for b in books %}
                        <tr class="table-row-hover transition catalog-row">
                            <td class="p-4">
                                <img src="https://api.qrserver.com/v1/create-qr-code/?size=60x60&data={{ b.book_code }}-{{ b.title|urlencode }}"
                                     alt="QR" class="w-12 h-12 rounded-xl bg-white p-1 border border-slate-300 shadow-md">
                            </td>
                            <td class="p-4 font-mono text-xs font-extrabold text-cyan-400">{{ b.book_code }}</td>
                            <td class="p-4">
                                <div class="font-extrabold heading-main text-base">{{ b.title }}</div>
                                <div class="text-xs sub-text">{{ b.author }}</div>
                            </td>
                            <td class="p-4">
                                <span class="text-xs font-bold bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 px-3 py-1 rounded-xl">{{ b.category }}</span>
                            </td>
                            <td class="p-4">
                                <span class="px-3.5 py-1.5 rounded-full text-xs font-extrabold {% if b.available_copies > 0 %}bg-emerald-500/15 text-emerald-400 border border-emerald-500/30{% else %}bg-rose-500/15 text-rose-400 border border-rose-500/30{% endif %}">
                                    {{ b.available_copies }} / {{ b.total_copies }} Available
                                </span>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        {% else %}
        <!-- ================= LIBRARIAN ADMIN PORTAL VIEW ================= -->
        {% if not session.get('admin_logged_in') %}
        <div class="max-w-md mx-auto mt-10 glass-panel p-8 rounded-3xl relative overflow-hidden">
            <div class="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-fuchsia-500 via-purple-500 to-indigo-500"></div>
            <div class="text-center mb-6">
                <div class="w-16 h-16 mx-auto mb-3 rounded-2xl bg-gradient-to-tr from-fuchsia-600 to-indigo-600 text-white flex items-center justify-center text-3xl shadow-xl">
                    🔐
                </div>
                <span class="bg-fuchsia-500/15 text-fuchsia-400 border border-fuchsia-500/30 px-3 py-1 rounded-full text-[11px] font-extrabold uppercase">
                    Authorized Admin Access
                </span>
                <h2 class="text-2xl font-black heading-main mt-3">Admin Command Login</h2>
                <p class="text-xs sub-text mt-1">Login ID: <strong class="text-cyan-400 font-mono">Bomo</strong></p>
            </div>
            <form method="POST" action="/admin_login" class="space-y-4">
                <div>
                    <label class="text-xs font-bold sub-text block mb-1">Admin User ID</label>
                    <input type="text" name="username" value="Bomo" required class="w-full input-cyber rounded-xl px-4 py-3 text-sm font-semibold outline-none">
                </div>
                <div>
                    <label class="text-xs font-bold sub-text block mb-1">Admin Password</label>
                    <input type="password" name="password" value="Tharik007" required class="w-full input-cyber rounded-xl px-4 py-3 text-sm font-semibold outline-none">
                </div>
                <button type="submit" class="w-full bg-gradient-to-r from-fuchsia-600 via-purple-600 to-indigo-600 hover:from-fuchsia-500 hover:to-indigo-500 text-white font-black py-3.5 rounded-xl text-sm shadow-xl transition">
                    ⚡ Login as Bomo
                </button>
            </form>
        </div>

        {% else %}
        <!-- Excel Export & 14-Day Due Bar -->
        <div class="bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-700 text-white p-6 rounded-3xl shadow-xl flex flex-wrap items-center justify-between gap-4">
            <div class="flex items-center gap-4">
                <span class="bg-white/20 p-3.5 rounded-2xl text-2xl">📊</span>
                <div>
                    <h3 class="text-lg font-black">14-Day Due Tracker, WhatsApp Reminder & Microsoft Excel Exporter</h3>
                    <p class="text-xs text-emerald-100">Download Student Register No, Mobile No, Due Date & Fine Amount in Excel (.csv)</p>
                </div>
            </div>
            <div class="flex flex-wrap gap-3">
                <a href="/admin/export_excel?filter=due" class="bg-white text-slate-950 hover:bg-emerald-50 font-black px-5 py-3 rounded-xl text-xs shadow-lg transition transform hover:scale-105">
                    📥 Download Due & Fine List (Excel)
                </a>
                <a href="/admin/export_excel?filter=all" class="bg-slate-950/40 hover:bg-slate-950/60 text-white border border-white/30 font-bold px-4 py-3 rounded-xl text-xs transition">
                    📥 Export All History (Excel)
                </a>
            </div>
        </div>

        <!-- Master Student Issue Register & Direct WhatsApp Msg Table -->
        <div class="glass-panel rounded-3xl overflow-hidden relative">
            <div class="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-cyan-400 via-indigo-500 to-purple-600"></div>
            <div class="p-6 border-b border-slate-500/20 flex flex-wrap justify-between items-center gap-4">
                <div>
                    <h3 class="font-black text-lg heading-main">📋 Student Issue Register, Mobile Numbers & 14-Day Due Tracker</h3>
                    <p class="text-xs sub-text">Click "📲 Send WhatsApp Msg" to send a direct WhatsApp message to the student's mobile number</p>
                </div>
                <input type="text" id="regSearch" onkeyup="filterRegister()" placeholder="🔍 Search Name, Reg No, Mobile..."
                       class="input-cyber rounded-xl px-4 py-2.5 text-xs w-64 outline-none">
            </div>

            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse text-sm">
                    <thead>
                        <tr class="table-header text-xs uppercase tracking-wider">
                            <th class="p-4">Student & Mobile No</th>
                            <th class="p-4">Issued Book</th>
                            <th class="p-4">Issue & Due Date</th>
                            <th class="p-4">Due Status</th>
                            <th class="p-4">Fine (₹)</th>
                            <th class="p-4 text-right">Smart Actions (WhatsApp Msg • Renew • UPI QR • Return)</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-500/15">
                        {% for t in transactions %}
                        <tr class="table-row-hover transition reg-row">
                            <td class="p-4">
                                <div class="font-extrabold heading-main text-base">{{ t.student_name }}</div>
                                <div class="flex flex-wrap gap-1.5 mt-1">
                                    <span class="font-mono text-xs bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 px-2 py-0.5 rounded font-bold">
                                        {{ t.student_id }}
                                    </span>
                                    <span class="font-mono text-xs bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded font-bold">
                                        📱 +91 {{ t.student_phone }}
                                    </span>
                                </div>
                            </td>
                            <td class="p-4">
                                <div class="font-bold heading-main">{{ t.book.title }}</div>
                                <div class="text-xs font-mono sub-text">{{ t.book.book_code }} • {{ t.book.category }}</div>
                            </td>
                            <td class="p-4 text-xs">
                                <div class="sub-text">Issued: <strong class="heading-main">{{ t.issue_date.strftime('%d %b %Y') }}</strong></div>
                                <div class="mt-1 font-extrabold {% if t.overdue_days > 0 and t.status == 'Issued' %}text-rose-400{% else %}text-cyan-400{% endif %}">
                                    Due: {{ t.due_date.strftime('%d %b %Y') }}
                                </div>
                            </td>
                            <td class="p-4 text-xs">
                                {% if t.overdue_days > 0 and t.status == 'Issued' %}
                                    <span class="bg-rose-500/20 text-rose-400 border border-rose-500/40 px-3 py-1 rounded-full font-extrabold">
                                        ⚠️ {{ t.overdue_days }}d Overdue
                                    </span>
                                {% elif t.status == 'Issued' %}
                                    <span class="bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 px-3 py-1 rounded-full font-bold">
                                        ● {{ t.days_remaining }}d Left
                                    </span>
                                {% else %}
                                    <span class="bg-slate-500/20 sub-text px-3 py-1 rounded-full font-bold">
                                        ✔ Returned
                                    </span>
                                {% endif %}
                            </td>
                            <td class="p-4">
                                {% if t.current_fine > 0 %}
                                    <span class="text-rose-400 font-black text-base">₹{{ t.current_fine }}</span>
                                {% else %}
                                    <span class="text-emerald-400 font-bold text-xs">₹0</span>
                                {% endif %}
                            </td>
                            <td class="p-4 text-right">
                                {% if t.status == 'Issued' %}
                                <div class="flex flex-wrap justify-end gap-1.5">
                                    <a href="{{ t.whatsapp_direct_url }}" target="_blank"
                                       class="bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-3 py-1.5 rounded-xl text-xs shadow-md transition">
                                        📲 Send WhatsApp Msg
                                    </a>
                                    <form method="POST" action="/renew/{{ t.id }}">
                                        <input type="hidden" name="from_page" value="admin">
                                        <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold px-2.5 py-1.5 rounded-xl text-xs shadow-md transition">
                                            +7d Renew
                                        </button>
                                    </form>
                                    {% if t.current_fine > 0 %}
                                    <button type="button"
                                            onclick="openUpiModal('{{ t.id }}','{{ t.student_name }}','{{ t.student_id }}','{{ t.book.title }}','{{ t.current_fine }}','admin')"
                                            class="bg-rose-600 hover:bg-rose-500 text-white font-bold px-3 py-1.5 rounded-xl text-xs shadow-md transition">
                                        💳 Fine QR
                                    </button>
                                    {% endif %}
                                    <form method="POST" action="/return/{{ t.id }}">
                                        <input type="hidden" name="from_page" value="admin">
                                        <button type="submit" class="bg-cyan-600 hover:bg-cyan-500 text-white font-bold px-3 py-1.5 rounded-xl text-xs shadow-md transition">
                                            Return
                                        </button>
                                    </form>
                                </div>
                                {% else %}
                                <span class="text-xs sub-text font-semibold">Closed</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 3 Admin Action Cards: Upload Original Scanner, Issue Book, Add Book -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="glass-panel p-6 rounded-3xl relative overflow-hidden">
                <div class="absolute top-0 left-0 w-full h-1.5 bg-emerald-500"></div>
                <span class="bg-emerald-500/15 text-emerald-400 text-[11px] font-extrabold uppercase px-2.5 py-1 rounded-full">Original Scanner Setup</span>
                <h3 class="text-base font-black heading-main mt-2 mb-3">📷 Upload Your Original UPI Scanner</h3>
                <form method="POST" action="/admin/update_scanner" enctype="multipart/form-data" class="space-y-3">
                    <div>
                        <label class="text-xs font-bold sub-text block mb-1">Select Your GPay / PhonePe QR Image</label>
                        <input type="file" name="scanner_file" accept="image/*"
                               class="w-full text-xs sub-text file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-emerald-500/20 file:text-emerald-400 file:font-bold">
                    </div>
                    <div>
                        <label class="text-xs font-bold sub-text block mb-1">Or Enter Your UPI ID</label>
                        <input type="text" name="upi_id" value="{{ config.upi_id }}" placeholder="e.g., name@okaxis"
                               class="w-full input-cyber rounded-xl px-3.5 py-2.5 text-xs font-mono outline-none">
                    </div>
                    <button type="submit" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black py-2.5 rounded-xl text-xs shadow-lg transition">
                        Save My Original Scanner
                    </button>
                </form>
            </div>

            <div class="glass-panel p-6 rounded-3xl relative overflow-hidden">
                <div class="absolute top-0 left-0 w-full h-1.5 bg-cyan-500"></div>
                <span class="bg-cyan-500/15 text-cyan-400 text-[11px] font-extrabold uppercase px-2.5 py-1 rounded-full">Circulation Desk</span>
                <h3 class="text-base font-black heading-main mt-2 mb-3">📲 Issue Book with Mobile No</h3>
                <form method="POST" action="/issue" class="space-y-2.5">
                    <input type="hidden" name="from_page" value="admin">
                    <input type="text" name="student_id" required placeholder="Register No (e.g., 730224243014)" class="w-full input-cyber rounded-xl px-3.5 py-2 text-xs font-mono outline-none">
                    <input type="text" name="student_name" required placeholder="Student Full Name" class="w-full input-cyber rounded-xl px-3.5 py-2 text-xs outline-none">
                    <input type="tel" name="student_phone" required pattern="[0-9]{10}" maxlength="10" placeholder="10-Digit WhatsApp Mobile No" class="w-full input-cyber rounded-xl px-3.5 py-2 text-xs font-mono outline-none">
                    <select name="book_id" required class="w-full input-cyber rounded-xl px-3.5 py-2 text-xs outline-none">
                        <option value="">-- Select Book --</option>
                        {% for b in books %}{% if b.available_copies > 0 %}<option value="{{ b.id }}">[{{ b.book_code }}] {{ b.title }}</option>{% endif %}{% endfor %}
                    </select>
                    <button type="submit" class="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-black py-2.5 rounded-xl text-xs shadow-lg transition">
                        Issue Book Now
                    </button>
                </form>
            </div>

            <div class="glass-panel p-6 rounded-3xl relative overflow-hidden">
                <div class="absolute top-0 left-0 w-full h-1.5 bg-purple-500"></div>
                <span class="bg-purple-500/15 text-purple-400 text-[11px] font-extrabold uppercase px-2.5 py-1 rounded-full">Catalog Control</span>
                <h3 class="text-base font-black heading-main mt-2 mb-3">➕ Add New Book to Cloud</h3>
                <form method="POST" action="/add_book" class="space-y-2.5">
                    <div class="grid grid-cols-2 gap-2">
                        <input type="text" name="book_code" required placeholder="Code (LIB-AI105)" class="input-cyber rounded-xl px-3 py-2 text-xs font-mono outline-none">
                        <input type="text" name="category" required placeholder="Category" class="input-cyber rounded-xl px-3 py-2 text-xs outline-none">
                    </div>
                    <input type="text" name="title" required placeholder="Book Title" class="w-full input-cyber rounded-xl px-3 py-2 text-xs outline-none">
                    <div class="grid grid-cols-3 gap-2">
                        <input type="text" name="author" required placeholder="Author" class="col-span-2 input-cyber rounded-xl px-3 py-2 text-xs outline-none">
                        <input type="number" name="copies" value="3" min="1" required class="input-cyber rounded-xl px-3 py-2 text-xs outline-none">
                    </div>
                    <input type="text" name="tags" required placeholder="AI Keywords (python, ml, cloud)" class="w-full input-cyber rounded-xl px-3 py-2 text-xs outline-none">
                    <button type="submit" class="w-full bg-purple-600 hover:bg-purple-500 text-white font-black py-2.5 rounded-xl text-xs shadow-lg transition">
                        Save Book & Update Charts
                    </button>
                </form>
            </div>
        </div>

        <!-- Live Interactive Charts -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div class="lg:col-span-7 glass-panel p-6 rounded-3xl">
                <h3 class="text-sm font-black heading-main mb-4">📊 Category-Wise Cloud Book Inventory</h3>
                <div class="h-60">
                    <canvas id="categoryBarChart"></canvas>
                </div>
            </div>
            <div class="lg:col-span-5 glass-panel p-6 rounded-3xl">
                <h3 class="text-sm font-black heading-main mb-4">📈 Circulation & Overdue Status</h3>
                <div class="h-60 flex items-center justify-center">
                    <canvas id="statusPieChart"></canvas>
                </div>
            </div>
        </div>
        {% endif %}
        {% endif %}
    </main>

    <!-- ORIGINAL UPI QR MODAL -->
    <div id="upiModal" class="fixed inset-0 bg-slate-950/80 backdrop-blur-md hidden items-center justify-center z-50 p-4">
        <div class="glass-panel max-w-sm w-full rounded-3xl p-6 text-center shadow-2xl relative border-t-4 border-t-emerald-400">
            <button onclick="closeUpiModal()" class="absolute top-3.5 right-4 sub-text hover:text-rose-400 font-bold text-lg">✕</button>
            <span class="bg-emerald-500/20 text-emerald-300 px-3 py-0.5 rounded-full text-xs font-extrabold uppercase">
                Official Library Fine Scanner
            </span>
            <h3 class="text-base font-black heading-main mt-2" id="upiStudentName"></h3>
            <p class="text-xs sub-text" id="upiBookTitle"></p>

            <div class="my-4 bg-white border border-slate-200 p-3 rounded-2xl inline-block shadow-lg">
                {% if config and config.custom_qr_base64 %}
                    <img src="{{ config.custom_qr_base64 }}" class="w-48 h-48 object-contain mx-auto rounded-lg">
                    <span class="block text-[11px] text-emerald-700 font-extrabold mt-1">✔ Official Uploaded Library Scanner</span>
                {% else %}
                    <img id="upiQrImg" src="" class="w-44 h-44 mx-auto">
                    <span class="block text-[11px] text-slate-700 font-bold mt-1">UPI ID: {{ config.upi_id if config else 'mohamedtharik@okaxis' }}</span>
                {% endif %}
            </div>

            <p class="text-2xl font-black heading-main" id="upiAmountText"></p>
            <p class="text-xs sub-text mt-0.5">Scan with GPay, PhonePe, or Paytm</p>

            <form id="upiReturnForm" method="POST" action="" class="mt-4">
                <input type="hidden" name="from_page" id="upiFromPage" value="student">
                <button type="submit" class="w-full bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-black py-3 rounded-xl text-sm shadow-lg">
                    ✅ Confirm Fine Paid & Return Book
                </button>
            </form>
        </div>
    </div>

    <script>
        function updateClock() {
            const now = new Date();
            const el = document.getElementById("liveClock");
            if (el) el.innerText = now.toLocaleTimeString('en-IN', { hour12: true });
        }
        setInterval(updateClock, 1000);
        updateClock();

        function applyTheme(theme) {
            const root = document.getElementById("htmlRoot");
            const icon = document.getElementById("themeIcon");
            const label = document.getElementById("themeLabel");
            if (theme === "crystal") {
                root.classList.remove("theme-aurora");
                root.classList.add("theme-crystal");
                icon.innerText = "🌌";
                label.innerText = "Aurora Dark";
            } else {
                root.classList.remove("theme-crystal");
                root.classList.add("theme-aurora");
                icon.innerText = "☀️";
                label.innerText = "Crystal Light";
            }
        }

        function toggleTheme() {
            const current = localStorage.getItem("smartlib_ui_mode") || "aurora";
            const next = current === "aurora" ? "crystal" : "aurora";
            localStorage.setItem("smartlib_ui_mode", next);
            applyTheme(next);
        }

        applyTheme(localStorage.getItem("smartlib_ui_mode") || "aurora");

        function filterRegister() {
            const q = document.getElementById("regSearch").value.toLowerCase();
            document.querySelectorAll(".reg-row").forEach(r => {
                r.style.display = r.innerText.toLowerCase().includes(q) ? "" : "none";
            });
        }

        function filterCatalog() {
            const q = document.getElementById("catalogSearch").value.toLowerCase();
            document.querySelectorAll(".catalog-row").forEach(r => {
                r.style.display = r.innerText.toLowerCase().includes(q) ? "" : "none";
            });
        }

        function openUpiModal(txId, sName, sId, bTitle, fine, page) {
            document.getElementById("upiStudentName").innerText = sName + " (" + sId + ")";
            document.getElementById("upiBookTitle").innerText = bTitle;
            document.getElementById("upiAmountText").innerText = "₹" + fine + ".00";
            document.getElementById("upiFromPage").value = page;
            const qrImg = document.getElementById("upiQrImg");
            if (qrImg) {
                const uri = encodeURIComponent("upi://pay?pa={{ config.upi_id if config else 'mohamedtharik@okaxis' }}&pn=SmartLib&am=" + fine + "&cu=INR");
                qrImg.src = "https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=" + uri;
            }
            document.getElementById("upiReturnForm").action = "/return/" + txId;
            document.getElementById("upiModal").classList.remove("hidden");
            document.getElementById("upiModal").classList.add("flex");
        }

        function closeUpiModal() {
            document.getElementById("upiModal").classList.add("hidden");
            document.getElementById("upiModal").classList.remove("flex");
        }

        {% if mode == 'admin' and session.get('admin_logged_in') %}
        new Chart(document.getElementById('categoryBarChart'), {
            type: 'bar',
            data: {
                labels: {{ chart_categories | tojson }},
                datasets: [{
                    label: 'Books',
                    data: {{ chart_counts | tojson }},
                    backgroundColor: ['#6366F1', '#06B6D4', '#10B981', '#A855F7', '#F43F5E'],
                    borderRadius: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#94A3B8' }, grid: { display: false } },
                    y: { ticks: { color: '#94A3B8', stepSize: 2 }, grid: { color: 'rgba(148,163,184,0.12)' } }
                }
            }
        });

        new Chart(document.getElementById('statusPieChart'), {
            type: 'doughnut',
            data: {
                labels: ['Available Stock', 'Issued (Within 14d)', 'Overdue (>14d)'],
                datasets: [{
                    data: [{{ stats.available_books }}, {{ stats.on_time_issues }}, {{ stats.overdue_count }}],
                    backgroundColor: ['#10B981', '#38BDF8', '#F43F5E'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#94A3B8', font: { size: 11 } } }
                }
            }
        });
        {% endif %}
    </script>
</body>
</html>
"""

# ----------------- ROUTES -----------------

@app.route("/")
def index():
    interest = request.args.get("interest", "").strip()
    my_reg = request.args.get("my_reg", "").strip()
    books = Book.query.order_by(Book.id.desc()).all()
    recommendations = get_ai_recommendations(interest) if interest else []
    config = SystemConfig.query.first()

    my_transactions = []
    if my_reg:
        search_term = f"%{my_reg}%"
        my_transactions = Transaction.query.filter(
            (Transaction.student_id.ilike(search_term)) |
            (Transaction.student_name.ilike(search_term)) |
            (Transaction.student_phone.ilike(search_term))
        ).order_by(Transaction.id.desc()).all()

    active_tx = Transaction.query.filter_by(status="Issued").all()
    stats = {
        "total_books": sum(b.total_copies for b in books),
        "available_books": sum(b.available_copies for b in books),
        "active_issues": len(active_tx),
        "overdue_count": sum(1 for t in active_tx if t.overdue_days > 0),
        "total_fine": sum(t.current_fine for t in active_tx)
    }
    return render_template_string(
        PORTAL_HTML,
        mode="student",
        books=books,
        recommendations=recommendations,
        interest=interest,
        my_reg=my_reg,
        my_transactions=my_transactions,
        stats=stats,
        config=config
    )

@app.route("/admin")
def admin_portal():
    books = Book.query.order_by(Book.id.desc()).all()
    transactions = Transaction.query.order_by(Transaction.id.desc()).all()
    active_tx = [t for t in transactions if t.status == "Issued"]
    overdue_count = sum(1 for t in active_tx if t.overdue_days > 0)
    config = SystemConfig.query.first()

    cat_map = {}
    for b in books:
        cat_map[b.category] = cat_map.get(b.category, 0) + b.total_copies

    stats = {
        "total_books": sum(b.total_copies for b in books),
        "available_books": sum(b.available_copies for b in books),
        "active_issues": len(active_tx),
        "on_time_issues": max(0, len(active_tx) - overdue_count),
        "overdue_count": overdue_count,
        "total_fine": sum(t.current_fine for t in active_tx)
    }
    return render_template_string(
        PORTAL_HTML,
        mode="admin",
        books=books,
        transactions=transactions,
        stats=stats,
        config=config,
        chart_categories=list(cat_map.keys()),
        chart_counts=list(cat_map.values())
    )

@app.route("/admin/update_scanner", methods=["POST"])
def update_scanner():
    config = SystemConfig.query.first()
    upi_id = request.form.get("upi_id", "").strip()
    if upi_id:
        config.upi_id = upi_id
    file = request.files.get("scanner_file")
    if file and file.filename:
        raw_bytes = file.read()
        encoded = base64.b64encode(raw_bytes).decode("utf-8")
        mime = file.mimetype or "image/png"
        config.custom_qr_base64 = f"data:{mime};base64,{encoded}"
        flash("✅ Your Original UPI Scanner Image has been uploaded and activated!", "success")
    else:
        flash("✅ UPI ID updated successfully!", "success")
    db.session.commit()
    return redirect(url_for("admin_portal"))

@app.route("/renew/<int:tx_id>", methods=["POST"])
def renew_book(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    from_page = request.form.get("from_page", "admin")
    my_reg = request.form.get("my_reg", tx.student_id)
    if tx.status == "Issued":
        base_date = max(datetime.utcnow(), tx.due_date)
        tx.due_date = base_date + timedelta(days=7)
        db.session.commit()
        flash(f"✅ Book '{tx.book.title}' renewed for +7 Days! New Due Date: {tx.due_date.strftime('%d %b %Y')}", "success")
    if from_page == "student":
        return redirect(url_for("index", my_reg=my_reg))
    return redirect(url_for("admin_portal"))

@app.route("/admin/export_excel")
def export_excel():
    filter_type = request.args.get("filter", "due")
    transactions = Transaction.query.order_by(Transaction.id.desc()).all()
    records = [t for t in transactions if t.status == "Issued"] if filter_type == "due" else transactions
    filename = f"SmartLib_Due_Report_{datetime.now().strftime('%d_%b_%Y')}.csv"

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(["S.No", "Register Number", "Student Name", "Mobile Number", "Book Code", "Book Title", "Category", "Issue Date", "Due Date (14 Days)", "Status", "Overdue Days", "Fine Amount (Rs.)"])
    for idx, t in enumerate(records, start=1):
        writer.writerow([
            idx, t.student_id, t.student_name, t.student_phone, t.book.book_code, t.book.title,
            t.book.category, t.issue_date.strftime('%d-%b-%Y'), t.due_date.strftime('%d-%b-%Y'),
            "Overdue" if (t.status == "Issued" and t.overdue_days > 0) else t.status,
            t.overdue_days, f"Rs. {t.current_fine}"
        ])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename={filename}"})

@app.route("/admin_login", methods=["POST"])
def admin_login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    if username.lower() == "bomo" and password == "Tharik007":
        session["admin_logged_in"] = True
        session["admin_user"] = "Bomo"
        flash("✅ Welcome Bomo! Librarian Command Center unlocked.", "success")
    else:
        flash("❌ Invalid Admin credentials! Use ID: Bomo and Password: Tharik007", "error")
    return redirect(url_for("admin_portal"))

@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_user", None)
    return redirect(url_for("admin_portal"))

@app.route("/add_book", methods=["POST"])
def add_book():
    book_code = request.form.get("book_code").strip().upper()
    if Book.query.filter_by(book_code=book_code).first():
        flash(f"Book Code {book_code} already exists!", "error")
        return redirect(url_for("admin_portal"))
    copies = int(request.form.get("copies", 3))
    db.session.add(Book(
        book_code=book_code, title=request.form.get("title").strip(),
        author=request.form.get("author").strip(), category=request.form.get("category").strip(),
        tags=request.form.get("tags").strip(), total_copies=copies, available_copies=copies
    ))
    db.session.commit()
    flash("✅ New book added to Cloud Catalog!", "success")
    return redirect(url_for("admin_portal"))

@app.route("/issue", methods=["POST"])
def issue_book():
    student_id = request.form.get("student_id").strip().upper()
    student_name = request.form.get("student_name").strip()
    student_phone = request.form.get("student_phone", "9876543210").strip()
    book_id = int(request.form.get("book_id"))
    from_page = request.form.get("from_page", "student")

    book = Book.query.get_or_404(book_id)
    if book.available_copies <= 0:
        flash("Sorry, no copies available.", "error")
        return redirect(url_for("admin_portal") if from_page == "admin" else url_for("index"))

    book.available_copies -= 1
    due_dt = datetime.utcnow() + timedelta(days=14)
    db.session.add(Transaction(
        student_id=student_id, student_name=student_name, student_phone=student_phone,
        book_id=book.id, issue_date=datetime.utcnow(), due_date=due_dt,
        status="Issued"
    ))
    db.session.commit()
    flash(f"✅ Book '{book.title}' issued to {student_name} (📱 {student_phone})! 14-Day Due Date: {due_dt.strftime('%d %b %Y')}", "success")
    return redirect(url_for("admin_portal") if from_page == "admin" else url_for("index", my_reg=student_id))

@app.route("/return/<int:tx_id>", methods=["POST"])
def return_book(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    from_page = request.form.get("from_page", "admin")
    if tx.status == "Issued":
        fine_paid = tx.current_fine
        tx.status = "Returned"
        tx.return_date = datetime.utcnow()
        tx.book.available_copies += 1
        db.session.commit()
        flash(f"✅ Book '{tx.book.title}' returned by {tx.student_name}! Fine settled: ₹{fine_paid}", "success")
    return redirect(url_for("index", my_reg=tx.student_id) if from_page == "student" else url_for("admin_portal"))

if __name__ == "__main__":
    with app.app_context():
        init_and_migrate_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
