from collections import Counter, defaultdict

from django.db import migrations


def _milliseconds(ticks, tick_rate):
    if tick_rate <= 0:
        return 0
    return max((ticks * 1_000 + tick_rate // 2) // tick_rate, 0)


def _consider(best, metric, value, entry, *, lower_is_better=False):
    if value <= 0:
        return
    existing = best.get(metric)
    if existing is None:
        best[metric] = (value, entry)
        return
    existing_value, existing_entry = existing
    is_better = value < existing_value if lower_is_better else value > existing_value
    if is_better or (
        value == existing_value and entry.racer_id < existing_entry.racer_id
    ):
        best[metric] = (value, entry)


def _seed_records(apps, schema_editor):
    Race = apps.get_model("racing", "Race")
    RacerWorldRecord = apps.get_model("racing", "RacerWorldRecord")
    best = {}
    races = (
        Race.objects.filter(round__settled_at__isnull=False)
        .select_related("round")
        .prefetch_related("entries")
        .order_by("round__number")
    )
    for race in races.iterator(chunk_size=50):
        entries = list(race.entries.all())
        entries_by_racer = {entry.racer_id: entry for entry in entries}
        for entry in entries:
            if entry.finish_place is None or entry.finish_tick is None:
                continue
            _consider(
                best,
                "fastest_finish",
                _milliseconds(entry.finish_tick, race.tick_rate),
                entry,
                lower_is_better=True,
            )

        frames = sorted(
            (
                frame
                for frame in (race.timeline or [])
                if isinstance(frame, dict) and isinstance(frame.get("tick"), int)
            ),
            key=lambda frame: frame["tick"],
        )
        falls = Counter()
        crawl_ticks = defaultdict(int)
        previous_states = {}
        for index, frame in enumerate(frames):
            tick = frame["tick"]
            next_tick = (
                frames[index + 1]["tick"]
                if index + 1 < len(frames)
                else max(race.duration_ticks, tick)
            )
            interval_ticks = max(next_tick - tick, 0)
            racers = frame.get("racers")
            if not isinstance(racers, list):
                continue
            for racer_frame in racers:
                if not isinstance(racer_frame, dict):
                    continue
                racer_id = racer_frame.get("id")
                state = racer_frame.get("state")
                if not isinstance(racer_id, int) or not isinstance(state, str):
                    continue
                if state == "fallen":
                    crawl_ticks[racer_id] += interval_ticks
                    if previous_states.get(racer_id) != "fallen":
                        falls[racer_id] += 1
                previous_states[racer_id] = state
        for racer_id, value in falls.items():
            entry = entries_by_racer.get(racer_id)
            if entry is not None:
                _consider(best, "most_falls", value, entry)
        for racer_id, ticks in crawl_ticks.items():
            entry = entries_by_racer.get(racer_id)
            if entry is not None:
                _consider(
                    best,
                    "longest_crawl",
                    _milliseconds(ticks, race.tick_rate),
                    entry,
                )

        metric_by_kind = {
            "wrong_way": "most_wrong_way",
            "recover": "most_recoveries",
            "showboat": "most_showboats",
        }
        counts = defaultdict(Counter)
        for event in race.events or []:
            if not isinstance(event, dict):
                continue
            metric = metric_by_kind.get(event.get("kind"))
            racer_id = event.get("racer_id")
            if metric is not None and isinstance(racer_id, int):
                counts[metric][racer_id] += 1
        for metric, metric_counts in counts.items():
            for racer_id, value in metric_counts.items():
                entry = entries_by_racer.get(racer_id)
                if entry is not None:
                    _consider(best, metric, value, entry)

    RacerWorldRecord.objects.bulk_create(
        [
            RacerWorldRecord(
                metric=metric,
                value=value,
                racer_id=entry.racer_id,
                round_id=entry.race.round_id,
                race_entry_id=entry.pk,
            )
            for metric, (value, entry) in best.items()
        ]
    )


def _clear_records(apps, schema_editor):
    RacerWorldRecord = apps.get_model("racing", "RacerWorldRecord")
    RacerWorldRecord.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("racing", "0016_racer_world_records"),
    ]

    operations = [
        migrations.RunPython(_seed_records, _clear_records),
    ]
