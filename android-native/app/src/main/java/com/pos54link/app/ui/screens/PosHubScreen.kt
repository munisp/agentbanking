package com.pos54link.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

data class PosMenuItem(
    val title: String,
    val description: String,
    val icon: ImageVector,
    val route: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PosHubScreen(
    onNavigate: (String) -> Unit,
    onBack: () -> Unit
) {
    val menuItems = listOf(
        PosMenuItem("Terminal Fleet", "Manage POS terminals", Icons.Default.Devices, "pos_fleet"),
        PosMenuItem("Settlement", "Batch settlements", Icons.Default.AccountBalance, "pos_settlement"),
        PosMenuItem("Disputes", "File & track disputes", Icons.Default.Report, "pos_disputes"),
        PosMenuItem("Voice Command", "Voice-guided transactions", Icons.Default.Mic, "pos_voice"),
        PosMenuItem("Leasing", "Terminal leases", Icons.Default.Assignment, "pos_leasing"),
        PosMenuItem("Firmware", "OTA updates", Icons.Default.SystemUpdate, "pos_firmware"),
        PosMenuItem("IoT Health", "Device sensors & alerts", Icons.Default.Sensors, "pos_iot"),
        PosMenuItem("Receipt Printer", "Print receipts", Icons.Default.Print, "pos_receipt")
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("POS Management") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { padding ->
        LazyVerticalGrid(
            columns = GridCells.Fixed(2),
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            items(menuItems) { item ->
                PosMenuCard(item = item, onClick = { onNavigate(item.route) })
            }
        }
    }
}

@Composable
fun PosMenuCard(item: PosMenuItem, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(140.dp)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(12.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = item.icon,
                contentDescription = item.title,
                modifier = Modifier.size(36.dp),
                tint = MaterialTheme.colorScheme.primary
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = item.title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = item.description,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )
        }
    }
}
