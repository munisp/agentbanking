package main

import (
	"context"
	"encoding/json"
	"fmt"
	"image"
	"image/jpeg"
	"image/png"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/disintegration/imaging"
	"github.com/go-redis/redis/v8"
	"github.com/gorilla/mux"
	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu"
)

// DocumentPreprocessor handles high-performance document preprocessing
type DocumentPreprocessor struct {
	s3Client    *s3.Client
	redisClient *redis.Client
	workerPool  *WorkerPool
	config      *Config
}

// Config holds service configuration
type Config struct {
	S3Bucket       string
	S3Region       string
	RedisAddr      string
	WorkerCount    int
	MaxImageWidth  int
	MaxImageHeight int
	JPEGQuality    int
}

// PreprocessRequest represents a preprocessing request
type PreprocessRequest struct {
	DocumentID   string `json:"document_id"`
	S3Key        string `json:"s3_key"`
	DocumentType string `json:"document_type"`
	Operations   []string `json:"operations"` // resize, normalize, denoise, etc.
}

// PreprocessResponse represents preprocessing result
type PreprocessResponse struct {
	DocumentID       string   `json:"document_id"`
	Status           string   `json:"status"`
	ProcessedS3Keys  []string `json:"processed_s3_keys"`
	ProcessingTimeMs int64    `json:"processing_time_ms"`
	PageCount        int      `json:"page_count"`
	Message          string   `json:"message"`
}

// WorkerPool manages parallel document processing
type WorkerPool struct {
	workers   int
	jobQueue  chan *PreprocessJob
	wg        sync.WaitGroup
	processor *DocumentPreprocessor
}

// PreprocessJob represents a single preprocessing job
type PreprocessJob struct {
	Request  *PreprocessRequest
	Response chan *PreprocessResponse
}

// NewConfig creates default configuration
func NewConfig() *Config {
	return &Config{
		S3Bucket:       getEnv("S3_BUCKET", "remittance-documents"),
		S3Region:       getEnv("S3_REGION", "us-east-1"),
		RedisAddr:      getEnv("REDIS_ADDR", "localhost:6379"),
		WorkerCount:    getEnvInt("WORKER_COUNT", 10),
		MaxImageWidth:  getEnvInt("MAX_IMAGE_WIDTH", 2048),
		MaxImageHeight: getEnvInt("MAX_IMAGE_HEIGHT", 2048),
		JPEGQuality:    getEnvInt("JPEG_QUALITY", 95),
	}
}

// NewDocumentPreprocessor creates a new preprocessor instance
func NewDocumentPreprocessor(cfg *Config) (*DocumentPreprocessor, error) {
	// Initialize AWS S3 client
	awsCfg, err := config.LoadDefaultConfig(context.TODO(), config.WithRegion(cfg.S3Region))
	if err != nil {
		return nil, fmt.Errorf("failed to load AWS config: %w", err)
	}

	s3Client := s3.NewFromConfig(awsCfg)

	// Initialize Redis client
	redisClient := redis.NewClient(&redis.Options{
		Addr: cfg.RedisAddr,
		DB:   0,
	})

	// Test Redis connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := redisClient.Ping(ctx).Err(); err != nil {
		log.Printf("Warning: Redis connection failed: %v", err)
	}

	processor := &DocumentPreprocessor{
		s3Client:    s3Client,
		redisClient: redisClient,
		config:      cfg,
	}

	// Initialize worker pool
	processor.workerPool = NewWorkerPool(cfg.WorkerCount, processor)

	return processor, nil
}

// NewWorkerPool creates a new worker pool
func NewWorkerPool(workers int, processor *DocumentPreprocessor) *WorkerPool {
	pool := &WorkerPool{
		workers:   workers,
		jobQueue:  make(chan *PreprocessJob, workers*2),
		processor: processor,
	}

	// Start workers
	for i := 0; i < workers; i++ {
		pool.wg.Add(1)
		go pool.worker(i)
	}

	return pool
}

// worker processes jobs from the queue
func (wp *WorkerPool) worker(id int) {
	defer wp.wg.Done()

	log.Printf("Worker %d started", id)

	for job := range wp.jobQueue {
		startTime := time.Now()

		response := wp.processor.processDocument(job.Request)
		response.ProcessingTimeMs = time.Since(startTime).Milliseconds()

		job.Response <- response
	}

	log.Printf("Worker %d stopped", id)
}

// Submit submits a job to the worker pool
func (wp *WorkerPool) Submit(job *PreprocessJob) {
	wp.jobQueue <- job
}

// Shutdown gracefully shuts down the worker pool
func (wp *WorkerPool) Shutdown() {
	close(wp.jobQueue)
	wp.wg.Wait()
}

// processDocument processes a single document
func (dp *DocumentPreprocessor) processDocument(req *PreprocessRequest) *PreprocessResponse {
	ctx := context.Background()

	response := &PreprocessResponse{
		DocumentID:      req.DocumentID,
		Status:          "processing",
		ProcessedS3Keys: []string{},
	}

	// Download file from S3
	localPath, err := dp.downloadFromS3(ctx, req.S3Key)
	if err != nil {
		response.Status = "failed"
		response.Message = fmt.Sprintf("Failed to download from S3: %v", err)
		return response
	}
	defer os.Remove(localPath)

	// Determine file type
	ext := filepath.Ext(localPath)

	var processedPaths []string
	var pageCount int

	switch ext {
	case ".pdf":
		processedPaths, pageCount, err = dp.processPDF(localPath, req.Operations)
	case ".jpg", ".jpeg", ".png", ".tiff":
		processedPaths, err = dp.processImage(localPath, req.Operations)
		pageCount = 1
	default:
		response.Status = "failed"
		response.Message = fmt.Sprintf("Unsupported file type: %s", ext)
		return response
	}

	if err != nil {
		response.Status = "failed"
		response.Message = fmt.Sprintf("Processing failed: %v", err)
		return response
	}

	// Upload processed files to S3
	for _, path := range processedPaths {
		s3Key := fmt.Sprintf("processed/%s/%s", req.DocumentID, filepath.Base(path))
		if err := dp.uploadToS3(ctx, path, s3Key); err != nil {
			log.Printf("Failed to upload %s: %v", path, err)
			continue
		}
		response.ProcessedS3Keys = append(response.ProcessedS3Keys, s3Key)
		os.Remove(path)
	}

	response.Status = "completed"
	response.PageCount = pageCount
	response.Message = "Document preprocessed successfully"

	return response
}

// processPDF processes PDF documents
func (dp *DocumentPreprocessor) processPDF(pdfPath string, operations []string) ([]string, int, error) {
	// Extract pages as images
	outputDir := filepath.Join("/tmp", fmt.Sprintf("pdf_%d", time.Now().UnixNano()))
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return nil, 0, err
	}

	// Configure PDF extraction
	conf := pdfcpu.NewDefaultConfiguration()
	conf.ValidationMode = pdfcpu.ValidationRelaxed

	// Extract images from PDF
	if err := api.ExtractImagesFile(pdfPath, outputDir, nil, conf); err != nil {
		log.Printf("Warning: Image extraction failed: %v", err)
	}

	// Get page count
	ctx, err := api.ReadContextFile(pdfPath)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to read PDF: %w", err)
	}
	pageCount := ctx.PageCount

	// Process extracted images
	var processedPaths []string
	files, _ := filepath.Glob(filepath.Join(outputDir, "*"))

	for _, file := range files {
		processed, err := dp.processImage(file, operations)
		if err != nil {
			log.Printf("Failed to process %s: %v", file, err)
			continue
		}
		processedPaths = append(processedPaths, processed...)
	}

	// If no images extracted, convert PDF pages to images
	if len(processedPaths) == 0 {
		log.Printf("No images extracted, PDF may be text-only")
		// In production, use pdf2image or similar
		processedPaths = []string{pdfPath} // Return original PDF
	}

	return processedPaths, pageCount, nil
}

// processImage processes image files
func (dp *DocumentPreprocessor) processImage(imagePath string, operations []string) ([]string, error) {
	// Load image
	img, err := imaging.Open(imagePath)
	if err != nil {
		return nil, fmt.Errorf("failed to open image: %w", err)
	}

	// Apply operations
	for _, op := range operations {
		switch op {
		case "resize":
			img = dp.resizeImage(img)
		case "normalize":
			img = dp.normalizeImage(img)
		case "denoise":
			img = dp.denoiseImage(img)
		case "enhance":
			img = dp.enhanceImage(img)
		}
	}

	// Save processed image
	outputPath := filepath.Join("/tmp", fmt.Sprintf("processed_%d.jpg", time.Now().UnixNano()))
	if err := imaging.Save(img, outputPath, imaging.JPEGQuality(dp.config.JPEGQuality)); err != nil {
		return nil, fmt.Errorf("failed to save image: %w", err)
	}

	return []string{outputPath}, nil
}

// resizeImage resizes image to max dimensions
func (dp *DocumentPreprocessor) resizeImage(img image.Image) image.Image {
	bounds := img.Bounds()
	width := bounds.Dx()
	height := bounds.Dy()

	// Check if resize needed
	if width <= dp.config.MaxImageWidth && height <= dp.config.MaxImageHeight {
		return img
	}

	// Calculate new dimensions maintaining aspect ratio
	ratio := float64(width) / float64(height)
	var newWidth, newHeight int

	if width > height {
		newWidth = dp.config.MaxImageWidth
		newHeight = int(float64(newWidth) / ratio)
	} else {
		newHeight = dp.config.MaxImageHeight
		newWidth = int(float64(newHeight) * ratio)
	}

	return imaging.Resize(img, newWidth, newHeight, imaging.Lanczos)
}

// normalizeImage normalizes image brightness and contrast
func (dp *DocumentPreprocessor) normalizeImage(img image.Image) image.Image {
	// Auto-adjust brightness and contrast
	img = imaging.AdjustContrast(img, 10)
	img = imaging.AdjustBrightness(img, 5)
	return img
}

// denoiseImage reduces image noise
func (dp *DocumentPreprocessor) denoiseImage(img image.Image) image.Image {
	// Apply Gaussian blur for denoising
	return imaging.Blur(img, 0.5)
}

// enhanceImage enhances image for better OCR
func (dp *DocumentPreprocessor) enhanceImage(img image.Image) image.Image {
	// Sharpen image
	img = imaging.Sharpen(img, 1.0)
	// Increase contrast
	img = imaging.AdjustContrast(img, 15)
	return img
}

// downloadFromS3 downloads file from S3
func (dp *DocumentPreprocessor) downloadFromS3(ctx context.Context, s3Key string) (string, error) {
	output, err := dp.s3Client.GetObject(ctx, &s3.GetObjectInput{
		Bucket: aws.String(dp.config.S3Bucket),
		Key:    aws.String(s3Key),
	})
	if err != nil {
		return "", err
	}
	defer output.Body.Close()

	// Create temp file
	localPath := filepath.Join("/tmp", fmt.Sprintf("download_%d%s", time.Now().UnixNano(), filepath.Ext(s3Key)))
	file, err := os.Create(localPath)
	if err != nil {
		return "", err
	}
	defer file.Close()

	// Copy content
	if _, err := io.Copy(file, output.Body); err != nil {
		os.Remove(localPath)
		return "", err
	}

	return localPath, nil
}

// uploadToS3 uploads file to S3
func (dp *DocumentPreprocessor) uploadToS3(ctx context.Context, localPath, s3Key string) error {
	file, err := os.Open(localPath)
	if err != nil {
		return err
	}
	defer file.Close()

	_, err = dp.s3Client.PutObject(ctx, &s3.PutObjectInput{
		Bucket: aws.String(dp.config.S3Bucket),
		Key:    aws.String(s3Key),
		Body:   file,
	})

	return err
}

// HTTP Handlers

func (dp *DocumentPreprocessor) preprocessHandler(w http.ResponseWriter, r *http.Request) {
	var req PreprocessRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, fmt.Sprintf("Invalid request: %v", err), http.StatusBadRequest)
		return
	}

	// Submit job to worker pool
	job := &PreprocessJob{
		Request:  &req,
		Response: make(chan *PreprocessResponse, 1),
	}

	dp.workerPool.Submit(job)

	// Wait for response
	response := <-job.Response

	w.Header().Set("Content-Type", "application/json")
	if response.Status == "failed" {
		w.WriteHeader(http.StatusInternalServerError)
	}
	json.NewEncoder(w).Encode(response)
}

func (dp *DocumentPreprocessor) batchPreprocessHandler(w http.ResponseWriter, r *http.Request) {
	var requests []PreprocessRequest
	if err := json.NewDecoder(r.Body).Decode(&requests); err != nil {
		http.Error(w, fmt.Sprintf("Invalid request: %v", err), http.StatusBadRequest)
		return
	}

	// Process in parallel
	responses := make([]*PreprocessResponse, len(requests))
	var wg sync.WaitGroup

	for i, req := range requests {
		wg.Add(1)
		go func(idx int, request PreprocessRequest) {
			defer wg.Done()

			job := &PreprocessJob{
				Request:  &request,
				Response: make(chan *PreprocessResponse, 1),
			}

			dp.workerPool.Submit(job)
			responses[idx] = <-job.Response
		}(i, req)
	}

	wg.Wait()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"total":     len(responses),
		"responses": responses,
	})
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":    "healthy",
		"service":   "document-preprocessor",
		"version":   "1.0.0",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

// Utility functions

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		var intValue int
		if _, err := fmt.Sscanf(value, "%d", &intValue); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func main() {
	// Load configuration
	cfg := NewConfig()

	// Initialize preprocessor
	preprocessor, err := NewDocumentPreprocessor(cfg)
	if err != nil {
		log.Fatalf("Failed to initialize preprocessor: %v", err)
	}

	// Setup HTTP router
	router := mux.NewRouter()
	router.HandleFunc("/api/v1/preprocess", preprocessor.preprocessHandler).Methods("POST")
	router.HandleFunc("/api/v1/preprocess/batch", preprocessor.batchPreprocessHandler).Methods("POST")
	router.HandleFunc("/health", healthHandler).Methods("GET")

	// Start server
	port := getEnv("PORT", "8041")
	addr := fmt.Sprintf("0.0.0.0:%s", port)

	log.Printf("Document Preprocessor starting on %s with %d workers", addr, cfg.WorkerCount)

	server := &http.Server{
		Addr:         addr,
		Handler:      router,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 60 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// Graceful shutdown
	go func() {
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	log.Println("Document Preprocessor is running")

	// Wait for interrupt signal
	<-make(chan struct{})
}
