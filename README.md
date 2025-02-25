# ZHA based Zigbee gateway to MQTT

## System Overview
This project is a basic implementation of a Zigbee gateway in Python that serves as a bridge between Zigbee and MQTT. The system is based on the zigpy and zha repositories:
- [ZHA Repository](https://github.com/zigpy/zha)
- [Zigpy Repository](https://github.com/zigpy/zigpy)

It can use any radio that zigpy supports as its foundation, for example:
- [Zigpy ZNP](https://github.com/zigpy/zigpy-znp)
- [Zigpy Deconz](https://github.com/zigpy/zigpy-deconz)

I tested it using [NRF52840 and zigpy-zboss](https://github.com/kardia-as/zigpy-zboss)

### Tested ZigbeeDevices
- Aquara Smart Plug
- Aqara Led Bulb
- Aqara door sensor

## Installation
```bash
pip install -r requirements.txt
```

## MQTT Topics Reference

### Pairing Mode Control
```bash
# Enable pairing mode
mosquitto_pub -t "zigbee/permit_join" -m '{"permit_join": true}'

# Disable pairing mode
mosquitto_pub -t "zigbee/permit_join" -m '{"permit_join": false}'
```

### Device Control Examples

#### Smart Plug Control
```bash
# Turn on Smart Plug
mosquitto_pub -t "zigbee/device/54:ef:44:10:00:c2:86:53/switch/set" -m '{"state": "on"}'

# Turn off Smart Plug
mosquitto_pub -t "zigbee/device/54:ef:44:10:00:c2:86:53/switch/set" -m '{"state": "off"}'
```

#### Light Bulb Control
```bash
# Turn on/off the light bulb
mosquitto_pub -t "zigbee/device/54:ef:44:10:00:cd:d9:b6/light/set" -m '{"state": "on"}'
mosquitto_pub -t "zigbee/device/54:ef:44:10:00:cd:d9:b6/light/set" -m '{"state": "off"}'

# Set brightness
mosquitto_pub -t "zigbee/device/54:ef:44:10:00:cd:d9:b6/light/brightness/set" -m '{"brightness": 128}'

# Set color using hue/saturation
mosquitto_pub -t "zigbee/device/54:ef:44:10:00:cd:d9:b6/light/color/set" -m '{"hue": 120, "saturation": 100}'

# Set color using xy
mosquitto_pub -t "zigbee/device/54:ef:44:10:00:cd:d9:b6/light/color/set" -m '{"x": 0.4, "y": 0.4}'
```

### Monitoring Topics
```bash
# Status monitoring
mosquitto_sub -t "zigbee/coordinator/status"
mosquitto_sub -t "zigbee/permit_join/status"
mosquitto_sub -t "zigbee/ias/#"
mosquitto_sub -t "#" -v

# All device events
mosquitto_sub -v -t "zigbee/devices/#"

# Events for a specific device
mosquitto_sub -v -t "zigbee/devices/00:12:4b:00:14:b5:23:01/#"

# List of all devices
mosquitto_sub -v -t "zigbee/devices"
```

## Connecting Zigbee Devices

### System Preparation

1. Ensure the Zigbee coordinator (e.g., nrf52840, CC2531, CC2652R, or similar) is connected to the system
2. Verify that the coordinator device path is correct (default `/dev/ttyACM0`)
3. Ensure the MQTT broker is running and accessible
4. Start the coordinator:
   ```bash
   python3 __main__.py
   ```

### Adding a New Device

1. Enable pairing mode:
   ```json
   {
     "permit_join": true
   }
   ```
   Send to topic: `zigbee/permit_join`

2. Put the device in pairing mode:
   | Device Type      | Pairing Method                   |
   | ---------------- | -------------------------------- |
   | Sensors          | Hold pairing button 5-10 seconds |
   | Outlets/Switches | Triple-click button              |
   | Lamps            | Power cycle 5-6 times            |

3. After successful pairing, device information will be published to `zigbee/device/joined`:
   - Device IEEE address
   - Device type
   - Supported features
   - Cluster list

4. The system automatically configures reporting for supported features

## Architecture

### Main Components

#### 1. Coordinator (`coordinator.py`)
- Central system component
- Manages Zigbee network initialization and operation
- Coordinates interaction between all components
- Provides automatic recovery after failures

#### 2. MQTTHandler (`mqtt_handler.py`)
- Handles MQTT communication
- Publishes device states
- Receives control commands
- Supported topics:
  - `zigbee/permit_join` - pairing mode control
  - `zigbee/device/+/switch/set` - switch control
  - `zigbee/device/+/light/set` - lighting control
  - `zigbee/device/+/light/brightness/set` - brightness control
  - `zigbee/device/+/light/color/set` - color control

3. **EventHandler** (event_handler.py)
   - Handles Zigbee network events
   - Monitors device connections/disconnections
   - Processes device attribute updates
   - Publishes events to MQTT

4. **ClusterHandler** (cluster_handler.py)
   - Manages Zigbee device clusters
   - Configures reporting for different device types
   - Supports the following clusters:
     - On/Off (0x0006)
     - Level Control (0x0008)
     - Color Control (0x0300)
     - IAS Zone (0x0500)
     - Temperature (0x0402)
     - Humidity (0x0405)

5. **DeviceCommandHandler** (device_command_handler.py)
   - Processes device commands
   - Supports control of:
     - Switches
     - Lighting
     - Brightness
     - Color
   - Provides retry attempts on failures

### Helper Functions

**Helpers** (helpers.py)
- Provides utilities for working with devices
- Determines device capabilities
- Extracts endpoint information
- Determines device types

## Supported Features

- Automatic device discovery
- Pairing mode control
- Lighting control (on/off, brightness, color)
- Sensor monitoring (temperature, humidity, IAS)
- Automatic connection recovery
- Detailed event logging

## MQTT Protocol

### Published Topics
- `zigbee/coordinator/status` - coordinator status
- `zigbee/device/joined` - new device information
- `zigbee/device/{ieee}/status` - device status
- `zigbee/device/{ieee}/*/state` - device states

### Control Topics
- `zigbee/permit_join` - pairing mode control
- `zigbee/device/{ieee}/switch/set` - switch control
- `zigbee/device/{ieee}/light/set` - lighting control
- `zigbee/device/{ieee}/light/brightness/set` - brightness control
- `zigbee/device/{ieee}/light/color/set` - color control

### Supported Device Types

1. **Switches and Outlets**
   - Control: `zigbee/device/{ieee}/switch/set`
   - Status: `zigbee/device/{ieee}/switch/state`
   ```json
   {"state": "on"}  // or "off"
   ```

2. **Lamps and Lighting**
   - On/Off: `zigbee/device/{ieee}/light/set`
   - Brightness: `zigbee/device/{ieee}/light/brightness/set`
   - Color: `zigbee/device/{ieee}/light/color/set`
   ```json
   {"brightness": 255}  // 0-255
   {"hue": 100, "saturation": 100}  // for color lamps
   {"x": 0.4, "y": 0.4}  // for color control in xy space
   ```

3. **Temperature and Humidity Sensors**
   - Status: `zigbee/device/{ieee}/temperature/state`
   - Status: `zigbee/device/{ieee}/humidity/state`

4. **Motion and Opening Sensors (IAS)**
   - Status: `zigbee/device/{ieee}/ias_zone/state`

### Adding New Devices

#### Device Analysis
1. Connect the device and study its clusters:
   - Check logs to determine supported clusters
   - Record incoming (in_clusters) and outgoing (out_clusters) clusters
   - Determine device profile and type (device_type)

2. Determine required handlers:
   ```python
   # Example of device cluster analysis
   endpoint_info = {
       "profile_id": "0x0104",  # HA Profile
       "device_type": "0x0100", # Device type
       "in_clusters": ["0x0000", "0x0003", "0x0004", "0x0005", "0x0006"],
       "out_clusters": ["0x0019"]
   }
   ```

#### Adding Cluster Support
1. Add handler for new cluster type in `cluster_handler.py`:
   ```python
   def _setup_new_cluster(self, cluster_handler):
       """Setup handler for new cluster type."""
       try:
           cluster_handler.REPORT_CONFIG = (
               AttrReportConfig(
                   attr="your_attribute",
                   config=REPORT_CONFIG_DEFAULT,
               ),
           )
           
           cluster_handler.on_event(
               CLUSTER_HANDLER_ATTRIBUTE_UPDATED,
               self.coordinator.event_handler.handle_new_attribute_updated
           )
       except Exception as e:
           logger.error(f"Error setting up new cluster: {e}", exc_info=True)
   ```

2. Create event handler in `event_handler.py`:
   ```python
   def handle_new_attribute_updated(self, event: ClusterAttributeUpdatedEvent):
       """Handle new cluster attribute updates."""
       device_ieee = str(event.cluster_handler_unique_id)
       message = {
           "attribute": event.attribute_name,
           "value": event.attribute_value,
           "ieee": device_ieee,
           "timestamp": datetime.now(timezone.utc).isoformat()
       }
       
       self.mqtt_handler.mqtt_client.publish(
           f"zigbee/device/{device_ieee}/new_device/state",
           json.dumps(message, indent=2),
           qos=self.mqtt_handler.mqtt_config["qos"],
           retain=True
       )
   ```

#### Adding Control Commands
1. Add subscription to new topics in `mqtt_handler.py`:
   ```python
   def _on_mqtt_connect(self, client, userdata, flags, rc):
       # ... existing subscriptions ...
       client.subscribe("zigbee/device/+/new_device/set")
   ```

2. Implement command handling in `device_command_handler.py`:
   ```python
   async def handle_new_device_command(self, ieee: str, command_data: dict):
       """Handle commands for new device type."""
       try:
           device = self.gateway.devices.get(ieee)
           if not device:
               logger.error(f"Device {ieee} not found")
               return

           for endpoint in device.endpoints.values():
               if endpoint.id != 0:
                   for cluster_handler in endpoint.all_cluster_handlers.values():
                       if cluster_handler.cluster.cluster_id == 0xNNNN:  # Your cluster
                           await cluster_handler.cluster.your_command(
                               command_data.get("parameter")
                           )
                           return

           logger.error(f"Required cluster not found for device {ieee}")

       except Exception as e:
           logger.error(f"Error handling new device command: {e}", exc_info=True)
   ```

#### Updating helpers.py
1. Add capability definition for new device:
   ```python
   def get_endpoint_capabilities(endpoint):
       capabilities = {}
       try:
           if hasattr(endpoint, "in_clusters"):
               # ... existing capabilities ...
               if 0xNNNN in endpoint.in_clusters:
                   capabilities["new_device"] = True
       except Exception:
           pass
       return capabilities
   ```

#### Testing
1. Check device discovery:
   - Connect the device
   - Verify correct cluster detection
   - Ensure automatic reporting configuration is correct

2. Test event handling:
   - Check state update reception
   - Verify MQTT message format correctness

3. Check control:
   - Test command sending
   - Check error handling
   - Verify feedback correctness

