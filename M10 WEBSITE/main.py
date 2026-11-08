"""Damla damla kurtararak göl oluşur.

Birleşik M10 uygulaması: iklim farkındalığı, eko hesaplayıcı ve günlük.
Kaynak projelerdeki hesaplama ve günlük fikrini tek bir kullanıcı akışında
birleştirir. Veriler, uygulama klasöründeki instance/eco_diary.db dosyasında
yerel olarak saklanır.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, instance_relative_config=True)
app.config.update(
    SECRET_KEY=os.environ.get(
        "DAMLA_SECRET_KEY", "damla-damla-gol-olusur-local-secret"
    ),
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{(INSTANCE_DIR / 'eco_diary.db').as_posix()}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
db = SQLAlchemy(app)


LEVEL_META: dict[str, dict[str, str]] = {
    "low": {
        "label": "Düşük elektrik etkisi",
        "short": "Az",
        "tone": "good",
        "image": "planet_good.svg",
        "description": "Günlük elektrik seçimlerin oldukça verimli görünüyor.",
    },
    "medium": {
        "label": "Orta elektrik etkisi",
        "short": "Orta",
        "tone": "medium",
        "image": "planet_medium.svg",
        "description": "Birkaç küçük değişiklikle etkini daha da azaltabilirsin.",
    },
    "high": {
        "label": "Yüksek elektrik etkisi",
        "short": "Çok",
        "tone": "high",
        "image": "planet_bad.svg",
        "description": "Enerji kullanımında öncelikli birkaç fırsat alanı var.",
    },
}


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(180), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    assessments = db.relationship(
        "Assessment",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Assessment.created_at",
    )
    cards = db.relationship(
        "Card", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Assessment(db.Model):
    __tablename__ = "assessment"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    follow_up_at = db.Column(db.DateTime, nullable=False)
    home_size = db.Column(db.Integer, nullable=False)
    lights = db.Column(db.Integer, nullable=False)
    devices = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Float, nullable=False)
    level = db.Column(db.String(20), nullable=False)
    strengths_json = db.Column(db.Text, nullable=False, default="[]")
    suggestions_json = db.Column(db.Text, nullable=False, default="[]")
    summary = db.Column(db.Text, nullable=False, default="")
    is_followup = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", back_populates="assessments")
    card = db.relationship(
        "Card", back_populates="assessment", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def strengths(self) -> list[str]:
        return _json_list(self.strengths_json)

    @property
    def suggestions(self) -> list[str]:
        return _json_list(self.suggestions_json)

    @property
    def meta(self) -> dict[str, str]:
        return LEVEL_META.get(self.level, LEVEL_META["medium"])


class Card(db.Model):
    """Günlük kartı.

    Bu model, diary-tur-main'deki Card fikrini korur; artık her test sonucu
    otomatik olarak bir günlük kartına dönüşür. Manuel notlar da eklenebilir.
    """

    __tablename__ = "card"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    assessment_id = db.Column(
        db.Integer, db.ForeignKey("assessment.id"), nullable=True, unique=True
    )
    title = db.Column(db.String(140), nullable=False)
    subtitle = db.Column(db.String(240), nullable=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="cards")
    assessment = db.relationship("Assessment", back_populates="card")


def _json_list(value: str | None) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _dump(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=False)


def result_calculate(size: int, lights: int, device: int) -> float:
    """Kaynak TUR_Calculator formülünü koruyan toplam tüketim puanı."""

    home_coef = 100
    light_coef = 0.04
    devices_coef = 5
    return round(size * home_coef + lights * light_coef + device * devices_coef, 2)


def level_for(score: float) -> str:
    if score <= 150:
        return "low"
    if score < 300:
        return "medium"
    return "high"


def make_feedback(size: int, lights: int, devices: int, score: float) -> tuple[list[str], list[str], str]:
    strengths: list[str] = []
    suggestions: list[str] = []

    if size == 1:
        strengths.append("Yaşam alanını ihtiyacına uygun, kompakt kullanıyorsun.")
    elif size == 2:
        strengths.append("Orta büyüklükteki alanını dengeli kullanma fırsatın var.")
    else:
        suggestions.append("Kullanılmayan odaların ışık ve ısıtmasını kapatmayı dene.")

    if lights <= 3:
        strengths.append("Aydınlatma sayın düşük; bu iyi bir başlangıç.")
    elif lights <= 7:
        suggestions.append("Boş odalarda ışığı kapat ve mümkünse LED ampule geç.")
    else:
        suggestions.append("Gün ışığını daha çok kullanıp gereksiz lambaları azalt.")

    if devices <= 4:
        strengths.append("Bağlı cihaz sayını sınırlı tutuyorsun.")
    elif devices <= 7:
        suggestions.append("Kullanmadığın cihazları bekleme modunda bırakmamaya çalış.")
    else:
        suggestions.append("Şarj aletlerini ve çoklu prizleri işin bitince kapat.")

    if score <= 150:
        suggestions.append("Bu alışkanlıklarını koru ve çevrendeki bir kişiye de aktar.")
    elif score < 300:
        suggestions.append("Önümüzdeki hafta tek bir alışkanlık seçip her gün takip et.")
    else:
        suggestions.append("Önce en çok kullandığın cihazı belirle; değişimi oradan başlat.")

    # Kartın kısa özetini, üç öneriyi de kapsayacak şekilde oluşturuyoruz.
    summary = f"Elektrik etkin {LEVEL_META[level_for(score)]['short'].lower()} düzeyde. "
    summary += suggestions[0] if suggestions else "İyi alışkanlıklarını sürdür."
    return strengths[:3], suggestions[:3], summary


QUESTION_DATA: dict[str, dict[str, Any]] = {
    "size": {
        "step": 2,
        "eyebrow": "Yaşam alanın",
        "title": "Evindeki yaşam alanı nasıl?",
        "description": "Yaklaşık seçmen yeterli; sonuç bir farkındalık pusulası.",
        "field": "home_size",
        "options": [
            {
                "value": 1,
                "label": "Küçük bir ev",
                "detail": "1–2 odalı yaşam alanı",
                "icon": "home.svg",
            },
            {
                "value": 2,
                "label": "Orta büyüklükte",
                "detail": "3–4 odalı yaşam alanı",
                "icon": "home.svg",
            },
            {
                "value": 3,
                "label": "Büyük bir ev",
                "detail": "5+ odalı yaşam alanı",
                "icon": "home.svg",
            },
        ],
    },
    "lights": {
        "step": 3,
        "eyebrow": "Aydınlatma",
        "title": "Evinde yaklaşık kaç lamba var?",
        "description": "Sık kullandığın lambaları da düşünerek en yakın seçeneği işaretle.",
        "field": "lights",
        "options": [
            {"value": 3, "label": "2–4 lamba", "detail": "Az aydınlatma noktası", "icon": "light.svg"},
            {"value": 7, "label": "4–6 lamba", "detail": "Orta aydınlatma", "icon": "light.svg"},
            {"value": 10, "label": "8+ lamba", "detail": "Çok sayıda aydınlatma", "icon": "light.svg"},
        ],
    },
    "devices": {
        "step": 4,
        "eyebrow": "Elektronik cihazlar",
        "title": "Kaç elektrikli cihaz kullanıyorsun?",
        "description": "Telefon, bilgisayar, TV ve mutfak cihazlarını birlikte düşün.",
        "field": "devices",
        "options": [
            {"value": 4, "label": "3–5 cihaz", "detail": "Temel cihazlar", "icon": "battery.svg"},
            {"value": 7, "label": "6–8 cihaz", "detail": "Orta kullanım", "icon": "battery.svg"},
            {"value": 10, "label": "10+ cihaz", "detail": "Yoğun kullanım", "icon": "battery.svg"},
        ],
    },
}


def _parse_choice(field: str, allowed: set[int]) -> int | None:
    try:
        value = int(request.form.get(field, ""))
    except (TypeError, ValueError):
        return None
    return value if value in allowed else None


def _current_user() -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def _format_date(value: datetime | None, include_time: bool = False) -> str:
    if not value:
        return ""
    if include_time:
        return value.strftime("%d.%m.%Y %H:%M")
    return value.strftime("%d.%m.%Y")


@app.template_filter("trdate")
def trdate(value: datetime | None) -> str:
    return _format_date(value)


@app.template_filter("trdatetime")
def trdatetime(value: datetime | None) -> str:
    return _format_date(value, include_time=True)


@app.context_processor
def inject_globals() -> dict[str, Any]:
    return {
        "level_meta": LEVEL_META,
        "current_user": _current_user(),
        "year": datetime.now().year,
    }


@app.route("/")
def index():
    user = _current_user()
    latest = None
    if user:
        latest = (
            Assessment.query.filter_by(user_id=user.id)
            .order_by(Assessment.created_at.desc())
            .first()
        )
    return render_template("index.html", latest=latest)


@app.route("/start", methods=["GET", "POST"])
@app.route("/test", methods=["GET", "POST"])
def start():
    followup_requested = request.args.get("followup") == "1" or request.form.get("followup") == "1"
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()

        if len(first_name) < 2 or len(last_name) < 2:
            flash("Lütfen adını ve soyadını en az iki harfle yaz.", "error")
            return render_template("start.html", followup=followup_requested)
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Geçerli bir e-posta adresi yazmalısın.", "error")
            return render_template("start.html", followup=followup_requested)

        user = User.query.filter_by(email=email).first()
        returning = user is not None
        if user is None:
            user = User(first_name=first_name, last_name=last_name, email=email)
            db.session.add(user)
            db.session.flush()
        else:
            # E-posta geçmişin için anahtar; isim değiştiyse profilini güncelle.
            user.first_name = first_name
            user.last_name = last_name

        session["user_id"] = user.id
        session["returning"] = returning
        session["followup"] = bool(followup_requested and returning)
        session["assessment_answers"] = {}
        db.session.commit()

        if returning and not followup_requested:
            flash("Tekrar hoş geldin! Yeni sonucunu önceki kayıtlarınla karşılaştıracağız.", "success")
        elif returning and followup_requested:
            flash("Takip testi başladı. Geçen haftaki alışkanlıklarınla karşılaştıracağız.", "success")
        else:
            flash("İlk adım tamam. Şimdi evinin enerji fotoğrafını çıkaralım.", "success")
        return redirect(url_for("question", kind="size"))

    return render_template("start.html", followup=followup_requested)


@app.route("/question/<kind>", methods=["GET", "POST"])
def question(kind: str):
    if kind not in QUESTION_DATA:
        abort(404)
    if not session.get("user_id"):
        return redirect(url_for("start"))

    config = QUESTION_DATA[kind]
    answers = dict(session.get("assessment_answers", {}))
    if request.method == "POST":
        allowed = {int(option["value"]) for option in config["options"]}
        value = _parse_choice(config["field"], allowed)
        if value is None:
            flash("Devam etmek için seçeneklerden birini işaretle.", "error")
        else:
            answers[config["field"]] = value
            session["assessment_answers"] = answers
            next_kind = {"size": "lights", "lights": "devices"}.get(kind)
            if next_kind:
                return redirect(url_for("question", kind=next_kind))
            return redirect(url_for("finish_assessment"))

    return render_template(
        "question.html",
        config=config,
        kind=kind,
        selected=answers.get(config["field"]),
    )


@app.route("/finish", methods=["GET"])
def finish_assessment():
    user = _current_user()
    answers = session.get("assessment_answers", {})
    if user is None or not all(key in answers for key in ("home_size", "lights", "devices")):
        flash("Üç soruya da cevap ver, kişisel sonucunu hazırlayalım.", "error")
        return redirect(url_for("question", kind="size"))

    previous = (
        Assessment.query.filter_by(user_id=user.id)
        .order_by(Assessment.created_at.desc())
        .first()
    )
    score = result_calculate(
        int(answers["home_size"]), int(answers["lights"]), int(answers["devices"])
    )
    level = level_for(score)
    strengths, suggestions, summary = make_feedback(
        int(answers["home_size"]), int(answers["lights"]), int(answers["devices"]), score
    )
    created_at = datetime.utcnow()
    assessment = Assessment(
        user_id=user.id,
        created_at=created_at,
        follow_up_at=created_at + timedelta(days=7),
        home_size=int(answers["home_size"]),
        lights=int(answers["lights"]),
        devices=int(answers["devices"]),
        score=score,
        level=level,
        strengths_json=_dump(strengths),
        suggestions_json=_dump(suggestions),
        summary=summary,
        is_followup=bool(session.get("followup")),
    )
    db.session.add(assessment)
    db.session.flush()

    card_text = (
        f"{summary}\n\nGüçlü olduğun alanlar:\n- "
        + "\n- ".join(strengths)
        + "\n\nÖnümüzdeki hafta için önerilerin:\n- "
        + "\n- ".join(suggestions)
    )
    card = Card(
        user_id=user.id,
        assessment_id=assessment.id,
        title=f"{LEVEL_META[level]['short']} elektrik etkisi · {score:g} puan",
        subtitle=f"{_format_date(created_at)} · {'Takip testi' if assessment.is_followup else 'İlk test'}",
        text=card_text,
    )
    db.session.add(card)
    db.session.commit()

    session.pop("assessment_answers", None)
    session.pop("followup", None)
    session["last_assessment_id"] = assessment.id
    return redirect(url_for("result", assessment_id=assessment.id))


@app.route("/result/<int:assessment_id>")
def result(assessment_id: int):
    user = _current_user()
    assessment = db.session.get(Assessment, assessment_id)
    if user is None or assessment is None or assessment.user_id != user.id:
        abort(404)
    previous = (
        Assessment.query.filter(
            Assessment.user_id == user.id, Assessment.id != assessment.id,
            Assessment.created_at <= assessment.created_at,
        )
        .order_by(Assessment.created_at.desc())
        .first()
    )
    delta = None
    if previous:
        delta = round(assessment.score - previous.score, 2)
    return render_template("result.html", assessment=assessment, previous=previous, delta=delta)


@app.route("/dashboard")
@app.route("/progress")
def dashboard():
    user = _current_user()
    if user is None:
        return redirect(url_for("start"))
    history = (
        Assessment.query.filter_by(user_id=user.id)
        .order_by(Assessment.created_at.desc())
        .all()
    )
    latest = history[0] if history else None
    baseline = history[-1] if history else None
    delta = round(latest.score - baseline.score, 2) if latest and baseline and latest.id != baseline.id else None
    due = latest is not None and datetime.utcnow() >= latest.follow_up_at
    return render_template(
        "dashboard.html",
        history=history,
        latest=latest,
        baseline=baseline,
        delta=delta,
        due=due,
    )


@app.route("/followup/<int:user_id>")
def followup(user_id: int):
    user = _current_user()
    if user is None or user.id != user_id:
        return redirect(url_for("start", followup=1))
    session["followup"] = True
    session["assessment_answers"] = {}
    return redirect(url_for("question", kind="size"))


@app.route("/diary")
def diary():
    user = _current_user()
    if user is None:
        return redirect(url_for("start"))
    cards = Card.query.filter_by(user_id=user.id).order_by(Card.created_at.desc()).all()
    return render_template("diary.html", cards=cards)


@app.route("/card/<int:card_id>")
def card(card_id: int):
    user = _current_user()
    entry = db.session.get(Card, card_id)
    if user is None or entry is None or entry.user_id != user.id:
        abort(404)
    return render_template("card.html", card=entry)


@app.route("/create", methods=["GET", "POST"])
@app.route("/diary/create", methods=["GET", "POST"])
def create():
    user = _current_user()
    if user is None:
        return redirect(url_for("start"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        subtitle = request.form.get("subtitle", "").strip()
        text = request.form.get("text", "").strip()
        if not title or not text:
            flash("Başlık ve not alanı boş bırakılamaz.", "error")
            return render_template("create_card.html")
        entry = Card(user_id=user.id, title=title, subtitle=subtitle, text=text)
        db.session.add(entry)
        db.session.commit()
        flash("Notun günlüğe eklendi.", "success")
        return redirect(url_for("diary"))
    return render_template("create_card.html")


@app.route("/form_create", methods=["POST"])
def form_create():
    return create()


@app.route("/logout")
def logout():
    session.clear()
    flash("Görüşmek üzere! Yeni bir test için istediğin zaman dönebilirsin.", "success")
    return redirect(url_for("index"))


def init_db() -> None:
    with app.app_context():
        db.create_all()


init_db()


if __name__ == "__main__":
    app.run(debug=True)
