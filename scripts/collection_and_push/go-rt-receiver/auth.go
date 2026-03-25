package main

import (
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"

	jwt "github.com/golang-jwt/jwt/v5"
)

var (
	validMarkets        = map[string]struct{}{"a_stock": {}, "etf": {}, "index": {}, "hk": {}}
	validSchemaVersions = map[string]struct{}{"v2": {}}
	validModes          = map[string]struct{}{"raw_tick_batch": {}}
)

type EffectiveScope struct {
	UserID     string
	Markets    map[string]struct{}
	Levels     map[string]struct{}
	MaxSubs    int
	SymbolMode string
	SymbolList map[string]struct{}
	Revision   int
}

func normalizeSymbol(value string) (string, error) {
	symbol := strings.ToUpper(strings.TrimSpace(value))
	if symbol == "" || !strings.Contains(symbol, ".") {
		return "", fmt.Errorf("invalid symbol: %s", value)
	}
	return symbol, nil
}

func normalizeMarket(value string) string {
	market := strings.ToUpper(strings.TrimSpace(value))
	alias := map[string]string{
		"A_STOCK": "CN",
		"ASTOCK":  "CN",
		"CN":      "CN",
		"STOCK":   "CN",
		"ETF":     "CN",
		"INDEX":   "CN",
		"HK":      "HK",
	}
	if normalized, ok := alias[market]; ok {
		return normalized
	}
	return market
}

func detectSymbolMarket(symbol string) string {
	normalized, err := normalizeSymbol(symbol)
	if err != nil {
		return ""
	}
	if strings.HasSuffix(normalized, ".HK") {
		return "HK"
	}
	return "CN"
}

func parseSymbolList(raw string) ([]string, error) {
	items := strings.Split(raw, ",")
	result := make([]string, 0, len(items))
	for _, item := range items {
		item = strings.TrimSpace(item)
		if item == "" {
			continue
		}
		symbol, err := normalizeSymbol(item)
		if err != nil {
			return nil, err
		}
		result = append(result, symbol)
	}
	return result, nil
}

func parseSymbolItems(rawItems []any) ([]string, []map[string]string) {
	symbols := make([]string, 0, len(rawItems))
	rejected := make([]map[string]string, 0)
	for _, item := range rawItems {
		symbol, err := normalizeSymbol(asString(item))
		if err != nil {
			rejected = append(rejected, map[string]string{
				"symbol": asString(item),
				"reason": err.Error(),
			})
			continue
		}
		symbols = append(symbols, symbol)
	}
	return symbols, rejected
}

func validatePayload(payload map[string]any) error {
	schemaVersion := asString(payload["schema_version"])
	if _, ok := validSchemaVersions[schemaVersion]; !ok {
		return fmt.Errorf("unsupported schema_version: %s, expected: %v", schemaVersion, sortedKeys(validSchemaVersions))
	}

	mode := asString(payload["mode"])
	if _, ok := validModes[mode]; !ok {
		return fmt.Errorf("unsupported mode: %s, expected: %v", mode, sortedKeys(validModes))
	}

	market := asString(payload["market"])
	if _, ok := validMarkets[market]; !ok {
		return fmt.Errorf("invalid market: %s, valid: %v", market, sortedKeys(validMarkets))
	}

	items, ok := payload["items"].([]any)
	if !ok {
		return errors.New("items must be an array")
	}

	if countValue, exists := payload["count"]; exists && countValue != nil {
		count, err := intFromAny(countValue)
		if err != nil {
			return errors.New("count must be an integer")
		}
		if count != len(items) {
			return fmt.Errorf("count mismatch: declared %d, actual %d", count, len(items))
		}
	}

	if _, exists := payload["batch_seq"]; !exists {
		return errors.New("missing batch_seq")
	}

	return nil
}

func loadRSAPublicKey(path string) (*rsa.PublicKey, error) {
	if strings.TrimSpace(path) == "" {
		return nil, errors.New("jwt public key path is required")
	}

	content, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("jwt public key not found: %s", path)
	}

	block, _ := pem.Decode(content)
	if block == nil {
		return nil, errors.New("invalid PEM public key")
	}

	if pub, err := x509.ParsePKIXPublicKey(block.Bytes); err == nil {
		rsaPub, ok := pub.(*rsa.PublicKey)
		if !ok {
			return nil, errors.New("public key is not RSA")
		}
		return rsaPub, nil
	}

	if pub, err := x509.ParsePKCS1PublicKey(block.Bytes); err == nil {
		return pub, nil
	}

	cert, err := x509.ParseCertificate(block.Bytes)
	if err == nil {
		rsaPub, ok := cert.PublicKey.(*rsa.PublicKey)
		if !ok {
			return nil, errors.New("certificate public key is not RSA")
		}
		return rsaPub, nil
	}

	return nil, errors.New("failed to parse RSA public key")
}

func verifySubscriptionToken(tokenString, publicKeyPath string) (jwt.MapClaims, error) {
	if strings.TrimSpace(tokenString) == "" {
		return nil, errors.New("missing token")
	}

	publicKey, err := loadRSAPublicKey(publicKeyPath)
	if err != nil {
		return nil, err
	}

	token, err := jwt.Parse(tokenString, func(token *jwt.Token) (any, error) {
		if token.Method == nil || token.Method.Alg() != jwt.SigningMethodRS256.Alg() {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return publicKey, nil
	}, jwt.WithValidMethods([]string{jwt.SigningMethodRS256.Alg()}))
	if err != nil {
		if errors.Is(err, jwt.ErrTokenExpired) {
			return nil, errors.New("token expired")
		}
		return nil, fmt.Errorf("invalid token: %w", err)
	}
	if !token.Valid {
		return nil, errors.New("invalid token")
	}

	claims, ok := token.Claims.(jwt.MapClaims)
	if !ok {
		return nil, errors.New("invalid token claims")
	}

	scope, _ := claims["scope"].(map[string]any)
	if scope != nil {
		scopeType := asString(scope["type"])
		if scopeType != "" && scopeType != "realtime_stock" {
			if _, ok := scope["markets"]; !ok {
				return nil, fmt.Errorf("invalid token scope type: %s", scopeType)
			}
		}
	}

	return claims, nil
}

func buildEffectiveSubscriptionScope(claims jwt.MapClaims, policy map[string]any) EffectiveScope {
	scopeMap, _ := claims["scope"].(map[string]any)
	if scopeMap == nil {
		scopeMap = map[string]any{}
	}

	tokenMarkets := toStringSet(scopeMap["markets"], normalizeMarket)
	tokenLevels := toStringSet(scopeMap["levels"], strings.ToUpper)
	tokenSymbols := toStringMap(scopeMap["symbols"])
	tokenSymbolMode := strings.ToLower(defaultString(tokenSymbols["mode"], "all"))
	tokenSymbolList := toStringSet(tokenSymbols["list"], func(v string) string {
		symbol, err := normalizeSymbol(v)
		if err != nil {
			return ""
		}
		return symbol
	})
	tokenQuota := toStringMap(scopeMap["quota"])
	tokenMaxSubs, _ := intFromAny(tokenQuota["max_subs"])

	result := EffectiveScope{
		UserID:     strings.TrimSpace(defaultString(claims["sub"], asString(claims["username"]))),
		Markets:    tokenMarkets,
		Levels:     tokenLevels,
		MaxSubs:    tokenMaxSubs,
		SymbolMode: tokenSymbolMode,
		SymbolList: tokenSymbolList,
		Revision:   maxInt(mustInt(claims["rev"]), 0),
	}

	if policy == nil {
		return result
	}

	policyMarkets := toStringSet(policy["markets"], normalizeMarket)
	policyLevels := toStringSet(policy["levels"], strings.ToUpper)
	policyMaxSubs, _ := intFromAny(policy["max_subs"])
	policySymbols := toStringMap(policy["symbols"])
	policySymbolMode := strings.ToLower(defaultString(policySymbols["mode"], "all"))
	policySymbolList := toStringSet(policySymbols["list"], func(v string) string {
		symbol, err := normalizeSymbol(v)
		if err != nil {
			return ""
		}
		return symbol
	})

	result.Markets = intersectOrFallback(tokenMarkets, policyMarkets)
	result.Levels = intersectOrFallback(tokenLevels, policyLevels)
	result.MaxSubs = minPositive(tokenMaxSubs, policyMaxSubs)

	if policySymbolMode == "list" {
		result.SymbolMode = "list"
		if len(result.SymbolList) == 0 {
			result.SymbolList = policySymbolList
		} else {
			result.SymbolList = intersectOrFallback(result.SymbolList, policySymbolList)
		}
	}

	result.Revision = maxInt(result.Revision, mustInt(policy["revision"]))
	return result
}

func validateSubscriptionSymbols(symbols []string, scope EffectiveScope) ([]string, []map[string]string) {
	uniqueSymbols := make([]string, 0, len(symbols))
	seen := make(map[string]struct{}, len(symbols))
	rejected := make([]map[string]string, 0)

	for _, symbol := range symbols {
		if _, exists := seen[symbol]; exists {
			continue
		}
		seen[symbol] = struct{}{}

		market := detectSymbolMarket(symbol)
		if len(scope.Markets) > 0 {
			if _, ok := scope.Markets[market]; !ok {
				rejected = append(rejected, map[string]string{"symbol": symbol, "reason": "market_not_allowed"})
				continue
			}
		}

		if scope.SymbolMode == "list" && len(scope.SymbolList) > 0 {
			if _, ok := scope.SymbolList[symbol]; !ok {
				rejected = append(rejected, map[string]string{"symbol": symbol, "reason": "symbol_not_allowed"})
				continue
			}
		}

		uniqueSymbols = append(uniqueSymbols, symbol)
	}

	if scope.MaxSubs > 0 && len(uniqueSymbols) > scope.MaxSubs {
		overflow := append([]string(nil), uniqueSymbols[scope.MaxSubs:]...)
		uniqueSymbols = uniqueSymbols[:scope.MaxSubs]
		for _, symbol := range overflow {
			rejected = append(rejected, map[string]string{"symbol": symbol, "reason": "quota_exceeded"})
		}
	}

	return uniqueSymbols, rejected
}

func toStringSet(raw any, normalize func(string) string) map[string]struct{} {
	result := map[string]struct{}{}
	items, ok := raw.([]any)
	if !ok {
		return result
	}
	for _, item := range items {
		value := strings.TrimSpace(asString(item))
		if value == "" {
			continue
		}
		if normalize != nil {
			value = normalize(value)
		}
		if value == "" {
			continue
		}
		result[value] = struct{}{}
	}
	return result
}

func toStringMap(raw any) map[string]any {
	mapped, ok := raw.(map[string]any)
	if !ok || mapped == nil {
		return map[string]any{}
	}
	return mapped
}

func intersectOrFallback(a, b map[string]struct{}) map[string]struct{} {
	if len(a) == 0 && len(b) == 0 {
		return map[string]struct{}{}
	}
	if len(a) == 0 {
		return cloneSet(b)
	}
	if len(b) == 0 {
		return cloneSet(a)
	}
	result := map[string]struct{}{}
	for key := range a {
		if _, ok := b[key]; ok {
			result[key] = struct{}{}
		}
	}
	return result
}

func cloneSet(src map[string]struct{}) map[string]struct{} {
	if len(src) == 0 {
		return map[string]struct{}{}
	}
	result := make(map[string]struct{}, len(src))
	for key := range src {
		result[key] = struct{}{}
	}
	return result
}

func sortedKeys(m map[string]struct{}) []string {
	keys := make([]string, 0, len(m))
	for key := range m {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func asString(value any) string {
	switch v := value.(type) {
	case nil:
		return ""
	case string:
		return v
	case fmt.Stringer:
		return v.String()
	case jsonNumberLike:
		return v.String()
	default:
		return fmt.Sprintf("%v", value)
	}
}

type jsonNumberLike interface {
	String() string
}

func defaultString(value any, fallback string) string {
	str := strings.TrimSpace(asString(value))
	if str == "" {
		return fallback
	}
	return str
}

func intFromAny(value any) (int, error) {
	switch v := value.(type) {
	case nil:
		return 0, errors.New("nil")
	case int:
		return v, nil
	case int8:
		return int(v), nil
	case int16:
		return int(v), nil
	case int32:
		return int(v), nil
	case int64:
		return int(v), nil
	case uint:
		return int(v), nil
	case uint8:
		return int(v), nil
	case uint16:
		return int(v), nil
	case uint32:
		return int(v), nil
	case uint64:
		return int(v), nil
	case float32:
		return int(v), nil
	case float64:
		return int(v), nil
	case string:
		return strconv.Atoi(strings.TrimSpace(v))
	case fmt.Stringer:
		return strconv.Atoi(strings.TrimSpace(v.String()))
	default:
		return 0, fmt.Errorf("unsupported integer type %T", value)
	}
}

func mustInt(value any) int {
	result, err := intFromAny(value)
	if err != nil {
		return 0
	}
	return result
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func minPositive(a, b int) int {
	if a > 0 && b > 0 {
		if a < b {
			return a
		}
		return b
	}
	if a > 0 {
		return a
	}
	if b > 0 {
		return b
	}
	return 0
}
