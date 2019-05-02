import os, requests, random

from flask import Flask, session, render_template, request, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
# set DATABASE_URL=postgres://vhxpyztttqopeq:d9f88853016924d9a7e9c30990a5c3d1ea59afafd6b31d33e3db56bbc2afdfbc@ec2-50-17-227-28.compute-1.amazonaws.com:5432/d7pcko0iplvkj8
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():

    if session.get("user_id") is None and session.get("user_name") is None:
        return render_template('login.html')
    else:
        return home()

@app.route("/login", methods=['POST'])
def login():

    user = request.form.get("user")
    password = request.form.get("password")
    btnRegistro = request.form.get("registro")

    user_row = db.execute("SELECT * FROM usuario WHERE user_name = :user_name", {"user_name": user}).fetchone()

    if btnRegistro is not None:
        if user_row is None:
            return registro()
        else:
            show_alert_user_exist = 1
            return render_template('login.html', user=user_row, show_alert_user_exist=show_alert_user_exist)
    else:
        if user_row is None:
            show_alert_registration = 1
            user_row = { "user_name": user, "password": password }
            return render_template('login.html', user=user_row, show_alert_registration=show_alert_registration)

        if user_row.password == password:
            session["user_id"] = user_row["id"]
            session["user_name"] = user_row["user_name"]

            return home()
        else:
            show_alert_wrong_pass = 1
            return render_template('login.html', user=user_row, show_alert_wrong_pass=show_alert_wrong_pass)

@app.route("/logout")
def logout():

    session.pop('user_id', None)
    session.pop('user_name', None)

    return render_template('login.html')

@app.route("/registro", methods=['POST'])
def registro():

    user = request.form.get("user")
    password = request.form.get("password")

    user_row = db.execute("INSERT INTO usuario (user_name, password) VALUES (:user_name, :password) RETURNING id", {"user_name": user, "password": password}).fetchone()
    db.commit()

    session["user_id"] = user_row["id"]
    session["user_name"] = user

    return home()

@app.route("/home", methods=['GET', 'POST'])
def home():

    if session.get("user_id") is None and session.get("user_name") is None:
        return render_template('login.html')
    else:
        buscar = request.form.get("buscar")

        libros_rows = db.execute("SELECT l.id, l.isbn, l.title, l.year, a.name FROM libro l, autor a WHERE l.autor_id = a.id").fetchall()

        libros_random_rows = random.choices(libros_rows, k=9)

        string_isbns = ""
        for libro in libros_random_rows:
            string_isbns += libro["isbn"] + ','
        string_isbns = string_isbns[:-1]

        goodreadsApiKey = "tpdr69k3CAh0DA53FqAWw"
        data = requests.get("https://www.goodreads.com/book/review_counts.json?isbns={}&key={}".format(string_isbns, goodreadsApiKey)).json()

        libros_random = []

        for goodread_book in data["books"]:
            for libro in libros_random_rows:
                if libro["isbn"] == goodread_book["isbn"]:
                    d = dict(libro.items())
                    d["average_rating"] = goodread_book["average_rating"]
                    d["work_ratings_count"] = goodread_book["work_ratings_count"]
                    libros_random.append(d)
                    break

        if buscar is not None:

            libros_rows = db.execute("SELECT l.id, l.isbn, l.title, l.year, a.name FROM libro l, autor a WHERE l.autor_id = a.id and \
                                    ( UPPER(l.isbn) LIKE UPPER('%{}%') OR UPPER(l.title) LIKE UPPER('%{}%') OR UPPER(a.name) LiKE UPPER('%{}%') )"
                                    .format(buscar, buscar, buscar)).fetchall()

            return render_template('home.html', libros=libros_rows, buscar=buscar, libros_random=libros_random, scroll='divBuscarLibros')

        return render_template('home.html', libros=libros_rows, libros_random=libros_random)

@app.route("/books/<int:book_id>", methods=['GET', 'POST'])
def book(book_id):

    if session.get("user_id") is None and session.get("user_name") is None:
        return render_template('login.html')
    else:
        usuario_review_row = db.execute("SELECT * FROM review WHERE usuario_id = :user_id and libro_id = :libro_id", {"user_id": session["user_id"], "libro_id": book_id}).fetchone()

        if usuario_review_row is not None:
            show_alert_usuario_review = 1
        else:
            show_alert_usuario_review = 0

        if request.method == 'POST':

            if show_alert_usuario_review is 0:
                detail = request.form.get("detail")
                stars = request.form.get("stars")

                db.execute("INSERT INTO review (detail, stars, libro_id, usuario_id) VALUES (:detail, :stars, :libro_id, :usuario_id)",
                                {"detail": detail, "stars": stars, "libro_id": book_id, "usuario_id": session["user_id"]})
                db.commit()

                show_alert_usuario_review = 1

        libro_row = db.execute("SELECT l.id, l.isbn, l.title, l.year, a.name FROM libro l, autor a WHERE l.autor_id = a.id and l.id = :id", {"id": book_id}).fetchone()
        reviews_rows = db.execute("SELECT r.*, u.user_name FROM review r, usuario u WHERE r.libro_id = :id and r.usuario_id = u.id", {"id": book_id}).fetchall()

        goodreadsApiKey = "tpdr69k3CAh0DA53FqAWw"

        data = requests.get("https://www.goodreads.com/book/review_counts.json?isbns={}&key={}".format(libro_row["isbn"], goodreadsApiKey)).json()
        average_rating = data["books"][0]["average_rating"]
        work_ratings_count = data["books"][0]["work_ratings_count"]

        goodreads_data = {"average_rating": average_rating, "work_ratings_count": work_ratings_count}

        return render_template('book.html', libro=libro_row, reviews=reviews_rows, show_alert_usuario_review=show_alert_usuario_review, goodreads_data=goodreads_data)

@app.route("/api/<isbn>")
def api(isbn):
    libro_row = db.execute("SELECT l.id, l.isbn, l.title, l.year, a.name FROM libro l, autor a WHERE l.autor_id = a.id and l.isbn = :isbn", {"isbn": isbn}).fetchone()
    goodreadsApiKey = "tpdr69k3CAh0DA53FqAWw"
    data = requests.get("https://www.goodreads.com/book/review_counts.json?isbns={}&key={}".format(libro_row["isbn"], goodreadsApiKey)).json()

    show_data = {"title": libro_row["title"], "author": libro_row["name"], "year": libro_row["year"], "isbn": libro_row["isbn"],
                    "review_count": data["books"][0]["reviews_count"], "average_score": data["books"][0]["average_rating"]}

    return jsonify(show_data)
