import logging

from zha.zigbee.cluster_handlers import (
    AttrReportConfig,
    CLUSTER_HANDLER_ATTRIBUTE_UPDATED,
)
from zha.zigbee.cluster_handlers.const import (
    REPORT_CONFIG_DEFAULT,
    REPORT_CONFIG_IMMEDIATE,
    REPORT_CONFIG_ASAP,
)

logger = logging.getLogger(__name__)

class ClusterHandler:
    """Handler for cluster operations."""

    def __init__(self, coordinator):
        """Initialize cluster handler."""
        self.coordinator = coordinator
        self.gateway = coordinator.gateway
        self.mqtt_handler = coordinator.mqtt_handler

    def setup_cluster_handlers(self, gateway, device=None, endpoint=None):
        """Setup cluster handlers for device endpoint or all devices."""
        self.gateway = gateway
        try:
            if device and endpoint:
                # Setup for single device/endpoint
                if not device.available:
                    logger.warning(f"Device {device.ieee} is not available, skipping cluster setup")
                    return
                self._setup_endpoint_cluster_handlers(device, endpoint)
            else:
                # Setup for all devices
                for device in self.gateway.devices.values():
                    if device.is_coordinator:
                        continue
                    if not device.available:
                        logger.warning(f"Device {device.ieee} is not available, skipping cluster setup")
                        continue
                    for endpoint in device.endpoints.values():
                        if endpoint.id != 0:  # Skip ZDO endpoint
                            self._setup_endpoint_cluster_handlers(device, endpoint)
                logger.debug("Subscribing to existing IAS Zone devices")
                self.subscribe_existing_ias_zones()
        except Exception as e:
            logger.error(f"Error setting up cluster handlers: {e}", exc_info=True)

    def _setup_endpoint_cluster_handlers(self, device, endpoint):
        """Setup cluster handlers for specific device endpoint."""
        for cluster_handler in endpoint.all_cluster_handlers.values():
            cluster_id = cluster_handler.cluster.cluster_id

            # Настраиваем отчетность для разных типов кластеров
            if cluster_id == 0x0006:  # On/Off cluster
                self._setup_onoff_cluster(cluster_handler)
            elif cluster_id == 0x0008:  # Level Control cluster
                self._setup_level_cluster(cluster_handler)
            elif cluster_id == 0x0300:  # Color Control cluster
                self._setup_color_cluster(cluster_handler)
            elif cluster_id == 0x0500:  # IAS Zone cluster
                self._setup_ias_zone_cluster(cluster_handler)
            elif cluster_id == 0x0402:  # Temperature Measurement cluster
                self._setup_temperature_cluster(cluster_handler)
            elif cluster_id == 0x0405:  # Relative Humidity cluster
                self._setup_humidity_cluster(cluster_handler)

    def _setup_onoff_cluster(self, cluster_handler):
        """Setup On/Off cluster handler."""
        try:
            cluster_handler.REPORT_CONFIG = (
                AttrReportConfig(
                    attr="on_off",
                    config=REPORT_CONFIG_IMMEDIATE,
                ),
            )
            
            cluster_handler.on_event(
                CLUSTER_HANDLER_ATTRIBUTE_UPDATED,
                self.coordinator.event_handler.handle_onoff_attribute_updated
            )

        except Exception as e:
            logger.error(f"Error setting up On/Off cluster: {e}", exc_info=True)

    def _setup_level_cluster(self, cluster_handler):
        """Setup Level Control cluster handler."""
        try:
            cluster_handler.REPORT_CONFIG = (
                AttrReportConfig(
                    attr="current_level",
                    config=REPORT_CONFIG_ASAP,
                ),
            )
            
            cluster_handler.on_event(
                CLUSTER_HANDLER_ATTRIBUTE_UPDATED,
                self.coordinator.event_handler.handle_level_attribute_updated
            )

        except Exception as e:
            logger.error(f"Error setting up Level Control cluster: {e}", exc_info=True)

    def _setup_color_cluster(self, cluster_handler):
        """Setup Color Control cluster handler."""
        try:
            cluster_handler.REPORT_CONFIG = (
                AttrReportConfig(
                    attr="current_x",
                    config=REPORT_CONFIG_DEFAULT,
                ),
                AttrReportConfig(
                    attr="current_y",
                    config=REPORT_CONFIG_DEFAULT,
                ),
                AttrReportConfig(
                    attr="color_temperature",
                    config=REPORT_CONFIG_DEFAULT,
                ),
            )
            
            cluster_handler.on_event(
                CLUSTER_HANDLER_ATTRIBUTE_UPDATED,
                self.coordinator.event_handler.handle_color_attribute_updated
            )

        except Exception as e:
            logger.error(f"Error setting up Color Control cluster: {e}", exc_info=True)

    def _setup_ias_zone_cluster(self, cluster_handler):
        """Setup IAS Zone cluster handler."""
        try:
            cluster_handler.REPORT_CONFIG = (
                AttrReportConfig(
                    attr="zone_status",
                    config=REPORT_CONFIG_IMMEDIATE,
                ),
            )
            
            cluster_handler.on_event(
                CLUSTER_HANDLER_ATTRIBUTE_UPDATED,
                self.coordinator.event_handler.handle_ias_zone_attribute_updated
            )

        except Exception as e:
            logger.error(f"Error setting up IAS Zone cluster: {e}", exc_info=True)

    def _setup_temperature_cluster(self, cluster_handler):
        """Setup Temperature Measurement cluster handler."""
        try:
            cluster_handler.REPORT_CONFIG = (
                AttrReportConfig(
                    attr="measured_value",
                    config=REPORT_CONFIG_DEFAULT,
                ),
            )
            
            cluster_handler.on_event(
                CLUSTER_HANDLER_ATTRIBUTE_UPDATED,
                self.coordinator.event_handler.handle_temperature_attribute_updated
            )

        except Exception as e:
            logger.error(f"Error setting up Temperature cluster: {e}", exc_info=True)

    def _setup_humidity_cluster(self, cluster_handler):
        """Setup Humidity Measurement cluster handler."""
        try:
            cluster_handler.REPORT_CONFIG = (
                AttrReportConfig(
                    attr="measured_value",
                    config=REPORT_CONFIG_DEFAULT,
                ),
            )
            
            cluster_handler.on_event(
                CLUSTER_HANDLER_ATTRIBUTE_UPDATED,
                self.coordinator.event_handler.handle_humidity_attribute_updated
            )

        except Exception as e:
            logger.error(f"Error setting up Humidity cluster: {e}", exc_info=True)

    def update_gateway(self, gateway):
        """Update gateway reference."""
        logger.debug("Updating gateway reference in Cluster Handler")
        self.gateway = gateway 

    def subscribe_existing_ias_zones(self):
        """Subscribe to existing IAS Zone devices."""
        if not self.gateway:
            return

        for device in self.gateway.devices.values():
            for endpoint in device.endpoints.values():
                if endpoint.id != 0:  # Skip ZDO endpoint
                    for cluster_handler in endpoint.all_cluster_handlers.values():
                        if cluster_handler.cluster.cluster_id == 0x0500:  # IAS Zone cluster
                            logger.debug(f"Subscribing to IAS Zone events for device {device.ieee}")
                            cluster_handler.cluster.add_listener(self.coordinator.event_handler)