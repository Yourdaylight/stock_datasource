-- Migration: 002_add_middleware_trace_id
-- Created: 2026-04-12
-- Description: Add middleware_trace_id column to system_structured_logs for middleware pipeline tracing

ALTER TABLE system_structured_logs ADD COLUMN IF NOT EXISTS middleware_trace_id String DEFAULT '-'
