import random, string, requests, json
from flask import Flask, request, render_template, redirect, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder="./html")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///database.db"
db = SQLAlchemy(app)

exts = ["jpg", "png", "jpeg", "webp"]

vars = json.loads(open("vars.json").read())
owner_code = vars["owner_code"]

def gen_code():
    return "".join(random.choices(string.ascii_letters + string.digits, k=6))

class User(db.Model):
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    permission = db.Column(db.Boolean, nullable=False)

class Image(db.Model):
    code = db.Column(db.String(6), primary_key=True)
    author_id = db.Column(db.BigInteger, db.ForeignKey(User.id), nullable=False)
    title = db.Column(db.String(100))
    filename = db.Column(db.String(12), nullable=False)

    author = db.relationship("User", foreign_keys="Image.author_id")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload")
def upload():
    return render_template("upload.html")

@app.route("/media/<string:file>")
def media_handler(file):
    return send_file(f"./media/{secure_filename(file)}")

@app.route("/<string:code>")
def image_handler(code):
    image = Image.query.filter_by(code=code).first()
    if not image:
        return {"text": "Image doesn't exist!", "error": "image_not_exist"}, 404

    return render_template("image.html", code=image.code, author=image.author.name, title=image.title)

@app.route("/raw/<string:code>")
def raw_image_handler(code):
    image = Image.query.filter_by(code=code).first()
    if not image:
        return {"text": "Image doesn't exist!", "error": "image_not_exist"}, 404

    return send_file(f"./images/{secure_filename(image.filename)}")

@app.route("/api/upload", methods=["POST"])
def api_upload():
    form = request.form

    token = request.headers.get("token")
    if not token or len(token) > 64: 
        return {"text": "Invalid token!", "error": "invalid_token"}, 400
    account = User.query.filter_by(token=token).first()
    if not account:
        return {"text": "Invalid token!", "error": "invalid_token"}, 401
    if not account.permission:
        return {"text": "Unauthorized token!", "error": "unauthorized_token"}, 403

    title = form.get("title")
    if not title:
        title = "Image"
    if len(title) > 100:
        return {"text": "Invalid title!", "error": "invalid_title"}, 400

    file = request.files.get("image")
    ext = file.filename.rsplit(".", 1)[1]
    if not file or ext not in exts:
        return {"text": "Invalid image file!", "error": "invalid_image"}, 400

    code = gen_code()
    while Image.query.filter_by(code=code).first():
        code = gen_code()

    file.save(f"./images/{code}.{ext}")

    db.session.add(Image(code=code, author_id=account.id, title=title, filename=f"{code}.{ext}"))
    db.session.commit()

    return {"text": "Uploaded image!", "code": code, "url": f"https://i.yoshiplex.dev/{code}", "raw": f"https://i.yoshiplex.dev/raw/{code}"}, 200

"""
@app.route("/oauth/callback")
def oauth_callback():
    print("hot dog")

    args = request.args
    if not args:
        return {"text": "Bad request!", "error": "bad_request"}, 400

    token = args.get("token")
    if not token or len(token) > 64: 
        return {"text": "Invalid token!", "error": "invalid_token"}, 400

    response = requests.get(f"https://connext.dev/oauth/user?token={token}")
    data = response.json()
    if response.status_code == 200:
        account = User.query.filter_by(token=token).first()
        if account:
            account.id = data["id"]
            account.name = data["name"]
            account.token = token
        else:
            db.session.add(User(id=data["id"], name=data["name"], token=token))

        db.session.commit()
    else:
        return {"text": "Invalid token!", "error": "invalid_token"}, 401

    return f"<script>localStorage.token = {account.token}; window.location.replace('/')</script>"
"""

@app.route("/api/authorize", methods=["POST"])
def api_authorize():
    json = request.json
    if not json:
        return {"text": "Bad request!", "error": "bad_request"}, 400

    code = json.get("code")
    if not code or len(code) > 64: 
        return {"text": "Invalid owner code!", "error": "invalid_code"}, 400
    elif code != owner_code:
        return {"text": "Invalid owner code!", "error": "invalid_code"}, 401

    id = json.get("id")
    if not id or len(id) > 16: 
        return {"text": "Invalid user ID!", "error": "invalid_user_id"}, 400
    account = User.query.filter_by(id=id).first()
    if not account:
        return {"text": "Invalid user ID!", "error": "invalid_user_id"}, 404

    account.permission = True
    db.session.commit()

    return {"text": "Authorized user to upload images."}, 200

db.create_all()

if __name__ == "__main__":
    app.run()