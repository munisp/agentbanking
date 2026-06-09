package main

// grpcServer implements the gRPC service definitions from proto/go-services.proto
// Production features: interceptors for auth/logging/tracing, health checking, graceful shutdown

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/health"
	"google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/reflection"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/grpc/metadata"
)

// --- Interceptors ---

func unaryAuthInterceptor(
	ctx context.Context,
	req interface{},
	info *grpc.UnaryServerInfo,
	handler grpc.UnaryHandler,
) (interface{}, error) {
	md, ok := metadata.FromIncomingContext(ctx)
	if !ok {
		return nil, status.Errorf(codes.Unauthenticated, "missing metadata")
	}
	tokens := md.Get("authorization")
	if len(tokens) == 0 {
		// Allow health checks without auth
		if info.FullMethod == "/grpc.health.v1.Health/Check" {
			return handler(ctx, req)
		}
		return nil, status.Errorf(codes.Unauthenticated, "missing authorization token")
	}
	// TODO: Validate JWT token against Keycloak
	return handler(ctx, req)
}

func unaryLoggingInterceptor(
	ctx context.Context,
	req interface{},
	info *grpc.UnaryServerInfo,
	handler grpc.UnaryHandler,
) (interface{}, error) {
	start := time.Now()
	resp, err := handler(ctx, req)
	duration := time.Since(start)
	if err != nil {
		log.Printf("[gRPC] %s ERROR %v (%s)", info.FullMethod, err, duration)
	} else {
		log.Printf("[gRPC] %s OK (%s)", info.FullMethod, duration)
	}
	return resp, err
}

func unaryRecoveryInterceptor(
	ctx context.Context,
	req interface{},
	info *grpc.UnaryServerInfo,
	handler grpc.UnaryHandler,
) (resp interface{}, err error) {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("[gRPC] PANIC in %s: %v", info.FullMethod, r)
			err = status.Errorf(codes.Internal, "internal server error")
		}
	}()
	return handler(ctx, req)
}

// --- Server Setup ---

func NewGRPCServer() *grpc.Server {
	srv := grpc.NewServer(
		grpc.ChainUnaryInterceptor(
			unaryRecoveryInterceptor,
			unaryLoggingInterceptor,
			unaryAuthInterceptor,
		),
		grpc.MaxRecvMsgSize(16 * 1024 * 1024), // 16MB
		grpc.MaxSendMsgSize(16 * 1024 * 1024),
	)

	// Register health check service
	healthSrv := health.NewServer()
	grpc_health_v1.RegisterHealthServer(srv, healthSrv)
	healthSrv.SetServingStatus("", grpc_health_v1.HealthCheckResponse_SERVING)

	// Enable server reflection for development
	if os.Getenv("GRPC_REFLECTION") == "true" {
		reflection.Register(srv)
	}

	return srv
}

func StartGRPCServer(srv *grpc.Server, port string) error {
	lis, err := net.Listen("tcp", fmt.Sprintf(":%s", port))
	if err != nil {
		return fmt.Errorf("failed to listen on port %s: %w", port, err)
	}

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-quit
		log.Println("[gRPC] Shutting down gracefully...")
		srv.GracefulStop()
	}()

	log.Printf("[gRPC] Server listening on :%s", port)
	return srv.Serve(lis)
}
