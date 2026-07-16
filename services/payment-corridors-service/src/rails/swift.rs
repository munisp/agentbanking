/// SWIFT / correspondent banking is the universal fallback rail.
///
/// Used for all corridors not covered by CIPS or PAPSS:
/// - Cross-border USD, EUR, GBP payments
/// - Transactions involving non-PAPSS countries
/// - Any corridor where no specialised rail is available
pub fn routing_reason(origin: &str, destination: &str, currency: &str) -> String {
    format!(
        "No specialised rail available for {}->{} in {}. \
         Routing via SWIFT correspondent banking.",
        origin, destination, currency
    )
}