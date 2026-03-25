import os
from unittest.mock import patch

import pytest

from config import validate_config


class TestValidateConfig:
    @patch.dict(
        os.environ,
        {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "12345"},
    )
    def test_valid_config(self):
        # Should not raise
        # Need to reimport to pick up patched env
        import importlib
        import config
        importlib.reload(config)
        config.validate_config()

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_required_vars(self):
        import importlib
        import config
        importlib.reload(config)
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            config.validate_config()
