package com.pos54link.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

data class Beneficiary(
    val id: String,
    val name: String,
    val email: String,
    val country: String,
    val bank: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BeneficiariesScreen() {
    val beneficiaries = remember {
        listOf(
            Beneficiary("1", "John Doe", "john@example.com", "Nigeria", "GTBank"),
            Beneficiary("2", "Jane Smith", "jane@example.com", "Ghana", "GCB Bank"),
            Beneficiary("3", "Bob Johnson", "bob@example.com", "Kenya", "KCB"),
            Beneficiary("4", "Alice Williams", "alice@example.com", "Nigeria", "Access Bank"),
            Beneficiary("5", "Charlie Brown", "charlie@example.com", "South Africa", "Standard Bank")
        )
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Beneficiaries") },
                actions = {
                    IconButton(onClick = { }) {
                        Icon(Icons.Default.Add, "Add Beneficiary")
                    }
                }
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { }) {
                Icon(Icons.Default.Add, "Add New Beneficiary")
            }
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            items(beneficiaries) { beneficiary ->
                BeneficiaryCard(beneficiary = beneficiary)
            }
        }
    }
}

@Composable
fun BeneficiaryCard(beneficiary: Beneficiary) {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.weight(1f)
            ) {
                // Avatar
                Box(
                    modifier = Modifier
                        .size(48.dp)
                        .background(
                            color = MaterialTheme.colorScheme.primaryContainer,
                            shape = CircleShape
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        Icons.Default.Person,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.onPrimaryContainer
                    )
                }
                
                // Beneficiary Info
                Column {
                    Text(
                        text = beneficiary.name,
                        style = MaterialTheme.typography.titleMedium
                    )
                    Text(
                        text = beneficiary.email,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.padding(top = 4.dp)
                    ) {
                        Text(
                            text = beneficiary.country,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = "•",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = beneficiary.bank,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
            
            // Actions
            Row(
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                IconButton(onClick = { }) {
                    Icon(
                        Icons.Default.Edit,
                        contentDescription = "Edit",
                        tint = MaterialTheme.colorScheme.primary
                    )
                }
                IconButton(onClick = { }) {
                    Icon(
                        Icons.Default.Delete,
                        contentDescription = "Delete",
                        tint = MaterialTheme.colorScheme.error
                    )
                }
            }
        }
    }
}
