// Package carrier identifies the Nigerian mobile network carrier from
// a phone number prefix (NCC-assigned number ranges).
// Reference: NCC Nigeria numbering plan — https://ncc.gov.ng
package carrier

import "strings"

// Carrier represents a Nigerian mobile network operator.
type Carrier struct {
	Name   string `json:"name"`
	Code   string `json:"code"`   // short code for USSD routing
	USSD   string `json:"ussd"`   // carrier USSD prefix for airtime/data
	Color  string `json:"color"`  // brand hex colour
}

var prefixMap = map[string]Carrier{
	// MTN Nigeria — 0803, 0806, 0703, 0706, 0813, 0816, 0810, 0814, 0903, 0906, 0913, 0916
	"0803": {Name: "MTN", Code: "mtn", USSD: "*556#", Color: "#FFCC00"},
	"0806": {Name: "MTN", Code: "mtn", USSD: "*556#", Color: "#FFCC00"},
	"0703": {Name: "MTN", Code: "mtn", USSD: "*556#", Color: "#FFCC00"},
	"0706": {Name: "MTN", Code: "mtn", USSD: "*556#", Color: "#FFCC00"},
	"0813": {Name: "MTN", Code: "mtn", USSD: "*556#", Color: "#FFCC00"},
	"0816": {Name: "MTN", Code: "mtn", USSD: "*556#", Color: "#FFCC00"},
	"0810": {Name: "MTN", Code: "mtn", USSD: "*556#", Color: "#FFCC00"},
	"0814": {Name: "MTN", Code: "mtn", USSD: "*556#", Color: "#FFCC00"},
	"0903": {Name: "MTN", Code: "mtn", USSD: "*556#", Color: "#FFCC00"},
	"0906": {Name: "MTN", Code: "mtn", USSD: "*556#", Color: "#FFCC00"},
	"0913": {Name: "MTN", Code: "mtn", USSD: "*556#", Color: "#FFCC00"},
	"0916": {Name: "MTN", Code: "mtn", USSD: "*556#", Color: "#FFCC00"},
	// Airtel Nigeria — 0802, 0808, 0708, 0812, 0701, 0902, 0907, 0912
	"0802": {Name: "Airtel", Code: "airtel", USSD: "*123#", Color: "#E40000"},
	"0808": {Name: "Airtel", Code: "airtel", USSD: "*123#", Color: "#E40000"},
	"0708": {Name: "Airtel", Code: "airtel", USSD: "*123#", Color: "#E40000"},
	"0812": {Name: "Airtel", Code: "airtel", USSD: "*123#", Color: "#E40000"},
	"0701": {Name: "Airtel", Code: "airtel", USSD: "*123#", Color: "#E40000"},
	"0902": {Name: "Airtel", Code: "airtel", USSD: "*123#", Color: "#E40000"},
	"0907": {Name: "Airtel", Code: "airtel", USSD: "*123#", Color: "#E40000"},
	"0912": {Name: "Airtel", Code: "airtel", USSD: "*123#", Color: "#E40000"},
	// Glo Nigeria — 0805, 0807, 0705, 0815, 0905, 0915
	"0805": {Name: "Glo", Code: "glo", USSD: "*777#", Color: "#008000"},
	"0807": {Name: "Glo", Code: "glo", USSD: "*777#", Color: "#008000"},
	"0705": {Name: "Glo", Code: "glo", USSD: "*777#", Color: "#008000"},
	"0815": {Name: "Glo", Code: "glo", USSD: "*777#", Color: "#008000"},
	"0905": {Name: "Glo", Code: "glo", USSD: "*777#", Color: "#008000"},
	"0915": {Name: "Glo", Code: "glo", USSD: "*777#", Color: "#008000"},
	// 9mobile (formerly Etisalat) — 0809, 0818, 0817, 0909, 0908
	"0809": {Name: "9mobile", Code: "9mobile", USSD: "*200#", Color: "#006400"},
	"0818": {Name: "9mobile", Code: "9mobile", USSD: "*200#", Color: "#006400"},
	"0817": {Name: "9mobile", Code: "9mobile", USSD: "*200#", Color: "#006400"},
	"0909": {Name: "9mobile", Code: "9mobile", USSD: "*200#", Color: "#006400"},
	"0908": {Name: "9mobile", Code: "9mobile", USSD: "*200#", Color: "#006400"},
}

var unknown = Carrier{Name: "Unknown", Code: "unknown", USSD: "", Color: "#888888"}

// Detect returns the Carrier for a Nigerian phone number.
// Accepts formats: 08XXXXXXXXX, +2348XXXXXXXXX, 2348XXXXXXXXX.
func Detect(phone string) Carrier {
	phone = strings.TrimSpace(phone)
	// Normalise to local 0XXXXXXXXXX format
	if strings.HasPrefix(phone, "+234") {
		phone = "0" + phone[4:]
	} else if strings.HasPrefix(phone, "234") {
		phone = "0" + phone[3:]
	}
	if len(phone) < 4 {
		return unknown
	}
	prefix := phone[:4]
	if c, ok := prefixMap[prefix]; ok {
		return c
	}
	return unknown
}
