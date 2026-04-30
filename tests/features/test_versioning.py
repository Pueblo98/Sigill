"""W2.3.3 — feature version coexistence.

When a feature is recomputed under a new version, predictions written before
the bump must remain queryable in their original version, and post-bump
predictions must write with the new version. Querying by `(feature_name,
version)` must return the right slice.

Schema (REVIEW-DECISIONS 2C): `prediction_features(prediction_id, feature_name,
value, version)` is a child of Prediction with a composite primary key on
`(prediction_id, feature_name)` and an index on `(feature_name, version)`.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from sigil.models import Prediction, PredictionFeature


pytestmark = pytest.mark.critical


async def _new_prediction(session, sample_market, predicted_prob: float = 0.6) -> Prediction:
    pred = Prediction(
        id=uuid4(),
        market_id=sample_market.id,
        model_id="m",
        model_version="v1",
        predicted_prob=predicted_prob,
        confidence=1.0,
    )
    session.add(pred)
    await session.flush()
    return pred


@pytest.mark.asyncio
async def test_old_version_features_stay_queryable_after_bump(session, sample_market):
    pred_old = await _new_prediction(session, sample_market, 0.55)
    session.add(
        PredictionFeature(
            prediction_id=pred_old.id,
            feature_name="elo_diff",
            value=42.0,
            version=1,
        )
    )
    await session.commit()

    pred_new = await _new_prediction(session, sample_market, 0.62)
    session.add(
        PredictionFeature(
            prediction_id=pred_new.id,
            feature_name="elo_diff",
            value=58.0,
            version=2,
        )
    )
    await session.commit()

    v1_rows = (
        await session.execute(
            select(PredictionFeature)
            .where(PredictionFeature.feature_name == "elo_diff")
            .where(PredictionFeature.version == 1)
        )
    ).scalars().all()
    assert len(v1_rows) == 1
    assert v1_rows[0].prediction_id == pred_old.id
    assert float(v1_rows[0].value) == pytest.approx(42.0)

    v2_rows = (
        await session.execute(
            select(PredictionFeature)
            .where(PredictionFeature.feature_name == "elo_diff")
            .where(PredictionFeature.version == 2)
        )
    ).scalars().all()
    assert len(v2_rows) == 1
    assert v2_rows[0].prediction_id == pred_new.id
    assert float(v2_rows[0].value) == pytest.approx(58.0)


@pytest.mark.asyncio
async def test_count_by_feature_name_aggregates_across_versions(session, sample_market):
    pred_a = await _new_prediction(session, sample_market, 0.55)
    pred_b = await _new_prediction(session, sample_market, 0.62)
    session.add_all(
        [
            PredictionFeature(prediction_id=pred_a.id, feature_name="rest_days", value=3.0, version=1),
            PredictionFeature(prediction_id=pred_b.id, feature_name="rest_days", value=4.0, version=2),
        ]
    )
    await session.commit()

    all_rows = (
        await session.execute(
            select(PredictionFeature).where(PredictionFeature.feature_name == "rest_days")
        )
    ).scalars().all()
    assert len(all_rows) == 2
    assert {r.version for r in all_rows} == {1, 2}


@pytest.mark.asyncio
async def test_same_prediction_can_carry_multiple_features(session, sample_market):
    """Composite PK on (prediction_id, feature_name) means one prediction can
    have many distinct features but only one row per feature_name."""
    pred = await _new_prediction(session, sample_market)
    session.add_all(
        [
            PredictionFeature(prediction_id=pred.id, feature_name="elo_diff", value=12.0, version=1),
            PredictionFeature(prediction_id=pred.id, feature_name="rest_days", value=3.0, version=1),
        ]
    )
    await session.commit()

    rows = (
        await session.execute(
            select(PredictionFeature).where(PredictionFeature.prediction_id == pred.id)
        )
    ).scalars().all()
    assert {r.feature_name for r in rows} == {"elo_diff", "rest_days"}


@pytest.mark.asyncio
async def test_predictions_join_features_by_version(session, sample_market):
    """Prediction → features relationship returns version-aware children."""
    pred = await _new_prediction(session, sample_market)
    session.add_all(
        [
            PredictionFeature(prediction_id=pred.id, feature_name="f1", value=1.0, version=1),
            PredictionFeature(prediction_id=pred.id, feature_name="f2", value=2.0, version=2),
        ]
    )
    await session.commit()

    refreshed = await session.get(Prediction, pred.id, populate_existing=True)
    await session.refresh(refreshed, attribute_names=["features"])
    by_name = {f.feature_name: f for f in refreshed.features}
    assert by_name["f1"].version == 1
    assert by_name["f2"].version == 2
