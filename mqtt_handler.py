import json
import logging
from typing import Any, Dict, TYPE_CHECKING
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from device_command_handler import DeviceCommandHandler

if TYPE_CHECKING:
    from .coordinator import Coordinator

logger = logging.getLogger(__name__)

class MQTTHandler:
    """Handler for MQTT operations."""

    def __init__(self, coordinator: "Coordinator", mqtt_config: Dict[str, Any] = None):
        """Initialize MQTT handler."""
        logger.debug("MQTTHandler init")
        self.coordinator = coordinator
        self.gateway = coordinator.gateway
        self.device_handler = DeviceCommandHandler(self.gateway, self)
        self._init_mqtt(mqtt_config)

    def _init_mqtt(self, mqtt_config: Dict[str, Any] = None) -> None:
        """Initialize MQTT client with configuration."""
        # MQTT configuration
        mqtt_defaults = {
            "broker": "localhost",
            "port": 1883,
            "qos": 1
        }
        self.mqtt_config = {**mqtt_defaults, **(mqtt_config or {})}

        # Initialize MQTT client
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message

    async def publish_status(self, status: str) -> None:
        """Publish coordinator status."""
        if not self.mqtt_client:
            return

        try:
            message = {
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            if self.gateway:
                try:
                    network_info = self.gateway.application_controller.state.network_info
                    if network_info:
                        message.update({
                            "channel": network_info.channel,
                            "pan_id": network_info.pan_id,
                            "extended_pan_id": network_info.extended_pan_id,
                            "children_count": len(self.gateway.devices)
                        })

                        # Add device list for detailed information
                        children = []
                        for device in self.gateway.devices.values():
                            children.append({
                                "ieee": str(device.ieee),
                                "nwk": f"0x{device.nwk:04x}",
                                "manufacturer": device.manufacturer,
                                "model": device.model
                            })
                        if children:
                            message["children"] = children

                except AttributeError:
                    pass

            self.mqtt_client.publish(
                "zigbee/coordinator/status",
                json.dumps(message),
                qos=self.mqtt_config["qos"],
                retain=True
            )
            logger.debug("Published %s status to MQTT", status)
        except Exception as e:
            logger.error("Failed to publish status: %s", str(e))

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        logger.debug("Connected to MQTT broker with code: %s", rc)
        client.subscribe("zigbee/permit_join")
        client.subscribe("zigbee/device/+/switch/set")
        client.subscribe("zigbee/device/+/light/set")
        client.subscribe("zigbee/device/+/light/brightness/set")
        client.subscribe("zigbee/device/+/light/color/set")

    def _on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT messages."""
        try:
            payload = json.loads(msg.payload.decode())

            if msg.topic == "zigbee/permit_join":
                permit_join = payload.get("permit_join", False)
                if self.gateway and self.gateway.application_controller:
                    permit_time = 120 if permit_join else 0

                    if self.coordinator.loop:
                        self.coordinator.loop.create_task(
                            self.device_handler.handle_permit_join(permit_time)
                        )
                        logger.debug("Permit join command received: %s seconds", permit_time)
                    else:
                        logger.error("No event loop available in coordinator")

            elif msg.topic.startswith("zigbee/device/") and msg.topic.endswith("/switch/set"):
                ieee = msg.topic.split('/')[2]
                state = payload.get("state", "").lower()

                if state in ["on", "off"] and self.coordinator.loop:
                    self.coordinator.loop.create_task(
                        self.device_handler.handle_switch_command(ieee, state == "on")
                    )
                    logger.debug("Switch command received for %s: %s", ieee, state)

            elif msg.topic.startswith("zigbee/device/") and msg.topic.endswith("/light/set"):
                ieee = msg.topic.split('/')[2]
                state = payload.get("state", "").lower()

                if state in ["on", "off"] and self.coordinator.loop:
                    self.coordinator.loop.create_task(
                        self.device_handler.handle_light_command(ieee, state == "on")
                    )
                    logger.debug("Light command received for %s: %s", ieee, state)

            elif msg.topic.startswith("zigbee/device/") and msg.topic.endswith("/light/brightness/set"):
                ieee = msg.topic.split('/')[2]
                brightness = payload.get("brightness", 0)

                if 0 <= brightness <= 255 and self.coordinator.loop:
                    self.coordinator.loop.create_task(
                        self.device_handler.handle_brightness_command(ieee, brightness)
                    )
                    logger.debug("Brightness command received for %s: %s", ieee, brightness)

            elif msg.topic.startswith("zigbee/device/") and msg.topic.endswith("/light/color/set"):
                ieee = msg.topic.split('/')[2]

                if self.coordinator.loop:
                    self.coordinator.loop.create_task(
                        self.device_handler.handle_color_command(
                            ieee,
                            payload.get("hue", 0),
                            payload.get("saturation", 0),
                            payload.get("x"),  # Для xy цвета
                            payload.get("y")   # Для xy цвета
                        )
                    )
                    logger.debug("Color command received for %s", ieee)

        except json.JSONDecodeError:
            logger.error("Invalid JSON in MQTT message")
        except Exception as e:
            logger.error("Error processing MQTT message: %s", str(e))

    def start(self):
        """Start MQTT client."""
        try:
            self.mqtt_client.connect(
                self.mqtt_config["broker"],
                self.mqtt_config["port"]
            )
            self.mqtt_client.loop_start()
            logger.debug("MQTT client started successfully")
        except Exception as e:
            logger.error("Failed to start MQTT client: %s", str(e))

    def stop(self):
        """Stop MQTT client."""
        try:
            if self.mqtt_client:
                self.mqtt_client.disconnect()
                self.mqtt_client.loop_stop()
            logger.debug("MQTT client stopped successfully")
        except Exception as e:
            logger.error("Error stopping MQTT client: %s", str(e))

    def is_connected(self) -> bool:
        """Check if MQTT client is connected."""
        return self.mqtt_client and self.mqtt_client.is_connected()

    def update_gateway(self, gateway):
        """Update gateway reference."""
        logger.debug("Updating gateway reference in MQTT handler")
        self.gateway = gateway
        self.device_handler.update_gateway(gateway)
