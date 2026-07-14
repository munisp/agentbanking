package main

import (
	"encoding/json"
	"net/http"

	"github.com/gin-gonic/gin"
)

type ErrorDetail struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Status  string `json:"status"`
	Service string `json:"service"`
}

type ErrorResponse struct {
	Detail ErrorDetail `json:"detail"`
}

var ErrorCodes = map[string]string{
	"bad_request":       "LOAN-LOAN-VAL-4001",
	"not_found":         "LOAN-LOAN-NF-4040",
	"internal_error":    "LOAN-LOAN-INT-5000",
	"validation_failed": "LOAN-LOAN-VAL-4002",
	"decode_error":      "LOAN-LOAN-VAL-4003",
	"already_exists":    "LOAN-LOAN-CONF-4009",
	"unauthorized":      "LOAN-LOAN-AUTH-4010",
}

func SendError(w http.ResponseWriter, codeKey, message string, status int, details interface{}) {
	code, ok := ErrorCodes[codeKey]
	if !ok {
		code = codeKey
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(ErrorResponse{
		Detail: ErrorDetail{
			Code:    code,
			Message: message,
			Status:  "error",
			Service: "loan-service",
		},
	})
}

// SendErrorGin sends error response using Gin context
func SendErrorGin(c *gin.Context, codeKey, message string, status int) {
	code, ok := ErrorCodes[codeKey]
	if !ok {
		code = codeKey
	}
	c.JSON(status, ErrorResponse{
		Detail: ErrorDetail{
			Code:    code,
			Message: message,
			Status:  "error",
			Service: "loan-service",
		},
	})
}
