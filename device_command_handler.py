import asyncio
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class DeviceCommandHandler:
    """Handler for device-specific commands."""

    def __init__(self, gateway, mqtt_handler):
        """Initialize device command handler."""
        self.gateway = gateway
        self.mqtt_handler = mqtt_handler

    async def handle_switch_command(self, ieee: str, state: bool):
        """Handle switch command."""
        try:
            # Добавим отладочную информацию о всех устройствах
            logger.debug("Available devices:")
            for dev_ieee, device in self.gateway.devices.items():
                logger.debug(f"IEEE: {dev_ieee} (type: {type(dev_ieee)}), NWK: 0x{device.nwk:04x}")

            # Находим устройство по IEEE адресу
            device = self.gateway.devices.get(ieee)
            if not device:
                # Попробуем найти устройство другим способом
                for dev in self.gateway.devices.values():
                    if str(dev.ieee) == ieee:
                        device = dev
                        break

                if not device:
                    logger.error(f"Device {ieee} not found. Available devices: {list(self.gateway.devices.keys())}")
                    return

            # Максимальное количество попыток
            max_attempts = 3
            attempt = 0

            while attempt < max_attempts:
                try:
                    for endpoint in device.endpoints.values():
                        if endpoint.id != 0:
                            for cluster_handler in endpoint.all_cluster_handlers.values():
                                if cluster_handler.cluster.cluster_id == 0x0006:
                                    # Увеличиваем таймаут для команды
                                    cluster_handler.cluster.request_timeout = 30.0  # 30 секунд

                                    if state:
                                        await cluster_handler.cluster.command(0x01)
                                    else:
                                        await cluster_handler.cluster.command(0x00)

                                    message = {
                                        "state": "on" if state else "off",
                                        "ieee": ieee,
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    }

                                    self.mqtt_handler.mqtt_client.publish(
                                        f"zigbee/device/{ieee}/switch/state",
                                        json.dumps(message, indent=2),
                                        qos=self.mqtt_handler.mqtt_config["qos"],
                                        retain=True
                                    )

                                    logger.debug(
                                        "Switch command sent to device %s: %s",
                                        ieee,
                                        "on" if state else "off"
                                    )
                                    return

                    logger.error(f"No On/Off cluster found for device {ieee}")
                    return

                except TimeoutError as e:
                    attempt += 1
                    if attempt < max_attempts:
                        logger.warning(
                            "Timeout sending command to device %s, attempt %d of %d",
                            ieee, attempt, max_attempts
                        )
                        await asyncio.sleep(2)  # Ждем 2 секунды перед повторной попыткой
                    else:
                        raise
                except Exception as e:
                    logger.error(f"Unexpected error sending command: {e}")
                    raise

        except Exception as e:
            logger.error(f"Error handling switch command: {e}", exc_info=True)

    async def handle_light_command(self, ieee: str, state: bool):
        """Handle light command."""
        try:
            # Находим устройство
            device = self.gateway.devices.get(ieee)
            if not device:
                for dev in self.gateway.devices.values():
                    if str(dev.ieee) == ieee:
                        device = dev
                        break

                if not device:
                    logger.error(f"Device {ieee} not found")
                    return

            # Отправляем команду
            for endpoint in device.endpoints.values():
                if endpoint.id != 0:
                    for cluster_handler in endpoint.all_cluster_handlers.values():
                        if cluster_handler.cluster.cluster_id == 0x0006:  # On/Off cluster
                            # Увеличиваем таймаут для команды
                            cluster_handler.cluster.request_timeout = 30.0

                            if state:
                                await cluster_handler.cluster.command(0x01)  # ON
                            else:
                                await cluster_handler.cluster.command(0x00)  # OFF

                            message = {
                                "state": "on" if state else "off",
                                "ieee": ieee,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }

                            self.mqtt_handler.mqtt_client.publish(
                                f"zigbee/device/{ieee}/light/state",
                                json.dumps(message, indent=2),
                                qos=self.mqtt_handler.mqtt_config["qos"],
                                retain=True
                            )

                            logger.debug(
                                "Light command sent to device %s: %s",
                                ieee,
                                "on" if state else "off"
                            )
                            return

            logger.error(f"No On/Off cluster found for device {ieee}")

        except Exception as e:
            logger.error(f"Error handling light command: {e}", exc_info=True)

    async def handle_brightness_command(self, ieee: str, brightness: int):
        """Handle brightness command."""
        try:
            # Находим устройство
            device = self.gateway.devices.get(ieee)
            if not device:
                for dev in self.gateway.devices.values():
                    if str(dev.ieee) == ieee:
                        device = dev
                        break

                if not device:
                    logger.error(f"Device {ieee} not found")
                    return

            # Отправляем команду
            for endpoint in device.endpoints.values():
                if endpoint.id != 0:
                    for cluster_handler in endpoint.all_cluster_handlers.values():
                        if cluster_handler.cluster.cluster_id == 0x0008:  # Level Control cluster
                            # Увеличиваем таймаут для команды
                            cluster_handler.cluster.request_timeout = 30.0

                            # Отправляем команду с включением, если яркость > 0
                            await cluster_handler.cluster.move_to_level_with_on_off(brightness, 0)

                            message = {
                                "brightness": brightness,
                                "ieee": ieee,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }

                            self.mqtt_handler.mqtt_client.publish(
                                f"zigbee/device/{ieee}/light/brightness/state",
                                json.dumps(message, indent=2),
                                qos=self.mqtt_handler.mqtt_config["qos"],
                                retain=True
                            )

                            logger.debug(
                                "Brightness command sent to device %s: %s",
                                ieee,
                                brightness
                            )
                            return

            logger.error(f"No Level Control cluster found for device {ieee}")

        except Exception as e:
            logger.error(f"Error handling brightness command: {e}", exc_info=True)

    async def handle_color_command(self, ieee: str, hue: int = 0, saturation: int = 0, x: float = None, y: float = None):
        """Handle color command."""
        try:
            # Находим устройство
            device = self.gateway.devices.get(ieee)
            if not device:
                for dev in self.gateway.devices.values():
                    if str(dev.ieee) == ieee:
                        device = dev
                        break

                if not device:
                    logger.error(f"Device {ieee} not found")
                    return

            # Отправляем команду
            for endpoint in device.endpoints.values():
                if endpoint.id != 0:
                    for cluster_handler in endpoint.all_cluster_handlers.values():
                        if cluster_handler.cluster.cluster_id == 0x0300:  # Color Control cluster
                            # Увеличиваем таймаут для команды
                            cluster_handler.cluster.request_timeout = 30.0

                            if x is not None and y is not None:
                                # Используем xy цвет
                                await cluster_handler.cluster.move_to_color(
                                    int(x * 65535),
                                    int(y * 65535),
                                    0  # transition time
                                )
                            else:
                                # Используем hue/saturation
                                await cluster_handler.cluster.move_to_hue_and_saturation(
                                    hue,
                                    saturation,
                                    0  # transition time
                                )

                            message = {
                                "hue": hue,
                                "saturation": saturation,
                                "x": x,
                                "y": y,
                                "ieee": ieee,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }

                            self.mqtt_handler.mqtt_client.publish(
                                f"zigbee/device/{ieee}/light/color/state",
                                json.dumps(message, indent=2),
                                qos=self.mqtt_handler.mqtt_config["qos"],
                                retain=True
                            )

                            logger.debug(
                                "Color command sent to device %s",
                                ieee
                            )
                            return

            logger.error(f"No Color Control cluster found for device {ieee}")

        except Exception as e:
            logger.error(f"Error handling color command: {e}", exc_info=True)

    async def handle_permit_join(self, time_s: int) -> None:
        """Handle permit join command."""
        try:
            if not self.gateway or not self.gateway.application_controller:
                logger.error("Gateway not initialized")
                return

            retry_count = 3
            for attempt in range(retry_count):
                try:
                    await self.gateway.application_controller.permit(time_s)
                    message = {
                        "status": "enabled" if time_s > 0 else "disabled",
                        "time": time_s,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }

                    self.mqtt_handler.mqtt_client.publish(
                        "zigbee/permit_join/status",
                        json.dumps(message),
                        qos=self.mqtt_handler.mqtt_config["qos"],
                        retain=True
                    )

                    logger.debug("Permit join %s for %s seconds",
                              'enabled' if time_s > 0 else 'disabled',
                              time_s)
                    break
                except asyncio.TimeoutError:
                    if attempt == retry_count - 1:
                        raise
                    logger.warning(f"Permit join timeout, attempt {attempt + 1} of {retry_count}")
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error("Failed to change permit join state: %s", str(e))

    def update_gateway(self, gateway):
        """Update gateway reference."""
        logger.debug("Updating gateway reference in Device Command Handler")
        self.gateway = gateway
