package logger

import (
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

var Logger *zap.Logger

// Init initializes the global logger
func Init() {
	config := zap.NewProductionConfig()
	config.EncoderConfig.TimeKey = "timestamp"
	config.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder
	config.EncoderConfig.StacktraceKey = ""

	var err error
	Logger, err = config.Build()
	if err != nil {
		panic(err)
	}
}

// WithWorkflow creates a logger with workflow_id field
func WithWorkflow(workflowID string) *zap.Logger {
	return Logger.With(zap.String("workflow_id", workflowID))
}

// Helper functions for structured logging
func String(key, val string) zap.Field {
	return zap.String(key, val)
}

func Int(key string, val int) zap.Field {
	return zap.Int(key, val)
}

func Float64(key string, val float64) zap.Field {
	return zap.Float64(key, val)
}

func Error(err error) zap.Field {
	return zap.Error(err)
}

func Duration(key string, val interface{}) zap.Field {
	return zap.Any(key, val)
}

// Uint64 creates a zap field for a uint64 value
func Uint64(key string, val uint64) zap.Field {
	return zap.Uint64(key, val)
}

// Warn logs a warning message
func Warn(msg string, fields ...zap.Field) {
	Logger.Warn(msg, fields...)
}

