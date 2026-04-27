from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required

from app.services.game_service import (
    MAX_DISCARD_ROUNDS,
    GameLimitError,
    deal_hand,
    equip_joker,
    history_for,
    ranking_for,
    record_score,
    replace_cards,
    status_for,
    unequip_joker,
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
        cards, deck, consume_source = deal_hand(current_user)
    except GameLimitError as exc:
        return _error(str(exc), 403)
    session["poker_lefties_hand"] = {
        "dealt": cards,
        "deck": deck,
        "discarded": [],
        "final": cards,
        "discard_round": 0,
        "discard_rounds": [],
        "discard_used": False,
        "scored": False,
        "consume_source": consume_source,
    }
    session.modified = True
    return jsonify({"ok": True, "cards": cards, "hand": cards, "round": 0, "rounds_remaining": MAX_DISCARD_ROUNDS, "can_score": False, "status": status_for(current_user)})


@game_bp.post("/discard")
@login_required
def discard():
    payload = session.get("poker_lefties_hand")
    if not payload:
        return _error("Primero tenes que iniciar una mano.")
    if payload.get("scored"):
        return _error("Esta mano ya fue puntuada.")
    if int(payload.get("discard_round", 0)) >= MAX_DISCARD_ROUNDS:
        return _error("Ya completaste las 3 vueltas de descarte.")
    data = request.get_json(silent=True) or {}
    discarded_ids = data.get("cards", data.get("discarded_ids", []))
    if not isinstance(discarded_ids, list):
        return _error("Solicitud invalida.")
    try:
        final_cards, discarded_cards, drawn_cards, deck = replace_cards(payload["final"], payload.get("deck", []), discarded_ids)
    except ValueError as exc:
        return _error(str(exc))
    round_number = int(payload.get("discard_round", 0)) + 1
    payload.setdefault("discard_rounds", []).append(
        {
            "round": round_number,
            "discarded": [card["id"] for card in discarded_cards],
            "drawn": [card["id"] for card in drawn_cards],
            "hand_after": [card["id"] for card in final_cards],
        }
    )
    payload["discarded"] = discarded_cards
    payload["final"] = final_cards
    payload["deck"] = deck
    payload["discard_round"] = round_number
    payload["discard_used"] = round_number >= MAX_DISCARD_ROUNDS
    session["poker_lefties_hand"] = payload
    session.modified = True
    rounds_remaining = MAX_DISCARD_ROUNDS - round_number
    return jsonify(
        {
            "ok": True,
            "round": round_number,
            "rounds_remaining": rounds_remaining,
            "hand": final_cards,
            "cards": final_cards,
            "discarded": discarded_cards,
            "drawn": drawn_cards,
            "message": f"Vuelta {round_number}/3 completada",
            "can_score": rounds_remaining == 0,
            "status": status_for(current_user),
        }
    )


@game_bp.post("/score")
@login_required
def score():
    payload = session.get("poker_lefties_hand")
    if not payload:
        return _error("No hay una mano activa para puntuar.")
    if payload.get("scored"):
        return _error("Esta mano ya fue puntuada.")
    if int(payload.get("discard_round", 0)) < MAX_DISCARD_ROUNDS:
        return _error("Tenes que completar las 3 vueltas de descarte antes de cerrar la mano.")
    try:
        hand, status_payload, unlocked_achievements, unlocked_jokers = record_score(
            current_user,
            payload["dealt"],
            payload.get("discarded", []),
            payload.get("final") or payload["dealt"],
            payload.get("discard_rounds", []),
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
                "result_name": hand.result_name,
                "base_score": hand.base_score,
                "bonuses": hand.score_breakdown_json.get("bonuses", []),
                "multipliers": hand.score_breakdown_json.get("multipliers", []),
                "streak_bonus": hand.streak_bonus,
                "multiplier": hand.multiplier,
                "score": hand.score,
                "final_score": hand.final_score,
                "score_breakdown": hand.score_breakdown_json,
                "played_at": format_datetime_ar(hand.played_at),
                "final_cards": hand.final_cards_json,
            },
            "unlocked_achievements": unlocked_achievements,
            "unlocked_jokers": unlocked_jokers,
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
                    "bonuses": hand.score_breakdown_json.get("bonuses", []) if hand.score_breakdown_json else hand.bonuses_json,
                    "multipliers": hand.score_breakdown_json.get("multipliers", []) if hand.score_breakdown_json else [],
                    "streak_bonus": hand.streak_bonus,
                    "multiplier": hand.multiplier,
                    "score": hand.score,
                    "final_score": hand.final_score or hand.score,
                    "final_cards": hand.final_cards_json,
                    "discarded_cards": hand.discarded_cards_json,
                    "discard_rounds": hand.discard_rounds_json or [],
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


@game_bp.post("/unequip-joker")
@login_required
def unequip():
    data = request.get_json(silent=True) or {}
    try:
        jokers = unequip_joker(current_user, data.get("code"))
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
