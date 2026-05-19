package com.pos54link.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SupportScreen(
    onNavigateBack: () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Help & Support") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .verticalScroll(rememberScrollState())
        ) {
            // Quick Actions
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                SupportAction(icon = Icons.Default.Chat, label = "Live Chat", onClick = { })
                SupportAction(icon = Icons.Default.Email, label = "Email Us", onClick = { })
                SupportAction(icon = Icons.Default.Phone, label = "Call Us", onClick = { })
            }

            HorizontalDivider()

            // FAQs
            Text(
                text = "Frequently Asked Questions",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(16.dp)
            )

            FAQItem(
                question = "How do I send money?",
                answer = "Go to Send Money, enter recipient details, amount, and confirm the transfer."
            )
            FAQItem(
                question = "What are the transfer limits?",
                answer = "Daily limit is NGN 5,000,000. You can increase this by completing KYC verification."
            )
            FAQItem(
                question = "How long do transfers take?",
                answer = "Domestic transfers are instant. International transfers take 1-3 business days."
            )
            FAQItem(
                question = "How do I verify my account?",
                answer = "Go to KYC Verification in your profile and follow the steps to upload your documents."
            )

            HorizontalDivider(modifier = Modifier.padding(vertical = 16.dp))

            // Contact Information
            Text(
                text = "Contact Information",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
            )

            ListItem(
                headlineContent = { Text("Email") },
                supportingContent = { Text("support@remittance.com") },
                leadingContent = { Icon(Icons.Default.Email, contentDescription = null) }
            )
            ListItem(
                headlineContent = { Text("Phone") },
                supportingContent = { Text("+234 800 123 4567") },
                leadingContent = { Icon(Icons.Default.Phone, contentDescription = null) }
            )
            ListItem(
                headlineContent = { Text("Hours") },
                supportingContent = { Text("24/7 Support Available") },
                leadingContent = { Icon(Icons.Default.Schedule, contentDescription = null) }
            )

            Spacer(modifier = Modifier.height(32.dp))
        }
    }
}

@Composable
private fun SupportAction(
    icon: ImageVector,
    label: String,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .size(100.dp)
            .clickable(onClick = onClick)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = icon,
                contentDescription = label,
                tint = MaterialTheme.colorScheme.primary
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall
            )
        }
    }
}

@Composable
private fun FAQItem(
    question: String,
    answer: String
) {
    var expanded by remember { mutableStateOf(false) }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp)
            .clickable { expanded = !expanded }
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = question,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.weight(1f)
                )
                Icon(
                    imageVector = if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = if (expanded) "Collapse" else "Expand"
                )
            }
            if (expanded) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = answer,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
