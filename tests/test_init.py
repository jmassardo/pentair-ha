"""Tests for Pentair EasyTouch integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.pentair_easytouch import async_setup_entry
from custom_components.pentair_easytouch.const import DOMAIN


@pytest.mark.asyncio
async def test_options_do_not_register_reload_listener() -> None:
    """Changing the super chlor timer must not reload the integration."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    entry = MagicMock()
    entry.entry_id = "test_entry"

    coordinator = MagicMock()
    coordinator.start = AsyncMock()
    coordinator.wait_for_first_update = AsyncMock()

    with patch(
        "custom_components.pentair_easytouch.PentairCoordinator",
        return_value=coordinator,
    ):
        assert await async_setup_entry(hass, entry) is True

    assert hass.data[DOMAIN][entry.entry_id] is coordinator
    entry.add_update_listener.assert_not_called()
