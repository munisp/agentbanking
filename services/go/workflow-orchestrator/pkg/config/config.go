package config

import (
	"github.com/spf13/viper"
)

// Config represents the application configuration
type Config struct {
	Server   ServerConfig   `mapstructure:"server"`
	Database DatabaseConfig `mapstructure:"database"`
	Redis    RedisConfig    `mapstructure:"redis"`
	Fluvio   FluvioConfig   `mapstructure:"fluvio"`
	Kafka    KafkaConfig    `mapstructure:"kafka"`
	Executor ExecutorConfig `mapstructure:"executor"`
}

// ServerConfig represents HTTP server configuration
type ServerConfig struct {
	Port         int `mapstructure:"port"`
	ReadTimeout  int `mapstructure:"read_timeout"`
	WriteTimeout int `mapstructure:"write_timeout"`
}

// DatabaseConfig represents PostgreSQL configuration
type DatabaseConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	User     string `mapstructure:"user"`
	Password string `mapstructure:"password"`
	Database string `mapstructure:"database"`
	PoolSize int    `mapstructure:"pool_size"`
}

// RedisConfig represents Redis configuration
type RedisConfig struct {
	Addr     string `mapstructure:"addr"`
	Password string `mapstructure:"password"`
	DB       int    `mapstructure:"db"`
	PoolSize int    `mapstructure:"pool_size"`
}

// FluvioConfig represents Fluvio configuration
type FluvioConfig struct {
	Brokers []string `mapstructure:"brokers"`
}

// KafkaConfig represents Kafka configuration
type KafkaConfig struct {
	Brokers []string `mapstructure:"brokers"`
}

// ExecutorConfig represents workflow executor configuration
type ExecutorConfig struct {
	Workers       int `mapstructure:"workers"`
	MaxConcurrent int `mapstructure:"max_concurrent"`
	MaxRetries    int `mapstructure:"max_retries"`
}

// Load loads configuration from file and environment variables
func Load() (*Config, error) {
	viper.SetConfigName("config")
	viper.SetConfigType("yaml")
	viper.AddConfigPath(".")
	viper.AddConfigPath("/etc/workflow-orchestrator/")
	viper.AddConfigPath("$HOME/.workflow-orchestrator")

	// Set defaults
	viper.SetDefault("server.port", 8080)
	viper.SetDefault("server.read_timeout", 30)
	viper.SetDefault("server.write_timeout", 30)
	viper.SetDefault("database.host", "localhost")
	viper.SetDefault("database.port", 5432)
	viper.SetDefault("database.user", "postgres")
	viper.SetDefault("database.password", "postgres")
	viper.SetDefault("database.database", "workflow_orchestrator")
	viper.SetDefault("database.pool_size", 100)
	viper.SetDefault("redis.addr", "localhost:6379")
	viper.SetDefault("redis.password", "")
	viper.SetDefault("redis.db", 0)
	viper.SetDefault("redis.pool_size", 100)
	viper.SetDefault("executor.workers", 10)
	viper.SetDefault("executor.max_concurrent", 1000)
	viper.SetDefault("executor.max_retries", 3)

	// Enable environment variable override
	viper.AutomaticEnv()
	viper.SetEnvPrefix("WORKFLOW")

	// Read config file (optional)
	if err := viper.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return nil, err
		}
		// Config file not found; using defaults and env vars
	}

	var config Config
	if err := viper.Unmarshal(&config); err != nil {
		return nil, err
	}

	return &config, nil
}

