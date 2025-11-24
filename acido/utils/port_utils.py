"""Utilities for handling port specifications and validation."""

def parse_port_spec(port_spec):
    """
    Parse port specification string.
    
    Args:
        port_spec (str): String like "5060:udp" or "8080:tcp"
    
    Returns:
        dict: {"port": 5060, "protocol": "UDP"}
        
    Raises:
        ValueError: If port_spec is invalid
    
    Example:
        >>> parse_port_spec("5060:udp")
        {"port": 5060, "protocol": "UDP"}
    """
    try:
        # Use maxsplit=1 to handle cases where protocol might contain colons
        parts = port_spec.split(':', maxsplit=1)
        if len(parts) != 2:
            raise ValueError("Missing port or protocol")
        
        port, protocol = parts
        port_num = int(port)
        protocol_upper = protocol.upper()
        
        # Validate port and protocol
        validate_port(port_num)
        validate_protocol(protocol_upper)
        
        return {
            "port": port_num,
            "protocol": protocol_upper
        }
    except ValueError as e:
        # Preserve original error details while providing helpful message
        raise ValueError(
            f"Invalid port specification: {port_spec}. "
            f"Format should be PORT:PROTOCOL (e.g., 5060:udp). "
            f"Original error: {str(e)}"
        ) from e
    except IndexError as e:
        raise ValueError(
            f"Invalid port specification: {port_spec}. "
            f"Format should be PORT:PROTOCOL (e.g., 5060:udp). "
            f"Original error: {str(e)}"
        ) from e

def validate_port(port):
    """
    Validate port number.
    
    Args:
        port (int): Port number
    
    Returns:
        bool: True if valid
        
    Raises:
        ValueError: If port is invalid
    """
    if not isinstance(port, int):
        raise ValueError(f"Port must be an integer, got {type(port)}")
    
    if port < 1 or port > 65535:
        raise ValueError(f"Port must be between 1 and 65535, got {port}")
    
    return True

def validate_protocol(protocol):
    """
    Validate protocol.
    
    Args:
        protocol (str): Protocol name (TCP or UDP)
    
    Returns:
        bool: True if valid
        
    Raises:
        ValueError: If protocol is invalid
    """
    protocol = protocol.upper()
    if protocol not in ['TCP', 'UDP']:
        raise ValueError(f"Protocol must be TCP or UDP, got {protocol}")
    
    return True

def format_port_list(ports):
    """
    Format list of ports for display.
    
    Args:
        ports (list): List of port dicts
    
    Returns:
        str: Formatted string like "5060/UDP, 8080/TCP"
        
    Example:
        >>> format_port_list([{"port": 5060, "protocol": "UDP"}])
        "5060/UDP"
    """
    return ', '.join([f"{p['port']}/{p['protocol']}" for p in ports])
