package com.pos54link.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * IoT Device Health Screen
 *
 * Maps to backend: iotSmartPos.ts
 * Features:
 *   - View IoT sensors (temperature, GPS, tamper, battery)
 *   - Alert severity scoring (critical/high/medium/low)
 *   - Auto-escalation display for unacknowledged alerts
 *   - Predictive failure indicators
 *   - Device telemetry (battery level, temp, signal strength)
 *   - Acknowledge alerts action
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun IoTDeviceHealthScreen(onBack: () -> Unit) {
    var selectedTab by remember { mutableIntStateOf(0) }
    val tabs = listOf("Devices", "Alerts")

    val devices = remember {
        listOf(
            IoTDevice("IOT-001", "temperature", "online", 28.5, 85, -50, false, false),
            IoTDevice("IOT-002", "gps", "online", null, 92, -38, false, false),
            IoTDevice("IOT-003", "tamper", "tampered", null, 76, -55, true, false),
            IoTDevice("IOT-004", "battery", "offline", null, 8, -90, false, true),
        )
    }

    val alerts = remember {
        mutableStateListOf(
            IoTAlert("ALT-001", "IOT-003", "critical", "Tamper detected — device casing opened", "2026-05-19 14:30", false),
            IoTAlert("ALT-002", "IOT-004", "high", "Battery critically low (8%)", "2026-05-19 13:15", false),
            IoTAlert("ALT-003", "IOT-001", "medium", "Temperature above threshold (28.5°C)", "2026-05-19 12:00", true),
            IoTAlert("ALT-004", "IOT-002", "low", "GPS signal weak", "2026-05-18 22:45", true),
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("IoT Device Health") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } },
                actions = {
                    IconButton(onClick = { /* checkAlerts API */ }) { Icon(Icons.Default.NotificationsActive, "Check") }
                }
            )
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding)) {
            // Summary
            Row(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                val critical = alerts.count { it.severity == "critical" && !it.acknowledged }
                val high = alerts.count { it.severity == "high" && !it.acknowledged }
                val online = devices.count { it.status == "online" }
                StatCard("Online", "$online/${devices.size}", Color(0xFF16A34A), Modifier.weight(1f))
                StatCard("Critical", "$critical", Color(0xFFDC2626), Modifier.weight(1f))
                StatCard("High", "$high", Color(0xFFF59E0B), Modifier.weight(1f))
            }

            TabRow(selectedTabIndex = selectedTab) {
                tabs.forEachIndexed { i, title ->
                    Tab(selected = selectedTab == i, onClick = { selectedTab = i }, text = { Text(title) })
                }
            }

            when (selectedTab) {
                0 -> DevicesList(devices)
                1 -> AlertsList(alerts) { alert ->
                    val idx = alerts.indexOf(alert)
                    if (idx >= 0) alerts[idx] = alert.copy(acknowledged = true)
                }
            }
        }
    }
}

@Composable
private fun DevicesList(devices: List<IoTDevice>) {
    LazyColumn(
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(devices) { device ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(device.id, fontWeight = FontWeight.Bold)
                            Text("Type: ${device.type}", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                        }
                        val statusColor = when (device.status) {
                            "online" -> Color(0xFF16A34A)
                            "offline" -> Color(0xFFDC2626)
                            "tampered" -> Color(0xFFDC2626)
                            "maintenance" -> Color(0xFFF59E0B)
                            else -> Color.Gray
                        }
                        Surface(color = statusColor.copy(alpha = 0.1f), shape = MaterialTheme.shapes.small) {
                            Text(
                                device.status.uppercase(),
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                color = statusColor, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        val batteryColor = when {
                            device.batteryLevel > 50 -> Color(0xFF16A34A)
                            device.batteryLevel > 20 -> Color(0xFFF59E0B)
                            else -> Color(0xFFDC2626)
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.BatteryFull, null, tint = batteryColor, modifier = Modifier.size(16.dp))
                            Text(" ${device.batteryLevel}%", style = MaterialTheme.typography.bodySmall)
                        }
                        Text("Signal: ${device.signalStrength}dBm", style = MaterialTheme.typography.bodySmall)
                        if (device.temperature != null) {
                            Text("Temp: ${device.temperature}°C", style = MaterialTheme.typography.bodySmall)
                        }
                    }

                    if (device.tamperDetected) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFFEF2F2))) {
                            Row(modifier = Modifier.padding(8.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                Icon(Icons.Default.Warning, null, tint = Color(0xFFDC2626), modifier = Modifier.size(16.dp))
                                Text("TAMPER DETECTED", color = Color(0xFFDC2626), style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                            }
                        }
                    }

                    if (device.predictedFailure) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFFEF3C7))) {
                            Row(modifier = Modifier.padding(8.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                Icon(Icons.Default.Warning, null, tint = Color(0xFFF59E0B), modifier = Modifier.size(16.dp))
                                Text("Predicted failure — schedule maintenance", color = Color(0xFFF59E0B), style = MaterialTheme.typography.labelSmall)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun AlertsList(alerts: List<IoTAlert>, onAcknowledge: (IoTAlert) -> Unit) {
    LazyColumn(
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(alerts) { alert ->
            val severityColor = when (alert.severity) {
                "critical" -> Color(0xFFDC2626)
                "high" -> Color(0xFFF59E0B)
                "medium" -> Color(0xFF3B82F6)
                "low" -> Color(0xFF6B7280)
                else -> Color.Gray
            }

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = if (!alert.acknowledged && alert.severity in listOf("critical", "high"))
                    CardDefaults.cardColors(containerColor = Color(0xFFFEF2F2))
                else CardDefaults.cardColors()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                            Surface(color = severityColor.copy(alpha = 0.1f), shape = MaterialTheme.shapes.small) {
                                Text(
                                    alert.severity.uppercase(),
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                    color = severityColor, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold
                                )
                            }
                            Text(alert.id, fontWeight = FontWeight.Bold)
                        }
                        if (alert.acknowledged) {
                            Icon(Icons.Default.CheckCircle, null, tint = Color(0xFF16A34A), modifier = Modifier.size(20.dp))
                        }
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(alert.message, style = MaterialTheme.typography.bodyMedium)
                    Text("Device: ${alert.deviceId} — ${alert.timestamp}", style = MaterialTheme.typography.bodySmall, color = Color.Gray)

                    if (!alert.acknowledged) {
                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedButton(
                            onClick = { onAcknowledge(alert) },
                            modifier = Modifier.fillMaxWidth()
                        ) { Text("Acknowledge") }
                    }
                }
            }
        }
    }
}

private data class IoTDevice(
    val id: String,
    val type: String,
    val status: String,
    val temperature: Double?,
    val batteryLevel: Int,
    val signalStrength: Int,
    val tamperDetected: Boolean,
    val predictedFailure: Boolean
)

private data class IoTAlert(
    val id: String,
    val deviceId: String,
    val severity: String,
    val message: String,
    val timestamp: String,
    val acknowledged: Boolean
)
