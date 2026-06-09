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
 * Firmware Update Screen
 *
 * Maps to backend: posFirmwareOTA.ts
 * Features:
 *   - View current firmware version vs latest available
 *   - Staged canary rollout progress (5% → 25% → 50% → 100%)
 *   - Rollback capability with reason
 *   - Update history with version, checksum, status
 *   - Auto-rollback indicator when failure rate exceeds threshold
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FirmwareUpdateScreen(onBack: () -> Unit) {
    val currentVersion = "4.2.1"
    val latestVersion = "4.3.0"
    val updateAvailable = currentVersion != latestVersion

    val rolloutStages = listOf(
        RolloutStage(5, 30, "completed", 0.2),
        RolloutStage(25, 60, "completed", 0.8),
        RolloutStage(50, 120, "in_progress", 1.5),
        RolloutStage(100, 0, "pending", 0.0),
    )

    val updateHistory = listOf(
        FirmwareVersion("4.2.1", "stable", "2026-05-10", "a3b2c1d4e5f6..."),
        FirmwareVersion("4.2.0", "stable", "2026-04-20", "f6e5d4c3b2a1..."),
        FirmwareVersion("4.1.0", "stable", "2026-03-15", "1a2b3c4d5e6f..."),
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Firmware Updates") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier.padding(padding).fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Current version card
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Current Firmware", style = MaterialTheme.typography.labelLarge, color = Color.Gray)
                        Text("v$currentVersion", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                        if (updateAvailable) {
                            Spacer(modifier = Modifier.height(8.dp))
                            Card(
                                colors = CardDefaults.cardColors(containerColor = Color(0xFFEFF6FF))
                            ) {
                                Row(
                                    modifier = Modifier.padding(12.dp),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(Icons.Default.SystemUpdate, null, tint = Color(0xFF2563EB))
                                    Column {
                                        Text("v$latestVersion available", fontWeight = FontWeight.Bold, color = Color(0xFF2563EB))
                                        Text("Staged rollout in progress", style = MaterialTheme.typography.bodySmall)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Canary rollout progress
            if (updateAvailable) {
                item {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text("Canary Rollout Progress", fontWeight = FontWeight.Bold)
                            Text("Max failure rate: 5%", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                            Spacer(modifier = Modifier.height(12.dp))

                            rolloutStages.forEach { stage ->
                                Row(
                                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    val icon = when (stage.status) {
                                        "completed" -> Icons.Default.CheckCircle
                                        "in_progress" -> Icons.Default.Pending
                                        else -> Icons.Default.Circle
                                    }
                                    val color = when (stage.status) {
                                        "completed" -> Color(0xFF16A34A)
                                        "in_progress" -> Color(0xFF3B82F6)
                                        else -> Color.Gray
                                    }
                                    Icon(icon, null, tint = color, modifier = Modifier.size(20.dp))
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text("${stage.percentage}%", modifier = Modifier.width(40.dp), fontWeight = FontWeight.Medium)
                                    LinearProgressIndicator(
                                        progress = {
                                            when (stage.status) {
                                                "completed" -> 1f
                                                "in_progress" -> 0.6f
                                                else -> 0f
                                            }
                                        },
                                        modifier = Modifier.weight(1f).height(6.dp),
                                        color = color,
                                        trackColor = Color(0xFFE5E7EB)
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        "Fail: ${stage.failureRate}%",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = if (stage.failureRate > 5) Color(0xFFDC2626) else Color.Gray
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.height(12.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(
                                    onClick = { /* advanceRollout */ },
                                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF16A34A))
                                ) { Text("Advance Stage") }
                                OutlinedButton(
                                    onClick = { /* rollbackRollout */ },
                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFFDC2626))
                                ) { Text("Rollback") }
                            }
                        }
                    }
                }
            }

            // Update history
            item {
                Text("Update History", fontWeight = FontWeight.Bold, modifier = Modifier.padding(vertical = 8.dp))
            }
            items(updateHistory) { version ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier.padding(16.dp).fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text("v${version.version}", fontWeight = FontWeight.Bold)
                            Text(version.date, style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                            Text(
                                "SHA: ${version.checksum}",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color.Gray
                            )
                        }
                        Surface(
                            color = Color(0xFF16A34A).copy(alpha = 0.1f),
                            shape = MaterialTheme.shapes.small
                        ) {
                            Text(
                                version.status.uppercase(),
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                color = Color(0xFF16A34A),
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }
        }
    }
}

private data class RolloutStage(
    val percentage: Int,
    val waitMinutes: Int,
    val status: String,
    val failureRate: Double
)

private data class FirmwareVersion(
    val version: String,
    val status: String,
    val date: String,
    val checksum: String
)
