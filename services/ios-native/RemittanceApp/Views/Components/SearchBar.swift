import SwiftUI
import Combine

/// OpenSearch-integrated SearchBar component for iOS
/// Features: autocomplete, suggestions, recent searches, debouncing
struct SearchBarView: View {
    @Binding var text: String
    let placeholder: String
    let index: SearchIndex?
    let onSearch: (String) -> Void
    
    @State private var isExpanded = false
    @State private var suggestions: [SearchSuggestion] = []
    @State private var recentSearches: [RecentSearch] = []
    @State private var isLoading = false
    @State private var debounceTask: Task<Void, Never>?
    
    @FocusState private var isFocused: Bool
    
    private let searchService = SearchService.shared
    private let debounceMs: UInt64 = 300_000_000 // 300ms in nanoseconds
    
    init(
        text: Binding<String>,
        placeholder: String = "Search...",
        index: SearchIndex? = nil,
        onSearch: @escaping (String) -> Void
    ) {
        self._text = text
        self.placeholder = placeholder
        self.index = index
        self.onSearch = onSearch
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Search Input Field
            HStack(spacing: 12) {
                Image(systemName: "magnifyingglass")
                    .foregroundColor(.secondary)
                    .font(.system(size: 16, weight: .medium))
                
                TextField(placeholder, text: $text)
                    .textFieldStyle(.plain)
                    .focused($isFocused)
                    .submitLabel(.search)
                    .onSubmit {
                        performSearch()
                    }
                    .onChange(of: text) { newValue in
                        handleTextChange(newValue)
                    }
                
                if isLoading {
                    ProgressView()
                        .scaleEffect(0.8)
                } else if !text.isEmpty {
                    Button(action: clearSearch) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.secondary)
                            .font(.system(size: 16))
                    }
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(Color(.systemGray6))
            .cornerRadius(12)
            
            // Dropdown for suggestions and recent searches
            if isExpanded && (suggestions.count > 0 || (recentSearches.count > 0 && text.isEmpty)) {
                VStack(spacing: 0) {
                    if text.isEmpty && recentSearches.count > 0 {
                        // Recent Searches Section
                        VStack(alignment: .leading, spacing: 0) {
                            HStack {
                                Text("Recent Searches")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                Spacer()
                                Button("Clear") {
                                    Task {
                                        try? await searchService.clearRecentSearches()
                                        recentSearches = []
                                    }
                                }
                                .font(.caption)
                                .foregroundColor(.blue)
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            
                            ForEach(recentSearches.prefix(5)) { search in
                                RecentSearchRow(search: search) {
                                    text = search.query
                                    performSearch()
                                }
                            }
                        }
                    } else if suggestions.count > 0 {
                        // Suggestions Section
                        ForEach(suggestions) { suggestion in
                            SuggestionRow(suggestion: suggestion, query: text) {
                                text = suggestion.text
                                performSearch()
                            }
                        }
                    }
                }
                .background(Color(.systemBackground))
                .cornerRadius(12)
                .shadow(color: Color.black.opacity(0.1), radius: 8, x: 0, y: 4)
                .padding(.top, 4)
            }
        }
        .onChange(of: isFocused) { focused in
            withAnimation(.easeInOut(duration: 0.2)) {
                isExpanded = focused
            }
            if focused && text.isEmpty {
                loadRecentSearches()
            }
        }
    }
    
    private func handleTextChange(_ newValue: String) {
        debounceTask?.cancel()
        
        if newValue.count >= 2 {
            debounceTask = Task {
                try? await Task.sleep(nanoseconds: debounceMs)
                if !Task.isCancelled {
                    await fetchSuggestions(for: newValue)
                }
            }
        } else {
            suggestions = []
        }
    }
    
    private func fetchSuggestions(for query: String) async {
        isLoading = true
        do {
            suggestions = try await searchService.getSuggestions(query: query, index: index)
        } catch {
            suggestions = []
        }
        isLoading = false
    }
    
    private func loadRecentSearches() {
        Task {
            do {
                recentSearches = try await searchService.getRecentSearches()
            } catch {
                recentSearches = []
            }
        }
    }
    
    private func performSearch() {
        guard !text.isEmpty else { return }
        
        Task {
            try? await searchService.saveRecentSearch(query: text, index: index)
        }
        
        onSearch(text)
        isFocused = false
        isExpanded = false
    }
    
    private func clearSearch() {
        text = ""
        suggestions = []
        onSearch("")
    }
}

// MARK: - Suggestion Row
struct SuggestionRow: View {
    let suggestion: SearchSuggestion
    let query: String
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                Image(systemName: "magnifyingglass")
                    .foregroundColor(.secondary)
                    .font(.system(size: 14))
                
                highlightedText
                    .font(.body)
                
                Spacer()
                
                Text(suggestion.index)
                    .font(.caption)
                    .foregroundColor(.blue)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.blue.opacity(0.1))
                    .cornerRadius(4)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
    
    private var highlightedText: Text {
        let text = suggestion.text
        let query = query.lowercased()
        
        guard let range = text.lowercased().range(of: query) else {
            return Text(text)
        }
        
        let before = String(text[..<range.lowerBound])
        let match = String(text[range])
        let after = String(text[range.upperBound...])
        
        return Text(before) + Text(match).bold().foregroundColor(.blue) + Text(after)
    }
}

// MARK: - Recent Search Row
struct RecentSearchRow: View {
    let search: RecentSearch
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                Image(systemName: "clock.arrow.circlepath")
                    .foregroundColor(.secondary)
                    .font(.system(size: 14))
                
                Text(search.query)
                    .font(.body)
                    .foregroundColor(.primary)
                
                Spacer()
                
                if let index = search.index {
                    Text(index)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Search View Model
@MainActor
class SearchViewModel<T: Codable>: ObservableObject {
    @Published var query = ""
    @Published var results: [SearchHit<T>] = []
    @Published var isLoading = false
    @Published var error: Error?
    @Published var total = 0
    @Published var page = 1
    
    private let searchService = SearchService.shared
    private let index: SearchIndex
    private let pageSize = 20
    
    init(index: SearchIndex) {
        self.index = index
    }
    
    func search() async {
        guard !query.isEmpty else {
            results = []
            total = 0
            return
        }
        
        isLoading = true
        error = nil
        
        do {
            let response: SearchResponse<T> = try await searchService.search(
                query: SearchQuery(
                    query: query,
                    index: [index],
                    pagination: SearchPagination(page: page, size: pageSize)
                )
            )
            results = response.hits
            total = response.total
        } catch {
            self.error = error
            results = []
        }
        
        isLoading = false
    }
    
    func loadMore() async {
        guard results.count < total else { return }
        page += 1
        await search()
    }
    
    func reset() {
        query = ""
        results = []
        total = 0
        page = 1
        error = nil
    }
}

// MARK: - Transaction Search View Model
@MainActor
class TransactionSearchViewModel: ObservableObject {
    @Published var query = ""
    @Published var results: [TransactionSearchResult] = []
    @Published var isLoading = false
    @Published var error: Error?
    @Published var total = 0
    @Published var page = 1
    @Published var filters: [String: String] = [:]
    
    private let searchService = SearchService.shared
    private let pageSize = 20
    
    func search() async {
        isLoading = true
        error = nil
        
        do {
            let response = try await searchService.searchTransactions(
                query: query.isEmpty ? "*" : query,
                filters: filters.isEmpty ? nil : filters,
                pagination: SearchPagination(page: page, size: pageSize)
            )
            results = response.hits.map { $0.source }
            total = response.total
        } catch {
            self.error = error
            // Fallback to empty results on error
            results = []
        }
        
        isLoading = false
    }
    
    func setFilter(key: String, value: String?) {
        if let value = value {
            filters[key] = value
        } else {
            filters.removeValue(forKey: key)
        }
    }
}

// MARK: - Beneficiary Search View Model
@MainActor
class BeneficiarySearchViewModel: ObservableObject {
    @Published var query = ""
    @Published var results: [BeneficiarySearchResult] = []
    @Published var isLoading = false
    @Published var error: Error?
    @Published var total = 0
    @Published var page = 1
    
    private let searchService = SearchService.shared
    private let pageSize = 20
    
    func search() async {
        isLoading = true
        error = nil
        
        do {
            let response = try await searchService.searchBeneficiaries(
                query: query.isEmpty ? "*" : query,
                pagination: SearchPagination(page: page, size: pageSize)
            )
            results = response.hits.map { $0.source }
            total = response.total
        } catch {
            self.error = error
            results = []
        }
        
        isLoading = false
    }
}

// MARK: - Preview
struct SearchBarView_Previews: PreviewProvider {
    static var previews: some View {
        VStack {
            SearchBarView(
                text: .constant(""),
                placeholder: "Search transactions...",
                index: .transactions
            ) { query in
                print("Searching for: \(query)")
            }
            .padding()
            
            Spacer()
        }
    }
}
