## ADDED Requirements

### Requirement: Tushare News Flash Integration
The system SHALL fetch short news flashes from 9 financial media sources via the Tushare `news` API, supporting source filtering by `src` parameter (sina, wallstreetcn, 10jqka, eastmoney, yuncaijing, fenghuang, jinrongjie, cls, yicai).

#### Scenario: Fetch news flashes by source and time range
- **WHEN** a request is made with `src=sina`, `start_date=2026-03-06 09:00:00`, `end_date=2026-03-06 18:00:00`
- **THEN** the system returns up to 1500 news items with `datetime`, `content`, `title`, `channels` fields
- **AND** each item is mapped to a `NewsItem` with category `FLASH`

#### Scenario: Default multi-source aggregation
- **WHEN** no specific source is provided for the flash news category
- **THEN** the system fetches sources with grouped concurrency and per-group sequential rate limiting (≥1s interval)
- **AND** results are deduplicated by title and merged by publish time

### Requirement: Tushare Major News Integration
The system SHALL fetch long-form news articles from major financial media via the Tushare `major_news` API, supporting source filtering (新华网, 凤凰财经, 同花顺, 新浪财经, 华尔街见闻, 中证网, 财新网, 第一财经, 财联社).

#### Scenario: Fetch major news with content
- **WHEN** a request is made with `src=新浪财经` and a date range
- **THEN** the system returns news items with `title`, `content`, `pub_time`, `src` fields
- **AND** each item is mapped to a `NewsItem` with category `ANALYSIS` and full content

#### Scenario: Rate limit protection
- **WHEN** the API returns a rate limit error
- **THEN** the system retries with exponential backoff (max 3 attempts)
- **AND** returns cached data if all retries fail

### Requirement: CCTV News Integration
The system SHALL fetch CCTV Evening News transcripts via the Tushare `cctv_news` API, providing text versions of daily broadcasts since 2017.

#### Scenario: Fetch CCTV news by date
- **WHEN** a request is made with `date=20260306`
- **THEN** the system returns all news segments with `date`, `title`, `content` fields
- **AND** each item is mapped to a `NewsItem` with category `CCTV`

#### Scenario: Cache CCTV news for 24 hours
- **WHEN** CCTV news for a specific date has been fetched within the last 24 hours
- **THEN** the system returns the cached version without making an API call

### Requirement: Enhanced Announcement Integration
The system SHALL fetch listed company announcements via the Tushare `anns_d` API, replacing the existing `anns()` call with improved date range query support.

#### Scenario: Fetch announcements by date range
- **WHEN** a request is made with `start_date=20260301`, `end_date=20260306`
- **THEN** the system returns up to 2000 announcements with `ann_date`, `ts_code`, `name`, `title`, `url` fields
- **AND** each item is mapped to a `NewsItem` with category `ANNOUNCEMENT`

#### Scenario: Fetch announcements by stock code
- **WHEN** a request is made with `ts_code=600519.SH`
- **THEN** the system returns all announcements for the specified stock

### Requirement: Research Report Integration
The system SHALL fetch broker research reports via the Tushare `research_report` API, supporting filtering by date, stock code, broker name, industry, and report type (个股研报/行业研报).

#### Scenario: Fetch research reports by date
- **WHEN** a request is made with `trade_date=20260306`
- **THEN** the system returns up to 1000 reports with `trade_date`, `title`, `abstr`, `author`, `ts_code`, `inst_csname`, `ind_name`, `url` fields
- **AND** each item is mapped to a `NewsItem` with category `RESEARCH`

#### Scenario: Filter reports by stock and broker
- **WHEN** a request is made with `ts_code=600519.SH`, `inst_csname=中信证券`
- **THEN** the system returns only matching research reports

### Requirement: National Policy Repository Integration
The system SHALL fetch national policy documents via the Tushare `npr` API, including regulations, notifications, and official responses from government agencies.

#### Scenario: Fetch policies by issuing organization
- **WHEN** a request is made with `org=国务院`
- **THEN** the system returns up to 500 policy items with `pubtime`, `title`, `url`, `content_html`, `pcode`, `puborg`, `ptype` fields
- **AND** each item is mapped to a `NewsItem` with category `NPR`

#### Scenario: Filter policies by topic category
- **WHEN** a request is made with `ptype=科技`
- **THEN** the system returns only policies matching the specified topic

### Requirement: Extended News Categories
The system SHALL support three additional `NewsCategory` values: `CCTV` (新闻联播), `RESEARCH` (券商研报), `NPR` (国家政策), in addition to existing categories (ANNOUNCEMENT, FLASH, ANALYSIS, POLICY, INDUSTRY, ALL).

#### Scenario: Category-based routing
- **WHEN** `get_market_news(category=CCTV)` is called
- **THEN** the system routes the request to the `cctv_news` data source
- **AND** returns only CCTV news items

### Requirement: Per-Source Cache Strategy
The system SHALL implement independent cache TTLs for each data source: news flash (5min memory / 30min file), major news (30min / 2h), CCTV (2h / 24h), announcements (30min / 2h), research reports (1h / 4h), policies (4h / 24h).

#### Scenario: Cache TTL enforcement
- **WHEN** cached data for a source has not expired
- **THEN** the system returns the cached version without API calls
- **AND** triggers a background refresh if the data is older than 80% of its TTL

### Requirement: Partial Failure Degradation
The system SHALL return partial results when one or more upstream news sources fail, instead of failing the entire request.

#### Scenario: Single source failure does not break response
- **WHEN** one source request fails while others succeed
- **THEN** the API returns success with available data
- **AND** sets `partial=true` and populates `failed_sources` with failed source identifiers

#### Scenario: Failure observability
- **WHEN** a source request fails after retries
- **THEN** the system logs structured failure details including source, error code/message, and retry count

### Requirement: Sina Fallback Rollout
The system SHALL keep Sina crawling as a configurable fallback during migration and support phased decommission.

#### Scenario: Fallback enabled
- **WHEN** fallback is enabled and Tushare flash source is unavailable
- **THEN** the system supplements flash data from Sina source

#### Scenario: Fallback disabled
- **WHEN** fallback switch is disabled
- **THEN** the system does not call Sina source and uses only Tushare-based sources
