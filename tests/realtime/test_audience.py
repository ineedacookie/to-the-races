from __future__ import annotations

import pytest
from apps.realtime.audience import AudienceValidationError, parse_audience_reaction

pytestmark = pytest.mark.django_db


def test_audience_reaction_validation() -> None:
    reaction = parse_audience_reaction({"kind": "cheer"})
    assert reaction.kind == "cheer"
    assert reaction.text == "CHEER!"

    with pytest.raises(AudienceValidationError, match="Links"):
        parse_audience_reaction({"kind": "shout", "text": "visit http://evil.test"})

    with pytest.raises(AudienceValidationError, match="not allowed"):
        parse_audience_reaction({"kind": "shout", "text": "damn"})

    class_act = parse_audience_reaction({"kind": "shout", "text": "class act!"})
    assert class_act.text == "class act!"

    with pytest.raises(AudienceValidationError, match="kind"):
        parse_audience_reaction({"kind": "wave", "text": "hi"})
