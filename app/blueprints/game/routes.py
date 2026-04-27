from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required

from app.services.game_service import (
    GameLimitError,
    deal_hand,
    equip_joker,
    history_for,
    ranking_for,
    record_score,
    replace_cards,
    status_for,
)
from app.time_utils import format_datetime_ar

game_bp = Blueprint("game", __name__, url_prefix="/game")


def _error(message, status=400):
    return jsonify({"ok": False, "error": message, "status": status_for(current_user)}), status


@game_bp.get("/status")
@login_required
def status():
    active = session.get("poker_lefties_hand")
    return jsonify({"ok": True, "status": status_for(current_user), "active_hand": active})


@game_bp.post("/start-hand")
@login_required
def start_hand():
    try:
        cards = deal_hand(current_user)
    except GameLimitError as exc:
        return _error(str(exc), 403)
    session["poker_lefties_hand"] = {
        "dealt": cards,
        "discarded": [],
        "final": cards,
        "discard_used": False,
        "scored": False,
    }
    session.modified = True
    return jsonify({"ok": True, "cards": cards, "status": status_for(current_user)})


@game_bp.post("/discard")
@login_required
def discard():
    payload = session.get("poker_lefties_hand")
    if not payload:
        return _error("Primero tenes que iniciar una mano.")
    if payload.get("discard_used"):
        return _error("Ya usaste el descarte de esta mano.")
    discarded_ids = (request.get_json(silent=True) or {}).get("discarded_ids", [])
    if not isinstance(discarded_ids, list):
        return _error("Solicitud invalida.")
    try:
        final_cards, discarded_cards = replace_cards(payload["dealt"], discarded_ids)
    except ValueError as exc:
        return _error(str(exc))
    payload["discarded"] = discarded_cards
    payload["final"] = final_cards
    payload["discard_used"] = True
    session["poker_lefties_hand"] = payload
    session.modified = True
    return jsonify({"ok": True, "cards": final_cards, "discarded": discarded_cards, "status": status_for(current_user)})


@game_bp.post("/score")
@login_required
def score():
    payload = session.get("poker_lefties_hand")
    if not payload:
        return _error("No hay una mano activa para puntuar.")
    if payload.get("scored"):
        return _error("Esta mano ya fue puntuada.")
    try:
        hand, status_payload, unlocked_achievements = record_score(
            current_user,
            payload["dealt"],
            payload.get("discarded", []),
            payload.get("final") or payload["dealt"],
        )
    except GameLimitError as exc:
        return _error(str(exc), 403)
    session.pop("poker_lefties_hand", None)
    session.modified = True
    return jsonify(
        {
            "ok": True,
            "result": {
                "name": hand.result_name,
                "base_score": hand.base_score,
                "bonuses": hand.bonuses_json,
                "multiplier": hand.multiplier,
                "score": hand.score,
                "played_at": format_datetime_ar(hand.played_at),
                "final_cards": hand.final_cards_json,
            },
            "unlocked_achievements": unlocked_achievements,
            "status": status_payload,
        }
    )


@game_bp.get("/history")
@login_required
def history():
    hands = history_for(current_user)
    return jsonify(
        {
            "ok": True,
            "hands": [
                {
                    "id": hand.id,
                    "played_at": format_datetime_ar(hand.played_at),
                    "result_name": hand.result_name,
                    "base_score": hand.base_score,
                    "bonuses": hand.bonuses_json,
                    "multiplier": hand.multiplier,
                    "score": hand.score,
                    "final_cards": hand.final_cards_json,
                    "discarded_cards": hand.discarded_cards_json,
                }
                for hand in hands
            ],
        }
    )


@game_bp.post("/equip-joker")
@login_required
def equip():
    data = request.get_json(silent=True) or {}
    try:
        jokers = equip_joker(current_user, data.get("code"), int(data.get("slot", 1)))
    except (TypeError, ValueError) as exc:
        return _error(str(exc))
    return jsonify({"ok": True, "jokers": jokers, "status": status_for(current_user)})


@game_bp.get("/ranking")
@login_required
def ranking():
    status_payload = status_for(current_user)
    if not status_payload["ranking_enabled"]:
        return jsonify({"ok": True, "enabled": False, "ranking": {"points": [], "best_hand": [], "streak": []}})
    return jsonify({"ok": True, "enabled": True, "ranking": ranking_for()})
