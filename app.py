import os
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "smart_cloud_library_secret_key"

# Cloud DB Configuration (Unga Neon Link Direct-aa Set Aagiruku!)
db_url = "postgresql://neondb_owner:npg_lg85vUsoYVGi@ep-dawn-mouse-b5zf4euu-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ----------------- DATABASE MODELS -----------------

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
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False)
    return_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default="Issued")

    book = db.relationship('Book', backref=db.backref('transactions', lazy=True))

    @property
    def current_fine(self):
        end_time = self.return_date if self.return_date else datetime.utcnow()
        if end_time > self.due_date:
            overdue_days = (end_time - self.due_date).days
            return max(0, overdue_days * 10)
        return 0

# ----------------- SEED INITIAL DATA -----------------

def seed_initial_books():
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
            student_id="26AIDS01",
            student_name="Mohamed Tharik",
            book_id=1,
            issue_date=datetime.utcnow() - timedelta(days=5),
            due_date=datetime.utcnow() + timedelta(days=9),
            status="Issued"
        )
        t2 = Transaction(
            student_id="26AIDS15",
            student_name="Karthik Raja",
            book_id=4,
            issue_date=datetime.utcnow() - timedelta(days=18),
            due_date=datetime.utcnow() - timedelta(days=4),
            status="Issued"
        )
        db.session.add_all([t1, t2])
        db.session.commit()

# ----------------- SMART AI RECOMMENDATION ENGINE -----------------

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

# ----------------- FRONTEND HTML TEMPLATE -----------------

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cloud-Based Smart Library System</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen font-sans">
    <nav class="bg-indigo-950 border-b border-indigo-800 px-4 py-4 sticky top-0 z-50 shadow-lg">
        <div class="max-w-7xl mx-auto flex flex-wrap justify-between items-center gap-3">
            <div class="flex items-center space-x-3">
                <span class="bg-indigo-600 text-white p-2 rounded-lg font-bold text-xl">☁️ SmartLib</span>
                <div>
                    <h1 class="text-lg font-bold tracking-wide">Cloud-Based Smart Library Management</h1>
                    <p class="text-xs text-indigo-300">AI Recommender • QR Pass • Auto Fine Engine</p>
                </div>
            </div>
            <div class="flex items-center gap-2 text-xs bg-slate-800 px-3 py-1.5 rounded-full border border-slate-700">
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Neon Cloud DB: <strong>Connected</strong></span>
            </div>
        </div>
    </nav>

    <div class="max-w-7xl mx-auto px-4 py-6 space-y-8">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <div class="space-y-2">
              {% for category, message in messages %}
                <div class="p-4 rounded-xl text-sm font-medium {% if category == 'error' %}bg-rose-900/70 border border-rose-600 text-rose-100{% else %}bg-emerald-900/70 border border-emerald-600 text-emerald-100{% endif %}">
                  {{ message }}
                </div>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}

        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="bg-slate-800/90 border border-slate-700 p-4 rounded-2xl shadow">
                <p class="text-xs text-slate-400 uppercase">Total Books</p>
                <p class="text-2xl font-extrabold text-white mt-1">{{ stats.total_books }}</p>
            </div>
            <div class="bg-slate-800/90 border border-slate-700 p-4 rounded-2xl shadow">
                <p class="text-xs text-slate-400 uppercase">Available Now</p>
                <p class="text-2xl font-extrabold text-emerald-400 mt-1">{{ stats.available_books }}</p>
            </div>
            <div class="bg-slate-800/90 border border-slate-700 p-4 rounded-2xl shadow">
                <p class="text-xs text-slate-400 uppercase">Active Issued</p>
                <p class="text-2xl font-extrabold text-indigo-400 mt-1">{{ stats.active_issues }}</p>
            </div>
            <div class="bg-slate-800/90 border border-slate-700 p-4 rounded-2xl shadow">
                <p class="text-xs text-slate-400 uppercase">Overdue Fines (₹)</p>
                <p class="text-2xl font-extrabold text-rose-400 mt-1">₹{{ stats.total_fine }}</p>
            </div>
        </div>

        <div class="bg-gradient-to-r from-indigo-900/60 to-slate-800 border border-indigo-700/60 p-5 rounded-2xl shadow-lg">
            <h2 class="text-base font-bold text-indigo-300">🤖 AI Smart Book Recommender & Instant Filter</h2>
            <p class="text-xs text-slate-300 mt-1">Enter domain keywords (e.g., "python ai", "cloud", "networks", "coding")</p>
            <form method="GET" action="/" class="mt-3 flex flex-col sm:flex-row gap-3">
                <input type="text" name="interest" value="{{ interest }}" placeholder="Ask AI: e.g., machine learning python or cloud protocols..."
                       class="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white">
                <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-6 py-2.5 rounded-xl text-sm">
                    Recommend Books
                </button>
                {% if interest %}
                <a href="/" class="bg-slate-700 hover:bg-slate-600 text-slate-200 px-4 py-2.5 rounded-xl text-sm text-center">Reset</a>
                {% endif %}
            </form>

            {% if recommendations %}
            <div class="mt-4 pt-4 border-t border-indigo-800/60">
                <p class="text-xs font-semibold text-amber-300 mb-2">✨ Top AI Matches for "{{ interest }}":</p>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {% for rec in recommendations %}
                    <div class="bg-slate-900/80 p-3 rounded-xl border border-indigo-600/40 flex justify-between items-center">
                        <div>
                            <span class="text-xs bg-indigo-950 text-indigo-300 px-2 py-0.5 rounded">{{ rec.book_code }}</span>
                            <h4 class="font-bold text-sm mt-1">{{ rec.title }}</h4>
                            <p class="text-xs text-slate-400">{{ rec.author }} • {{ rec.category }}</p>
                        </div>
                        <span class="text-xs font-semibold px-2.5 py-1 rounded-full {% if rec.available_copies > 0 %}bg-emerald-950 text-emerald-300{% else %}bg-rose-950 text-rose-300{% endif %}">
                            {{ rec.available_copies }} left
                        </span>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="bg-slate-800 border border-slate-700 p-5 rounded-2xl">
                <h3 class="text-base font-bold text-white mb-3">📲 Smart Book Issue (14-Day Auto Due Date)</h3>
                <form method="POST" action="/issue" class="space-y-3">
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <input type="text" name="student_id" required placeholder="Student Roll No (e.g., 26AIDS01)"
                               class="bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white">
                        <input type="text" name="student_name" required placeholder="Student Name"
                               class="bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white">
                    </div>
                    <select name="book_id" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white">
                        <option value="">-- Select Available Book --</option>
                        {% for b in books %}
                            {% if b.available_copies > 0 %}
                            <option value="{{ b.id }}">[{{ b.book_code }}] {{ b.title }} ({{ b.available_copies }} available)</option>
                            {% endif %}
                        {% endfor %}
                    </select>
                    <button type="submit" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-2.5 rounded-xl text-sm">
                        Issue Book Instantly
                    </button>
                </form>
            </div>

            <div class="bg-slate-800 border border-slate-700 p-5 rounded-2xl">
                <h3 class="text-base font-bold text-white mb-3">➕ Add Book to Cloud Catalog</h3>
                <form method="POST" action="/add_book" class="space-y-3">
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <input type="text" name="book_code" required placeholder="Book Code (e.g., LIB-AI105)"
                               class="bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white">
                        <input type="text" name="category" required placeholder="Category (e.g., AI & DS)"
                               class="bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white">
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <input type="text" name="title" required placeholder="Book Title"
                               class="bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white">
                        <input type="text" name="author" required placeholder="Author Name"
                               class="bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white">
                    </div>
                    <div class="grid grid-cols-3 gap-3">
                        <input type="text" name="tags" required placeholder="Smart AI Tags (comma separated)"
                               class="col-span-2 bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white">
                        <input type="number" name="copies" value="3" min="1" required placeholder="Copies"
                               class="bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white">
                    </div>
                    <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-xl text-sm">
                        Save Book & Generate QR Tag
                    </button>
                </form>
            </div>
        </div>

        <div class="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden shadow">
            <div class="p-4 border-b border-slate-700 flex justify-between items-center">
                <h3 class="font-bold text-base">📚 Cloud Book Inventory & Smart QR Tags</h3>
                <span class="text-xs text-slate-400">Scan QR with Mobile to verify Book ID</span>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse text-sm">
                    <thead>
                        <tr class="bg-slate-900/60 text-slate-400 text-xs uppercase">
                            <th class="p-3.5">QR Tag</th>
                            <th class="p-3.5">Code</th>
                            <th class="p-3.5">Title & Author</th>
                            <th class="p-3.5">Category</th>
                            <th class="p-3.5">Availability</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-700/70">
                        {% for b in books %}
                        <tr class="hover:bg-slate-700/30">
                            <td class="p-3.5">
                                <img src="https://api.qrserver.com/v1/create-qr-code/?size=60x60&data={{ b.book_code }}-{{ b.title|urlencode }}"
                                     alt="QR" class="w-11 h-11 rounded bg-white p-1">
                            </td>
                            <td class="p-3.5 font-mono text-xs text-indigo-300 font-semibold">{{ b.book_code }}</td>
                            <td class="p-3.5">
                                <div class="font-bold text-white">{{ b.title }}</div>
                                <div class="text-xs text-slate-400">{{ b.author }}</div>
                            </td>
                            <td class="p-3.5">
                                <span class="text-xs bg-slate-900 border border-slate-700 px-2.5 py-1 rounded-lg">{{ b.category }}</span>
                            </td>
                            <td class="p-3.5">
                                <span class="px-2.5 py-1 rounded-full text-xs font-semibold {% if b.available_copies > 0 %}bg-emerald-950 text-emerald-300 border border-emerald-700{% else %}bg-rose-950 text-rose-300 border border-rose-700{% endif %}">
                                    {{ b.available_copies }} / {{ b.total_copies }} Available
                                </span>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden shadow">
            <div class="p-4 border-b border-slate-700">
                <h3 class="font-bold text-base">⏱️ Live Circulation & Auto-Fine Tracker (₹10 / Overdue Day)</h3>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse text-sm">
                    <thead>
                        <tr class="bg-slate-900/60 text-slate-400 text-xs uppercase">
                            <th class="p-3.5">Student</th>
                            <th class="p-3.5">Book</th>
                            <th class="p-3.5">Issue Date</th>
                            <th class="p-3.5">Due Date</th>
                            <th class="p-3.5">Fine (₹)</th>
                            <th class="p-3.5">Status / Action</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-700/70">
                        {% for t in transactions %}
                        <tr class="hover:bg-slate-700/30">
                            <td class="p-3.5">
                                <div class="font-semibold text-white">{{ t.student_name }}</div>
                                <div class="text-xs text-slate-400">{{ t.student_id }}</div>
                            </td>
                            <td class="p-3.5 font-medium text-indigo-200">{{ t.book.title }}</td>
                            <td class="p-3.5 text-xs text-slate-300">{{ t.issue_date.strftime('%d %b %Y') }}</td>
                            <td class="p-3.5 text-xs {% if t.current_fine > 0 and t.status == 'Issued' %}text-rose-400 font-bold{% else %}text-slate-300{% endif %}">
                                {{ t.due_date.strftime('%d %b %Y') }}
                            </td>
                            <td class="p-3.5">
                                {% if t.current_fine > 0 %}
                                    <span class="text-rose-400 font-bold">₹{{ t.current_fine }}</span>
                                {% else %}
                                    <span class="text-emerald-400 text-xs">₹0 (No Fine)</span>
                                {% endif %}
                            </td>
                            <td class="p-3.5">
                                {% if t.status == 'Issued' %}
                                <form method="POST" action="/return/{{ t.id }}">
                                    <button type="submit" class="bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-3 py-1.5 rounded-lg text-xs">
                                        Mark Returned
                                    </button>
                                </form>
                                {% else %}
                                <span class="text-xs bg-slate-900 text-slate-400 px-2.5 py-1 rounded-lg border border-slate-700">
                                    Returned ({{ t.return_date.strftime('%d %b') }})
                                </span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

# ----------------- ROUTES -----------------

@app.route("/")
def index():
    interest = request.args.get("interest", "").strip()
    books = Book.query.order_by(Book.id.desc()).all()
    transactions = Transaction.query.order_by(Transaction.id.desc()).all()
    recommendations = get_ai_recommendations(interest) if interest else []

    stats = {
        "total_books": sum(b.total_copies for b in books),
        "available_books": sum(b.available_copies for b in books),
        "active_issues": Transaction.query.filter_by(status="Issued").count(),
        "total_fine": sum(t.current_fine for t in transactions if t.status == "Issued")
    }
    return render_template_string(
        HTML_TEMPLATE,
        books=books,
        transactions=transactions,
        recommendations=recommendations,
        interest=interest,
        stats=stats
    )

@app.route("/add_book", methods=["POST"])
def add_book():
    book_code = request.form.get("book_code").strip().upper()
    title = request.form.get("title").strip()
    author = request.form.get("author").strip()
    category = request.form.get("category").strip()
    tags = request.form.get("tags").strip()
    copies = int(request.form.get("copies", 1))

    if Book.query.filter_by(book_code=book_code).first():
        flash(f"Book Code {book_code} already exists in Cloud Catalog!", "error")
        return redirect(url_for("index"))

    new_book = Book(
        book_code=book_code, title=title, author=author,
        category=category, tags=tags, total_copies=copies, available_copies=copies
    )
    db.session.add(new_book)
    db.session.commit()
    flash(f"'{title}' added to Cloud Database with Smart QR!", "success")
    return redirect(url_for("index"))

@app.route("/issue", methods=["POST"])
def issue_book():
    student_id = request.form.get("student_id").strip().upper()
    student_name = request.form.get("student_name").strip()
    book_id = int(request.form.get("book_id"))

    book = Book.query.get_or_404(book_id)
    if book.available_copies <= 0:
        flash("Sorry, no copies currently available.", "error")
        return redirect(url_for("index"))

    book.available_copies -= 1
    new_tx = Transaction(
        student_id=student_id, student_name=student_name, book_id=book.id,
        issue_date=datetime.utcnow(), due_date=datetime.utcnow() + timedelta(days=14), status="Issued"
    )
    db.session.add(new_tx)
    db.session.commit()
    flash(f"Book '{book.title}' issued to {student_name} ({student_id})!", "success")
    return redirect(url_for("index"))

@app.route("/return/<int:tx_id>", methods=["POST"])
def return_book(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if tx.status == "Issued":
        tx.status = "Returned"
        tx.return_date = datetime.utcnow()
        tx.book.available_copies += 1
        db.session.commit()
        flash(f"Book '{tx.book.title}' returned! Fine collected: ₹{tx.current_fine}", "success")
    return redirect(url_for("index"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_initial_books()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)