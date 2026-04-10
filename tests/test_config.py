import importlib
import os
from unittest.mock import patch

import pytest


class TestValidateConfig:
    @patch.dict(
        os.environ,
        {
            'TELEGRAM_BOT_TOKEN': 'test-token',
            'TELEGRAM_CHAT_ID': '12345',
        },
        clear=True,
    )
    def test_valid_config(self):
        import ai_news_digest.config.settings as settings
        importlib.reload(settings)
        settings.validate_config()

    @patch.dict(
        os.environ,
        {
            'TELEGRAM_DESTINATIONS_JSON': '[{"name":"main","chat_id":"123","bot_token":"abc"}]',
        },
        clear=True,
    )
    def test_destinations_json_supported(self):
        import ai_news_digest.config.settings as settings
        importlib.reload(settings)
        destinations = settings.get_telegram_destinations()
        assert len(destinations) == 1
        assert destinations[0]['chat_id'] == '123'

    @patch('dotenv.load_dotenv')
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_required_vars(self, _mock_load_dotenv):
        import ai_news_digest.config.settings as settings
        importlib.reload(settings)
        with pytest.raises(ValueError, match='Missing Telegram destination configuration'):
            settings.validate_config()
