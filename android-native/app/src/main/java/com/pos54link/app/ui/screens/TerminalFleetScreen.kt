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
 * Terminal Fleet Management Screen
 *
 * Maps to backend: posTerminalFleet.ts
 * Features:
 *   - View assigned terminals with status, battery, signal, firmware version
 *   - Send remote commands (reboot, lock, unlock, wipe, diagnostics)
 *   - Heartbeat tracking with last-seen indicator
 *   - Terminal statistics (active, suspended, offline)
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TerminalFleetScreen(onBack: () -> Unit) {
    val terminals = remember {
        listOf(
            TerminalInfo("TRM-PAX-001", "PAX A920", "active", 78, -55, "4.2.1", "2 min ago"),
            TerminalInfo("TRM-SUN-002", "Sunmi P2", "active", 92, -42, "4.2.1", "5 min ago"),
            TerminalInfo("TRM-PAX-003", "PAX A930", "suspended", 15, -80, "4.1.0", "2 hours ago"),
        )
    }

    var showCommandDialog by remember { mutableStateOf(false) }
    var selectedTerminal by remember { mutableStateOf<TerminalInfo?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Terminal Fleet") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } },
                actions = {
                    IconButton(onClick = { /* refresh */ }) { Icon(Icons.Default.Refresh, "Refresh") }
                }
            )
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding)) {
            // Summary cards
            Row(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                val active = terminals.count { it.status == "active" }
                val suspended = terminals.count { it.status == "suspended" }
                StatCard("Active", "$active", Color(0xFF16A34A), Modifier.weight(1f))
                StatCard("Suspended", "$suspended", Color(0xFFF59E0B), Modifier.weight(1f))
                StatCard("Total", "${terminals.size}", Color(0xFF3B82F6), Modifier.weight(1f))
            }

            // Terminal list
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(terminals) { terminal ->
                    TerminalCard(
                        terminal = terminal,
                        onCommand = {
                            selectedTerminal = terminal
                            showCommandDialog = true
                        }
                    )
                }
            }
        }
    }

    if (showCommandDialog && selectedTerminal != null) {
        CommandDialog(
            terminal = selectedTerminal!!,
            onDismiss = { showCommandDialog = false }
        )
    }
}

@Composable
private fun TerminalCard(terminal: TerminalInfo, onCommand: () -> Unit) {
    val statusColor = when (terminal.status) {
        "active" -> Color(0xFF16A34A)
        "suspended" -> Color(0xFFF59E0B)
        "terminated" -> Color(0xFFDC2626)
        else -> Color.Gray
    }

    val batteryColor = when {
        terminal.batteryLevel > 50 -> Color(0xFF16A34A)
        terminal.batteryLevel > 20 -> Color(0xFFF59E0B)
        else -> Color(0xFFDC2626)
    }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(terminal.serialNumber, fontWeight = FontWeight.Bold)
                    Text(terminal.model, style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                }
                Surface(color = statusColor.copy(alpha = 0.1f), shape = MaterialTheme.shapes.small) {
                    Text(
                        terminal.status.uppercase(),
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        color = statusColor,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
            Spacer(modifier = Modifier.height(12.dp))

            // Metrics row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.BatteryFull, null, tint = batteryColor, modifier = Modifier.size(16.dp))
                    Text(" ${terminal.batteryLevel}%", style = MaterialTheme.typography.bodySmall)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.SignalCellularAlt, null, tint = Color.Gray, modifier = Modifier.size(16.dp))
                    Text(" ${terminal.signalStrength}dBm", style = MaterialTheme.typography.bodySmall)
                }
                Text("v${terminal.firmwareVersion}", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                Text(terminal.lastSeen, style = MaterialTheme.typography.bodySmall, color = Color.Gray)
            }

            Spacer(modifier = Modifier.height(8.dp))
            OutlinedButton(onClick = onCommand, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.Terminal, null, modifier = Modifier.size(16.dp))
                Spacer(modifier = Modifier.width(4.dp))
                Text("Send Command")
            }
        }
    }
}

@Composable
private fun CommandDialog(terminal: TerminalInfo, onDismiss: () -> Unit) {
    val commands = listOf(
        "reboot" to "Reboot Terminal",
        "lock" to "Lock Screen",
        "unlock" to "Unlock Screen",
        "wipe" to "Factory Reset",
        "diagnostics" to "Run Diagnostics",
        "screenshot" to "Capture Screenshot",
        "update_config" to "Update Config"
    )

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Send Command to ${terminal.serialNumber}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                commands.forEach { (cmd, label) ->
                    val isDestructive = cmd in listOf("wipe", "lock")
                    TextButton(
                        onClick = { /* send command via API */ onDismiss() },
                        modifier = Modifier.fillMaxWidth(),
                        colors = if (isDestructive) ButtonDefaults.textButtonColors(contentColor = Color(0xFFDC2626))
                        else ButtonDefaults.textButtonColors()
                    ) {
                        Text(label, modifier = Modifier.fillMaxWidth())
                    }
                }
            }
        },
        confirmButton = {},
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } }
    )
}

private data class TerminalInfo(
    val serialNumber: String,
    val model: String,
    val status: String,
    val batteryLevel: Int,
    val signalStrength: Int,
    val firmwareVersion: String,
    val lastSeen: String
)
