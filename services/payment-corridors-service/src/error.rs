use thiserror::Error;

#[derive(Debug, Error)]
pub enum CorridorError {
    #[error("invalid currency code: {0}")]
    InvalidCurrency(String),

    #[error("invalid country code: {0}")]
    InvalidCountry(String),

    #[error("invalid amount: {0}")]
    InvalidAmount(String),

    #[error("missing required field: {0}")]
    MissingField(String),

    #[error("configuration error: {0}")]
    Config(String),
}

impl From<CorridorError> for tonic::Status {
    fn from(e: CorridorError) -> Self {
        match e {
            CorridorError::InvalidCurrency(_)
            | CorridorError::InvalidCountry(_)
            | CorridorError::InvalidAmount(_)
            | CorridorError::MissingField(_) => tonic::Status::invalid_argument(e.to_string()),
            CorridorError::Config(_) => tonic::Status::internal(e.to_string()),
        }
    }
}