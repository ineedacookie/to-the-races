from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

# Dialogue lines are authored as single strings so copy editors can review the spoken
# sentence without reconstructing it across source lines.
# ruff: noqa: E501

HIGHLIGHT_HOST_NAME = "Chip McChatter"
SpeakerKind = Literal["host", "racer"]


@dataclass(frozen=True, slots=True)
class DialogueBeat:
    speaker_kind: SpeakerKind
    speaker_name: str
    caption: str
    detail: str
    racer_id: int | None = None
    sprite_key: str | None = None


@dataclass(frozen=True, slots=True)
class RacerVoice:
    openers: tuple[str, ...]
    boasts: tuple[str, ...]
    excuses: tuple[str, ...]
    metaphors: tuple[str, ...]
    reactions: tuple[str, ...]
    sign_offs: tuple[str, ...]
    potion_reactions: tuple[str, ...]


GENERIC_VOICE = RacerVoice(
    openers=(
        "Listen closely:",
        "Here is the official story:",
        "For the record:",
        "Straight from the winner's circle:",
        "Let the replay show:",
    ),
    boasts=(
        "I found another gear when the track got loud.",
        "I made the chaos work for me.",
        "That finish had my name on it.",
        "I stayed focused when everything went sideways.",
        "I earned every step of that victory.",
        "The track tested me, and I answered.",
    ),
    excuses=(
        "the track kept moving when nobody was looking.",
        "somebody greased the laws of physics.",
        "the corners were behaving suspiciously.",
        "the timing was less than cooperative.",
        "the course had its own ideas today.",
        "the obstacles were unusually ambitious.",
    ),
    metaphors=(
        "I was a comet with a lane assignment.",
        "I threaded that field like a needle wearing racing boots.",
        "I surfed the panic all the way home.",
        "I chased victory through a storm of bad decisions.",
        "I raced like a legend trying to catch itself.",
        "I turned chaos into a straight path forward.",
    ),
    reactions=(
        "That was wild.",
        "I would absolutely do it again.",
        "I barely saw it coming.",
        "That was a race worth remembering.",
        "The finish line tells the story.",
        "I gave everything I had.",
    ),
    potion_reactions=(
        "Wait, that was not regular hydration?",
        "I had no idea anything unusual was in that drink.",
        "I thought I was simply preparing for the race.",
        "I would never knowingly use an unauthorized advantage.",
        "The victory was mine, but I need answers about that bottle.",
        "I trusted what I was given. Maybe I should have asked more questions.",
    ),
    sign_offs=(
        "Print that.",
        "Put it on the poster.",
        "See you at the next starting horn.",
        "The next race starts soon.",
        "I will be ready when the gates open again.",
    ),
)

RACER_VOICES: Mapping[str, RacerVoice] = {
    "skeleton": RacerVoice(
        openers=(
            "Rattle this down:",
            "From the bottom of my rib cage:",
            "Bone to be blunt:",
            "Straight from the skeleton crew:",
            "My bones have reached a conclusion:",
        ),
        boasts=(
            "I had the strongest finish in the skeleton crew.",
            "Every joint clicked into championship mode.",
            "I left nothing on the track except one optional femur.",
            "My bones knew the path before my feet did.",
            "I stayed together when the competition fell apart.",
            "I proved that experience is the strongest bone in the body.",
        ),
        excuses=(
            "my left tibia was buffering.",
            "somebody moved the finish line behind my eye sockets.",
            "the track lacked adequate calcium support.",
            "my knee joint requested a maintenance break.",
            "I lost valuable time searching for a missing rib.",
            "my skeleton briefly entered a loose-parts situation.",
        ),
        metaphors=(
            "I came through like a xylophone in a tumble dryer.",
            "I was ninety percent momentum and ten percent spare parts.",
            "I rattled past the field like loose coins down a staircase.",
            "I charged forward like a haunted marching band.",
            "I shook the competition like a bag of bones in a storm.",
            "I moved with the unstoppable rhythm of a skeleton parade.",
        ),
        reactions=(
            "No bones about it.",
            "My skull is still applauding.",
            "That shook my marrow.",
            "My skeleton is celebrating internally.",
            "That was a bone-rattling performance.",
            "Every vertebra agrees with that result.",
        ),
        potion_reactions=(
            "Hold on... that was not ordinary water?",
            "I did not knowingly consume anything unusual. My bones have standards.",
            "A magical enhancement? I thought I was simply staying hydrated.",
            "I may be missing some flesh, but I am not missing good judgment.",
            "My joints felt stronger, but I assumed that was confidence.",
            "I would remember drinking a suspicious potion. My memory is mostly stored in my skull.",
        ),
        sign_offs=(
            "Stay bony.",
            "Put that in the fossil record.",
            "I am off to count my ribs.",
            "Remember: old bones still race.",
            "Until next time, keep your skeletons organized.",
        ),
    ),

    "mushroom": RacerVoice(
        openers=(
            "The network reports:",
            "According to the mycelium:",
            "Humidity check complete:",
            "The colony has reviewed the data:",
            "The spores have reached consensus:",
        ),
        boasts=(
            "my distributed racing cluster reached full fruiting capacity.",
            "every spore voted for maximum acceleration.",
            "I scaled horizontally across the entire track.",
            "my growth strategy produced championship results.",
            "the whole colony contributed to this victory.",
            "I bloomed exactly when the race needed me.",
        ),
        excuses=(
            "the lane suffered a brief moisture outage.",
            "my root network detected hostile packet loss.",
            "someone introduced an unlicensed fungicide metaphor.",
            "the soil conditions were unexpectedly competitive.",
            "my spores were distracted by poor environmental planning.",
            "the track conditions were not ideal for growth.",
        ),
        metaphors=(
            "I spread through that field like gossip through damp soil.",
            "I popped at the finish like a perfectly timed mushroom cloud.",
            "I routed around trouble like roots around a suspicious pebble.",
            "I grew through the competition like a forest after rain.",
            "I covered the track like a garden refusing to be ignored.",
            "I bloomed through chaos and left everyone composting plans.",
        ),
        reactions=(
            "The spores are thrilled.",
            "That result is fully compostable.",
            "We have achieved bloom.",
            "The colony celebrates.",
            "The harvest was excellent today.",
            "The growth report is extremely positive.",
        ),
        potion_reactions=(
            "A magical effect? I believed that was normal hydration.",
            "I would never knowingly consume unauthorized growth assistance.",
            "The bottle was unusual, but I assumed it was premium garden water.",
            "My spores noticed something different, but I did not know it was prohibited.",
            "The colony supports fair competition and responsible beverages.",
            "I was focused on racing, not analyzing mysterious liquids.",
        ),
        sign_offs=(
            "Stay connected underground.",
            "The colony thanks you.",
            "Please mist responsibly.",
            "May your soil remain excellent.",
            "Until next bloom.",
        ),
    ),

    "goblin": RacerVoice(
        openers=(
            "Oi, write this down:",
            "No rules lawyer can stop me:",
            "I yelled this into existence:",
            "Official goblin statement:",
            "Record this before anyone changes the rules:",
        ),
        boasts=(
            "I found the fastest illegal-looking legal line.",
            "I bullied every corner into cooperating.",
            "I speedran the part where everyone doubted me.",
            "I turned chaos into a championship strategy.",
            "I won with confidence, creativity, and questionable planning.",
            "I discovered shortcuts destiny forgot to remove.",
        ),
        excuses=(
            "the horn started it.",
            "the track patched my favorite exploit.",
            "some coward installed collision detection.",
            "someone fixed the shortcut I definitely discovered first.",
            "the rules changed after I already understood them.",
            "the obstacle clearly had a personal issue.",
        ),
        metaphors=(
            "I hit that finish like a shopping cart full of fireworks.",
            "I was a bad decision with excellent acceleration.",
            "I chewed through the field like a goblin through fine print.",
            "I raced like chaos got a driver's license.",
            "I attacked the track like it owed me money.",
            "I was a victory speech with legs and bad intentions.",
        ),
        reactions=(
            "Again, but louder.",
            "That is going in my exploit guide.",
            "I regret nothing useful.",
            "The goblin council will hear about this.",
            "Beautiful. Suspicious. Perfect.",
            "That went exactly according to my questionable plan.",
        ),
        potion_reactions=(
            "Whoa, hold on. I did not knowingly drink anything magical.",
            "Someone gave me mystery water and forgot to mention the magic part?",
            "I may break rules, but I do not cheat without knowing the rules.",
            "Whoever labeled that potion as water has my respect and my complaints.",
            "I should have inspected the bottle. Rookie mistake.",
            "I am offended someone pulled a trick before I could.",
        ),
        sign_offs=(
            "Stay mad.",
            "Invoice the track.",
            "Tell the rulebook I said hello.",
            "Catch me before they patch me.",
            "I will accept apologies in gold.",
        ),
    ),

    "flying-eye": RacerVoice(
        openers=(
            "I observed the following:",
            "All lenses agree:",
            "My telemetry is unblinking:",
            "Visual analysis complete:",
            "The evidence has been recorded:",
        ),
        boasts=(
            "I saw the winning line three corners before it existed.",
            "my peripheral vision defeated the entire field.",
            "I monitored every threat and still had time to pose.",
            "my calculations predicted the perfect victory path.",
            "every angle favored my performance.",
            "the outcome was visible before everyone noticed.",
        ),
        excuses=(
            "the venue briefly violated my privacy policy.",
            "dust corrupted lens number three.",
            "someone introduced an unaudited blind spot.",
            "the lighting conditions reduced accuracy.",
            "the track introduced an unexpected variable.",
            "my observation window was briefly compromised.",
        ),
        metaphors=(
            "I orbited the chaos like a very judgmental moon.",
            "I cut through the field like a stare through a flimsy alibi.",
            "I watched victory arrive, then met it halfway.",
            "I tracked the competition like a hawk with a schedule.",
            "I navigated the race like a prophecy with excellent vision.",
            "I floated above confusion and selected victory.",
        ),
        reactions=(
            "I saw that coming.",
            "Blink and archive it.",
            "The footage confirms everything.",
            "My analysis remains correct.",
            "The evidence speaks clearly.",
            "The replay supports my conclusion.",
        ),
        potion_reactions=(
            "My analysis confirms I did not knowingly consume an enhancement.",
            "Interesting. The beverage was not what my predictions expected.",
            "I detected unusual energy but not unauthorized intent.",
            "A rare oversight: I monitored the race but not the bottle.",
            "The evidence suggests contamination, not cooperation.",
            "My vision caught everything except the identity of whoever altered it.",
        ),
        sign_offs=(
            "Remain observable.",
            "Consent to victory accepted.",
            "I will be watching the rematch.",
            "The next race is already under surveillance.",
            "My cameras remain active.",
        ),
    ),
}


def _index(seed: str, length: int) -> int:
    digest = hashlib.sha256(seed.encode()).digest()
    return int.from_bytes(digest[:8], "big") % length


def _choose(seed: str, options: Sequence[str]) -> str:
    return options[_index(seed, len(options))]


def _host(caption: str, detail: str) -> DialogueBeat:
    return DialogueBeat(
        speaker_kind="host",
        speaker_name=HIGHLIGHT_HOST_NAME,
        caption=caption,
        detail=detail,
    )


def _racer(
    racer: Mapping[str, Any],
    caption: str,
    detail: str,
) -> DialogueBeat:
    return DialogueBeat(
        speaker_kind="racer",
        speaker_name=str(racer["name"]),
        racer_id=int(racer["racer_id"]),
        sprite_key=str(racer["sprite_key"]),
        caption=caption,
        detail=detail,
    )


def serialize_dialogue(beat: DialogueBeat) -> dict[str, Any]:
    return {
        "speaker": {
            "kind": beat.speaker_kind,
            "name": beat.speaker_name,
            "racer_id": beat.racer_id,
            "sprite_key": beat.sprite_key,
        },
        "caption": beat.caption,
        "detail": beat.detail,
    }


def host_intro(
    playback_key: str,
    *,
    clip_count: int,
    beat: int,
) -> DialogueBeat:
    if beat == 1:
        opener = _choose(
            f"{playback_key}:intro:opener",
            (
                "Good evening, racers, rivals, and fans of irresponsible speed!",
                "Welcome back to the greatest spectacle this side of the enchanted finish line!",
                "The crowd is roaring, the track is trembling, and Chip McChatter has the replay!",
                "Gather your banners and hold onto your helmets—the race report begins now!",
                "Welcome, champions and challengers, to another night of legendary competition!",
                "The starting gates are closed, the excuses are ready, and the footage is here!",
                "Good evening, speed seekers! The track has spoken, and we have the evidence!",
                "From the grandstands to the goblin tunnels, everyone is talking about this race!",
            ),
        )

        promise = _choose(
            f"{playback_key}:intro:promise",
            (
                "Tonight's replay is packed with bold moves, questionable decisions, and one very confused finish line.",
                "We have every turn, every tumble, and every moment where someone thought they had a plan.",
                "Our magical cameras captured the speed, the strategy, and several questionable shortcuts.",
                "The footage is ready, the scoreboard is waiting, and the drama is already warming up.",
                "We slowed down the action so our experts could determine exactly who made the brilliant move and who made the mistake.",
                "Tonight we break down the victories, the surprises, and the moments that made the crowd lose their enchanted hats.",
                "The racers gave us speed. The track gave us chaos. We brought the replay crystal.",
                "Every leap, dodge, and dramatic overtake is waiting for its moment in the spotlight.",
            ),
        )

        return _host(
            f"{opener} {promise}",
            "Chip McChatter opens the post-race spectacular.",
        )

    tease = _choose(
        f"{playback_key}:intro:tease",
        (
            f"I have {clip_count} must-see moments from the track, each one replayed for maximum drama and questionable heroics.",
            f"Roll all {clip_count} highlights! The replay crystal is charged, and the truth is about to be revealed.",
            f"Our {clip_count} biggest moments are ready: the victories, the mistakes, and the decisions nobody can explain.",
            f"Prepare for {clip_count} angles of pure racing chaos, because apparently one view was not enough.",
            f"We have {clip_count} pieces of evidence from the battlefield of speed. The racers may defend themselves afterward.",
            f"Every jump, clash, and impossible comeback from all {clip_count} highlights is ready for review.",
            f"{clip_count} replays await, featuring speed, strategy, and at least one moment where everyone yelled at the same time.",
            f"The replay vault contains {clip_count} legendary moments. Some are impressive. Some require an explanation.",
        ),
    )

    return _host(
        tease,
        f"{clip_count} highlights · half speed · full drama",
    )


def host_clip_reaction(
    playback_key: str,
    *,
    clip_id: str,
    clip_kind: str,
    event_kind: str | None,
    racer_names: Sequence[str],
    source_caption: str,
) -> DialogueBeat:
    subject = " and ".join(racer_names) if racer_names else "the entire field"
    incident = (event_kind or clip_kind).replace("_", " ")
    event_key = event_kind or clip_kind

    event_flavor: Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
        "finish": (
            (
                "Freeze that finish!",
                "Bring up the championship angle!",
                "Enhance the final stretch!",
                "Check the finish crystal!",
                "That is why we watch racing!",
                "The scoreboard is ready for judgment!",
            ),
            (
                "made the final moments unforgettable",
                "found victory in the smallest window",
                "turned pure speed into a legendary finish",
                "crossed the line with championship timing",
                "delivered a finish worthy of the history scrolls",
                "forced the finish line to make the toughest decision of the day",
            ),
        ),

        "destroyed": (
            (
                "The obstacle has officially retired!",
                "Somebody check the structural integrity!",
                "The track crew has been summoned!",
                "That obstacle will remember this race!",
                "Roll the impact replay!",
            ),
            (
                "turned a challenge into a pile of enchanted debris",
                "changed the landscape of the race forever",
                "introduced the obstacle to a very different kind of speed",
                "made the course itself part of the story",
                "left the track with a new landmark",
            ),
        ),

        "knockout": (
            (
                "Replay that collision!",
                "The arena just felt that one!",
                "That was a championship-level impact!",
                "Someone check the recovery spell!",
                "The crowd went silent for that one!",
            ),
            (
                "delivered a dramatic turning point",
                "sent a powerful message to the competition",
                "changed the entire race in one moment",
                "made contact count in the biggest way possible",
                "turned a battle for position into a battle for survival",
            ),
        ),

        "pileup": (
            (
                "We have a full track inspection moment!",
                "Bring up the wide camera!",
                "The field has become a traffic puzzle!",
                "Everyone found the same piece of track!",
                "The replay crystal is working overtime!",
            ),
            (
                "turned the racing line into a complete adventure",
                "created the most crowded corner of the season",
                "made every racer rethink personal space",
                "changed the race with one chaotic chain reaction",
                "created a moment nobody planned for",
            ),
        ),

        "obstacle_hit": (
            (
                "Zoom in on that encounter!",
                "The obstacle gets the first replay!",
                "That was a very one-sided conversation with the scenery!",
                "The course fought back!",
                "The track has entered the competition!",
            ),
            (
                "found the one thing on the course that refused to move",
                "learned that the track always gets a vote",
                "made an unexpected appointment with the scenery",
                "turned a simple mistake into a legendary replay",
                "gave the obstacle its greatest moment of the season",
            ),
        ),

        "portal_hop": (
            (
                "Open the portal replay!",
                "Someone explain the geography!",
                "The track just changed dimensions!",
                "Bring out the map mages!",
                "That shortcut deserves its own chapter!",
            ),
            (
                "rewrote the rules of distance",
                "found a path nobody else could see",
                "turned a normal race into a magical journey",
                "made the track much larger and much smaller at the same time",
                "arrived from a place the scoreboard barely understands",
            ),
        ),

        "wrong_way": (
            (
                "Reverse the replay!",
                "Someone check the direction markers!",
                "The compass is asking questions!",
                "That was a very unusual strategy!",
                "The map has concerns!",
            ),
            (
                "challenged the traditional meaning of forward",
                "treated the track directions as optional advice",
                "created a completely different race strategy",
                "proved confidence can survive even without navigation",
                "took the scenic route through confusion",
            ),
        ),

        "showboat": (
            (
                "Bring out the style camera!",
                "Replay that confidence!",
                "The swagger meter is off the charts!",
                "Give that move the spotlight!",
                "That was maximum flair!",
            ),
            (
                "turned racing into a performance",
                "spent speed for style points",
                "made the finish line wait for the grand entrance",
                "proved confidence can be a strategy",
                "gave the crowd exactly what they came to see",
            ),
        ),

        "stumble": (
            (
                "Slow that moment down!",
                "Replay the recovery!",
                "The track found a weakness!",
                "That was a difficult step in the journey!",
                "Every champion has a moment like this!",
            ),
            (
                "fought gravity and barely won the argument",
                "turned a tiny mistake into a memorable moment",
                "proved recovery is part of racing",
                "created a challenge worthy of the highlight reel",
                "showed that the race is never over until the finish",
            ),
        ),
    }

    flavor = event_flavor.get(event_key)

    opener = _choose(
        f"{playback_key}:{clip_id}:opener",
        flavor[0] if flavor is not None else (
            "Freeze the replay!",
            "Bring up the highlight angle!",
            "The arena cameras caught something special!",
            "Roll the championship footage!",
            "This deserves another look!",
            "The replay crystal has spoken!",
        ),
    )

    action = _choose(
        f"{playback_key}:{clip_id}:action",
        flavor[1] if flavor is not None else (
            "stole the spotlight",
            "changed the momentum",
            "raised the stakes",
            "made the crowd erupt",
            "put on a performance",
            "changed the entire race",
            "proved they belonged here",
            "answered the challenge",
            "kept the pressure alive",
            "made history on the track",
            "showed true racing skill",
            "gave us a moment to remember",
        ),
    )

    verdict = _choose(
        f"{playback_key}:{clip_id}:verdict",
        (
            f"{subject} {action}.",
            f"{subject} turns {incident} into a moment the crowd will remember.",
            f"{subject} has made {incident} look like a championship strategy.",
            f"{subject} just created one of the defining moments of this race.",
            f"{subject} has given the replay crew plenty to talk about.",
        ),
    )

    return _host(
        f"{opener} {verdict}",
        source_caption,
    )


def host_betting_spotlight(
        playback_key: str,
        spotlight: Mapping[str, Any],
) -> DialogueBeat:
    gain = spotlight.get("highest_gain")
    loss = spotlight.get("highest_loss")
    focus = spotlight.get("host_focus")

    def money(cents: int) -> str:
        return f"${abs(cents) / 100:,.2f}"

    if focus == "both" and isinstance(gain, Mapping) and isinstance(loss, Mapping):
        caption = _choose(
            f"{playback_key}:bets:both",
            (
                f"Tonight's betting board has a hero and a casualty! {gain['nickname']} claims a fortune boost of {money(int(gain['net_cents']))}, while {loss['nickname']} learns that predictions can be dangerous magic.",

                f"The odds have spoken! {gain['nickname']} walks away with {money(int(gain['net_cents']))} in winnings, while {loss['nickname']} pays the price for a bold prediction.",

                f"A tale of two fortunes! {gain['nickname']} rises on the leaderboard with {money(int(gain['net_cents']))}, while {loss['nickname']} faces the legendary cost of being wrong.",

                f"The betting arena has delivered its verdict! Celebration for {gain['nickname']}, sympathy for {loss['nickname']}, and a reminder that every wager carries a story.",
            ),
        )

    elif focus == "gain" and isinstance(gain, Mapping):
        caption = _choose(
            f"{playback_key}:bets:gain",
            (
                f"The betting champion of this race is {gain['nickname']}! A brilliant prediction earns a reward of {money(int(gain['net_cents']))}.",

                f"Raise the banners for {gain['nickname']}! Their instincts were sharper than a champion's blade, gaining {money(int(gain['net_cents']))}.",

                f"The odds were challenged and victory was claimed! {gain['nickname']} turns a prediction into {money(int(gain['net_cents']))} of pure profit.",

                f"Someone studied the racers, trusted their instincts, and now {gain['nickname']} collects {money(int(gain['net_cents']))}.",
            ),
        )

    elif focus == "loss" and isinstance(loss, Mapping):
        caption = _choose(
            f"{playback_key}:bets:loss",
            (
                f"Not every prophecy comes true. {loss['nickname']} loses {money(int(loss['net_cents']))}, but true competitors know every great comeback starts somewhere.",

                f"The betting scroll was unforgiving tonight. {loss['nickname']} falls by {money(int(loss['net_cents']))}, but the arena remembers the courage behind the wager.",

                f"A bold prediction was made, and the race had other plans. {loss['nickname']} drops {money(int(loss['net_cents']))} in tonight's betting battle.",

                f"The fortune wheel did not turn in {loss['nickname']}'s favor. A loss of {money(int(loss['net_cents']))}, but plenty of racing left ahead.",
            ),
        )

    else:
        caption = _choose(
            f"{playback_key}:bets:none",
            (
                "The wagers are settled, the predictions are recorded, and the betting arena prepares for the next challenge.",

                "The gold has changed hands, the guesses have been judged, and the racers live to influence another wager.",

                "The betting board has closed for now. Some celebrate, some recover, and everyone is already thinking about the next race.",

                "No major fortune shifts this round, but every prediction tells part of the racing story.",
            ),
        )

    return _host(
        caption,
        f"{int(spotlight['bet_count'])} settled bets from {int(spotlight['player_count'])} players",
    )


def host_record_intro(playback_key: str, count: int) -> DialogueBeat:
    caption = _choose(
        f"{playback_key}:records:intro",
        (
            f"HOLD EVERYTHING! The record books are being rewritten! {count} new world record{'s' if count != 1 else ''} have been set tonight!",

            f"History has arrived at the arena! {count} record{'s' if count != 1 else ''} have fallen, and the champions who made it happen will be remembered!",

            f"Sound the victory horns! The impossible just became official—{count} new world record{'s' if count != 1 else ''} are entering the archives!",

            f"The legends grow tonight! Our historians are updating the record scrolls after {count} incredible new achievement{'s' if count != 1 else ''}.",

            f"Champions are made in moments like this! {count} world record{'s' if count != 1 else ''} have been shattered before our very eyes!",

            f"Raise the banners and open the archives! The arena has witnessed {count} record-breaking performance{'s' if count != 1 else ''}!",

            f"The replay crystal is glowing, the record keepers are scrambling, and {count} new mark{'s' if count != 1 else ''} have been carved into racing history!",

            f"Attention racers and fans! Tonight's competition has crossed into legendary territory with {count} new world record{'s' if count != 1 else ''}!",
        ),
    )
    return _host(
        caption,
        "WORLD RECORD ALERT · the record book is changing live",
    )


def host_record_shoutout(
        playback_key: str,
        *,
        index: int,
        record: Mapping[str, Any],
) -> DialogueBeat:
    racer = str(record["racer_name"])
    label = str(record["label"])
    value = str(record["display_value"])

    caption = _choose(
        f"{playback_key}:records:{index}:{record['metric']}",
        (
            f"Make way for a new legend! {racer} now holds {label} at {value}! The record archives have a brand-new name written across the top.",

            f"Raise the banners! {racer} has officially claimed {label} with a mark of {value}. That is not just a number—that is racing history.",

            f"The arena has witnessed greatness! {racer} sets the new standard for {label}: {value}. Every future challenger now has a target.",

            f"History has a new champion! {racer} takes the record for {label} at {value}, and the old mark has been sent into the archives.",

            f"Record keepers, update the scrolls! {racer} has shattered expectations with {label}: {value}. A new chapter begins today.",

            f"The crowd will remember this moment! {racer} conquers {label} at {value}, earning a permanent place among the greats.",

            f"That is a performance worthy of a trophy room! {racer} now owns {label} at {value}. The competition has a new mountain to climb.",

            f"The impossible has become official! {racer} has rewritten the record for {label} with a stunning {value}.",
        ),
    )

    previous = record.get("previous_racer_name")
    detail = (
        f"New holder · previous record by {previous} · history rewritten"
        if isinstance(previous, str) and previous
        else "First official holder · the legend begins"
    )

    return _host(
        caption,
        detail,
    )


def host_record_finale(playback_key: str, count: int) -> DialogueBeat:
    caption = _choose(
        f"{playback_key}:records:finale",
        (
            "Raise the banners, light the victory flames, and celebrate the champions! Tonight's record breakers have earned their place in racing history.",

            "The archives are updated, the legends are recorded, and the arena has witnessed greatness. A final salute to tonight's record breakers!",

            "The record books close on an unforgettable night! The champions have spoken, the numbers have changed, and history moves forward.",

            "One final cheer for the racers who pushed beyond the impossible! Their names will stand in the records until someone dares to challenge them.",

            "The crowd has witnessed history, the record keepers have finished their work, and the legends of tonight's race are officially written.",

            "The victory horns sound across the arena! Tonight's record breakers leave behind more than numbers—they leave behind a legacy.",

            "What a night of competition! The records have fallen, the champions have risen, and the next challengers are already watching.",

            "Close the archives and celebrate the heroes! Tonight's racers have carved their names into the greatest moments this track has ever seen.",
        ),
    )

    return _host(
        caption,
        f"{count} new record{'s' if count != 1 else ''} · final championship celebration",
    )


def host_podium(
        playback_key: str,
        winner: Mapping[str, Any] | None,
) -> DialogueBeat:
    if winner is None:
        return _host(
            _choose(
                f"{playback_key}:podium:none",
                (
                    "An unbelievable result! No racer reached the finish line, and tonight the track itself claims victory.",
                    "The arena has delivered the rarest outcome: complete chaos. No champion stands above the rest tonight.",
                    "No official winner has emerged, but the crowd has witnessed a race that will be discussed for ages.",
                    "The finish line remains untouched, the racers remain confused, and chaos takes the trophy.",
                ),
            ),
            "No official finisher · chaos claims the championship",
        )

    name = str(winner["name"])

    caption = _choose(
        f"{playback_key}:podium:{winner['racer_id']}",
        (
            f"Raise the banners for {name}! The champion has conquered the track and earned a place in racing history.",

            f"The crowd erupts for {name}! Gold belongs to the racer who mastered speed, strategy, and everything this course could throw at them.",

            f"{name} stands above the field as today's champion! The trophy is claimed, the legends grow, and the celebration begins.",

            f"Sound the victory horns! {name} takes the top step of the podium and writes another chapter in the racing chronicles.",

            f"The final results are official! {name} has earned the gold and proven themselves among the greatest racers in the arena.",

            f"Champions are made in moments like this! {name} rises above the competition and claims the ultimate prize.",

            f"The track has chosen its champion! {name} takes the gold, the glory, and the cheers of the crowd.",

            f"After twists, turns, and impossible challenges, {name} stands victorious. A well-earned championship performance!",
        ),
    )

    return _host(
        caption,
        "Gold · silver · bronze · championship podium ceremony",
    )


def winner_interview_question(
    playback_key: str,
    winner: Mapping[str, Any],
) -> tuple[str, DialogueBeat]:
    question_kind = _choose(
        f"{playback_key}:interview:theme:{winner['racer_id']}",
        ("strategy", "chaos", "legacy", "rivals"),
    )

    name = str(winner["name"])

    questions = {
        "strategy": (
            (
                f"{name}, take us inside that championship performance. What was the plan when the gates opened?",
                f"{name}, everyone saw the result. What was the strategy that carried you to victory?",
                f"{name}, was this a carefully crafted plan or did greatness simply find you today?",
                f"{name}, what was the key moment where you knew this race was yours?",
            )
        ),

        "chaos": (
            (
                f"{name}, this race had more twists than a wizard's map. How did you stay focused through the chaos?",
                f"{name}, when the track turned unpredictable, what helped you keep control?",
                f"{name}, obstacles, surprises, and impossible moments filled this race. How did you overcome them?",
                f"{name}, the arena witnessed absolute chaos today. How did you turn that chaos into victory?",
            )
        ),

        "legacy": (
            (
                f"{name}, champions are remembered long after the finish line. What does this victory mean to you?",
                f"{name}, does this feel like the beginning of something bigger for your racing career?",
                f"{name}, your name is now part of racing history. What do you want future challengers to remember?",
                f"{name}, today you earned your place among the legends. How does it feel to join them?",
            )
        ),

        "rivals": (
            (
                f"{name}, the competition pushed you all race long. Which rival made you fight hardest for this victory?",
                f"{name}, every champion needs a worthy opponent. Who challenged you the most today?",
                f"{name}, the field gave everything they had. Which racer impressed you the most?",
                f"{name}, when you took the lead, did you know the rest of the field was still coming for you?",
            )
        ),
    }

    question = _choose(
        f"{playback_key}:interview:question:{winner['racer_id']}",
        questions[question_kind],
    )

    return question_kind, _host(
        question,
        f"Chip goes trackside with {name}.",
    )


def winner_interview_answer(
    playback_key: str,
    winner: Mapping[str, Any],
    *,
    question_kind: str,
) -> DialogueBeat:
    voice = RACER_VOICES.get(
        str(winner["sprite_key"]),
        GENERIC_VOICE,
    )

    racer_id = str(winner["racer_id"])

    opener = _choose(
        f"{playback_key}:answer:opener:{racer_id}",
        voice.openers,
    )

    if question_kind == "strategy":
        middle = _choose(
            f"{playback_key}:answer:boast:{racer_id}",
            voice.boasts,
        )

        bridge = _choose(
            f"{playback_key}:answer:strategy_bridge:{racer_id}",
            (
                "I trusted the plan from the very beginning.",
                "Every move had a purpose.",
                "I knew exactly when to make my move.",
                "The key was staying focused when everyone else panicked.",
                "Champions prepare for moments like this.",
            ),
        )

        answer = f"{opener} {bridge} {middle}"

    elif question_kind == "chaos":
        middle = _choose(
            f"{playback_key}:answer:metaphor:{racer_id}",
            voice.metaphors,
        )

        bridge = _choose(
            f"{playback_key}:answer:chaos_bridge:{racer_id}",
            (
                "When everything went wrong, I knew I was in my element.",
                "The chaos was just another obstacle to overcome.",
                "A great racer does not fear the unexpected.",
                "The track tried to surprise me, but I was ready.",
                "That kind of race is why I compete.",
            ),
        )

        answer = f"{opener} {bridge} {middle}"

    elif question_kind == "legacy":
        reaction = _choose(
            f"{playback_key}:answer:reaction:{racer_id}",
            voice.reactions,
        )

        boast = _choose(
            f"{playback_key}:answer:boast:{racer_id}",
            voice.boasts,
        )

        bridge = _choose(
            f"{playback_key}:answer:legacy_bridge:{racer_id}",
            (
                "I hope this is only the beginning.",
                "This moment belongs to everyone who believed in me.",
                "Records fade, but legends remain.",
                "I came here to compete, and I leave here remembered.",
                "Today was special, but I am not finished yet.",
            ),
        )

        answer = f"{opener} {bridge} {reaction} {boast}"

    else:  # rivals
        metaphor = _choose(
            f"{playback_key}:answer:metaphor:{racer_id}",
            voice.metaphors,
        )

        bridge = _choose(
            f"{playback_key}:answer:rival_bridge:{racer_id}",
            (
                "The field was strong, and I respect anyone brave enough to race me.",
                "My rivals pushed me harder than they realize.",
                "A champion needs competition, and today I had plenty.",
                "They gave me a challenge worth remembering.",
                "I knew I had to bring my best.",
            ),
        )

        answer = f"{opener} {bridge} {metaphor}"

    sign_off = _choose(
        f"{playback_key}:answer:signoff:{racer_id}",
        voice.sign_offs,
    )

    return _racer(
        winner,
        f"{answer} {sign_off}",
        f"{winner['name']} joins Chip live at trackside",
    )


def host_potion_callout(
        playback_key: str,
        winner: Mapping[str, Any],
        potion: Mapping[str, Any],
) -> DialogueBeat:
    name = str(winner["name"])
    item_name = str(potion["item_name"])

    caption = _choose(
        f"{playback_key}:potion:callout:{potion['effect_id']}",
        (
            f"Hold the celebration, {name}! Officials have discovered something unusual. The hydration sample tested positive for {item_name}. The question now: did you know what you were drinking?",

            f"We have a developing story from the trackside desk! A routine beverage check revealed traces of {item_name} before the race. {name}, can you explain how that ended up in your cup?",

            f"Breaking from the investigation desk: the champion's pre-race drink contained an unexpected magical effect. Tests confirm the presence of {item_name}. The mystery begins here.",

            f"The officials have completed their analysis, and the results are surprising. {name}'s hydration was not ordinary water—it contained the effects of {item_name}. The arena wants answers.",

            f"Attention racers and fans! We have an unusual development. A drink believed to be standard hydration has tested positive for {item_name}. {name}, this victory now comes with some questions.",

            f"The replay crystal showed the race. The alchemy report shows something else. {name}, the beverage you consumed before the race contained {item_name}. Was this known, or was this a surprise?",

            f"Championship review is underway! Officials have confirmed an unauthorized magical effect: {item_name} was detected in the winner's drink. We need the racer's side of the story.",

            f"This is not a normal post-race interview. The officials found evidence of {item_name} in a pre-race beverage. {name}, before we discuss the victory, we need to discuss the drink.",
        ),
    )

    return _host(
        caption,
        f"POTION INVESTIGATION · unauthorized magical effect detected #{potion['effect_id']}",
    )


def winner_potion_response(
    playback_key: str,
    winner: Mapping[str, Any],
    potion: Mapping[str, Any],
) -> DialogueBeat:
    voice = RACER_VOICES.get(
        str(winner["sprite_key"]),
        GENERIC_VOICE,
    )

    racer_id = str(winner["racer_id"])
    item_name = str(potion["item_name"])
    buyer = str(potion["buyer"])

    potion_reaction = _choose(
        f"{playback_key}:potion:reaction:{racer_id}",
        voice.potion_reactions,
    )

    defense = _choose(
        f"{playback_key}:potion:defense:{racer_id}",
        (
            "I want to be clear: I had no idea there was anything unusual in that drink.",
            "I signed up to race, not to participate in some magical experiment.",
            "I trained for this victory. I did not train with mystery beverages.",
            "Whatever happened with that bottle, I earned my place on the podium.",
            "I would never knowingly use something that could compromise a fair race.",
            "The victory is mine, but I want answers about what happened.",
        ),
    )

    suspicion = _choose(
        f"{playback_key}:potion:suspicion:{racer_id}",
        (
            f"That said... {buyer} was acting a little unusual near the drinks before the race.",
            f"I am not making accusations, but {buyer} seemed very interested in my hydration situation.",
            f"I did notice {buyer} paying a surprising amount of attention to that bottle.",
            f"I cannot prove anything, but the timing involving {buyer} is certainly interesting.",
            f"Maybe it is nothing, but {buyer} did seem unusually confident that I would enjoy that drink.",
            f"I am just saying, if someone knew what was happening, I would start asking questions around {buyer}.",
        ),
    )

    victory_statement = _choose(
        f"{playback_key}:potion:victory:{racer_id}",
        (
            "The potion did not drive the racer. I did.",
            "A strange drink does not replace skill.",
            "The track still had to be conquered.",
            "Magic may have been involved, but so was talent.",
            "Whatever the investigation finds, I still crossed that finish line first.",
        ),
    )

    reaction = _choose(
        f"{playback_key}:potion:reaction_line:{racer_id}",
        voice.reactions,
    )

    metaphor = _choose(
        f"{playback_key}:potion:metaphor:{racer_id}",
        voice.metaphors,
    )

    sign_off = _choose(
        f"{playback_key}:potion:signoff:{racer_id}",
        voice.sign_offs,
    )

    return _racer(
        winner,
        (
            f"{potion_reaction} "
            f"{defense} "
            f"{suspicion} "
            f"{victory_statement} "
            f"{reaction} "
            f"{metaphor} "
            f"{sign_off}"
        ),
        f"{winner['name']} responds to the mysterious {item_name} investigation",
    )


def host_outro(playback_key: str, winner_name: str | None) -> DialogueBeat:
    subject = winner_name or "the house"

    caption = _choose(
        f"{playback_key}:outro",
        (
            f"That is the race! Congratulations to {subject}, tonight's champion. I am Chip McChatter, and from the arena to the archives, this story is officially recorded.",

            f"The finish line is crossed, the legends are written, and the crowd has spoken! Congratulations to {subject}. I am Chip McChatter, signing off from an unforgettable night of racing.",

            f"One final cheer for {subject}! Through chaos, competition, and questionable track decisions, we have witnessed a champion emerge. This is Chip McChatter saying: what a race!",

            f"The banners are raised, the trophies are polished, and the track is finally catching its breath. Congratulations to {subject}, and thank you for joining us for tonight's spectacular showdown.",

            f"Another chapter of racing history comes to a close! Congratulations to {subject}. I am Chip McChatter, reminding you that in this arena, anything can happen—and usually does.",

            f"The crowd has roared, the racers have battled, and the record books have a new story to tell. Congratulations to {subject}. Until next time, keep your helmets on and your strategies ready.",

            f"From the starting horn to the final celebration, what a journey! Congratulations to {subject}, our champion. I am Chip McChatter, and this broadcast is officially complete.",

            f"That concludes tonight's legendary race! Congratulations to {subject}. The track will rest, the racers will recover, and somewhere a future champion is already preparing.",
        ),
    )

    return _host(
        caption,
        "Broadcast complete · thanks for watching",
    )
