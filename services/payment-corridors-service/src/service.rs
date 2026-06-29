use tonic::{Request, Response, Status};
use tracing::{info, warn};

use crate::{
    config::SecurityConfig,
    router::{PaymentInstruction, Rail, RailSelector},
};

pub mod proto {
    tonic::include_proto!("paymentcorridor");
}

use proto::{
    corridor_service_server::CorridorService,
    HealthRequest, HealthResponse, Rail as ProtoRail, RouteRequest, RouteResponse,
};

pub struct CorridorHandler {
    selector: RailSelector,
}

pub fn api_key_interceptor(
    security: SecurityConfig,
) -> impl FnMut(Request<()>) -> Result<Request<()>, Status> {
    move |request: Request<()>| {
        if !security.enforce_api_key {
            return Ok(request);
        }

        if security.api_key.is_empty() {
            return Err(Status::internal(
                "security.enforce_api_key is true but security.api_key is empty",
            ));
        }

        let provided = request
            .metadata()
            .get("x-api-key")
            .and_then(|v| v.to_str().ok())
            .unwrap_or_default();

        if provided != security.api_key {
            return Err(Status::unauthenticated("invalid or missing x-api-key"));
        }

        Ok(request)
    }
}

impl CorridorHandler {
    pub fn new(selector: RailSelector) -> Self {
        Self { selector }
    }
}

#[tonic::async_trait]
impl CorridorService for CorridorHandler {
    async fn select_rail(
        &self,
        request: Request<RouteRequest>,
    ) -> Result<Response<RouteResponse>, Status> {
        let req = request.into_inner();

        let instruction = PaymentInstruction::from_raw(
            req.transaction_id.clone(),
            req.currency.clone(),
            req.origin_country.clone(),
            req.dest_country.clone(),
            req.origin_bank_bic,
            req.dest_bank_bic,
            &req.amount_minor,
            req.sender_id,
            req.beneficiary_id,
        )
        .map_err(|e| {
            warn!(transaction_id = %req.transaction_id, error = %e, "validation failed");
            Status::from(e)
        })?;

        let decision = self.selector.select(&instruction);

        info!(
            transaction_id = %instruction.transaction_id,
            rail = ?decision.rail,
            currency = %instruction.currency,
            origin = %instruction.origin_country,
            dest = %instruction.dest_country,
            ttl_s = decision.estimated_ttl_s,
            "rail selected"
        );

        metrics::counter!("corridor.routing.total", "rail" => format!("{:?}", decision.rail))
            .increment(1);

        let proto_rail = match decision.rail {
            Rail::Cips  => ProtoRail::Cips,
            Rail::Papss => ProtoRail::Papss,
            Rail::Swift => ProtoRail::Swift,
        };

        Ok(Response::new(RouteResponse {
            transaction_id:   instruction.transaction_id,
            selected_rail:    proto_rail.into(),
            reason:           decision.reason,
            estimated_ttl_s:  decision.estimated_ttl_s,
            routed_at:        decision.routed_at,
        }))
    }

    async fn health_check(
        &self,
        _request: Request<HealthRequest>,
    ) -> Result<Response<HealthResponse>, Status> {
        Ok(Response::new(HealthResponse {
            ok:      true,
            version: env!("CARGO_PKG_VERSION").into(),
        }))
    }
}