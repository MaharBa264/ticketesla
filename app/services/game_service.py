import random
from collections import Counter
from datetime import timedelta, timezone

from sqlalchemy import desc, func

from app.extensions import db
from app.models import (
    Area,
    GameAchievement,
    GameHand,
    GameHandGrant,
    GameJoker,
    GameUserAchievement,
    GameUserJoker,
    GameUserSettings,
    GameUserState,
    User,
)
from app.time_utils import format_datetime_ar, now_utc, utc_to_local

MAX_DISCARD_ROUNDS = 3
SUITS = ("S", "H", "D", "C")
RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
SUIT_LABELS = {"S": "Picas", "H": "Corazones", "D": "Diamantes", "C": "Treboles"}
SUIT_SYMBOLS = {"S": "\u2660", "H": "\u2665", "D": "\u2666", "C": "\u2663"}
RANK_VALUES = {rank: index + 2 for index, rank in enumerate(RANKS)}

SCORES = {
    "Carta alta": 5,
    "Par": 15,
    "Doble par": 30,
    "Trio": 50,
    "Escalera": 80,
    "Color": 90,
    "Full": 120,
    "Poker": 200,
    "Escalera color": 350,
}
PAIR_OR_BETTER = {"Par", "Doble par", "Trio", "Escalera", "Color", "Full", "Poker", "Escalera color"}

DEFAULT_JOKERS = [
    ("rtu_estable", "RTU estable", "Efecto: +10 puntos si en alguna vuelta mantenes todas las cartas.", "Disponible desde el inicio.", {"type": "held_round_bonus", "points": 10}, "comun"),
    ("rele_sensible", "Rele sensible", "Efecto: x1.5 si la jugada final es par o mejor.", "Disponible desde el inicio.", {"type": "pair_multiplier", "multiplier": 1.5}, "comun"),
    ("fibra_cortada", "Fibra cortada", "Efecto: +20 puntos si descartaste 3 cartas o mas en una vuelta.", "Descartar 3 cartas o mas en una mano.", {"type": "big_round_discard_bonus", "points": 20}, "raro"),
    ("scada_bendecido", "SCADA bendecido", "Efecto: +25 puntos a cualquier mano con trio o mejor.", "Alcanzar 300 puntos totales.", {"type": "three_kind_plus_bonus", "points": 25}, "raro"),
    ("full_protecciones", "Full de Protecciones", "Efecto: +50 puntos si conseguis Full.", "Conseguir un Full.", {"type": "full_bonus", "points": 50}, "epico"),
    ("escalera_iec", "Escalera IEC 61850", "Efecto: x2 si conseguis Escalera.", "Conseguir una Escalera.", {"type": "straight_double", "multiplier": 2.0}, "epico"),
    ("derivador_compulsivo", "Derivador compulsivo", "Efecto: +5 puntos por cada vuelta de descarte usada.", "Jugar 20 manos.", {"type": "rounds_used_bonus", "points_per_round": 5}, "raro"),
    ("cmd_preciso", "CMD preciso", "Efecto: +15 puntos si la mano final tiene J, Q, K o A.", "Conseguir 5 manos con par o mejor.", {"type": "face_or_ace_bonus", "points": 15}, "comun"),
]

DEFAULT_ACHIEVEMENTS = [
    ("derivador_compulsivo", "Derivador compulsivo", "Jugar 20 manos.", "hands_20", 10),
    ("full_protecciones", "Full de Protecciones", "Conseguir un Full.", "full", 20),
    ("escalera_iec", "Escalera IEC 61850", "Conseguir una Escalera.", "straight", 15),
    ("rtu_zen", "RTU zen", "Completar una mano sin descartar cartas.", "no_discard_all_rounds", 10),
    ("scada_bendecido", "SCADA bendecido", "Superar 500 puntos acumulados.", "points_500", 25),
    ("operador_nocturno", "Operador nocturno", "Jugar entre las 00:00 y las 05:00.", "night", 12),
    ("par_guardia", "Par de guardia", "Obtener par o mejor 10 veces.", "pair_10", 15),
    ("poker_campo", "Poker de campo", "Conseguir Poker.", "poker", 35),
    ("rele_sin_falsa", "Rele sin falsa operacion", "Completar una ventana de manos con todas las manos puntuadas.", "clean_window", 20),
    ("fibra_viva", "Fibra cortada pero viva", "Puntuar despues de descartar 3 o mas cartas en una vuelta.", "big_round_discard", 15),
]


class GameLimitError(ValueError):
    pass


def serialize_card(rank, suit):
    return {"id": f"{rank}{suit}", "rank": rank, "suit": suit, "symbol": SUIT_SYMBOLS[suit], "label": f"{rank} de {SUIT_LABELS[suit]}"}


def build_deck():
    return [serialize_card(rank, suit) for suit in SUITS for rank in RANKS]


def card_ids(cards):
    return {card["id"] for card in cards}


def as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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
        state = GameUserState(user_id=user.id, points_total=0, hands_played_total=0, hands_used_in_window=0, streak_current=0, streak_best=0, best_hand_score=0)
        db.session.add(state)
        db.session.flush()
    return state


def normalize_window(state, settings):
    now = now_utc()
    window_start = as_utc(state.current_window_start)
    if window_start is None or window_start + timedelta(minutes=settings.window_minutes) <= now:
        state.current_window_start = now
        state.hands_used_in_window = 0
    elif window_start != state.current_window_start:
        state.current_window_start = window_start
    return state


def current_window_end(state, settings):
    return as_utc(state.current_window_start) + timedelta(minutes=settings.window_minutes)


def ensure_seed_catalogs():
    for code, name, description, unlock_rule, effect, rarity in DEFAULT_JOKERS:
        joker = GameJoker.query.filter_by(code=code).first()
        if joker is None:
            db.session.add(GameJoker(code=code, name=name, description=description, unlock_rule=unlock_rule, effect_json={**effect, "rarity": rarity}, active=True))
        else:
            joker.name = name
            joker.description = description
            joker.unlock_rule = unlock_rule
            joker.effect_json = {**effect, "rarity": rarity}
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


def max_discarded_in_round(discard_rounds):
    return max((len(round_item.get("discarded", [])) for round_item in discard_rounds or []), default=0)


def no_discard_rounds(discard_rounds):
    return sum(1 for item in discard_rounds or [] if not item.get("discarded"))


def used_round_count(discard_rounds):
    return len(discard_rounds or [])


def pair_or_better_count(user):
    return GameHand.query.filter(GameHand.user_id == user.id, GameHand.result_name.in_(PAIR_OR_BETTER)).count()


def unlocked_joker_codes(user, state, hand_result=None, discard_rounds=None):
    codes = {"rtu_estable", "rele_sensible"}
    if max_discarded_in_round(discard_rounds) >= 3:
        codes.add("fibra_cortada")
    if state.points_total >= 300:
        codes.add("scada_bendecido")
    if hand_result == "Full" or GameHand.query.filter_by(user_id=user.id, result_name="Full").first():
        codes.add("full_protecciones")
    if hand_result in ("Escalera", "Escalera color") or GameHand.query.filter(GameHand.user_id == user.id, GameHand.result_name.in_(("Escalera", "Escalera color"))).first():
        codes.add("escalera_iec")
    if state.hands_played_total >= 20:
        codes.add("derivador_compulsivo")
    if pair_or_better_count(user) >= 5:
        codes.add("cmd_preciso")
    return codes


def sync_unlocked_jokers(user, hand_result=None, discard_rounds=None):
    ensure_seed_catalogs()
    state = get_state(user)
    existing = {row.joker.code for row in GameUserJoker.query.filter_by(user_id=user.id).join(GameJoker).all()}
    unlocked = []
    for code in unlocked_joker_codes(user, state, hand_result, discard_rounds) - existing:
        joker = GameJoker.query.filter_by(code=code, active=True).first()
        if joker:
            db.session.add(GameUserJoker(user_id=user.id, joker_id=joker.id))
            unlocked.append({"code": joker.code, "name": joker.name, "description": joker.description})
    db.session.flush()
    return unlocked


def get_user_jokers(user):
    sync_unlocked_jokers(user)
    owned_rows = GameUserJoker.query.filter_by(user_id=user.id).join(GameJoker).all()
    owned_by_code = {row.joker.code: row for row in owned_rows}
    equipped = []
    unlocked = []
    locked = []
    for joker in GameJoker.query.filter_by(active=True).order_by(GameJoker.name).all():
        row = owned_by_code.get(joker.code)
        payload = {
            "code": joker.code,
            "name": joker.name,
            "description": joker.description,
            "effect": joker.description,
            "unlock_rule": joker.unlock_rule,
            "rarity": (joker.effect_json or {}).get("rarity", "comun"),
            "equipped_slot": row.equipped_slot if row else None,
            "state": "locked",
        }
        if row and row.equipped_slot:
            payload["state"] = "equipped"
            equipped.append(payload)
        elif row:
            payload["state"] = "unlocked"
            unlocked.append(payload)
        else:
            locked.append(payload)
    return {"equipped": equipped, "unlocked": unlocked, "locked": locked, "items": equipped + unlocked}


def joker_payload(user):
    return get_user_jokers(user)


def equipped_jokers(user):
    sync_unlocked_jokers(user)
    return [row.joker for row in GameUserJoker.query.filter(GameUserJoker.user_id == user.id, GameUserJoker.equipped_slot != None).join(GameJoker).order_by(GameUserJoker.equipped_slot).all()]


def equip_joker(user, joker_code, slot=1):
    if slot not in (1, 2):
        raise ValueError("Slot invalido.")
    sync_unlocked_jokers(user)
    target = GameUserJoker.query.filter_by(user_id=user.id).join(GameJoker).filter(GameJoker.code == joker_code).first()
    if not target:
        raise ValueError("Ese comodin todavia no esta desbloqueado.")
    GameUserJoker.query.filter_by(user_id=user.id, equipped_slot=slot).update({"equipped_slot": None})
    target.equipped_slot = slot
    db.session.commit()
    return joker_payload(user)


def unequip_joker(user, joker_code):
    target = GameUserJoker.query.filter_by(user_id=user.id).join(GameJoker).filter(GameJoker.code == joker_code).first()
    if not target:
        raise ValueError("Ese comodin no esta desbloqueado.")
    target.equipped_slot = None
    db.session.commit()
    return joker_payload(user)


def achievement_rows(user):
    owned = {row.achievement.code: row for row in GameUserAchievement.query.filter_by(user_id=user.id).join(GameAchievement).all()}
    unlocked = []
    locked = []
    for achievement in GameAchievement.query.filter_by(active=True).order_by(GameAchievement.name).all():
        row = owned.get(achievement.code)
        payload = {
            "code": achievement.code,
            "name": achievement.name,
            "description": achievement.description,
            "points_reward": achievement.points_reward,
            "unlocked_at": format_datetime_ar(row.unlocked_at) if row else "",
            "state": "unlocked" if row else "locked",
        }
        (unlocked if row else locked).append(payload)
    return {"unlocked": unlocked, "locked": locked}


def extra_hand_grants(user, state=None, settings=None):
    state = state or normalize_window(get_state(user), get_settings(user))
    settings = settings or get_settings(user)
    now = now_utc()
    window_start = as_utc(state.current_window_start)
    rows = (
        GameHandGrant.query.filter(
            GameHandGrant.user_id == user.id,
            GameHandGrant.expires_at > now,
            GameHandGrant.window_start == window_start,
            GameHandGrant.hands_used < GameHandGrant.hands_granted,
        )
        .order_by(GameHandGrant.expires_at.asc(), GameHandGrant.id.asc())
        .all()
    )
    return rows


def extra_grant_payload(grants):
    labels = {"ticket_resolved": "Ticket resuelto", "ticket_closed": "Ticket cerrado"}
    return [
        {
            "id": grant.id,
            "source": grant.ticket.number if grant.ticket else f"Ticket {grant.ticket_id}",
            "reason": labels.get(grant.action, grant.action),
            "remaining": grant.hands_granted - grant.hands_used,
            "expires_at": format_datetime_ar(grant.expires_at),
        }
        for grant in grants
    ]


def status_for(user):
    settings = get_settings(user)
    state = normalize_window(get_state(user), settings)
    sync_unlocked_jokers(user)
    base_remaining = max(settings.hands_limit - state.hands_used_in_window, 0) if settings.enabled else 0
    grants = extra_hand_grants(user, state, settings) if settings.enabled else []
    extra_remaining = sum(grant.hands_granted - grant.hands_used for grant in grants)
    resets_at = current_window_end(state, settings) if state.current_window_start else None
    db.session.commit()
    return {
        "enabled": settings.enabled,
        "ranking_enabled": settings.ranking_enabled,
        "hands_limit": settings.hands_limit,
        "window_minutes": settings.window_minutes,
        "points_total": state.points_total,
        "hands_played_total": state.hands_played_total,
        "hands_used_in_window": state.hands_used_in_window,
        "base_hands_remaining": base_remaining,
        "extra_hands_remaining": extra_remaining,
        "total_hands_remaining": base_remaining + extra_remaining,
        "hands_remaining": base_remaining + extra_remaining,
        "extra_hand_grants": extra_grant_payload(grants),
        "window_start": format_datetime_ar(state.current_window_start),
        "resets_at": format_datetime_ar(resets_at),
        "streak_current": state.streak_current,
        "streak_best": state.streak_best,
        "best_hand_score": state.best_hand_score,
        "best_result_name": state.best_result_name,
        "jokers": joker_payload(user),
        "achievements": achievement_rows(user),
    }


def ensure_can_play(user):
    settings = get_settings(user)
    state = normalize_window(get_state(user), settings)
    if not settings.enabled:
        raise GameLimitError("El juego no esta habilitado para tu usuario.")
    base_remaining = max(settings.hands_limit - state.hands_used_in_window, 0)
    grants = extra_hand_grants(user, state, settings)
    if base_remaining <= 0 and not grants:
        raise GameLimitError(f"No quedan manos disponibles. Se renuevan el {format_datetime_ar(current_window_end(state, settings))}.")
    return settings, state, grants


def consume_hand_for_start(user):
    _settings, state, grants = ensure_can_play(user)
    if grants:
        grant = grants[0]
        grant.hands_used += 1
        source = {"type": "extra", "grant_id": grant.id, "ticket": grant.ticket.number if grant.ticket else str(grant.ticket_id)}
    else:
        state.hands_used_in_window += 1
        source = {"type": "base"}
    db.session.flush()
    return source


def deal_hand(user):
    consume_source = consume_hand_for_start(user)
    deck = build_deck()
    random.SystemRandom().shuffle(deck)
    hand = deck[:5]
    return hand, deck[5:], consume_source


def validate_discard(current_hand, discarded_ids):
    if not isinstance(discarded_ids, list):
        raise ValueError("Solicitud invalida.")
    if len(discarded_ids) > 5:
        raise ValueError("No se pueden descartar mas de 5 cartas.")
    discarded_ids = set(discarded_ids)
    if not discarded_ids.issubset(card_ids(current_hand)):
        raise ValueError("El descarte contiene cartas invalidas.")
    return discarded_ids


def replace_cards(current_hand, deck, discarded_ids):
    discarded_ids = validate_discard(current_hand, discarded_ids)
    kept = [card for card in current_hand if card["id"] not in discarded_ids]
    drawn = deck[: len(discarded_ids)]
    if len(drawn) < len(discarded_ids):
        raise ValueError("No quedan cartas suficientes en el mazo.")
    discarded_cards = [card for card in current_hand if card["id"] in discarded_ids]
    return kept + drawn, discarded_cards, drawn, deck[len(discarded_ids):]


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


def add_bonus(items, code, name, description, points):
    items.append({"code": code, "name": name, "description": description, "points": points})


def add_multiplier(items, code, name, description, multiplier):
    items.append({"code": code, "name": name, "description": description, "multiplier": multiplier})


def score_breakdown(user, result_name, base_score, dealt_cards, discarded_cards, final_cards, discard_rounds, state):
    bonuses = []
    multipliers = []
    max_round_discard = max_discarded_in_round(discard_rounds)
    held_rounds = no_discard_rounds(discard_rounds)
    if held_rounds:
        add_bonus(bonuses, "rtu_estable", "RTU estable", "No descartaste cartas en una vuelta.", 10)
    if max_round_discard >= 3:
        add_bonus(bonuses, "fibra_cortada", "Fibra cortada", "Descartaste 3 cartas o mas en una vuelta.", 20)
    if result_name in ("Trio", "Escalera", "Color", "Full", "Poker", "Escalera color"):
        add_bonus(bonuses, "scada_bendecido", "SCADA bendecido", "La mano final fue trio o mejor.", 15)
    if result_name in ("Full", "Poker", "Escalera color"):
        add_bonus(bonuses, "proteccion_selectiva", "Proteccion selectiva", "Jugada de alta selectividad tecnica.", 20)
    if any(round_item.get("discarded") for round_item in discard_rounds):
        add_bonus(bonuses, "comunicacion_restablecida", "Comunicacion restablecida", "Usaste el descarte para estabilizar la mano.", 8)
    if any(card["rank"] in ("J", "Q", "K", "A") for card in final_cards):
        add_bonus(bonuses, "cmd_preciso", "CMD preciso", "La mano final tiene figura o As.", 10)
    if result_name in ("Escalera", "Escalera color"):
        add_multiplier(multipliers, "telecontrol_sincronizado", "Telecontrol sincronizado", "Se activa con escalera.", 1.25)

    jokers_used = []
    for joker in equipped_jokers(user):
        effect = joker.effect_json or {}
        effect_type = effect.get("type")
        if effect_type == "held_round_bonus" and held_rounds:
            add_bonus(bonuses, joker.code, joker.name, "Comodin: mantuviste todas las cartas en una vuelta.", effect.get("points", 0))
            jokers_used.append(joker.code)
        elif effect_type == "pair_multiplier" and result_name in PAIR_OR_BETTER:
            add_multiplier(multipliers, joker.code, joker.name, "Comodin: se activa con par o mejor.", effect.get("multiplier", 1.0))
            jokers_used.append(joker.code)
        elif effect_type == "big_round_discard_bonus" and max_round_discard >= 3:
            add_bonus(bonuses, joker.code, joker.name, "Comodin: descarte grande en una vuelta.", effect.get("points", 0))
            jokers_used.append(joker.code)
        elif effect_type == "three_kind_plus_bonus" and result_name in ("Trio", "Escalera", "Color", "Full", "Poker", "Escalera color"):
            add_bonus(bonuses, joker.code, joker.name, "Comodin: trio o mejor.", effect.get("points", 0))
            jokers_used.append(joker.code)
        elif effect_type == "full_bonus" and result_name == "Full":
            add_bonus(bonuses, joker.code, joker.name, "Comodin: full detectado.", effect.get("points", 0))
            jokers_used.append(joker.code)
        elif effect_type == "straight_double" and result_name in ("Escalera", "Escalera color"):
            add_multiplier(multipliers, joker.code, joker.name, "Comodin: escalera IEC 61850.", effect.get("multiplier", 1.0))
            jokers_used.append(joker.code)
        elif effect_type == "rounds_used_bonus":
            points = used_round_count(discard_rounds) * effect.get("points_per_round", 0)
            add_bonus(bonuses, joker.code, joker.name, "Comodin: bono por vueltas usadas.", points)
            jokers_used.append(joker.code)
        elif effect_type == "face_or_ace_bonus" and any(card["rank"] in ("J", "Q", "K", "A") for card in final_cards):
            add_bonus(bonuses, joker.code, joker.name, "Comodin: figura o As en mano final.", effect.get("points", 0))
            jokers_used.append(joker.code)

    next_streak = state.streak_current + 1
    streak_bonus = 5 * (next_streak // 3) if next_streak >= 3 else 0
    bonus_score = sum(item["points"] for item in bonuses)
    total_multiplier = 1.0
    for item in multipliers:
        total_multiplier *= item["multiplier"]
    final_score = int(round((base_score + bonus_score + streak_bonus) * total_multiplier))
    return {
        "result_name": result_name,
        "base_score": base_score,
        "bonuses": bonuses,
        "multipliers": multipliers,
        "bonus_score": bonus_score,
        "streak_bonus": streak_bonus,
        "total_multiplier": round(total_multiplier, 2),
        "final_score": final_score,
        "jokers_used": jokers_used,
    }


def update_streak(state, final_score):
    if final_score > 0:
        state.streak_current += 1
        state.streak_best = max(state.streak_best, state.streak_current)
    else:
        state.streak_current = 0


def unlock_achievements(user, hand, state, discard_rounds):
    unlocked = []
    existing = {row.achievement.code for row in GameUserAchievement.query.filter_by(user_id=user.id).join(GameAchievement).all()}
    local_hour = utc_to_local(hand.played_at).hour
    max_round_discard = max_discarded_in_round(discard_rounds)
    no_discard_all = all(not item.get("discarded") for item in discard_rounds or [])
    pair_count = pair_or_better_count(user)
    conditions = {
        "hands_20": state.hands_played_total >= 20,
        "full": hand.result_name == "Full",
        "straight": hand.result_name in ("Escalera", "Escalera color"),
        "no_discard_all_rounds": no_discard_all,
        "points_500": state.points_total >= 500,
        "night": 0 <= local_hour <= 5,
        "pair_10": pair_count >= 10,
        "poker": hand.result_name == "Poker",
        "clean_window": state.hands_used_in_window >= get_settings(user).hands_limit and state.streak_current >= state.hands_used_in_window,
        "big_round_discard": max_round_discard >= 3 and hand.score > 0,
    }
    for achievement in GameAchievement.query.filter_by(active=True).all():
        if achievement.code not in existing and conditions.get(achievement.condition_key):
            db.session.add(GameUserAchievement(user_id=user.id, achievement_id=achievement.id))
            state.points_total += achievement.points_reward
            unlocked.append({"code": achievement.code, "name": achievement.name, "description": achievement.description, "points_reward": achievement.points_reward})
    return unlocked


def record_score(user, dealt_cards, discarded_cards, final_cards, discard_rounds=None):
    state = get_state(user)
    result_name, base_score = evaluate_hand(final_cards)
    breakdown = score_breakdown(user, result_name, base_score, dealt_cards, discarded_cards, final_cards, discard_rounds or [], state)
    now = now_utc()
    hand = GameHand(
        user_id=user.id,
        dealt_cards_json=dealt_cards,
        discarded_cards_json=discarded_cards,
        discard_rounds_json=discard_rounds or [],
        final_cards_json=final_cards,
        result_name=result_name,
        base_score=base_score,
        bonuses_json=breakdown["bonuses"] + breakdown["multipliers"],
        bonuses_applied_json=breakdown["bonuses"],
        jokers_used_json=breakdown["jokers_used"],
        score_breakdown_json=breakdown,
        bonus_score=breakdown["bonus_score"],
        streak_bonus=breakdown["streak_bonus"],
        multiplier=breakdown["total_multiplier"],
        score=breakdown["final_score"],
        final_score=breakdown["final_score"],
        played_at=now,
    )
    update_streak(state, breakdown["final_score"])
    state.points_total += breakdown["final_score"]
    state.hands_played_total += 1
    state.last_played_at = now
    if breakdown["final_score"] > state.best_hand_score:
        state.best_hand_score = breakdown["final_score"]
        state.best_result_name = result_name
    db.session.add(hand)
    db.session.flush()
    unlocked_achievements = unlock_achievements(user, hand, state, discard_rounds or [])
    unlocked_jokers = sync_unlocked_jokers(user, result_name, discard_rounds or [])
    db.session.commit()
    return hand, status_for(user), unlocked_achievements, unlocked_jokers


def history_for(user, limit=20):
    return GameHand.query.filter_by(user_id=user.id).order_by(GameHand.played_at.desc()).limit(limit).all()


def ranking_for(limit=10):
    points = (
        db.session.query(User.full_name, User.username, Area.name.label("area_name"), GameUserState.points_total)
        .join(GameUserState, GameUserState.user_id == User.id)
        .join(GameUserSettings, GameUserSettings.user_id == User.id)
        .join(Area, Area.id == User.main_area_id)
        .filter(GameUserSettings.ranking_enabled == True)
        .order_by(desc(GameUserState.points_total))
        .limit(limit)
        .all()
    )
    best_hand = (
        db.session.query(User.full_name, User.username, Area.name.label("area_name"), GameUserState.best_hand_score, GameUserState.best_result_name)
        .join(GameUserState, GameUserState.user_id == User.id)
        .join(GameUserSettings, GameUserSettings.user_id == User.id)
        .join(Area, Area.id == User.main_area_id)
        .filter(GameUserSettings.ranking_enabled == True)
        .order_by(desc(GameUserState.best_hand_score))
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
        "best_hand": [{"name": row.full_name or row.username, "area": row.area_name, "value": row.best_hand_score, "result": row.best_result_name or ""} for row in best_hand],
        "streak": [{"name": row.full_name or row.username, "area": row.area_name, "value": row.streak_best} for row in streak],
    }


def reset_current_window(user):
    state = get_state(user)
    state.current_window_start = now_utc()
    state.hands_used_in_window = 0
    db.session.flush()
    return state


def grant_extra_hand_for_ticket_action(user, ticket, action):
    action_map = {"Resuelto": "ticket_resolved", "Cerrado": "ticket_closed", "ticket_resolved": "ticket_resolved", "ticket_closed": "ticket_closed"}
    grant_action = action_map.get(action)
    if not grant_action:
        return False
    settings = get_settings(user)
    state = normalize_window(get_state(user), settings)
    existing = GameHandGrant.query.filter_by(user_id=user.id, ticket_id=ticket.id, action=grant_action).first()
    if existing:
        return False
    grant = GameHandGrant(
        user_id=user.id,
        ticket_id=ticket.id,
        action=grant_action,
        hands_granted=1,
        hands_used=0,
        granted_at=now_utc(),
        expires_at=current_window_end(state, settings),
        window_start=as_utc(state.current_window_start),
    )
    db.session.add(grant)
    return True
