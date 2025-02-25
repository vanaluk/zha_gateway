import json
import logging
from datetime import datetime, timezone
import asyncio

from zha.application.const import (
    ZHA_GW_MSG_DEVICE_JOINED,
    ZHA_GW_MSG_DEVICE_LEFT,
)
from zha.zigbee.cluster_handlers import (
    ClusterAttributeUpdatedEvent,
)

from helpers import get_endpoint_info, get_endpoint_capabilities, get_device_type_info

logger = logging.getLogger(__name__)

class EventHandler:
    """Handler for ZHA events."""

    def __init__(self, coordinator):
        """Initialize event handler."""
        self.coordinator = coordinator
        self.gateway = None
        self.mqtt_handler = coordinator.mqtt_handler

    def update_gateway(self, gateway):
        """Update gateway reference."""
        logger.debug("Updating gateway reference in Event Handler")
        self.gateway = gateway

    def setup_event_handlers(self, gateway):
        """Setup event handlers for the gateway."""

        self.gateway = gateway
        self.gateway.on_event(ZHA_GW_MSG_DEVICE_JOINED, self._handle_device_joined)
        self.gateway.on_event(ZHA_GW_MSG_DEVICE_LEFT, self._handle_device_left)
        self.gateway.on_all_events(self._forward_event)

    def _forward_event(self, event):
        """Forward events from gateway to coordinator."""
        try:
            logger.debug("Forwarding event: %s", event)
            if hasattr(event, 'event'):
                self.coordinator.emit(event.event, event)
        except Exception as e:
            logger.error("Error forwarding event: %s", str(e), exc_info=True)

    def _handle_device_joined(self, event):
        """Handle device joined event."""
        try:
            device_info = event.device_info
            device = self.gateway.application_controller.get_device(
                ieee=device_info.ieee
            )

            logger.debug(f"Processing device joined event for {device_info.ieee}")

            # Создаем базовое сообщение о присоединении устройства
            message = {
                "event": "device_joined",
                "ieee": str(device_info.ieee),
                "nwk": device_info.nwk,
                "manufacturer": device.manufacturer,
                "model": device.model,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Добавляем информацию о всех endpoints
            endpoints_info = {}
            capabilities = {}

            # Ждем инициализации endpoints
            for _ in range(3):  # Максимум 3 попытки
                if device.endpoints:
                    break
                asyncio.sleep(1)

            for ep_id, endpoint in device.endpoints.items():
                if ep_id == 0:  # Пропускаем ZDO endpoint
                    continue

                # Используем функции из helpers.py
                endpoint_info = get_endpoint_info(endpoint)
                if endpoint_info:
                    endpoints_info[ep_id] = endpoint_info

                # Получаем возможности endpoint
                ep_capabilities = get_endpoint_capabilities(endpoint)
                capabilities.update(ep_capabilities)

            if endpoints_info:
                message["endpoints"] = endpoints_info

            # Добавляем информацию о типе устройства используя helper
            device_type_info = get_device_type_info(device)
            if device_type_info:
                message["device_type"] = device_type_info

            # Добавляем обнаруженные возможности
            if capabilities:
                message["capabilities"] = capabilities

            # Setup cluster handlers for the new device
            device = self.gateway.devices.get(device_info.ieee)
            for endpoint in device.endpoints.values():
                if endpoint.id != 0:  # Skip ZDO endpoint
                    self.coordinator.cluster_handler.setup_cluster_handlers(
                        self.gateway, device, endpoint
                    )

            # Публикуем полную информацию о устройстве
            try:
                self.mqtt_handler.mqtt_client.publish(
                    "zigbee/device/joined",
                    json.dumps(message, indent=2),
                    qos=self.mqtt_handler.mqtt_config["qos"],
                )

                # Публикуем статус устройства
                device_status = {
                    "ieee": str(device_info.ieee),
                    "nwk": device_info.nwk,
                    "manufacturer": device.manufacturer,
                    "model": device.model,
                    "status": "joined",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                self.mqtt_handler.mqtt_client.publish(
                    f"zigbee/device/{device_info.ieee}/status",
                    json.dumps(device_status),
                    qos=self.mqtt_handler.mqtt_config["qos"],
                    retain=True,
                )
            except Exception as e:
                logger.error(f"Error publishing MQTT messages: {str(e)}")

            logger.debug(
                "Device joined: %s (%s) - %s %s",
                device_info.ieee,
                device_info.nwk,
                device.manufacturer,
                device.model,
            )

        except Exception as e:
            logger.error(f"Error handling device joined event: {e}", exc_info=True)

    def _handle_device_left(self, event):
        """Handle device left event."""
        try:
            message = {
                "event": "device_left",
                "ieee": str(event.ieee),
                "nwk": event.nwk,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            self.mqtt_handler.mqtt_client.publish(
                "zigbee/device/left",
                json.dumps(message),
                qos=self.mqtt_handler.mqtt_config["qos"]
            )
            logger.debug("Device left: %s", event.ieee)

        except Exception as e:
            logger.error("Error handling device left event: %s", str(e))

    def handle_attribute_updated(self, event: ClusterAttributeUpdatedEvent, topic_prefix: str):
        """Handle cluster attribute updates."""
        try:
            device_ieee = str(event.cluster_handler_unique_id)
            message = {
                "attribute": event.attribute_name,
                "value": event.attribute_value,
                "ieee": device_ieee,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            self.mqtt_handler.mqtt_client.publish(
                f"{topic_prefix}/state",
                json.dumps(message, indent=2),
                qos=self.mqtt_handler.mqtt_config["qos"],
                retain=True
            )

        except Exception as e:
            logger.error(f"Error handling attribute update: {e}", exc_info=True)

    def handle_onoff_attribute_updated(self, event: ClusterAttributeUpdatedEvent):
        """Handle On/Off cluster attribute updates."""
        if event.attribute_name == "on_off":
            device_ieee = str(event.cluster_handler_unique_id)
            message = {
                "state": "on" if event.attribute_value else "off",
                "ieee": device_ieee,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            self.mqtt_handler.mqtt_client.publish(
                f"zigbee/device/{device_ieee}/switch/state",
                json.dumps(message, indent=2),
                qos=self.mqtt_handler.mqtt_config["qos"],
                retain=True
            )

    def handle_level_attribute_updated(self, event: ClusterAttributeUpdatedEvent):
        """Handle Level Control cluster attribute updates."""
        if event.attribute_name == "current_level":
            device_ieee = str(event.cluster_handler_unique_id)
            self.handle_attribute_updated(
                event,
                f"zigbee/device/{device_ieee}/light/brightness"
            )

    def handle_color_attribute_updated(self, event: ClusterAttributeUpdatedEvent):
        """Handle Color Control cluster attribute updates."""
        device_ieee = str(event.cluster_handler_unique_id)
        self.handle_attribute_updated(
            event,
            f"zigbee/device/{device_ieee}/light/color"
        )

    def handle_ias_zone_attribute_updated(self, event: ClusterAttributeUpdatedEvent):
        """Handle IAS Zone cluster attribute updates."""
        if event.attribute_name == "zone_status":
            device_ieee = str(event.cluster_handler_unique_id)
            zone_status = int(event.attribute_value)
            
            # Decode zone status
            zone_status_flags = []
            if zone_status & 0x0001:
                zone_status_flags.append("alarm1")
            if zone_status & 0x0002:
                zone_status_flags.append("alarm2")
            if zone_status & 0x0004:
                zone_status_flags.append("tamper")
            if zone_status & 0x0008:
                zone_status_flags.append("battery")
            if zone_status & 0x0010:
                zone_status_flags.append("supervision_reports")
            if zone_status & 0x0020:
                zone_status_flags.append("restore_reports")
            if zone_status & 0x0040:
                zone_status_flags.append("trouble")
            if zone_status & 0x0080:
                zone_status_flags.append("ac_mains")

            message = {
                "zone_status": zone_status,
                "zone_status_flags": zone_status_flags,
                "ieee": device_ieee,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            self.mqtt_handler.mqtt_client.publish(
                f"zigbee/device/{device_ieee}/ias_zone/state",
                json.dumps(message, indent=2),
                qos=self.mqtt_handler.mqtt_config["qos"],
                retain=True
            )

    def handle_temperature_attribute_updated(self, event: ClusterAttributeUpdatedEvent):
        """Handle Temperature Measurement cluster attribute updates."""
        if event.attribute_name == "measured_value":
            device_ieee = str(event.cluster_handler_unique_id)
            temperature = event.attribute_value / 100.0
            
            message = {
                "temperature": temperature,
                "ieee": device_ieee,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            self.mqtt_handler.mqtt_client.publish(
                f"zigbee/device/{device_ieee}/temperature/state",
                json.dumps(message, indent=2),
                qos=self.mqtt_handler.mqtt_config["qos"],
                retain=True
            )

    def handle_humidity_attribute_updated(self, event: ClusterAttributeUpdatedEvent):
        """Handle Humidity Measurement cluster attribute updates."""
        if event.attribute_name == "measured_value":
            device_ieee = str(event.cluster_handler_unique_id)
            humidity = event.attribute_value / 100.0
            
            message = {
                "humidity": humidity,
                "ieee": device_ieee,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            self.mqtt_handler.mqtt_client.publish(
                f"zigbee/device/{device_ieee}/humidity/state",
                json.dumps(message, indent=2),
                qos=self.mqtt_handler.mqtt_config["qos"],
                retain=True
            ) 