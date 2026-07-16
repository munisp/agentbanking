"""
Enhanced POS Device Drivers
USB and Bluetooth device support with advanced communication protocols
"""

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Union, Callable
from enum import Enum
import threading
import queue

# USB support
try:
    import usb.core
    import usb.util
    USB_AVAILABLE = True
except ImportError:
    USB_AVAILABLE = False
    logging.warning("USB support not available. Install pyusb: pip install pyusb")

# Bluetooth support
try:
    import bluetooth
    BLUETOOTH_AVAILABLE = True
except ImportError:
    BLUETOOTH_AVAILABLE = False
    logging.warning("Bluetooth support not available. Install pybluez: pip install pybluez")

# Serial support
import serial
import serial.tools.list_ports

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeviceProtocol(str, Enum):
    SERIAL = "serial"
    USB = "usb"
    BLUETOOTH = "bluetooth"
    TCP = "tcp"
    WEBSOCKET = "websocket"

class DeviceCommand(str, Enum):
    PRINT_RECEIPT = "print_receipt"
    OPEN_CASH_DRAWER = "open_cash_drawer"
    READ_CARD = "read_card"
    DISPLAY_MESSAGE = "display_message"
    GET_STATUS = "get_status"
    SCAN_BARCODE = "scan_barcode"
    PROCESS_PAYMENT = "process_payment"
    CANCEL_TRANSACTION = "cancel_transaction"

@dataclass
class DeviceCapability:
    name: str
    supported: bool
    version: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

@dataclass
class DeviceInfo:
    device_id: str
    device_type: str
    protocol: DeviceProtocol
    name: str
    manufacturer: str
    model: str
    firmware_version: str
    capabilities: List[DeviceCapability]
    connection_params: Dict[str, Any]
    status: str = "disconnected"

@dataclass
class DeviceResponse:
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class BaseDeviceDriver(ABC):
    """Base class for all device drivers"""
    
    def __init__(self, device_info: DeviceInfo):
        self.device_info = device_info
        self.connected = False
        self.connection = None
        self.event_callbacks: Dict[str, List[Callable]] = {}
        self.command_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.worker_thread = None
        self.stop_event = threading.Event()
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the device"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the device"""
        pass
    
    @abstractmethod
    async def send_command(self, command: DeviceCommand, data: Any = None) -> DeviceResponse:
        """Send command to device"""
        pass
    
    def add_event_callback(self, event_type: str, callback: Callable):
        """Add event callback"""
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        self.event_callbacks[event_type].append(callback)
    
    def emit_event(self, event_type: str, data: Any = None):
        """Emit event to callbacks"""
        if event_type in self.event_callbacks:
            for callback in self.event_callbacks[event_type]:
                try:
                    callback(event_type, data)
                except Exception as e:
                    logger.error(f"Event callback error: {e}")

class SerialDeviceDriver(BaseDeviceDriver):
    """Serial device driver with ESC/POS support"""
    
    def __init__(self, device_info: DeviceInfo):
        super().__init__(device_info)
        self.serial_port = None
        self.baud_rate = device_info.connection_params.get("baud_rate", 9600)
        self.timeout = device_info.connection_params.get("timeout", 5)
    
    async def connect(self) -> bool:
        """Connect to serial device"""
        try:
            port = self.device_info.connection_params.get("port")
            if not port:
                raise ValueError("Serial port not specified")
            
            self.serial_port = serial.Serial(
                port=port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            
            # Test connection
            self.serial_port.write(b'\x1B\x40')  # ESC @ (Initialize printer)
            time.sleep(0.1)
            
            self.connected = True
            self.device_info.status = "connected"
            self.emit_event("connected", {"device_id": self.device_info.device_id})
            
            logger.info(f"Connected to serial device: {port}")
            return True
            
        except Exception as e:
            logger.error(f"Serial connection failed: {e}")
            self.connected = False
            self.device_info.status = "error"
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from serial device"""
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            
            self.connected = False
            self.device_info.status = "disconnected"
            self.emit_event("disconnected", {"device_id": self.device_info.device_id})
            
            return True
            
        except Exception as e:
            logger.error(f"Serial disconnection failed: {e}")
            return False
    
    async def send_command(self, command: DeviceCommand, data: Any = None) -> DeviceResponse:
        """Send command to serial device"""
        if not self.connected or not self.serial_port:
            return DeviceResponse(success=False, error="Device not connected")
        
        try:
            if command == DeviceCommand.PRINT_RECEIPT:
                return await self._print_receipt(data)
            elif command == DeviceCommand.OPEN_CASH_DRAWER:
                return await self._open_cash_drawer()
            elif command == DeviceCommand.READ_CARD:
                return await self._read_card()
            elif command == DeviceCommand.DISPLAY_MESSAGE:
                return await self._display_message(data)
            elif command == DeviceCommand.GET_STATUS:
                return await self._get_status()
            else:
                return DeviceResponse(success=False, error=f"Unsupported command: {command}")
                
        except Exception as e:
            logger.error(f"Serial command failed: {e}")
            return DeviceResponse(success=False, error=str(e))
    
    async def _print_receipt(self, receipt_data: Dict[str, Any]) -> DeviceResponse:
        """Print receipt using ESC/POS commands"""
        try:
            # ESC/POS receipt formatting
            commands = []
            
            # Initialize printer
            commands.append(b'\x1B\x40')  # ESC @
            
            # Set character set
            commands.append(b'\x1B\x74\x00')  # ESC t 0 (PC437)
            
            # Header
            if receipt_data.get("header"):
                commands.append(b'\x1B\x61\x01')  # ESC a 1 (Center align)
                commands.append(b'\x1B\x21\x30')  # ESC ! 48 (Double height/width)
                commands.append(receipt_data["header"].encode() + b'\n\n')
            
            # Transaction details
            commands.append(b'\x1B\x61\x00')  # ESC a 0 (Left align)
            commands.append(b'\x1B\x21\x00')  # ESC ! 0 (Normal text)
            
            if receipt_data.get("transaction_id"):
                commands.append(f"Transaction ID: {receipt_data['transaction_id']}\n".encode())
            
            if receipt_data.get("amount"):
                commands.append(f"Amount: {receipt_data['amount']}\n".encode())
            
            if receipt_data.get("payment_method"):
                commands.append(f"Payment: {receipt_data['payment_method']}\n".encode())
            
            if receipt_data.get("timestamp"):
                commands.append(f"Date/Time: {receipt_data['timestamp']}\n".encode())
            
            # Footer
            commands.append(b'\n')
            commands.append(b'\x1B\x61\x01')  # Center align
            commands.append(b'Thank you for your business!\n')
            
            # Cut paper
            commands.append(b'\x1D\x56\x42\x00')  # GS V B 0 (Full cut)
            
            # Send all commands
            for cmd in commands:
                self.serial_port.write(cmd)
                time.sleep(0.01)  # Small delay between commands
            
            return DeviceResponse(success=True, data={"printed": True})
            
        except Exception as e:
            return DeviceResponse(success=False, error=f"Print failed: {e}")
    
    async def _open_cash_drawer(self) -> DeviceResponse:
        """Open cash drawer"""
        try:
            # ESC/POS cash drawer command
            self.serial_port.write(b'\x1B\x70\x00\x19\xFA')  # ESC p 0 25 250
            return DeviceResponse(success=True, data={"drawer_opened": True})
        except Exception as e:
            return DeviceResponse(success=False, error=f"Cash drawer failed: {e}")
    
    async def _read_card(self) -> DeviceResponse:
        """Read card data"""
        try:
            # Send card read command
            self.serial_port.write(b'\x02READ_CARD\x03')
            
            # Wait for response
            response = self.serial_port.read(100)
            
            if response:
                card_data = response.decode('utf-8', errors='ignore')
                return DeviceResponse(success=True, data={"card_data": card_data})
            else:
                return DeviceResponse(success=False, error="No card data received")
                
        except Exception as e:
            return DeviceResponse(success=False, error=f"Card read failed: {e}")
    
    async def _display_message(self, message: str) -> DeviceResponse:
        """Display message on device"""
        try:
            # Clear display and show message
            commands = [
                b'\x1B\x40',  # Initialize
                b'\x1B\x61\x01',  # Center align
                message.encode() + b'\n'
            ]
            
            for cmd in commands:
                self.serial_port.write(cmd)
            
            return DeviceResponse(success=True, data={"message_displayed": True})
            
        except Exception as e:
            return DeviceResponse(success=False, error=f"Display failed: {e}")
    
    async def _get_status(self) -> DeviceResponse:
        """Get device status"""
        try:
            # Send status request
            self.serial_port.write(b'\x1B\x76')  # ESC v (Status request)
            
            # Read response
            response = self.serial_port.read(10)
            
            status = {
                "connected": self.connected,
                "port": self.serial_port.port,
                "baud_rate": self.baud_rate,
                "response_length": len(response)
            }
            
            return DeviceResponse(success=True, data=status)
            
        except Exception as e:
            return DeviceResponse(success=False, error=f"Status check failed: {e}")

class USBDeviceDriver(BaseDeviceDriver):
    """USB device driver"""
    
    def __init__(self, device_info: DeviceInfo):
        super().__init__(device_info)
        self.usb_device = None
        self.vendor_id = device_info.connection_params.get("vendor_id")
        self.product_id = device_info.connection_params.get("product_id")
        self.endpoint_in = None
        self.endpoint_out = None
    
    async def connect(self) -> bool:
        """Connect to USB device"""
        if not USB_AVAILABLE:
            logger.error("USB support not available")
            return False
        
        try:
            # Find USB device
            self.usb_device = usb.core.find(
                idVendor=self.vendor_id,
                idProduct=self.product_id
            )
            
            if self.usb_device is None:
                raise ValueError(f"USB device not found: {self.vendor_id:04x}:{self.product_id:04x}")
            
            # Set configuration
            self.usb_device.set_configuration()
            
            # Get endpoints
            cfg = self.usb_device.get_active_configuration()
            intf = cfg[(0, 0)]
            
            self.endpoint_out = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
            )
            
            self.endpoint_in = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
            )
            
            if self.endpoint_out is None:
                raise ValueError("USB OUT endpoint not found")
            
            self.connected = True
            self.device_info.status = "connected"
            self.emit_event("connected", {"device_id": self.device_info.device_id})
            
            logger.info(f"Connected to USB device: {self.vendor_id:04x}:{self.product_id:04x}")
            return True
            
        except Exception as e:
            logger.error(f"USB connection failed: {e}")
            self.connected = False
            self.device_info.status = "error"
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from USB device"""
        try:
            if self.usb_device:
                usb.util.dispose_resources(self.usb_device)
                self.usb_device = None
            
            self.connected = False
            self.device_info.status = "disconnected"
            self.emit_event("disconnected", {"device_id": self.device_info.device_id})
            
            return True
            
        except Exception as e:
            logger.error(f"USB disconnection failed: {e}")
            return False
    
    async def send_command(self, command: DeviceCommand, data: Any = None) -> DeviceResponse:
        """Send command to USB device"""
        if not self.connected or not self.usb_device:
            return DeviceResponse(success=False, error="Device not connected")
        
        try:
            # Prepare command data
            command_data = {
                "command": command.value,
                "data": data,
                "timestamp": time.time()
            }
            
            command_bytes = json.dumps(command_data).encode()
            
            # Send command
            self.endpoint_out.write(command_bytes)
            
            # Read response if input endpoint available
            if self.endpoint_in:
                try:
                    response_bytes = self.endpoint_in.read(1024, timeout=5000)
                    response_data = json.loads(response_bytes.decode())
                    
                    return DeviceResponse(
                        success=response_data.get("success", True),
                        data=response_data.get("data"),
                        error=response_data.get("error")
                    )
                except Exception as e:
                    logger.warning(f"USB response read failed: {e}")
            
            return DeviceResponse(success=True, data={"command_sent": True})
            
        except Exception as e:
            logger.error(f"USB command failed: {e}")
            return DeviceResponse(success=False, error=str(e))

class BluetoothDeviceDriver(BaseDeviceDriver):
    """Bluetooth device driver"""
    
    def __init__(self, device_info: DeviceInfo):
        super().__init__(device_info)
        self.bt_socket = None
        self.bt_address = device_info.connection_params.get("address")
        self.bt_port = device_info.connection_params.get("port", 1)
    
    async def connect(self) -> bool:
        """Connect to Bluetooth device"""
        if not BLUETOOTH_AVAILABLE:
            logger.error("Bluetooth support not available")
            return False
        
        try:
            # Create Bluetooth socket
            self.bt_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            
            # Connect to device
            self.bt_socket.connect((self.bt_address, self.bt_port))
            
            # Set timeout
            self.bt_socket.settimeout(5.0)
            
            self.connected = True
            self.device_info.status = "connected"
            self.emit_event("connected", {"device_id": self.device_info.device_id})
            
            logger.info(f"Connected to Bluetooth device: {self.bt_address}")
            return True
            
        except Exception as e:
            logger.error(f"Bluetooth connection failed: {e}")
            self.connected = False
            self.device_info.status = "error"
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from Bluetooth device"""
        try:
            if self.bt_socket:
                self.bt_socket.close()
                self.bt_socket = None
            
            self.connected = False
            self.device_info.status = "disconnected"
            self.emit_event("disconnected", {"device_id": self.device_info.device_id})
            
            return True
            
        except Exception as e:
            logger.error(f"Bluetooth disconnection failed: {e}")
            return False
    
    async def send_command(self, command: DeviceCommand, data: Any = None) -> DeviceResponse:
        """Send command to Bluetooth device"""
        if not self.connected or not self.bt_socket:
            return DeviceResponse(success=False, error="Device not connected")
        
        try:
            # Prepare command
            command_data = {
                "command": command.value,
                "data": data,
                "timestamp": time.time()
            }
            
            command_json = json.dumps(command_data)
            
            # Send command
            self.bt_socket.send(command_json.encode())
            
            # Read response
            try:
                response_data = self.bt_socket.recv(1024)
                response_json = response_data.decode()
                response = json.loads(response_json)
                
                return DeviceResponse(
                    success=response.get("success", True),
                    data=response.get("data"),
                    error=response.get("error")
                )
                
            except Exception as e:
                logger.warning(f"Bluetooth response read failed: {e}")
                return DeviceResponse(success=True, data={"command_sent": True})
            
        except Exception as e:
            logger.error(f"Bluetooth command failed: {e}")
            return DeviceResponse(success=False, error=str(e))

class DeviceDriverManager:
    """Manager for all device drivers"""
    
    def __init__(self):
        self.drivers: Dict[str, BaseDeviceDriver] = {}
        self.device_registry: Dict[str, DeviceInfo] = {}
    
    def register_device(self, device_info: DeviceInfo) -> str:
        """Register a new device"""
        device_id = device_info.device_id
        self.device_registry[device_id] = device_info
        
        # Create appropriate driver
        if device_info.protocol == DeviceProtocol.SERIAL:
            driver = SerialDeviceDriver(device_info)
        elif device_info.protocol == DeviceProtocol.USB:
            driver = USBDeviceDriver(device_info)
        elif device_info.protocol == DeviceProtocol.BLUETOOTH:
            driver = BluetoothDeviceDriver(device_info)
        else:
            raise ValueError(f"Unsupported protocol: {device_info.protocol}")
        
        self.drivers[device_id] = driver
        logger.info(f"Registered device: {device_id} ({device_info.protocol})")
        
        return device_id
    
    def unregister_device(self, device_id: str) -> bool:
        """Unregister a device"""
        if device_id in self.drivers:
            driver = self.drivers[device_id]
            asyncio.create_task(driver.disconnect())
            del self.drivers[device_id]
            del self.device_registry[device_id]
            logger.info(f"Unregistered device: {device_id}")
            return True
        return False
    
    async def connect_device(self, device_id: str) -> bool:
        """Connect to a device"""
        if device_id not in self.drivers:
            raise ValueError(f"Device not registered: {device_id}")
        
        driver = self.drivers[device_id]
        return await driver.connect()
    
    async def disconnect_device(self, device_id: str) -> bool:
        """Disconnect from a device"""
        if device_id not in self.drivers:
            raise ValueError(f"Device not registered: {device_id}")
        
        driver = self.drivers[device_id]
        return await driver.disconnect()
    
    async def send_device_command(self, device_id: str, command: DeviceCommand, data: Any = None) -> DeviceResponse:
        """Send command to a device"""
        if device_id not in self.drivers:
            raise ValueError(f"Device not registered: {device_id}")
        
        driver = self.drivers[device_id]
        return await driver.send_command(command, data)
    
    def get_device_info(self, device_id: str) -> Optional[DeviceInfo]:
        """Get device information"""
        return self.device_registry.get(device_id)
    
    def list_devices(self) -> List[DeviceInfo]:
        """List all registered devices"""
        return list(self.device_registry.values())
    
    def get_connected_devices(self) -> List[DeviceInfo]:
        """Get list of connected devices"""
        connected = []
        for device_id, driver in self.drivers.items():
            if driver.connected:
                connected.append(self.device_registry[device_id])
        return connected
    
    async def discover_serial_devices(self) -> List[DeviceInfo]:
        """Discover serial devices"""
        devices = []
        
        try:
            ports = serial.tools.list_ports.comports()
            
            for port in ports:
                device_info = DeviceInfo(
                    device_id=f"serial_{port.device.replace('/', '_')}",
                    device_type="serial_device",
                    protocol=DeviceProtocol.SERIAL,
                    name=f"Serial Device ({port.device})",
                    manufacturer=port.manufacturer or "Unknown",
                    model=port.product or "Unknown",
                    firmware_version="Unknown",
                    capabilities=[
                        DeviceCapability("print_receipt", True),
                        DeviceCapability("open_cash_drawer", True),
                        DeviceCapability("display_message", True),
                    ],
                    connection_params={
                        "port": port.device,
                        "baud_rate": 9600,
                        "timeout": 5
                    }
                )
                devices.append(device_info)
                
        except Exception as e:
            logger.error(f"Serial device discovery failed: {e}")
        
        return devices
    
    async def discover_usb_devices(self) -> List[DeviceInfo]:
        """Discover USB devices"""
        devices = []
        
        if not USB_AVAILABLE:
            return devices
        
        try:
            # Common POS device vendor IDs
            pos_vendors = {
                0x04b8: "Epson",
                0x0519: "Star Micronics",
                0x154f: "Citizen",
                0x0483: "Custom",
            }
            
            usb_devices = usb.core.find(find_all=True)
            
            for dev in usb_devices:
                if dev.idVendor in pos_vendors:
                    device_info = DeviceInfo(
                        device_id=f"usb_{dev.idVendor:04x}_{dev.idProduct:04x}",
                        device_type="usb_pos_device",
                        protocol=DeviceProtocol.USB,
                        name=f"USB POS Device",
                        manufacturer=pos_vendors[dev.idVendor],
                        model=f"Model {dev.idProduct:04x}",
                        firmware_version="Unknown",
                        capabilities=[
                            DeviceCapability("print_receipt", True),
                            DeviceCapability("process_payment", True),
                            DeviceCapability("get_status", True),
                        ],
                        connection_params={
                            "vendor_id": dev.idVendor,
                            "product_id": dev.idProduct
                        }
                    )
                    devices.append(device_info)
                    
        except Exception as e:
            logger.error(f"USB device discovery failed: {e}")
        
        return devices
    
    async def discover_bluetooth_devices(self) -> List[DeviceInfo]:
        """Discover Bluetooth devices"""
        devices = []
        
        if not BLUETOOTH_AVAILABLE:
            return devices
        
        try:
            nearby_devices = bluetooth.discover_devices(lookup_names=True)
            
            for addr, name in nearby_devices:
                # Filter for POS-like devices
                if any(keyword in name.lower() for keyword in ["pos", "printer", "terminal", "payment"]):
                    device_info = DeviceInfo(
                        device_id=f"bt_{addr.replace(':', '_')}",
                        device_type="bluetooth_pos_device",
                        protocol=DeviceProtocol.BLUETOOTH,
                        name=name,
                        manufacturer="Unknown",
                        model="Bluetooth Device",
                        firmware_version="Unknown",
                        capabilities=[
                            DeviceCapability("print_receipt", True),
                            DeviceCapability("process_payment", True),
                        ],
                        connection_params={
                            "address": addr,
                            "port": 1
                        }
                    )
                    devices.append(device_info)
                    
        except Exception as e:
            logger.error(f"Bluetooth device discovery failed: {e}")
        
        return devices
    
    async def discover_all_devices(self) -> List[DeviceInfo]:
        """Discover all available devices"""
        all_devices = []
        
        # Discover serial devices
        serial_devices = await self.discover_serial_devices()
        all_devices.extend(serial_devices)
        
        # Discover USB devices
        usb_devices = await self.discover_usb_devices()
        all_devices.extend(usb_devices)
        
        # Discover Bluetooth devices
        bluetooth_devices = await self.discover_bluetooth_devices()
        all_devices.extend(bluetooth_devices)
        
        logger.info(f"Discovered {len(all_devices)} devices")
        return all_devices

# Global device manager instance
device_manager = DeviceDriverManager()

# Export main classes and functions
__all__ = [
    'DeviceProtocol',
    'DeviceCommand', 
    'DeviceCapability',
    'DeviceInfo',
    'DeviceResponse',
    'BaseDeviceDriver',
    'SerialDeviceDriver',
    'USBDeviceDriver', 
    'BluetoothDeviceDriver',
    'DeviceDriverManager',
    'device_manager'
]
