import os
import secrets
import uuid
from urllib.parse import urljoin, urlparse

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf.csrf import CSRFProtect

from models import STATUS_AVAILABLE, STATUS_DONE, Item, User, db

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_PRICE = 100_000_000
ITEMS_PER_PAGE = 12

os.makedirs(INSTANCE_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def load_secret_key():
    """환경변수 SECRET_KEY가 없으면 instance/secret_key에 한 번 생성해 재사용한다."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    key_path = os.path.join(INSTANCE_DIR, "secret_key")
    if not os.path.exists(key_path):
        with open(key_path, "w") as f:
            f.write(secrets.token_hex(32))
    with open(key_path) as f:
        return f.read().strip()


app = Flask(__name__)
app.config.update(
    SECRET_KEY=load_secret_key(),
    SQLALCHEMY_DATABASE_URI="sqlite:///"
    + os.path.join(INSTANCE_DIR, "anabada.db").replace("\\", "/"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # 업로드 최대 5MB
)

db.init_app(app)
CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "로그인이 필요한 서비스입니다."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


with app.app_context():
    db.create_all()


# ---------------------------------------------------------------- 유틸

def is_safe_redirect(target):
    """로그인 후 next 파라미터가 같은 사이트 내부 주소인지 검사 (open redirect 방지)."""
    if not target:
        return False
    host = urlparse(request.host_url)
    dest = urlparse(urljoin(request.host_url, target))
    return dest.scheme in ("http", "https") and host.netloc == dest.netloc


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file):
    """업로드된 이미지를 uuid 파일명으로 저장하고 파일명을 반환한다.

    한글 파일명은 secure_filename 처리 시 사라지므로 원본 이름은 확장자만 사용한다.
    """
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_DIR, filename))
    return filename


def delete_image(filename):
    if not filename:
        return
    path = os.path.join(UPLOAD_DIR, os.path.basename(filename))
    if os.path.isfile(path):
        os.remove(path)


def parse_item_form(form, files):
    """물품 폼을 검증한다. (cleaned, image_file, errors) 반환."""
    errors = []
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    is_free = form.get("is_free") == "on"
    price_raw = form.get("price", "").strip()
    price = 0

    if not title:
        errors.append("제목을 입력해 주세요.")
    elif len(title) > 100:
        errors.append("제목은 100자 이내로 입력해 주세요.")
    if not description:
        errors.append("상세 설명을 입력해 주세요.")

    if not is_free:
        if price_raw == "":
            errors.append("가격을 입력하거나 '무료 나눔'을 선택해 주세요.")
        else:
            try:
                price = int(price_raw)
            except ValueError:
                errors.append("가격은 숫자로 입력해 주세요.")
            else:
                if price < 0:
                    errors.append("가격은 0 이상이어야 합니다.")
                elif price > MAX_PRICE:
                    errors.append(f"가격은 {MAX_PRICE:,}원 이하로 입력해 주세요.")

    image = files.get("image")
    if image and image.filename:
        if not allowed_file(image.filename):
            errors.append("이미지는 png, jpg, jpeg, gif, webp 형식만 업로드할 수 있습니다.")
    else:
        image = None

    cleaned = {
        "title": title,
        "description": description,
        "price": 0 if is_free else price,
    }
    return cleaned, image, errors


def get_owned_item_or_403(item_id):
    item = db.get_or_404(Item, item_id)
    if item.author_id != current_user.id:
        abort(403)
    return item


# ---------------------------------------------------------------- 물품

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    free_only = request.args.get("free") == "1"
    page = request.args.get("page", 1, type=int)

    query = Item.query
    if q:
        like = f"%{q}%"
        query = query.filter(Item.title.ilike(like) | Item.description.ilike(like))
    if free_only:
        query = query.filter(Item.price == 0)

    pagination = db.paginate(
        query.order_by(Item.created_at.desc()),
        page=page,
        per_page=ITEMS_PER_PAGE,
        error_out=False,
    )
    return render_template(
        "index.html", pagination=pagination, q=q, free_only=free_only
    )


@app.route("/items/<int:item_id>")
def item_detail(item_id):
    item = db.get_or_404(Item, item_id)
    return render_template("item_detail.html", item=item)


@app.route("/items/new", methods=["GET", "POST"])
@login_required
def item_create():
    if request.method == "POST":
        cleaned, image, errors = parse_item_form(request.form, request.files)
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            item = Item(author_id=current_user.id, **cleaned)
            if image:
                item.image_filename = save_image(image)
            db.session.add(item)
            db.session.commit()
            flash("물품이 등록되었습니다.", "success")
            return redirect(url_for("item_detail", item_id=item.id))
        form = request.form
    else:
        form = {}
    return render_template("item_form.html", form=form, item=None)


@app.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def item_edit(item_id):
    item = get_owned_item_or_403(item_id)

    if request.method == "POST":
        cleaned, image, errors = parse_item_form(request.form, request.files)
        if errors:
            for e in errors:
                flash(e, "danger")
            form = request.form
        else:
            item.title = cleaned["title"]
            item.description = cleaned["description"]
            item.price = cleaned["price"]

            old_image = item.image_filename
            if image:
                item.image_filename = save_image(image)
                delete_image(old_image)
            elif request.form.get("remove_image") == "on":
                item.image_filename = None
                delete_image(old_image)

            db.session.commit()
            flash("물품 정보가 수정되었습니다.", "success")
            return redirect(url_for("item_detail", item_id=item.id))
    else:
        form = {
            "title": item.title,
            "description": item.description,
            "price": item.price if not item.is_free else "",
            "is_free": "on" if item.is_free else "",
        }
    return render_template("item_form.html", form=form, item=item)


@app.route("/items/<int:item_id>/delete", methods=["POST"])
@login_required
def item_delete(item_id):
    item = get_owned_item_or_403(item_id)
    delete_image(item.image_filename)
    db.session.delete(item)
    db.session.commit()
    flash("물품이 삭제되었습니다.", "info")
    return redirect(url_for("index"))


@app.route("/items/<int:item_id>/status", methods=["POST"])
@login_required
def item_toggle_status(item_id):
    item = get_owned_item_or_403(item_id)
    item.status = STATUS_AVAILABLE if item.is_done else STATUS_DONE
    db.session.commit()
    flash(f"상태가 '{item.status_label}'(으)로 변경되었습니다.", "success")
    return redirect(url_for("item_detail", item_id=item.id))


# ---------------------------------------------------------------- 회원

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        errors = []
        if not 2 <= len(username) <= 20:
            errors.append("사용자 이름은 2~20자로 입력해 주세요.")
        if len(password) < 6:
            errors.append("비밀번호는 6자 이상이어야 합니다.")
        if password != password2:
            errors.append("비밀번호 확인이 일치하지 않습니다.")
        if not errors and User.query.filter_by(username=username).first():
            errors.append("이미 사용 중인 사용자 이름입니다.")

        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("회원가입이 완료되었습니다. 로그인해 주세요.", "success")
            return redirect(url_for("login"))
    return render_template("register.html", username=username)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=request.form.get("remember") == "on")
            flash(f"{user.username}님, 환영합니다!", "success")
            next_url = request.args.get("next")
            return redirect(next_url if is_safe_redirect(next_url) else url_for("index"))
        flash("사용자 이름 또는 비밀번호가 올바르지 않습니다.", "danger")
    return render_template("login.html", username=username)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("로그아웃되었습니다.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------- 에러

@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


@app.errorhandler(403)
def forbidden(_):
    flash("해당 작업을 수행할 권한이 없습니다.", "danger")
    return redirect(url_for("index"))


@app.errorhandler(413)
def too_large(_):
    flash("이미지 용량은 5MB 이하여야 합니다.", "danger")
    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
