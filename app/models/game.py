from app.extensions import db
from app.time_utils import now_utc


class GameUserSettings(db.Model):
    __tablename__ = "game_user_settings"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    hands_limit = db.Column(db.Integer, default=3, nullable=False)
    window_minutes = db.Column(db.Integer, default=120, nullable=False)
    ranking_enabled = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("game_settings", uselist=False))
    updater = db.relationship("User", foreign_keys=[updated_by])


class GameUserState(db.Model):
    __tablename__ = "game_user_states"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    points_total = db.Column(db.Integer, default=0, nullable=False)
    hands_played_total = db.Column(db.Integer, default=0, nullable=False)
    current_window_start = db.Column(db.DateTime(timezone=True))
    hands_used_in_window = db.Column(db.Integer, default=0, nullable=False)
    last_played_at = db.Column(db.DateTime(timezone=True))
    streak_current = db.Column(db.Integer, default=0, nullable=False)
    streak_best = db.Column(db.Integer, default=0, nullable=False)
    best_hand_score = db.Column(db.Integer, default=0, nullable=False)
    last_streak_date = db.Column(db.Date)

    user = db.relationship("User", backref=db.backref("game_state", uselist=False))


class GameHand(db.Model):
    __tablename__ = "game_hands"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    dealt_cards_json = db.Column(db.JSON, nullable=False)
    discarded_cards_json = db.Column(db.JSON, nullable=False)
    final_cards_json = db.Column(db.JSON, nullable=False)
    result_name = db.Column(db.String(80), nullable=False)
    base_score = db.Column(db.Integer, default=0, nullable=False)
    bonuses_json = db.Column(db.JSON, default=list, nullable=False)
    multiplier = db.Column(db.Float, default=1.0, nullable=False)
    score = db.Column(db.Integer, nullable=False)
    played_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False, index=True)

    user = db.relationship("User", backref="game_hands")


class GameJoker(db.Model):
    __tablename__ = "game_jokers"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    unlock_rule = db.Column(db.String(160), nullable=False)
    effect_json = db.Column(db.JSON, default=dict, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)


class GameUserJoker(db.Model):
    __tablename__ = "game_user_jokers"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    joker_id = db.Column(db.Integer, db.ForeignKey("game_jokers.id"), nullable=False)
    unlocked_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    equipped_slot = db.Column(db.Integer)

    user = db.relationship("User", backref="game_user_jokers")
    joker = db.relationship("GameJoker")
    __table_args__ = (db.UniqueConstraint("user_id", "joker_id", name="uq_game_user_joker"),)


class GameAchievement(db.Model):
    __tablename__ = "game_achievements"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    condition_key = db.Column(db.String(80), nullable=False)
    points_reward = db.Column(db.Integer, default=0, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)


class GameUserAchievement(db.Model):
    __tablename__ = "game_user_achievements"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    achievement_id = db.Column(db.Integer, db.ForeignKey("game_achievements.id"), nullable=False)
    unlocked_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    user = db.relationship("User", backref="game_user_achievements")
    achievement = db.relationship("GameAchievement")
    __table_args__ = (db.UniqueConstraint("user_id", "achievement_id", name="uq_game_user_achievement"),)
