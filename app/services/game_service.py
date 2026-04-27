import random
from collections import Counter
from datetime import timedelta, timezone

from sqlalchemy import desc, func

from app.extensions import db
from app.models import (
    GameAchievement,
    GameHand,
    GameJoker,
    GameUserAchievement,
    GameUserJoker,
    GameUserSettings,
    GameUserState,
    Area,
    User,
)
from app.time_utils import format_datetime_ar, now_utc, utc_to_local

SUITS = ("S", "H", "D", "C")
RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
SUIT_LABELS = {"S": "Picas", "H": "Corazones", "D": "Diamantes", "C": "Treboles"}
SUIT_SYMBOLS = {"S": "\u2660", "H": "\u2665", "D": "\u2666", "C": "\u2663"}
RANK_VALUES = {rank: index + 2 for index, rank in enumerate(RANKS)}

SCORES = {
    "Carta alta": 5,
    "Par": 10,
    "Doble par": 20,
    "Trio": 35,
    "Escalera": 50,
    "Color": 65,
    "Full": 90,
    "Poker": 140,
    "Escalera color": 220,
}

DEFAULT_JOKERS = [
    {
        "code": "rtu_estable",
        "name": "RTU estable",
        "description": "+8 puntos si no descartas cartas.",
        "unlock_rule": "Disponible desde el inicio.",
        "effect": {"type": "no_discard_bonus", "amount": 8},
    },
    {
        "code": "rele_sensible",
        "name": "Rele sensible",
        "description": "+12 puntos si la mano tiene al menos un par.",
        "unlock_rule": "Disponible desde el inicio.",
        "effect": {"type": "pair_bonus", "amount": 12},
    },
    {
        "code": "fibra_cortada",
        "name": "Fibra cortada",
        "description": "x1.25 si descartas 3 o mas cartas.",
        "unlock_rule": "Juga 5 manos.",
        "effect": {"type": "big_discard_multiplier", "amount": 0.25},
    },
    {
        "code": "scada_bendecido",
        "name": "SCADA bendecido",
        "description": "+25 puntos con Color, Full, Poker o Escalera color.",
        "unlock_rule": "Alcanza 150 puntos ficticios.",
        "effect": {"type": "premium_bonus", "amount": 25},
    },
    {
        "code": "telecontrol_sincronizado",
        "name": "Telecontrol sincronizado",
        "description": "x1.30 en escaleras.",
        "unlock_rule": "Logra una Escalera.",
        "effect": {"type": "straight_multiplier", "amount": 0.30},
    },
    {
        "code": "cmd_preciso",
        "name": "CMD preciso",
        "description": "+10 puntos si la mano final tiene un As.",
        "unlock_rule": "Juga 10 manos.",
        "effect": {"type": "ace_bonus", "amount": 10},
    },
]

DEFAULT_ACHIEVEMENTS = [
    ("par_guardia", "Par de guardia", "Consegui un Par.", "pair", 5),
    ("derivador_compulsivo", "Derivador compulsivo", "Descarta 4 o mas cartas en una mano.", "big_discard", 7),
    ("full_protecciones", "Full de Protecciones", "Consegui un Full.", "full", 20),
    ("escalera_iec", "Escalera IEC 61850", "Consegui una Escalera.", "straight", 15),
    ("rtu_zen", "RTU zen", "Puntua una mano sin descartar.", "no_discard", 8),
    ("scada_bendecido", "SCADA bendecido", "Consegui Color o mejor.", "flush_or_better", 18),
    ("operador_nocturno", "Operador nocturno", "Juga entre las 00:00 y las 05:59.", "night", 12),
    ("poker_campo", "Poker de campo", "Consegui Poker.", "poker", 35),
    ("rele_sin_falsa", "Rele sin falsa operacion", "Llega a una racha de 5.", "streak_5", 20),
]


class GameLimitError(ValueError):
    pass


def serialize_card(rank, suit):
    return {"id": f"{rank}{suit}", "rank": rank, "suit": suit, "symbol": SUIT_SYMBOLS[suit], "label": f"{rank} de {SUIT_LABELS[suit]}"}


def build_deck():
    return [serialize_card(rank, suit) for suit in SUITS for rank in RANKS]


def get_settings(user, create=True):
    settings = GameUserSettings.query.get(user.id)
    if settings is None and create:
        settings = GameUserSettings(user_id=user.id, enabled=True, hands_limit=3, window_minutes=120, ranking_enabled=True)
        db.session.add(settings)
        db.session.flush()
    return settings


def get_state(user, create=True):
    state = GameUserState.query.get(user.id)
    if state is None and create:
        state = GameUserState(user_id=user.id, points_total=0, hands_played_total=0, hands_used_in_window=0)
        db.session.add(state)
        db.session.flush()
    return state


def as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_window(state, settings):
    now = now_utc()
    window_start = as_utc(state.current_window_start)
    if window_start is None or window_start + timedelta(minutes=settings.window_minutes) <= now:
        state.current_window_start = now
        state.hands_used_in_window = 0
    elif window_start != state.current_window_start:
        state.current_window_start = window_start
    return state


def ensure_seed_catalogs():
    for item in DEFAULT_JOKERS:
        joker = GameJoker.query.filter_by(code=item["code"]).first()
        if joker is None:
            db.session.add(GameJoker(code=item["code"], name=item["name"], description=item["description"], unlock_rule=item["unlock_rule"], effect_json=item["effect"], active=True))
        else:
            joker.name = item["name"]
            joker.description = item["description"]
            joker.unlock_rule = item["unlock_rule"]
            joker.effect_json = item["effect"]
            joker.active = True
    for code, name, description, condition_key, reward in DEFAULT_ACHIEVEMENTS:
        achievement = GameAchievement.query.filter_by(code=code).first()
        if achievement is None:
            db.session.add(GameAchievement(code=code, name=name, description=description, condition_key=condition_key, points_reward=reward, active=True))
        else:
            achievement.name = name
            achievement.description = description
            achievement.condition_key = condition_key
            achievement.points_reward = reward
            achievement.active = True


def unlocked_joker_codes(state, last_result_name=None):
    codes = {"rtu_estable", "rele_sensible"}
    if state.hands_played_total >= 5:
        codes.add("fibra_cortada")
    if state.points_total >= 150:
        codes.add("scada_bendecido")
    if state.hands_played_total >= 10:
        codes.add("cmd_preciso")
    if last_result_name == "Escalera" or state.best_hand_score >= SCORES["Escalera"]:
        codes.add("telecontrol_sincronizado")
    return codes


def sync_unlocked_jokers(user, last_result_name=None):
    ensure_seed_catalogs()
    state = get_state(user)
    existing = {row.joker.code for row in GameUserJoker.query.filter_by(user_id=user.id).join(GameJoker).all()}
    for code in unlocked_joker_codes(state, last_result_name) - existing:
        joker = GameJoker.query.filter_by(code=code, active=True).first()
        if joker:
            db.session.add(GameUserJoker(user_id=user.id, joker_id=joker.id))
    db.session.flush()


def joker_payload(user):
    sync_unlocked_jokers(user)
    owned = GameUserJoker.query.filter_by(user_id=user.id).join(GameJoker).order_by(GameJoker.name).all()
    equipped = {row.equipped_slot: row.joker.code for row in owned if row.equipped_slot}
    return {
        "equipped": equipped,
        "items": [
            {
                "code": row.joker.code,
                "name": row.joker.name,
                "description": row.joker.description,
                "unlock_rule": row.joker.unlock_rule,
                "equipped_slot": row.equipped_slot,
            }
            for row in owned
        ],
    }


def equipped_jokers(user):
    sync_unlocked_jokers(user)
    return [row.joker for row in GameUserJoker.query.filter(GameUserJoker.user_id == user.id, GameUserJoker.equipped_slot != None).join(GameJoker).order_by(GameUserJoker.equipped_slot).all()]


def equip_joker(user, joker_code, slot):
    if slot not in (1, 2):
        raise ValueError("Slot invalido.")
    sync_unlocked_jokers(user)
    target = GameUserJoker.query.filter_by(user_id=user.id).join(GameJoker).filter(GameJoker.code == joker_code).first()
    if not target:
        raise ValueError("Ese comodin todavia no esta desbloqueado.")
    GameUserJoker.query.filter_by(user_id=user.id, equipped_slot=slot).update({"equipped_slot": None})
    if target.equipped_slot == slot:
        target.equipped_slot = None
    else:
        target.equipped_slot = slot
    db.session.commit()
    return joker_payload(user)


def achievement_payload(user):
    rows = GameUserAchievement.query.filter_by(user_id=user.id).join(GameAchievement).order_by(GameUserAchievement.unlocked_at.desc()).all()
    return [
        {
            "code": row.achievement.code,
            "name": row.achievement.name,
            "description": row.achievement.description,
            "points_reward": row.achievement.points_reward,
            "unlocked_at": format_datetime_ar(row.unlocked_at),
        }
        for row in rows
    ]


def status_for(user):
    settings = get_settings(user)
    state = normalize_window(get_state(user), settings)
    sync_unlocked_jokers(user)
    remaining = max(settings.hands_limit - state.hands_used_in_window, 0) if settings.enabled else 0
    resets_at = as_utc(state.current_window_start) + timedelta(minutes=settings.window_minutes) if state.current_window_start else None
    db.session.commit()
    return {
        "enabled": settings.enabled,
        "ranking_enabled": settings.ranking_enabled,
        "hands_limit": settings.hands_limit,
        "window_minutes": settings.window_minutes,
        "points_total": state.points_total,
        "hands_played_total": state.hands_played_total,
        "hands_used_in_window": state.hands_used_in_window,
        "hands_remaining": remaining,
        "window_start": format_datetime_ar(state.current_window_start),
        "resets_at": format_datetime_ar(resets_at),
        "streak_current": state.streak_current,
        "streak_best": state.streak_best,
        "best_hand_score": state.best_hand_score,
        "jokers": joker_payload(user),
        "achievements": achievement_payload(user),
    }


def ensure_can_play(user):
    settings = get_settings(user)
    state = normalize_window(get_state(user), settings)
    if not settings.enabled:
        raise GameLimitError("El juego no esta habilitado para tu usuario.")
    if state.hands_used_in_window >= settings.hands_limit:
        resets_at = as_utc(state.current_window_start) + timedelta(minutes=settings.window_minutes)
        raise GameLimitError(f"No quedan manos disponibles. Se renuevan el {format_datetime_ar(resets_at)}.")
    return settings, state


def deal_hand(user):
    ensure_can_play(user)
    deck = build_deck()
    random.SystemRandom().shuffle(deck)
    return deck[:5]


def card_ids(cards):
    return {card["id"] for card in cards}


def replace_cards(dealt_cards, discarded_ids):
    if len(discarded_ids) > 5:
        raise ValueError("No se pueden descartar mas de 5 cartas.")
    discarded_ids = set(discarded_ids)
    dealt_ids = card_ids(dealt_cards)
    if not discarded_ids.issubset(dealt_ids):
        raise ValueError("El descarte contiene cartas invalidas.")
    deck = [card for card in build_deck() if card["id"] not in dealt_ids]
    random.SystemRandom().shuffle(deck)
    kept = [card for card in dealt_cards if card["id"] not in discarded_ids]
    return kept + deck[: len(discarded_ids)], [card for card in dealt_cards if card["id"] in discarded_ids]


def is_straight(values):
    unique = sorted(set(values))
    if len(unique) != 5:
        return False
    if unique == [2, 3, 4, 5, 14]:
        return True
    return unique[-1] - unique[0] == 4


def evaluate_hand(cards):
    values = [RANK_VALUES[card["rank"]] for card in cards]
    suits = [card["suit"] for card in cards]
    counts = sorted(Counter(values).values(), reverse=True)
    straight = is_straight(values)
    flush = len(set(suits)) == 1

    if straight and flush:
        name = "Escalera color"
    elif counts == [4, 1]:
        name = "Poker"
    elif counts == [3, 2]:
        name = "Full"
    elif flush:
        name = "Color"
    elif straight:
        name = "Escalera"
    elif counts == [3, 1, 1]:
        name = "Trio"
    elif counts == [2, 2, 1]:
        name = "Doble par"
    elif counts == [2, 1, 1, 1]:
        name = "Par"
    else:
        name = "Carta alta"
    return name, SCORES[name]


def thematic_bonuses(result_name, dealt_cards, discarded_cards, final_cards, state):
    bonuses = []
    if not discarded_cards:
        bonuses.append({"name": "RTU estable", "amount": 6, "kind": "bonus"})
    if result_name in ("Par", "Doble par", "Trio", "Full", "Poker"):
        bonuses.append({"name": "Rele sensible", "amount": 8, "kind": "bonus"})
    if len(discarded_cards) >= 3:
        bonuses.append({"name": "Fibra cortada", "amount": 10, "kind": "bonus"})
    if result_name in ("Color", "Full", "Poker", "Escalera color"):
        bonuses.append({"name": "SCADA bendecido", "amount": 18, "kind": "bonus"})
    if result_name in ("Escalera", "Escalera color"):
        bonuses.append({"name": "Telecontrol sincronizado", "amount": 0.20, "kind": "multiplier"})
    if result_name in ("Trio", "Full", "Poker", "Escalera color"):
        bonuses.append({"name": "Proteccion selectiva", "amount": 12, "kind": "bonus"})
    if discarded_cards:
        bonuses.append({"name": "Comunicacion restablecida", "amount": 5, "kind": "bonus"})
    if any(card["rank"] == "A" for card in final_cards):
        bonuses.append({"name": "CMD preciso", "amount": 0.10, "kind": "multiplier"})
    if state.streak_current >= 3:
        bonuses.append({"name": "Racha operativa", "amount": min(0.05 * state.streak_current, 0.35), "kind": "multiplier"})
    return bonuses


def apply_jokers(user, result_name, discarded_cards, final_cards):
    bonuses = []
    for joker in equipped_jokers(user):
        effect = joker.effect_json or {}
        effect_type = effect.get("type")
        amount = effect.get("amount", 0)
        if effect_type == "no_discard_bonus" and not discarded_cards:
            bonuses.append({"name": joker.name, "amount": amount, "kind": "bonus"})
        elif effect_type == "pair_bonus" and result_name in ("Par", "Doble par", "Trio", "Full", "Poker"):
            bonuses.append({"name": joker.name, "amount": amount, "kind": "bonus"})
        elif effect_type == "big_discard_multiplier" and len(discarded_cards) >= 3:
            bonuses.append({"name": joker.name, "amount": amount, "kind": "multiplier"})
        elif effect_type == "premium_bonus" and result_name in ("Color", "Full", "Poker", "Escalera color"):
            bonuses.append({"name": joker.name, "amount": amount, "kind": "bonus"})
        elif effect_type == "straight_multiplier" and result_name in ("Escalera", "Escalera color"):
            bonuses.append({"name": joker.name, "amount": amount, "kind": "multiplier"})
        elif effect_type == "ace_bonus" and any(card["rank"] == "A" for card in final_cards):
            bonuses.append({"name": joker.name, "amount": amount, "kind": "bonus"})
    return bonuses


def score_breakdown(user, result_name, base_score, dealt_cards, discarded_cards, final_cards, state):
    bonuses = thematic_bonuses(result_name, dealt_cards, discarded_cards, final_cards, state)
    bonuses.extend(apply_jokers(user, result_name, discarded_cards, final_cards))
    bonus_points = sum(item["amount"] for item in bonuses if item["kind"] == "bonus")
    multiplier = 1.0 + sum(item["amount"] for item in bonuses if item["kind"] == "multiplier")
    final_score = int(round((base_score + bonus_points) * multiplier))
    return bonuses, round(multiplier, 2), final_score


def update_streak(state, played_at):
    today = utc_to_local(played_at).date()
    if state.last_streak_date == today:
        return
    if state.last_streak_date == today - timedelta(days=1):
        state.streak_current += 1
    else:
        state.streak_current = 1
    state.last_streak_date = today
    state.streak_best = max(state.streak_best, state.streak_current)


def unlock_achievements(user, hand, state, discarded_cards):
    unlocked = []
    existing = {row.achievement.code for row in GameUserAchievement.query.filter_by(user_id=user.id).join(GameAchievement).all()}
    local_hour = utc_to_local(hand.played_at).hour
    conditions = {
        "pair": hand.result_name in ("Par", "Doble par", "Trio", "Full", "Poker"),
        "big_discard": len(discarded_cards) >= 4,
        "full": hand.result_name == "Full",
        "straight": hand.result_name in ("Escalera", "Escalera color"),
        "no_discard": len(discarded_cards) == 0,
        "flush_or_better": hand.result_name in ("Color", "Full", "Poker", "Escalera color"),
        "night": 0 <= local_hour <= 5,
        "poker": hand.result_name == "Poker",
        "streak_5": state.streak_current >= 5,
    }
    for achievement in GameAchievement.query.filter_by(active=True).all():
        if achievement.code not in existing and conditions.get(achievement.condition_key):
            db.session.add(GameUserAchievement(user_id=user.id, achievement_id=achievement.id))
            state.points_total += achievement.points_reward
            unlocked.append({"name": achievement.name, "description": achievement.description, "points_reward": achievement.points_reward})
    return unlocked


def record_score(user, dealt_cards, discarded_cards, final_cards):
    settings, state = ensure_can_play(user)
    result_name, base_score = evaluate_hand(final_cards)
    bonuses, multiplier, final_score = score_breakdown(user, result_name, base_score, dealt_cards, discarded_cards, final_cards, state)
    now = now_utc()
    hand = GameHand(
        user_id=user.id,
        dealt_cards_json=dealt_cards,
        discarded_cards_json=discarded_cards,
        final_cards_json=final_cards,
        result_name=result_name,
        base_score=base_score,
        bonuses_json=bonuses,
        multiplier=multiplier,
        score=final_score,
        played_at=now,
    )
    state.points_total += final_score
    state.hands_played_total += 1
    state.hands_used_in_window += 1
    state.last_played_at = now
    state.best_hand_score = max(state.best_hand_score, final_score)
    update_streak(state, now)
    db.session.add(hand)
    db.session.flush()
    unlocked_achievements = unlock_achievements(user, hand, state, discarded_cards)
    sync_unlocked_jokers(user, result_name)
    db.session.commit()
    return hand, status_for(user), unlocked_achievements


def history_for(user, limit=20):
    return GameHand.query.filter_by(user_id=user.id).order_by(GameHand.played_at.desc()).limit(limit).all()


def ranking_for(limit=10):
    points = (
        db.session.query(User.full_name, User.username, Area.name.label("area_name"), GameUserState.points_total, GameUserState.streak_best, GameUserState.best_hand_score)
        .join(GameUserState, GameUserState.user_id == User.id)
        .join(GameUserSettings, GameUserSettings.user_id == User.id)
        .join(Area, Area.id == User.main_area_id)
        .filter(GameUserSettings.ranking_enabled == True)
        .order_by(desc(GameUserState.points_total))
        .limit(limit)
        .all()
    )
    best_hand = (
        db.session.query(User.full_name, User.username, Area.name.label("area_name"), func.max(GameHand.score).label("best_score"))
        .join(GameHand, GameHand.user_id == User.id)
        .join(GameUserSettings, GameUserSettings.user_id == User.id)
        .join(Area, Area.id == User.main_area_id)
        .filter(GameUserSettings.ranking_enabled == True)
        .group_by(User.id, User.full_name, User.username, Area.name)
        .order_by(desc(func.max(GameHand.score)))
        .limit(limit)
        .all()
    )
    streak = (
        db.session.query(User.full_name, User.username, Area.name.label("area_name"), GameUserState.streak_best)
        .join(GameUserState, GameUserState.user_id == User.id)
        .join(GameUserSettings, GameUserSettings.user_id == User.id)
        .join(Area, Area.id == User.main_area_id)
        .filter(GameUserSettings.ranking_enabled == True)
        .order_by(desc(GameUserState.streak_best))
        .limit(limit)
        .all()
    )
    return {
        "points": [{"name": row.full_name or row.username, "area": row.area_name, "value": row.points_total} for row in points],
        "best_hand": [{"name": row.full_name or row.username, "area": row.area_name, "value": row.best_score} for row in best_hand],
        "streak": [{"name": row.full_name or row.username, "area": row.area_name, "value": row.streak_best} for row in streak],
    }


def reset_current_window(user):
    state = get_state(user)
    state.current_window_start = now_utc()
    state.hands_used_in_window = 0
    db.session.flush()
    return state
