def get_endpoint_info(endpoint):
    """Get endpoint information."""
    try:
        return {
            "profile_id": f"0x{endpoint.profile_id:04x}",
            "device_type": f"0x{endpoint.device_type:04x}",
            "in_clusters": [f"0x{c:04x}" for c in endpoint.in_clusters],
            "out_clusters": [f"0x{c:04x}" for c in endpoint.out_clusters]
        }
    except Exception:
        return {}

def get_endpoint_capabilities(endpoint):
    """Get endpoint capabilities."""
    capabilities = {}
    try:
        if hasattr(endpoint, "in_clusters"):
            if 0x0500 in endpoint.in_clusters:
                capabilities["ias_zone"] = True
            if 0x0006 in endpoint.in_clusters:
                capabilities["switch"] = True
            if 0x0201 in endpoint.in_clusters:
                capabilities["thermostat"] = True
            if 0x0101 in endpoint.in_clusters:
                capabilities["lock"] = True
            if 0x0300 in endpoint.in_clusters:
                capabilities["light"] = True
    except Exception:
        pass
    return capabilities

def get_device_type_info(device):
    """Get device type information."""
    try:
        if device.node_desc:
            return {
                "is_coordinator": device.node_desc.is_coordinator,
                "is_router": device.node_desc.is_router,
                "is_end_device": device.node_desc.is_end_device,
                "is_full_function_device": device.node_desc.is_full_function_device,
                "manufacturer_code": (
                    f"0x{device.node_desc.manufacturer_code:04x}"
                    if device.node_desc.manufacturer_code else None
                )
            }
    except Exception:
        return None