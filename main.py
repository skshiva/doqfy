from flask import Flask, request, redirect, render_template, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from cryptography.fernet import Fernet
import sqlite3 as sql
import string
import random

# Initialize Flask app and SQLAlchemy
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///urls.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
db = SQLAlchemy(app)


class Snippet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    short_url = db.Column(db.String(6), unique=True, nullable=False)
    secret_key = db.Column(db.String(44), nullable=True)


class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(2048), nullable=False)
    short_url = db.Column(db.String(6), unique=True, nullable=False)


def generate_short_url():
    characters = string.ascii_letters + string.digits
    while True:
        short_url = ''.join(random.choices(characters, k=6))
        if not URL.query.filter_by(short_url=short_url).first():
            return short_url


@app.route('/', methods=['GET', 'POST'])
@app.route("/index")
def index():
    con = sql.connect("instance/urls.db")
    con.row_factory = sql.Row
    cur = con.cursor()
    cur.execute("select * from url")
    data = cur.fetchall()
    snippets = Snippet.query.all()
    return render_template('index.html', url_list=data, snippets=snippets)


@app.route('/<short_url>', methods=['GET', 'POST'])
def view_snippet(short_url):
    snippet = Snippet.query.filter_by(short_url=short_url).first()
    if not snippet:
        return "Snippet not found.", 404

    if snippet.secret_key:
        if request.method == 'POST':
            provided_key = request.form['secret_key']
            cipher = Fernet(provided_key.encode())
            try:
                decrypted_content = cipher.decrypt(snippet.content.encode()).decode()
                return render_template('view_snippet.html', content=decrypted_content)
            except Exception:
                flash('Invalid secret key.', 'danger')
                return redirect(url_for('view_snippet', short_url=short_url))
        return render_template('enter_key.html')

    return render_template('view_snippet.html', content=snippet.content)


@app.route('/add_snippet', methods=['POST', 'GET'])
def add_snippet():
    if request.method == 'POST':
        content = request.form['content']
        secret_key = request.form.get('secret_key', None)

        if not content:
            flash("Please provide snippet content.", 'danger')
            return redirect(url_for("index"))

        short_url = generate_short_url()

        if secret_key:
            cipher = Fernet(secret_key.encode())
            encrypted_content = cipher.encrypt(content.encode()).decode()
        else:
            encrypted_content = content

        new_snippet = Snippet(content=encrypted_content, short_url=short_url, secret_key=secret_key)
        db.session.add(new_snippet)
        db.session.commit()
        flash(f"Snippet URL Created: {request.host_url}{short_url}", 'success')
        return redirect(url_for("index"))
    else:
        return render_template('add_snippet.html')


@app.route('/<short_url>')
def redirect_to_url(short_url):
    url = URL.query.filter_by(short_url=short_url).first()
    if url:
        return redirect(url.original_url)
    return "URL not found.", 404


@app.route("/add_url", methods=['POST', 'GET'])
def add_url():
    if request.method == 'POST':
        original_url = request.form['original_url']
        if not original_url:
            return "Please provide a URL."

        # Check if the URL is already shortened
        existing_url = URL.query.filter_by(original_url=original_url).first()
        if existing_url:
            flash(f"Short URL: {request.host_url}{existing_url.short_url}", 'success')
            return redirect(url_for("index"))

        short_url = generate_short_url()
        new_url = URL(original_url=original_url, short_url=short_url)
        db.session.add(new_url)
        db.session.commit()
        flash('URL Added', 'success')
        return redirect(url_for("index"))
    return render_template('add_url.html')


@app.route("/edit_url/<string:uid>", methods=['POST', 'GET'])
def edit_url(uid):
    if request.method == 'POST':
        original_url = request.form['original_url']
        short_url = request.form['short_url']
        con = sql.connect("instance/urls.db")
        cur = con.cursor()
        cur.execute("update url set original_url=?,short_url=? where id=?", (original_url, short_url, uid))
        con.commit()
        flash('URL Updated', 'success')
        return redirect(url_for("index"))
    con = sql.connect("instance/urls.db")
    con.row_factory = sql.Row
    cur = con.cursor()
    cur.execute("select * from url where id=?", (uid,))
    data = cur.fetchone()
    return render_template("edit_url.html", datas=data)


@app.route("/delete_url/<string:uid>", methods=['GET'])
def delete_url(uid):
    con = sql.connect("instance/urls.db")
    cur = con.cursor()
    cur.execute("delete from url where id=?", (uid,))
    con.commit()
    flash('URL Deleted', 'warning')
    return redirect(url_for("index"))


@app.route("/share_url/<int:uid>", methods=['GET'])
def share_url(uid):
    url = URL.query.get_or_404(uid)
    short_url = f"{request.host_url}{url.short_url}"
    flash(f"Share this URL: {short_url}", 'info')
    return redirect(url_for("index"))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create the database tables if they don't exist
    app.run(debug=True)
