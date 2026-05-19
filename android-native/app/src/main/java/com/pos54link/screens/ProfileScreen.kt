package com.pos54link.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * ProfileScreen.kt
 * User profile screen with avatar, personal info, verification status
 * 
 * Features:
 * - User profile display with avatar
 * - Personal information (name, email, phone)
 * - KYC verification status badge
 * - Account tier information
 * - Edit profile functionality
 * - Logout option
 * 
 * Architecture: MVVM with Jetpack Compose
 */

// MARK: - Data Models

data class UserProfile(
    val id: String,
    val firstName: String,
    val lastName: String,
    val email: String,
    val phoneNumber: String,
    val avatarUrl: String? = null,
    val kycStatus: KYCStatus,
    val accountTier: AccountTier,
    val dateJoined: String,
    val totalTransactions: Int,
    val totalVolume: Double
)

enum class KYCStatus {
    NOT_STARTED,
    PENDING,
    VERIFIED,
    REJECTED
}

enum class AccountTier {
    BASIC,
    SILVER,
    GOLD,
    PLATINUM
}

// MARK: - ViewModel

class ProfileViewModel : ViewModel() {
    private val _uiState = MutableStateFlow<ProfileUiState>(ProfileUiState.Loading)
    val uiState: StateFlow<ProfileUiState> = _uiState.asStateFlow()
    
    init {
        loadProfile()
    }
    
    fun loadProfile() {
        viewModelScope.launch {
            _uiState.value = ProfileUiState.Loading
            try {
                // Simulate API call
                kotlinx.coroutines.delay(1000)
                
                val profile = UserProfile(
                    id = "user123",
                    firstName = "Adebayo",
                    lastName = "Okonkwo",
                    email = "adebayo.okonkwo@example.com",
                    phoneNumber = "+234 803 456 7890",
                    avatarUrl = null,
                    kycStatus = KYCStatus.VERIFIED,
                    accountTier = AccountTier.GOLD,
                    dateJoined = "January 2024",
                    totalTransactions = 127,
                    totalVolume = 2450000.00
                )
                
                _uiState.value = ProfileUiState.Success(profile)
            } catch (e: Exception) {
                _uiState.value = ProfileUiState.Error(e.message ?: "Failed to load profile")
            }
        }
    }
    
    fun logout() {
        viewModelScope.launch {
            // Implement logout logic
            // Clear tokens, navigate to login
        }
    }
}

sealed class ProfileUiState {
    object Loading : ProfileUiState()
    data class Success(val profile: UserProfile) : ProfileUiState()
    data class Error(val message: String) : ProfileUiState()
}

// MARK: - Composable Screen

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    viewModel: ProfileViewModel = androidx.lifecycle.viewmodel.compose.viewModel(),
    onEditProfile: () -> Unit = {},
    onNavigateToSettings: () -> Unit = {},
    onNavigateToKYC: () -> Unit = {},
    onLogout: () -> Unit = {}
) {
    val uiState by viewModel.uiState.collectAsState()
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Profile") },
                actions = {
                    IconButton(onClick = onNavigateToSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                }
            )
        }
    ) { paddingValues ->
        when (val state = uiState) {
            is ProfileUiState.Loading -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(paddingValues),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator()
                }
            }
            is ProfileUiState.Error -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(paddingValues),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = state.message,
                            color = MaterialTheme.colorScheme.error
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(onClick = { viewModel.loadProfile() }) {
                            Text("Retry")
                        }
                    }
                }
            }
            is ProfileUiState.Success -> {
                ProfileContent(
                    profile = state.profile,
                    onEditProfile = onEditProfile,
                    onNavigateToKYC = onNavigateToKYC,
                    onLogout = {
                        viewModel.logout()
                        onLogout()
                    },
                    modifier = Modifier.padding(paddingValues)
                )
            }
        }
    }
}

@Composable
private fun ProfileContent(
    profile: UserProfile,
    onEditProfile: () -> Unit,
    onNavigateToKYC: () -> Unit,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
    ) {
        // Profile Header
        ProfileHeader(profile = profile, onEditProfile = onEditProfile)
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // KYC Status Card
        KYCStatusCard(
            kycStatus = profile.kycStatus,
            onNavigateToKYC = onNavigateToKYC
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Account Tier Card
        AccountTierCard(accountTier = profile.accountTier)
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Statistics Card
        StatisticsCard(
            totalTransactions = profile.totalTransactions,
            totalVolume = profile.totalVolume
        )
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // Personal Information
        PersonalInformationSection(profile = profile)
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // Logout Button
        Button(
            onClick = onLogout,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.error
            )
        ) {
            Icon(Icons.Default.ExitToApp, contentDescription = null)
            Spacer(modifier = Modifier.width(8.dp))
            Text("Logout")
        }
        
        Spacer(modifier = Modifier.height(32.dp))
    }
}

@Composable
private fun ProfileHeader(
    profile: UserProfile,
    onEditProfile: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.primaryContainer)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Avatar
        Box(
            modifier = Modifier
                .size(100.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.primary),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = "${profile.firstName.first()}${profile.lastName.first()}",
                style = MaterialTheme.typography.headlineMedium,
                color = MaterialTheme.colorScheme.onPrimary,
                fontWeight = FontWeight.Bold
            )
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Name
        Text(
            text = "${profile.firstName} ${profile.lastName}",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold
        )
        
        Spacer(modifier = Modifier.height(8.dp))
        
        // Member since
        Text(
            text = "Member since ${profile.dateJoined}",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Edit Profile Button
        OutlinedButton(onClick = onEditProfile) {
            Icon(Icons.Default.Edit, contentDescription = null)
            Spacer(modifier = Modifier.width(8.dp))
            Text("Edit Profile")
        }
    }
}

@Composable
private fun KYCStatusCard(
    kycStatus: KYCStatus,
    onNavigateToKYC: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "KYC Verification",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(4.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = when (kycStatus) {
                            KYCStatus.VERIFIED -> Icons.Default.CheckCircle
                            KYCStatus.PENDING -> Icons.Default.Info
                            KYCStatus.REJECTED -> Icons.Default.Warning
                            KYCStatus.NOT_STARTED -> Icons.Default.Info
                        },
                        contentDescription = null,
                        tint = when (kycStatus) {
                            KYCStatus.VERIFIED -> Color(0xFF4CAF50)
                            KYCStatus.PENDING -> Color(0xFFFFA726)
                            KYCStatus.REJECTED -> Color(0xFFF44336)
                            KYCStatus.NOT_STARTED -> Color.Gray
                        },
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = when (kycStatus) {
                            KYCStatus.VERIFIED -> "Verified"
                            KYCStatus.PENDING -> "Pending Review"
                            KYCStatus.REJECTED -> "Rejected"
                            KYCStatus.NOT_STARTED -> "Not Started"
                        },
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }
            
            if (kycStatus != KYCStatus.VERIFIED) {
                TextButton(onClick = onNavigateToKYC) {
                    Text("Complete KYC")
                }
            }
        }
    }
}

@Composable
private fun AccountTierCard(accountTier: AccountTier) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = Icons.Default.Star,
                contentDescription = null,
                tint = when (accountTier) {
                    AccountTier.PLATINUM -> Color(0xFFE5E4E2)
                    AccountTier.GOLD -> Color(0xFFFFD700)
                    AccountTier.SILVER -> Color(0xFFC0C0C0)
                    AccountTier.BASIC -> Color.Gray
                },
                modifier = Modifier.size(40.dp)
            )
            Spacer(modifier = Modifier.width(16.dp))
            Column {
                Text(
                    text = "Account Tier",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(
                    text = accountTier.name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
private fun StatisticsCard(
    totalTransactions: Int,
    totalVolume: Double
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceEvenly
        ) {
            StatItem(
                label = "Total Transactions",
                value = totalTransactions.toString()
            )
            Divider(
                modifier = Modifier
                    .height(50.dp)
                    .width(1.dp)
            )
            StatItem(
                label = "Total Volume",
                value = "₦${String.format("%,.0f", totalVolume)}"
            )
        }
    }
}

@Composable
private fun StatItem(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value,
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold
        )
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun PersonalInformationSection(profile: UserProfile) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp)
    ) {
        Text(
            text = "Personal Information",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold
        )
        Spacer(modifier = Modifier.height(16.dp))
        
        InfoItem(
            icon = Icons.Default.Email,
            label = "Email",
            value = profile.email
        )
        Spacer(modifier = Modifier.height(12.dp))
        
        InfoItem(
            icon = Icons.Default.Phone,
            label = "Phone Number",
            value = profile.phoneNumber
        )
        Spacer(modifier = Modifier.height(12.dp))
        
        InfoItem(
            icon = Icons.Default.Person,
            label = "User ID",
            value = profile.id
        )
    }
}

@Composable
private fun InfoItem(
    icon: ImageVector,
    label: String,
    value: String
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(24.dp)
        )
        Spacer(modifier = Modifier.width(16.dp))
        Column {
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                text = value,
                style = MaterialTheme.typography.bodyLarge
            )
        }
    }
}
