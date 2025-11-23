import pytest
from unittest.mock import ANY

from app.handlers.survey.commands import start_survey
from app.states import SurveyStates
from app.texts.survey import GENDER_QUESTION


@pytest.mark.asyncio
async def test_start_survey_starts_flow(callback_query, state):
    callback_query.data = "survey:start"

    await start_survey(callback_query, state)

    assert await state.get_state() == SurveyStates.GENDER.state
    callback_query.message.answer.assert_awaited_with(
        GENDER_QUESTION,
        reply_markup=ANY,
        parse_mode="HTML",
    )
    callback_query.answer.assert_awaited()
