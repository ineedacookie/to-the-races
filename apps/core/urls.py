from __future__ import annotations

from django.urls import path

from apps.core import api, views

urlpatterns = [
    path("", views.home, name="home"),
    path("bet/", views.betting_page, name="betting-page"),
    path("display/", views.display_page, name="display-page"),
    path("house/", views.house_account, name="house-account"),
    path("records/", views.records_page, name="world-records"),
    path("racers/<slug:slug>/", views.racer_detail, name="racer-detail"),
    path("betting-qr.svg", views.betting_qr, name="betting-qr"),
    path("health/", views.health, name="health"),
    path("api/state/", api.state, name="api-state"),
    path("api/player/", api.identify_player, name="api-player"),
    path("api/player/login/", api.login_existing_player, name="api-player-login"),
    path(
        "api/player/replay-preference/",
        api.player_replay_preference,
        name="api-player-replay-preference",
    ),
    path("api/rounds/<int:round_id>/replay/", api.round_replay, name="api-round-replay"),
    path("api/players/<int:player_id>/avatar/", api.player_avatar, name="api-player-avatar"),
    path("api/nickname-suggestion/", api.nickname_suggestion, name="api-nickname"),
    path("api/bets/", api.place_player_bet, name="api-bets"),
    path("api/items/purchase/", api.purchase_player_item, name="api-items-purchase"),
    path("api/items/discard/", api.discard_player_item, name="api-items-discard"),
    path("api/items/use/", api.use_player_item, name="api-items-use"),
    path("api/upgrades/purchase/", api.purchase_player_upgrade, name="api-upgrades-purchase"),
    path("api/seats/claim/", api.claim_round_seat, name="api-seats-claim"),
    path("api/bailout/start/", api.start_track_medic_bailout, name="api-bailout-start"),
    path("api/bailout/patch/", api.patch_track_medic_wound, name="api-bailout-patch"),
]
