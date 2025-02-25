import asyncio
import logging
from typing import Any, Dict, Optional

from zigpy.config import (
    CONF_DEVICE,
    CONF_DEVICE_PATH,
    CONF_DEVICE_BAUDRATE,
    CONF_DATABASE,
    CONF_OTA,
    CONF_NWK,
)

from zha.application.const import RadioType
from zha.application.gateway import Gateway
from zha.application.helpers import (
    ZHAData,
    CoordinatorConfiguration,
    QuirksConfiguration,
    DeviceOptions,
    ZHAConfiguration,
)
from zha.event import EventBase
from zha.decorators import periodic

from mqtt_handler import MQTTHandler
from event_handler import EventHandler
from cluster_handler import ClusterHandler

logger = logging.getLogger(__name__)


class Coordinator(EventBase):
    """Coordinator for managing ZHA network and MQTT interface."""

    def __init__(self, device_path: str, mqtt_config: Dict[str, Any] = None):
        """Initialize coordinator."""
        logger.debug("Coordinator init")
        super().__init__()
        self.device_path = device_path
        self.gateway: Optional[Gateway] = None
        self.loop = None

        # Timeouts
        self.startup_timeout = 60  # seconds
        self.command_timeout = 15  # seconds

        # Initialize handlers
        self.mqtt_handler = MQTTHandler(self, mqtt_config)
        self.event_handler = EventHandler(self)
        self.cluster_handler = ClusterHandler(self)

    async def start(self) -> None:
        """Start the coordinator."""
        try:
            # Start MQTT
            self.mqtt_handler.start()

            # Start Zigbee network with retry
            config = self._create_zigbee_config()
            retry_count = 3
            last_error = None

            for attempt in range(retry_count):
                try:
                    await self._start_zigbee_network(config)
                    break
                except Exception as e:
                    last_error = e
                    if attempt == retry_count - 1:
                        raise last_error from e
                    logger.warning(
                        "Retry %s/%s after error: %s", attempt + 1, retry_count, str(e)
                    )
                    await asyncio.sleep(2)

            # Publish initial status
            await self.mqtt_handler.publish_status("online")

        except Exception as e:
            logger.error("Failed to start coordinator", exc_info=e)
            await self.mqtt_handler.publish_status("offline")
            raise

    async def stop(self) -> None:
        """Stop the coordinator."""
        try:
            await self.mqtt_handler.publish_status("offline")

            if self.gateway:
                await self.gateway.shutdown()

            self.mqtt_handler.stop()

        except Exception as e:
            logger.error("Error stopping coordinator", exc_info=e)

    async def _start_zigbee_network(self, zigpy_config: Dict[str, Any]) -> None:
        """Initialize zigbee network."""
        try:
            self.loop = asyncio.get_running_loop()

            # Create configuration objects
            coordinator_config = CoordinatorConfiguration(
                path=self.device_path, baudrate=115200, radio_type=RadioType.zboss.name
            )

            config = ZHAConfiguration(
                coordinator_configuration=coordinator_config,
                quirks_configuration=QuirksConfiguration(enabled=False),
                device_options=DeviceOptions(
                    enable_identify_on_join=True,
                    consider_unavailable_mains=7200,
                    consider_unavailable_battery=21600,
                    enable_mains_startup_polling=True,
                ),
            )

            # Create ZHA data object
            zha_data = ZHAData(
                zigpy_config=zigpy_config, config=config, allow_polling=True
            )

            # Create gateway
            try:
                self.gateway = await asyncio.wait_for(
                    Gateway.async_from_config(zha_data), timeout=self.startup_timeout
                )
                self.mqtt_handler.update_gateway(self.gateway)

                await self.gateway.async_initialize()
                await self.gateway.async_initialize_devices_and_entities()
            except asyncio.TimeoutError:
                raise RuntimeError("Gateway initialization timeout") from None

            self.event_handler.setup_event_handlers(self.gateway)
            self.cluster_handler.setup_cluster_handlers(self.gateway)

            logger.debug("Zigbee network successfully initialized")

        except Exception as e:
            logger.error("Failed to start Zigbee network", exc_info=e)
            raise

    def _create_zigbee_config(self) -> Dict[str, Any]:
        """Create Zigbee configuration."""
        return {
            CONF_DEVICE: {
                CONF_DEVICE_PATH: self.device_path,
                CONF_DEVICE_BAUDRATE: 115200,
            },
            "radio_type": RadioType.zboss.name,
            CONF_DATABASE: "zigbee.db",
            CONF_OTA: {
                "enabled": False,
                "providers": [],
            },
            CONF_NWK: {
                "channel": 15,
                "channels": [15],
                "pan_id": None,
                "extended_pan_id": None,
            },
            "startup_energy_scan": False,
            "source_routing": False,
            "connect": {
                "attempts": 3,
                "retry_delay": 2.0,
            },
        }

    @periodic((30, 45))
    async def _refresh_devices(self):
        """Периодическое обновление состояния устройств."""
        try:
            if not self.gateway or not self.gateway.devices:
                return

            for device in self.gateway.devices.values():
                if device.is_coordinator:
                    continue

                for endpoint in device.endpoints.values():
                    if endpoint.id == 0:  # Пропускаем ZDO endpoint
                        continue

                    for cluster_handler in endpoint.all_cluster_handlers.values():
                        try:
                            await cluster_handler.async_update()
                        except Exception as e:
                            logger.debug(
                                "Error updating cluster 0x%04x for device %s: %s",
                                cluster_handler.cluster.cluster_id,
                                device.ieee,
                                str(e),
                            )

        except Exception as e:
            logger.error("Error in periodic refresh: %s", str(e))
