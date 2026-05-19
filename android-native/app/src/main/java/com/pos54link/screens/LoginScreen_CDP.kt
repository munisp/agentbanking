package com.pos54link.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.Email
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.pos54link.services.CDPAuthService
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun LoginScreen_CDP(
    cdpAuth: CDPAuthService,
    onLoginSuccess: () -> Unit
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    
    var email by remember { mutableStateOf("") }
    var otp by remember { mutableStateOf("") }
    var flowId by remember { mutableStateOf<String?>(null) }
    var showOTPField by remember { mutableStateOf(false) }
    var resendCooldown by remember { mutableStateOf(0) }
    
    val isLoading by cdpAuth.isLoading.collectAsState()
    val errorMessage by cdpAuth.errorMessage.collectAsState()
    
    // Cooldown timer
    LaunchedEffect(resendCooldown) {
        if (resendCooldown > 0) {
            delay(1000)
            resendCooldown--
        }
    }
    
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(
                        Color(0xFFE3F2FD),
                        Color(0xFFC5CAE9)
                    )
                )
            )
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Spacer(modifier = Modifier.height(60.dp))
            
            // Logo
            Box(
                modifier = Modifier
                    .size(80.dp)
                    .clip(CircleShape)
                    .background(
                        Brush.linearGradient(
                            colors = listOf(
                                Color(0xFF2196F3),
                                Color(0xFF3F51B5)
                            )
                        )
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Email,
                    contentDescription = "Email",
                    tint = Color.White,
                    modifier = Modifier.size(36.dp)
                )
            }
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // Title
            Text(
                text = "Welcome Back",
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF1A237E)
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                text = if (showOTPField) 
                    "Enter the code sent to your email" 
                else 
                    "Sign in with your email",
                fontSize = 16.sp,
                color = Color.Gray,
                textAlign = TextAlign.Center
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // Error Message
            errorMessage?.let { error ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 16.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = Color(0xFFFFEBEE)
                    )
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.Email, // Use error icon
                            contentDescription = "Error",
                            tint = Color(0xFFD32F2F)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = error,
                            fontSize = 14.sp,
                            color = Color(0xFFD32F2F)
                        )
                    }
                }
            }
            
            // Form Content
            if (!showOTPField) {
                EmailInputForm(
                    email = email,
                    onEmailChange = { email = it },
                    isLoading = isLoading,
                    onSendOTP = {
                        scope.launch {
                            cdpAuth.sendOTP(email).onSuccess {
                                flowId = it
                                showOTPField = true
                                resendCooldown = 60
                            }
                        }
                    }
                )
            } else {
                OTPVerificationForm(
                    email = email,
                    otp = otp,
                    onOTPChange = { if (it.length <= 6) otp = it },
                    isLoading = isLoading,
                    resendCooldown = resendCooldown,
                    onVerifyOTP = {
                        scope.launch {
                            flowId?.let { fid ->
                                cdpAuth.verifyOTP(fid, otp, email).onSuccess {
                                    onLoginSuccess()
                                }
                            }
                        }
                    },
                    onBack = {
                        showOTPField = false
                        otp = ""
                        flowId = null
                    },
                    onResendOTP = {
                        if (resendCooldown == 0) {
                            scope.launch {
                                cdpAuth.sendOTP(email).onSuccess {
                                    flowId = it
                                    resendCooldown = 60
                                    otp = ""
                                }
                            }
                        }
                    }
                )
            }
            
            Spacer(modifier = Modifier.height(32.dp))
            
            // Info Banner
            InfoBanner()
        }
    }
}

@Composable
private fun EmailInputForm(
    email: String,
    onEmailChange: (String) -> Unit,
    isLoading: Boolean,
    onSendOTP: () -> Unit
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        // Email Field
        Text(
            text = "Email Address",
            fontSize = 14.sp,
            fontWeight = FontWeight.Medium,
            color = Color.Gray,
            modifier = Modifier.padding(bottom = 8.dp)
        )
        
        OutlinedTextField(
            value = email,
            onValueChange = onEmailChange,
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("you@example.com") },
            leadingIcon = {
                Icon(
                    imageVector = Icons.Default.Email,
                    contentDescription = "Email"
                )
            },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            singleLine = true,
            shape = RoundedCornerShape(12.dp)
        )
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // Send Code Button
        Button(
            onClick = onSendOTP,
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp),
            enabled = !isLoading && email.isNotEmpty(),
            colors = ButtonDefaults.buttonColors(
                containerColor = Color(0xFF2196F3)
            ),
            shape = RoundedCornerShape(12.dp)
        ) {
            if (isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    color = Color.White,
                    strokeWidth = 2.dp
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text("Sending...")
            } else {
                Text("Send Code", fontSize = 16.sp)
                Spacer(modifier = Modifier.width(8.dp))
                Icon(
                    imageVector = Icons.Default.ArrowForward,
                    contentDescription = "Send"
                )
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Sign Up Link
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center
        ) {
            Text(
                text = "Don't have an account? ",
                fontSize = 14.sp,
                color = Color.Gray
            )
            TextButton(onClick = { /* Navigate to Register */ }) {
                Text(
                    text = "Sign up",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium
                )
            }
        }
    }
}

@Composable
private fun OTPVerificationForm(
    email: String,
    otp: String,
    onOTPChange: (String) -> Unit,
    isLoading: Boolean,
    resendCooldown: Int,
    onVerifyOTP: () -> Unit,
    onBack: () -> Unit,
    onResendOTP: () -> Unit
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        // OTP Field
        Text(
            text = "Verification Code",
            fontSize = 14.sp,
            fontWeight = FontWeight.Medium,
            color = Color.Gray,
            modifier = Modifier.padding(bottom = 8.dp)
        )
        
        OutlinedTextField(
            value = otp,
            onValueChange = { if (it.all { char -> char.isDigit() }) onOTPChange(it) },
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("000000", textAlign = TextAlign.Center) },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            singleLine = true,
            textStyle = LocalTextStyle.current.copy(
                fontSize = 24.sp,
                fontWeight = FontWeight.Medium,
                textAlign = TextAlign.Center
            ),
            shape = RoundedCornerShape(12.dp)
        )
        
        Spacer(modifier = Modifier.height(8.dp))
        
        Text(
            text = "Code sent to $email",
            fontSize = 12.sp,
            color = Color.Gray
        )
        
        Spacer(modifier = Modifier.height(24.dp))
        
        // Verify Button
        Button(
            onClick = onVerifyOTP,
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp),
            enabled = !isLoading && otp.length == 6,
            colors = ButtonDefaults.buttonColors(
                containerColor = Color(0xFF2196F3)
            ),
            shape = RoundedCornerShape(12.dp)
        ) {
            if (isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    color = Color.White,
                    strokeWidth = 2.dp
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text("Verifying...")
            } else {
                Text("Verify & Sign In", fontSize = 16.sp)
                Spacer(modifier = Modifier.width(8.dp))
                Icon(
                    imageVector = Icons.Default.ArrowForward,
                    contentDescription = "Verify"
                )
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Actions Row
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            TextButton(onClick = onBack) {
                Icon(
                    imageVector = Icons.Default.ArrowBack,
                    contentDescription = "Back",
                    modifier = Modifier.size(16.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text("Change email", fontSize = 14.sp)
            }
            
            TextButton(
                onClick = onResendOTP,
                enabled = resendCooldown == 0
            ) {
                Text(
                    text = if (resendCooldown > 0) 
                        "Resend in ${resendCooldown}s" 
                    else 
                        "Resend code",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium
                )
            }
        }
    }
}

@Composable
private fun InfoBanner() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = Color(0xFFE3F2FD)
        ),
        shape = RoundedCornerShape(12.dp)
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = Icons.Default.Email, // Use lock icon
                contentDescription = "Secure",
                tint = Color(0xFF2196F3)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Text(
                text = "Secure email authentication powered by Coinbase. Your wallet is created automatically.",
                fontSize = 12.sp,
                color = Color.Gray,
                lineHeight = 16.sp
            )
        }
    }
}
