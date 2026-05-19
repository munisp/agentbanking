package com.pos54link.app.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.pos54link.app.data.remote.RecentSearch
import com.pos54link.app.data.remote.SearchIndex
import com.pos54link.app.data.remote.SearchSuggestion
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * OpenSearch-integrated SearchBar component for Android
 * Features: autocomplete, suggestions, recent searches, debouncing
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchBar(
    modifier: Modifier = Modifier,
    placeholder: String = "Search...",
    index: SearchIndex? = null,
    onSearch: (String) -> Unit,
    onSuggestionsFetch: suspend (String) -> List<SearchSuggestion> = { emptyList() },
    onRecentSearchesFetch: suspend () -> List<RecentSearch> = { emptyList() },
    onSaveRecentSearch: suspend (String) -> Unit = {},
    debounceMs: Long = 300L,
    showSuggestions: Boolean = true,
    showRecentSearches: Boolean = true
) {
    var query by remember { mutableStateOf("") }
    var isExpanded by remember { mutableStateOf(false) }
    var suggestions by remember { mutableStateOf<List<SearchSuggestion>>(emptyList()) }
    var recentSearches by remember { mutableStateOf<List<RecentSearch>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    
    val focusRequester = remember { FocusRequester() }
    val focusManager = LocalFocusManager.current
    val scope = rememberCoroutineScope()
    var debounceJob by remember { mutableStateOf<Job?>(null) }

    // Load recent searches when focused
    LaunchedEffect(isExpanded) {
        if (isExpanded && showRecentSearches && query.isEmpty()) {
            recentSearches = onRecentSearchesFetch()
        }
    }

    // Debounced suggestions fetch
    LaunchedEffect(query) {
        if (query.length >= 2 && showSuggestions) {
            debounceJob?.cancel()
            debounceJob = scope.launch {
                delay(debounceMs)
                isLoading = true
                suggestions = onSuggestionsFetch(query)
                isLoading = false
            }
        } else {
            suggestions = emptyList()
        }
    }

    Column(modifier = modifier) {
        // Search Input Field
        OutlinedTextField(
            value = query,
            onValueChange = { newValue ->
                query = newValue
                if (newValue.isEmpty()) {
                    suggestions = emptyList()
                }
            },
            modifier = Modifier
                .fillMaxWidth()
                .focusRequester(focusRequester)
                .onFocusChanged { focusState ->
                    isExpanded = focusState.isFocused
                },
            placeholder = { Text(placeholder) },
            leadingIcon = {
                Icon(
                    imageVector = Icons.Default.Search,
                    contentDescription = "Search",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
            },
            trailingIcon = {
                if (query.isNotEmpty()) {
                    IconButton(onClick = {
                        query = ""
                        suggestions = emptyList()
                        onSearch("")
                    }) {
                        Icon(
                            imageVector = Icons.Default.Clear,
                            contentDescription = "Clear",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                } else if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        strokeWidth = 2.dp
                    )
                }
            },
            keyboardOptions = KeyboardOptions(
                imeAction = ImeAction.Search
            ),
            keyboardActions = KeyboardActions(
                onSearch = {
                    if (query.isNotEmpty()) {
                        scope.launch {
                            onSaveRecentSearch(query)
                        }
                        onSearch(query)
                        focusManager.clearFocus()
                        isExpanded = false
                    }
                }
            ),
            singleLine = true,
            shape = RoundedCornerShape(12.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = MaterialTheme.colorScheme.primary,
                unfocusedBorderColor = MaterialTheme.colorScheme.outline
            )
        )

        // Dropdown for suggestions and recent searches
        AnimatedVisibility(
            visible = isExpanded && (suggestions.isNotEmpty() || (recentSearches.isNotEmpty() && query.isEmpty())),
            enter = fadeIn(),
            exit = fadeOut()
        ) {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp),
                shape = RoundedCornerShape(12.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
            ) {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 300.dp)
                ) {
                    // Show suggestions if query is not empty
                    if (query.isNotEmpty() && suggestions.isNotEmpty()) {
                        items(suggestions) { suggestion ->
                            SuggestionItem(
                                suggestion = suggestion,
                                query = query,
                                onClick = {
                                    query = suggestion.text
                                    scope.launch {
                                        onSaveRecentSearch(suggestion.text)
                                    }
                                    onSearch(suggestion.text)
                                    focusManager.clearFocus()
                                    isExpanded = false
                                }
                            )
                        }
                    }
                    
                    // Show recent searches if query is empty
                    if (query.isEmpty() && recentSearches.isNotEmpty()) {
                        item {
                            Text(
                                text = "Recent Searches",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                            )
                        }
                        items(recentSearches.take(5)) { recentSearch ->
                            RecentSearchItem(
                                recentSearch = recentSearch,
                                onClick = {
                                    query = recentSearch.query
                                    onSearch(recentSearch.query)
                                    focusManager.clearFocus()
                                    isExpanded = false
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SuggestionItem(
    suggestion: SearchSuggestion,
    query: String,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = Icons.Default.Search,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.size(20.dp)
        )
        Spacer(modifier = Modifier.width(12.dp))
        Text(
            text = highlightMatch(suggestion.text, query),
            style = MaterialTheme.typography.bodyMedium
        )
        Spacer(modifier = Modifier.weight(1f))
        Text(
            text = suggestion.index,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.primary
        )
    }
}

@Composable
private fun RecentSearchItem(
    recentSearch: RecentSearch,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = Icons.Default.History,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.size(20.dp)
        )
        Spacer(modifier = Modifier.width(12.dp))
        Text(
            text = recentSearch.query,
            style = MaterialTheme.typography.bodyMedium
        )
        recentSearch.index?.let { index ->
            Spacer(modifier = Modifier.weight(1f))
            Text(
                text = index,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun highlightMatch(text: String, query: String) = buildAnnotatedString {
    val lowerText = text.lowercase()
    val lowerQuery = query.lowercase()
    var startIndex = 0
    
    while (true) {
        val matchIndex = lowerText.indexOf(lowerQuery, startIndex)
        if (matchIndex == -1) {
            append(text.substring(startIndex))
            break
        }
        
        // Append text before match
        append(text.substring(startIndex, matchIndex))
        
        // Append highlighted match
        withStyle(SpanStyle(fontWeight = FontWeight.Bold, color = Color(0xFF1976D2))) {
            append(text.substring(matchIndex, matchIndex + query.length))
        }
        
        startIndex = matchIndex + query.length
    }
}
