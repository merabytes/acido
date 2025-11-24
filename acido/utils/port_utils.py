"""Utilities for handling port specifications and validation."""

def parse_port_spec(port_spec):
    """
    Parse port specification string, including support for port ranges.
    
    Args:
        port_spec (str): String like "5060:udp", "8080:tcp", or "5060-5070:udp" (range)
    
    Returns:
        list: List of dicts with {"port": 5060, "protocol": "UDP"}
              For single port: [{"port": 5060, "protocol": "UDP"}]
              For range: [{"port": 5060, "protocol": "UDP"}, {"port": 5061, "protocol": "UDP"}, ...]
        
    Raises:
        ValueError: If port_spec is invalid
    
    Example:
        >>> parse_port_spec("5060:udp")
        [{"port": 5060, "protocol": "UDP"}]
        >>> parse_port_spec("5060-5062:udp")
        [{"port": 5060, "protocol": "UDP"}, {"port": 5061, "protocol": "UDP"}, {"port": 5062, "protocol": "UDP"}]
    """
    try:
        # Use maxsplit=1 to handle cases where protocol might contain colons
        parts = port_spec.split(':', maxsplit=1)
        if len(parts) != 2:
            raise ValueError("Missing port or protocol")
        
        port_part, protocol = parts
        protocol_upper = protocol.upper()
        
        # Validate protocol first
        validate_protocol(protocol_upper)
        
        # Check if it's a port range (contains hyphen)
        if '-' in port_part:
            # Parse port range
            range_parts = port_part.split('-', maxsplit=1)
            if len(range_parts) != 2:
                raise ValueError("Invalid port range format")
            
            start_port = int(range_parts[0])
            end_port = int(range_parts[1])
            
            # Validate both ports
            validate_port(start_port)
            validate_port(end_port)
            
            # Ensure start < end
            if start_port >= end_port:
                raise ValueError(f"Invalid port range: start port ({start_port}) must be less than end port ({end_port})")
            
            # Limit range size to prevent excessive rules
            range_size = end_port - start_port + 1
            if range_size > 100:
                raise ValueError(f"Port range too large ({range_size} ports). Maximum allowed is 100 ports.")
            
            # Generate list of ports in range
            result = []
            for port in range(start_port, end_port + 1):
                result.append({
                    "port": port,
                    "protocol": protocol_upper
                })
            return result
        else:
            # Single port
            port_num = int(port_part)
            validate_port(port_num)
            
            return [{
                "port": port_num,
                "protocol": protocol_upper
            }]
    except ValueError as e:
        # Preserve original error details while providing helpful message
        raise ValueError(
            f"Invalid port specification: {port_spec}. "
            f"Format should be PORT:PROTOCOL or PORT_START-PORT_END:PROTOCOL "
            f"(e.g., 5060:udp or 5060-5070:udp). "
            f"Original error: {str(e)}"
        ) from e
    except IndexError as e:
        raise ValueError(
            f"Invalid port specification: {port_spec}. "
            f"Format should be PORT:PROTOCOL or PORT_START-PORT_END:PROTOCOL "
            f"(e.g., 5060:udp or 5060-5070:udp). "
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
