package com.pos54link.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay

data class SavingsGoal(
    val goalId: String,
    val name: String,
    val category: String,
    val categoryIcon: String,
    val targetAmount: Double,
    val currentAmount: Double,
    val stablecoin: String,
    val progressPercent: Int,
    val status: String,
    val hasAutoConvert: Boolean,
    val autoConvertPercent: Int
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SavingsGoalsScreen(
    onNavigateBack: () -> Unit
) {
    var goals by remember { mutableStateOf<List<SavingsGoal>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var totalSaved by remember { mutableStateOf(0.0) }

    LaunchedEffect(Unit) {
        delay(500)
        goals = listOf(
            SavingsGoal("goal-001", "School Fees 2025", "EDUCATION", "🎓", 500.0, 325.0, "USDT", 65, "ACTIVE", true, 20),
            SavingsGoal("goal-002", "Emergency Fund", "EMERGENCY", "🚨", 1000.0, 450.0, "USDC", 45, "ACTIVE", false, 0),
            SavingsGoal("goal-003", "Lagos Trip", "TRAVEL", "✈️", 200.0, 200.0, "USDT", 100, "COMPLETED", false, 0)
        )
        totalSaved = goals.sumOf { it.currentAmount }
        loading = false
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Savings Goals") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { }) {
                        Icon(Icons.Default.Add, contentDescription = "New Goal")
                    }
                }
            )
        }
    ) { padding ->
        if (loading) {
            Box(modifier = Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                item {
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        StatCard(
                            modifier = Modifier.weight(1f),
                            title = "Total Saved",
                            value = "$${String.format("%,.0f", totalSaved)}",
                            color = Color(0xFF2196F3)
                        )
                        StatCard(
                            modifier = Modifier.weight(1f),
                            title = "Active Goals",
                            value = "${goals.count { it.status == "ACTIVE" }}",
                            color = Color(0xFF4CAF50)
                        )
                    }
                }

                item {
                    Text("Active Goals", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                }

                items(goals.filter { it.status == "ACTIVE" }) { goal ->
                    GoalCard(goal)
                }

                if (goals.any { it.status == "COMPLETED" }) {
                    item {
                        Text("Completed Goals", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    }
                    items(goals.filter { it.status == "COMPLETED" }) { goal ->
                        GoalCard(goal)
                    }
                }
            }
        }
    }
}

@Composable
private fun StatCard(modifier: Modifier, title: String, value: String, color: Color) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = color)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, color = Color.White.copy(alpha = 0.8f), fontSize = 12.sp)
            Text(value, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 20.sp)
        }
    }
}

@Composable
private fun GoalCard(goal: SavingsGoal) {
    val categoryColor = when (goal.category) {
        "EDUCATION" -> Color(0xFF2196F3)
        "EMERGENCY" -> Color(0xFFF44336)
        "TRAVEL" -> Color(0xFF9C27B0)
        "HOUSING" -> Color(0xFF4CAF50)
        else -> Color.Gray
    }

    Card(modifier = Modifier.fillMaxWidth().clickable { }) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(40.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(categoryColor),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(goal.categoryIcon, fontSize = 20.sp)
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(goal.name, fontWeight = FontWeight.Bold)
                        Text(goal.category.lowercase().replaceFirstChar { it.uppercase() }, 
                            fontSize = 12.sp, color = Color.Gray)
                    }
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("$${String.format("%,.0f", goal.currentAmount)} ${goal.stablecoin}", fontWeight = FontWeight.Bold)
                    Text("of $${String.format("%,.0f", goal.targetAmount)}", fontSize = 12.sp, color = Color.Gray)
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text("${goal.progressPercent}% complete", fontSize = 12.sp, color = Color.Gray)
            }
            Spacer(modifier = Modifier.height(4.dp))
            LinearProgressIndicator(
                progress = goal.progressPercent / 100f,
                modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp)),
                color = categoryColor
            )

            if (goal.hasAutoConvert) {
                Spacer(modifier = Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("🔄", fontSize = 14.sp)
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        "Auto-converting ${goal.autoConvertPercent}% of incoming remittances",
                        fontSize = 12.sp,
                        color = Color(0xFF4CAF50)
                    )
                }
            }
        }
    }
}
