#!/usr/bin/env python3
"""
Power Management and Battery Optimization Service
Manages device power consumption, battery optimization, and performance scaling
"""

import os
import sys
import json
import time
import uuid
import threading
import logging
import psutil
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS
import schedule

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PowerMode(Enum):
    """Power management modes"""
    PERFORMANCE = "performance"
    BALANCED = "balanced"
    POWER_SAVER = "power_saver"
    ULTRA_POWER_SAVER = "ultra_power_saver"
    EMERGENCY = "emergency"

class CPUGovernor(Enum):
    """CPU frequency governors"""
    PERFORMANCE = "performance"
    POWERSAVE = "powersave"
    ONDEMAND = "ondemand"
    CONSERVATIVE = "conservative"
    USERSPACE = "userspace"

class ThermalState(Enum):
    """Thermal states"""
    NORMAL = "normal"
    WARM = "warm"
    HOT = "hot"
    CRITICAL = "critical"

@dataclass
class PowerProfile:
    """Power management profile"""
    mode: PowerMode
    cpu_governor: CPUGovernor
    max_cpu_freq: Optional[int]
    cpu_cores_enabled: int
    screen_brightness: int
    wifi_power_save: bool
    bluetooth_enabled: bool
    background_apps_limit: int
    sync_interval_minutes: int
    video_quality: str
    processing_priority: str

@dataclass
class BatteryInfo:
    """Battery information"""
    level: float
    is_charging: bool
    time_remaining: Optional[int]  # minutes
    health: str
    temperature: Optional[float]
    voltage: Optional[float]
    current: Optional[float]

@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_usage: float
    temperature: Optional[float]
    power_consumption: Optional[float]
    battery_info: BatteryInfo

@dataclass
class PowerEvent:
    """Power management event"""
    id: str
    event_type: str
    timestamp: datetime
    old_mode: PowerMode
    new_mode: PowerMode
    trigger: str
    details: Dict[str, Any]

class BatteryMonitor:
    """Battery monitoring and management"""
    
    def __init__(self):
        self.monitoring = False
        self.callbacks = []
        
    def get_battery_info(self) -> Optional[BatteryInfo]:
        """Get current battery information"""
        try:
            battery = psutil.sensors_battery()
            if not battery:
                return None
                
            # Get additional battery info from system files (Linux)
            temperature = self._get_battery_temperature()
            voltage = self._get_battery_voltage()
            current = self._get_battery_current()
            health = self._get_battery_health()
            
            return BatteryInfo(
                level=battery.percent,
                is_charging=battery.power_plugged,
                time_remaining=battery.secsleft // 60 if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None,
                health=health,
                temperature=temperature,
                voltage=voltage,
                current=current
            )
            
        except Exception as e:
            logger.error(f"Error getting battery info: {e}")
            return None
            
    def _get_battery_temperature(self) -> Optional[float]:
        """Get battery temperature from system files"""
        try:
            # Try different paths for battery temperature
            temp_paths = [
                "/sys/class/power_supply/BAT0/temp",
                "/sys/class/power_supply/BAT1/temp",
                "/sys/class/thermal/thermal_zone0/temp"
            ]
            
            for path in temp_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        temp = int(f.read().strip())
                        # Convert from millidegrees to degrees
                        return temp / 1000.0 if temp > 1000 else temp
                        
            return None
            
        except Exception:
            return None
            
    def _get_battery_voltage(self) -> Optional[float]:
        """Get battery voltage"""
        try:
            voltage_paths = [
                "/sys/class/power_supply/BAT0/voltage_now",
                "/sys/class/power_supply/BAT1/voltage_now"
            ]
            
            for path in voltage_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        voltage = int(f.read().strip())
                        # Convert from microvolts to volts
                        return voltage / 1000000.0
                        
            return None
            
        except Exception:
            return None
            
    def _get_battery_current(self) -> Optional[float]:
        """Get battery current"""
        try:
            current_paths = [
                "/sys/class/power_supply/BAT0/current_now",
                "/sys/class/power_supply/BAT1/current_now"
            ]
            
            for path in current_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        current = int(f.read().strip())
                        # Convert from microamps to amps
                        return current / 1000000.0
                        
            return None
            
        except Exception:
            return None
            
    def _get_battery_health(self) -> str:
        """Get battery health status"""
        try:
            health_paths = [
                "/sys/class/power_supply/BAT0/health",
                "/sys/class/power_supply/BAT1/health"
            ]
            
            for path in health_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        return f.read().strip()
                        
            return "Unknown"
            
        except Exception:
            return "Unknown"
            
    def add_callback(self, callback):
        """Add battery event callback"""
        self.callbacks.append(callback)
        
    def start_monitoring(self, interval: int = 30):
        """Start battery monitoring"""
        self.monitoring = True
        
        def monitor_loop():
            last_level = None
            last_charging = None
            
            while self.monitoring:
                try:
                    battery_info = self.get_battery_info()
                    
                    if battery_info:
                        # Check for significant changes
                        level_changed = last_level is None or abs(battery_info.level - last_level) >= 5
                        charging_changed = last_charging is None or battery_info.is_charging != last_charging
                        
                        if level_changed or charging_changed:
                            # Notify callbacks
                            for callback in self.callbacks:
                                try:
                                    callback(battery_info)
                                except Exception as e:
                                    logger.error(f"Error in battery callback: {e}")
                                    
                            last_level = battery_info.level
                            last_charging = battery_info.is_charging
                            
                    time.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Error in battery monitoring: {e}")
                    time.sleep(interval)
                    
        threading.Thread(target=monitor_loop, daemon=True).start()
        logger.info("Battery monitoring started")
        
    def stop_monitoring(self):
        """Stop battery monitoring"""
        self.monitoring = False
        logger.info("Battery monitoring stopped")

class CPUManager:
    """CPU frequency and governor management"""
    
    def __init__(self):
        self.available_governors = self._get_available_governors()
        self.available_frequencies = self._get_available_frequencies()
        
    def _get_available_governors(self) -> List[str]:
        """Get available CPU governors"""
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors", 'r') as f:
                return f.read().strip().split()
        except Exception:
            return ["performance", "powersave", "ondemand", "conservative"]
            
    def _get_available_frequencies(self) -> List[int]:
        """Get available CPU frequencies"""
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies", 'r') as f:
                frequencies = f.read().strip().split()
                return [int(freq) for freq in frequencies]
        except Exception:
            return []
            
    def set_governor(self, governor: CPUGovernor) -> bool:
        """Set CPU governor"""
        try:
            if governor.value not in self.available_governors:
                logger.warning(f"Governor {governor.value} not available")
                return False
                
            # Set governor for all CPUs
            cpu_count = psutil.cpu_count()
            
            for cpu in range(cpu_count):
                governor_path = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor"
                
                if os.path.exists(governor_path):
                    try:
                        # This requires root privileges
                        subprocess.run(
                            ["sudo", "sh", "-c", f"echo {governor.value} > {governor_path}"],
                            check=True,
                            capture_output=True
                        )
                    except subprocess.CalledProcessError as e:
                        logger.warning(f"Could not set governor for CPU {cpu}: {e}")
                        
            logger.info(f"Set CPU governor to {governor.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting CPU governor: {e}")
            return False
            
    def set_max_frequency(self, frequency: int) -> bool:
        """Set maximum CPU frequency"""
        try:
            if frequency not in self.available_frequencies:
                logger.warning(f"Frequency {frequency} not available")
                return False
                
            cpu_count = psutil.cpu_count()
            
            for cpu in range(cpu_count):
                max_freq_path = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_max_freq"
                
                if os.path.exists(max_freq_path):
                    try:
                        subprocess.run(
                            ["sudo", "sh", "-c", f"echo {frequency} > {max_freq_path}"],
                            check=True,
                            capture_output=True
                        )
                    except subprocess.CalledProcessError as e:
                        logger.warning(f"Could not set max frequency for CPU {cpu}: {e}")
                        
            logger.info(f"Set max CPU frequency to {frequency}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting CPU frequency: {e}")
            return False
            
    def enable_cpu_cores(self, count: int) -> bool:
        """Enable/disable CPU cores"""
        try:
            total_cores = psutil.cpu_count()
            
            if count > total_cores:
                count = total_cores
                
            # Enable/disable cores
            for cpu in range(1, total_cores):  # CPU 0 cannot be disabled
                online_path = f"/sys/devices/system/cpu/cpu{cpu}/online"
                
                if os.path.exists(online_path):
                    try:
                        enable = "1" if cpu < count else "0"
                        subprocess.run(
                            ["sudo", "sh", "-c", f"echo {enable} > {online_path}"],
                            check=True,
                            capture_output=True
                        )
                    except subprocess.CalledProcessError as e:
                        logger.warning(f"Could not set online status for CPU {cpu}: {e}")
                        
            logger.info(f"Enabled {count} CPU cores")
            return True
            
        except Exception as e:
            logger.error(f"Error managing CPU cores: {e}")
            return False
            
    def get_current_governor(self) -> Optional[str]:
        """Get current CPU governor"""
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", 'r') as f:
                return f.read().strip()
        except Exception:
            return None
            
    def get_current_frequency(self) -> Optional[int]:
        """Get current CPU frequency"""
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", 'r') as f:
                return int(f.read().strip())
        except Exception:
            return None

class ThermalManager:
    """Thermal monitoring and management"""
    
    def __init__(self):
        self.thermal_zones = self._discover_thermal_zones()
        
    def _discover_thermal_zones(self) -> List[str]:
        """Discover available thermal zones"""
        zones = []
        thermal_path = Path("/sys/class/thermal")
        
        if thermal_path.exists():
            for zone_dir in thermal_path.glob("thermal_zone*"):
                zones.append(str(zone_dir))
                
        return zones
        
    def get_temperature(self) -> Optional[float]:
        """Get system temperature"""
        try:
            # Try psutil first
            temps = psutil.sensors_temperatures()
            
            if temps:
                # Get the first available temperature
                for name, entries in temps.items():
                    if entries:
                        return entries[0].current
                        
            # Fallback to thermal zones
            for zone in self.thermal_zones:
                temp_file = Path(zone) / "temp"
                if temp_file.exists():
                    with open(temp_file, 'r') as f:
                        temp = int(f.read().strip())
                        return temp / 1000.0  # Convert from millidegrees
                        
            return None
            
        except Exception as e:
            logger.error(f"Error getting temperature: {e}")
            return None
            
    def get_thermal_state(self, temperature: float) -> ThermalState:
        """Determine thermal state based on temperature"""
        if temperature < 60:
            return ThermalState.NORMAL
        elif temperature < 75:
            return ThermalState.WARM
        elif temperature < 85:
            return ThermalState.HOT
        else:
            return ThermalState.CRITICAL

class PowerProfileManager:
    """Power profile management"""
    
    def __init__(self):
        self.profiles = self._create_default_profiles()
        self.current_profile = self.profiles[PowerMode.BALANCED]
        
    def _create_default_profiles(self) -> Dict[PowerMode, PowerProfile]:
        """Create default power profiles"""
        return {
            PowerMode.PERFORMANCE: PowerProfile(
                mode=PowerMode.PERFORMANCE,
                cpu_governor=CPUGovernor.PERFORMANCE,
                max_cpu_freq=None,  # No limit
                cpu_cores_enabled=psutil.cpu_count(),
                screen_brightness=100,
                wifi_power_save=False,
                bluetooth_enabled=True,
                background_apps_limit=10,
                sync_interval_minutes=5,
                video_quality="high",
                processing_priority="high"
            ),
            
            PowerMode.BALANCED: PowerProfile(
                mode=PowerMode.BALANCED,
                cpu_governor=CPUGovernor.ONDEMAND,
                max_cpu_freq=None,
                cpu_cores_enabled=psutil.cpu_count(),
                screen_brightness=80,
                wifi_power_save=False,
                bluetooth_enabled=True,
                background_apps_limit=5,
                sync_interval_minutes=15,
                video_quality="medium",
                processing_priority="normal"
            ),
            
            PowerMode.POWER_SAVER: PowerProfile(
                mode=PowerMode.POWER_SAVER,
                cpu_governor=CPUGovernor.CONSERVATIVE,
                max_cpu_freq=None,  # Will be set to 70% of max
                cpu_cores_enabled=max(2, psutil.cpu_count() // 2),
                screen_brightness=60,
                wifi_power_save=True,
                bluetooth_enabled=False,
                background_apps_limit=3,
                sync_interval_minutes=30,
                video_quality="low",
                processing_priority="low"
            ),
            
            PowerMode.ULTRA_POWER_SAVER: PowerProfile(
                mode=PowerMode.ULTRA_POWER_SAVER,
                cpu_governor=CPUGovernor.POWERSAVE,
                max_cpu_freq=None,  # Will be set to 50% of max
                cpu_cores_enabled=2,
                screen_brightness=40,
                wifi_power_save=True,
                bluetooth_enabled=False,
                background_apps_limit=1,
                sync_interval_minutes=60,
                video_quality="very_low",
                processing_priority="very_low"
            ),
            
            PowerMode.EMERGENCY: PowerProfile(
                mode=PowerMode.EMERGENCY,
                cpu_governor=CPUGovernor.POWERSAVE,
                max_cpu_freq=None,  # Will be set to 30% of max
                cpu_cores_enabled=1,
                screen_brightness=20,
                wifi_power_save=True,
                bluetooth_enabled=False,
                background_apps_limit=0,
                sync_interval_minutes=120,
                video_quality="disabled",
                processing_priority="minimal"
            )
        }
        
    def get_profile(self, mode: PowerMode) -> PowerProfile:
        """Get power profile for mode"""
        return self.profiles.get(mode, self.profiles[PowerMode.BALANCED])
        
    def set_current_profile(self, mode: PowerMode):
        """Set current power profile"""
        self.current_profile = self.get_profile(mode)
        
    def get_current_profile(self) -> PowerProfile:
        """Get current power profile"""
        return self.current_profile

class PowerOptimizer:
    """Main power optimization service"""
    
    def __init__(self):
        self.app = Flask(__name__)
        CORS(self.app, origins="*")
        
        # Initialize components
        self.battery_monitor = BatteryMonitor()
        self.cpu_manager = CPUManager()
        self.thermal_manager = ThermalManager()
        self.profile_manager = PowerProfileManager()
        
        # State
        self.current_mode = PowerMode.BALANCED
        self.auto_mode = True
        self.events = []
        self.metrics_history = []
        
        # Setup battery monitoring
        self.battery_monitor.add_callback(self._on_battery_change)
        
        # Setup routes
        self.setup_routes()
        
        # Start monitoring
        self.start_monitoring()
        
        logger.info("Power Optimizer initialized")
        
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'service': 'power-optimizer',
                'version': '1.0.0'
            })
            
        @self.app.route('/power/mode', methods=['GET', 'POST'])
        def power_mode():
            return self.power_mode_handler()
            
        @self.app.route('/power/profile', methods=['GET'])
        def get_profile():
            return self.get_profile_handler()
            
        @self.app.route('/power/auto', methods=['POST'])
        def set_auto_mode():
            return self.set_auto_mode_handler()
            
        @self.app.route('/battery', methods=['GET'])
        def get_battery():
            return self.get_battery_handler()
            
        @self.app.route('/metrics', methods=['GET'])
        def get_metrics():
            return self.get_metrics_handler()
            
        @self.app.route('/thermal', methods=['GET'])
        def get_thermal():
            return self.get_thermal_handler()
            
        @self.app.route('/events', methods=['GET'])
        def get_events():
            return self.get_events_handler()
            
        @self.app.route('/optimize', methods=['POST'])
        def optimize():
            return self.optimize_handler()
            
    def power_mode_handler(self):
        """Handle power mode requests"""
        try:
            if request.method == 'GET':
                return jsonify({
                    'current_mode': self.current_mode.value,
                    'auto_mode': self.auto_mode,
                    'available_modes': [mode.value for mode in PowerMode],
                    'profile': asdict(self.profile_manager.get_current_profile())
                })
            else:  # POST
                data = request.get_json()
                mode_str = data.get('mode')
                auto_mode = data.get('auto_mode', self.auto_mode)
                
                try:
                    mode = PowerMode(mode_str)
                    success = self.set_power_mode(mode, auto_mode)
                    
                    return jsonify({
                        'success': success,
                        'mode': mode.value,
                        'auto_mode': auto_mode
                    })
                except ValueError:
                    return jsonify({'error': f'Invalid power mode: {mode_str}'}), 400
                    
        except Exception as e:
            logger.error(f"Error handling power mode: {e}")
            return jsonify({'error': str(e)}), 500
            
    def get_profile_handler(self):
        """Handle get profile requests"""
        try:
            profile = self.profile_manager.get_current_profile()
            return jsonify(asdict(profile))
            
        except Exception as e:
            logger.error(f"Error getting profile: {e}")
            return jsonify({'error': str(e)}), 500
            
    def set_auto_mode_handler(self):
        """Handle set auto mode requests"""
        try:
            data = request.get_json()
            auto_mode = data.get('auto_mode', True)
            
            self.auto_mode = auto_mode
            
            return jsonify({
                'success': True,
                'auto_mode': auto_mode
            })
            
        except Exception as e:
            logger.error(f"Error setting auto mode: {e}")
            return jsonify({'error': str(e)}), 500
            
    def get_battery_handler(self):
        """Handle battery info requests"""
        try:
            battery_info = self.battery_monitor.get_battery_info()
            
            if battery_info:
                return jsonify(asdict(battery_info))
            else:
                return jsonify({'error': 'Battery information not available'}), 404
                
        except Exception as e:
            logger.error(f"Error getting battery info: {e}")
            return jsonify({'error': str(e)}), 500
            
    def get_metrics_handler(self):
        """Handle metrics requests"""
        try:
            metrics = self.collect_metrics()
            return jsonify(asdict(metrics))
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return jsonify({'error': str(e)}), 500
            
    def get_thermal_handler(self):
        """Handle thermal info requests"""
        try:
            temperature = self.thermal_manager.get_temperature()
            
            if temperature is not None:
                thermal_state = self.thermal_manager.get_thermal_state(temperature)
                
                return jsonify({
                    'temperature': temperature,
                    'thermal_state': thermal_state.value,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return jsonify({'error': 'Temperature information not available'}), 404
                
        except Exception as e:
            logger.error(f"Error getting thermal info: {e}")
            return jsonify({'error': str(e)}), 500
            
    def get_events_handler(self):
        """Handle events requests"""
        try:
            limit = int(request.args.get('limit', 50))
            events = self.events[-limit:] if limit > 0 else self.events
            
            return jsonify({
                'events': [asdict(event) for event in events],
                'total': len(self.events)
            })
            
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return jsonify({'error': str(e)}), 500
            
    def optimize_handler(self):
        """Handle optimization requests"""
        try:
            data = request.get_json()
            target = data.get('target', 'battery_life')  # battery_life, performance, balanced
            
            if target == 'battery_life':
                recommended_mode = self._recommend_battery_mode()
            elif target == 'performance':
                recommended_mode = PowerMode.PERFORMANCE
            else:  # balanced
                recommended_mode = PowerMode.BALANCED
                
            success = self.set_power_mode(recommended_mode, auto_mode=False)
            
            return jsonify({
                'success': success,
                'recommended_mode': recommended_mode.value,
                'target': target
            })
            
        except Exception as e:
            logger.error(f"Error optimizing: {e}")
            return jsonify({'error': str(e)}), 500
            
    def set_power_mode(self, mode: PowerMode, auto_mode: bool = None) -> bool:
        """Set power mode"""
        try:
            old_mode = self.current_mode
            
            # Update auto mode if specified
            if auto_mode is not None:
                self.auto_mode = auto_mode
                
            # Apply power profile
            profile = self.profile_manager.get_profile(mode)
            success = self._apply_power_profile(profile)
            
            if success:
                self.current_mode = mode
                self.profile_manager.set_current_profile(mode)
                
                # Log event
                event = PowerEvent(
                    id=str(uuid.uuid4()),
                    event_type="mode_change",
                    timestamp=datetime.now(),
                    old_mode=old_mode,
                    new_mode=mode,
                    trigger="manual" if not auto_mode else "automatic",
                    details={'auto_mode': self.auto_mode}
                )
                
                self._add_event(event)
                
                logger.info(f"Power mode changed from {old_mode.value} to {mode.value}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error setting power mode: {e}")
            return False
            
    def _apply_power_profile(self, profile: PowerProfile) -> bool:
        """Apply power profile settings"""
        try:
            success = True
            
            # Set CPU governor
            if not self.cpu_manager.set_governor(profile.cpu_governor):
                success = False
                
            # Set CPU frequency limit
            if profile.max_cpu_freq:
                if not self.cpu_manager.set_max_frequency(profile.max_cpu_freq):
                    success = False
            else:
                # Set frequency based on mode
                available_freqs = self.cpu_manager.available_frequencies
                if available_freqs:
                    max_freq = max(available_freqs)
                    
                    if profile.mode == PowerMode.POWER_SAVER:
                        target_freq = int(max_freq * 0.7)
                    elif profile.mode == PowerMode.ULTRA_POWER_SAVER:
                        target_freq = int(max_freq * 0.5)
                    elif profile.mode == PowerMode.EMERGENCY:
                        target_freq = int(max_freq * 0.3)
                    else:
                        target_freq = max_freq
                        
                    # Find closest available frequency
                    closest_freq = min(available_freqs, key=lambda x: abs(x - target_freq))
                    
                    if not self.cpu_manager.set_max_frequency(closest_freq):
                        success = False
                        
            # Set CPU cores
            if not self.cpu_manager.enable_cpu_cores(profile.cpu_cores_enabled):
                success = False
                
            # Apply other settings (simplified for this example)
            # In a real implementation, you would:
            # - Set screen brightness
            # - Configure WiFi power save
            # - Enable/disable Bluetooth
            # - Limit background applications
            # - Adjust sync intervals
            
            logger.info(f"Applied power profile: {profile.mode.value}")
            return success
            
        except Exception as e:
            logger.error(f"Error applying power profile: {e}")
            return False
            
    def _on_battery_change(self, battery_info: BatteryInfo):
        """Handle battery change events"""
        try:
            if not self.auto_mode:
                return
                
            # Determine appropriate power mode based on battery level
            if battery_info.level <= 5:
                target_mode = PowerMode.EMERGENCY
            elif battery_info.level <= 15:
                target_mode = PowerMode.ULTRA_POWER_SAVER
            elif battery_info.level <= 30:
                target_mode = PowerMode.POWER_SAVER
            elif battery_info.level <= 50 and not battery_info.is_charging:
                target_mode = PowerMode.BALANCED
            else:
                target_mode = PowerMode.BALANCED if not battery_info.is_charging else PowerMode.PERFORMANCE
                
            # Change mode if different from current
            if target_mode != self.current_mode:
                self.set_power_mode(target_mode, auto_mode=True)
                
        except Exception as e:
            logger.error(f"Error handling battery change: {e}")
            
    def _recommend_battery_mode(self) -> PowerMode:
        """Recommend power mode for battery optimization"""
        try:
            battery_info = self.battery_monitor.get_battery_info()
            
            if not battery_info:
                return PowerMode.POWER_SAVER
                
            if battery_info.is_charging:
                return PowerMode.BALANCED
                
            if battery_info.level <= 10:
                return PowerMode.EMERGENCY
            elif battery_info.level <= 25:
                return PowerMode.ULTRA_POWER_SAVER
            elif battery_info.level <= 50:
                return PowerMode.POWER_SAVER
            else:
                return PowerMode.BALANCED
                
        except Exception as e:
            logger.error(f"Error recommending battery mode: {e}")
            return PowerMode.POWER_SAVER
            
    def collect_metrics(self) -> SystemMetrics:
        """Collect system metrics"""
        try:
            # Get battery info
            battery_info = self.battery_monitor.get_battery_info()
            if not battery_info:
                battery_info = BatteryInfo(
                    level=0, is_charging=False, time_remaining=None,
                    health="Unknown", temperature=None, voltage=None, current=None
                )
                
            # Get system metrics
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network usage (simplified)
            network_stats = psutil.net_io_counters()
            network_usage = (network_stats.bytes_sent + network_stats.bytes_recv) / (1024 * 1024)  # MB
            
            # Temperature
            temperature = self.thermal_manager.get_temperature()
            
            # Power consumption (estimated)
            power_consumption = self._estimate_power_consumption(cpu_usage, battery_info)
            
            metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_usage=cpu_usage,
                memory_usage=memory.percent,
                disk_usage=(disk.used / disk.total) * 100,
                network_usage=network_usage,
                temperature=temperature,
                power_consumption=power_consumption,
                battery_info=battery_info
            )
            
            # Store in history (keep last 100 entries)
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > 100:
                self.metrics_history.pop(0)
                
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_usage=0, memory_usage=0, disk_usage=0, network_usage=0,
                temperature=None, power_consumption=None,
                battery_info=BatteryInfo(
                    level=0, is_charging=False, time_remaining=None,
                    health="Unknown", temperature=None, voltage=None, current=None
                )
            )
            
    def _estimate_power_consumption(self, cpu_usage: float, battery_info: BatteryInfo) -> Optional[float]:
        """Estimate power consumption in watts"""
        try:
            # This is a simplified estimation
            # In practice, you would use more sophisticated methods
            
            base_power = 5.0  # Base system power in watts
            cpu_power = (cpu_usage / 100) * 15.0  # CPU power based on usage
            
            # Adjust based on power mode
            mode_multiplier = {
                PowerMode.PERFORMANCE: 1.2,
                PowerMode.BALANCED: 1.0,
                PowerMode.POWER_SAVER: 0.8,
                PowerMode.ULTRA_POWER_SAVER: 0.6,
                PowerMode.EMERGENCY: 0.4
            }.get(self.current_mode, 1.0)
            
            estimated_power = (base_power + cpu_power) * mode_multiplier
            
            return estimated_power
            
        except Exception:
            return None
            
    def _add_event(self, event: PowerEvent):
        """Add power event to history"""
        self.events.append(event)
        
        # Keep only last 100 events
        if len(self.events) > 100:
            self.events.pop(0)
            
    def start_monitoring(self):
        """Start monitoring services"""
        self.battery_monitor.start_monitoring()
        
        # Start periodic metrics collection
        def collect_metrics_periodically():
            while True:
                try:
                    self.collect_metrics()
                    time.sleep(60)  # Collect every minute
                except Exception as e:
                    logger.error(f"Error in periodic metrics collection: {e}")
                    time.sleep(60)
                    
        threading.Thread(target=collect_metrics_periodically, daemon=True).start()
        
        logger.info("Power monitoring started")
        
    def stop_monitoring(self):
        """Stop monitoring services"""
        self.battery_monitor.stop_monitoring()
        logger.info("Power monitoring stopped")
        
    def run(self, host='0.0.0.0', port=8094, debug=False):
        """Run the power optimizer"""
        logger.info(f"Starting Power Optimizer on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug, threaded=True)

if __name__ == '__main__':
    optimizer = PowerOptimizer()
    
    try:
        port = int(os.getenv('PORT', 8094))
        debug = os.getenv('DEBUG', 'false').lower() == 'true'
        
        optimizer.run(port=port, debug=debug)
    except KeyboardInterrupt:
        optimizer.stop_monitoring()

