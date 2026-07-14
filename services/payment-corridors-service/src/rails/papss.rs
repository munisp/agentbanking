use crate::config::PapssConfig;

/// Returns true if both origin and destination countries are PAPSS members.
///
/// PAPSS enables intra-African payments in local currencies, removing the
/// need to convert through USD/EUR for African corridors. Both the sending
/// and receiving country must be PAPSS participants for this rail to apply.
pub fn should_use(origin: &str, destination: &str, config: &PapssConfig) -> bool {
    let is_member = |code: &str| {
        config
            .member_countries
            .iter()
            .any(|c| c.eq_ignore_ascii_case(code))
    };
    is_member(origin) && is_member(destination)
}

pub fn routing_reason(origin: &str, destination: &str) -> String {
    format!(
        "Both {} and {} are PAPSS member countries — routing via Pan-African Payment \
         and Settlement System to settle in local currency",
        origin, destination
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::PapssConfig;

    fn config() -> PapssConfig {
        PapssConfig {
            member_countries: vec!["NG".into(), "GH".into(), "KE".into(), "ZA".into()],
            settlement_ttl_s: 120,
        }
    }

    #[test]
    fn routes_intra_african() {
        assert!(should_use("NG", "GH", &config()));
    }

    #[test]
    fn routes_case_insensitive() {
        assert!(should_use("ng", "gh", &config()));
    }

    #[test]
    fn does_not_route_if_origin_outside_africa() {
        assert!(!should_use("CN", "NG", &config()));
    }

    #[test]
    fn does_not_route_if_dest_outside_africa() {
        assert!(!should_use("NG", "GB", &config()));
    }

    #[test]
    fn does_not_route_non_member() {
        assert!(!should_use("NG", "US", &config()));
    }
}