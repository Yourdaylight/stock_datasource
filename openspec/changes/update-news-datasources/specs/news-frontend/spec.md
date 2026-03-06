## ADDED Requirements

### Requirement: CCTV News Tab
The frontend SHALL provide a "新闻联播" Tab in the 资讯中心, displaying CCTV Evening News transcripts with a date picker for navigation.

#### Scenario: View CCTV news for a specific date
- **WHEN** the user selects the "新闻联播" Tab and picks a date
- **THEN** the system displays a list of news segments for that date with titles and full text content
- **AND** defaults to the current date on first load

#### Scenario: No data available
- **WHEN** the selected date has no CCTV news data
- **THEN** the system shows an empty state with message "该日期暂无新闻联播数据"

### Requirement: Policy News Tab
The frontend SHALL provide a "政策法规" Tab in the 资讯中心, displaying national policy documents with filtering by issuing organization and topic category.

#### Scenario: Browse policies with filters
- **WHEN** the user selects the "政策法规" Tab
- **THEN** the system displays a list of policy documents with title, issuing org, publish time, and document code
- **AND** provides filter dropdowns for organization and topic category

#### Scenario: View policy detail
- **WHEN** the user clicks on a policy item
- **THEN** a detail dialog shows the full policy content with a link to the original document

### Requirement: Policy HTML Sanitization
The frontend MUST sanitize policy HTML content before rendering to prevent XSS attacks.

#### Scenario: Strip dangerous scripts and handlers
- **WHEN** policy content contains `<script>` tags, inline event handlers, or dangerous URL schemes
- **THEN** those unsafe fragments are removed before rendering
- **AND** only allowed tags/attributes are retained

#### Scenario: Render safe policy content
- **WHEN** policy content passes sanitization
- **THEN** the detail dialog renders sanitized HTML content
- **AND** the rendered output does not execute arbitrary scripts

### Requirement: Enhanced Source Filtering
The 新闻快讯 Tab SHALL support filtering by 9 Tushare media sources (新浪财经, 华尔街见闻, 同花顺, 东方财富, 云财经, 凤凰新闻, 金融界, 财联社, 第一财经) in addition to existing sources.

#### Scenario: Filter by specific media source
- **WHEN** the user selects "财联社" from the source filter dropdown
- **THEN** only news items from 财联社 are displayed
- **AND** the URL query parameter is updated to reflect the filter

#### Scenario: Multi-source default view
- **WHEN** no source filter is applied
- **THEN** news from all sources are displayed in reverse chronological order

### Requirement: Extended Category Filtering
The frontend SHALL display the extended news categories (新闻联播, 券商研报, 国家政策) in category filter UI components.

#### Scenario: Category filter reflects all types
- **WHEN** the category filter dropdown is opened
- **THEN** it includes: 全部, 公告, 快讯, 分析, 政策, 行业, 新闻联播, 券商研报, 国家政策

### Requirement: Research Report Enhancement
The 研报数据 Tab SHALL be enhanced with data from the Tushare `research_report` API, showing report abstract, author, broker, industry, and download link.

#### Scenario: Browse research reports with filters
- **WHEN** the user views the 研报数据 Tab
- **THEN** research reports are displayed with title, abstract, author, broker name, stock/industry name, and date
- **AND** filters for report type (个股研报/行业研报), broker name, and stock code are available

#### Scenario: Download research report
- **WHEN** the user clicks the download icon on a research report
- **THEN** the system opens the report download URL in a new browser tab

### Requirement: Partial Data UX
The frontend SHALL indicate partial data status when backend returns degraded but successful results.

#### Scenario: Show partial data warning
- **WHEN** response contains `partial=true` and `failed_sources` is non-empty
- **THEN** the UI shows a non-blocking warning with failed source names
- **AND** still renders available data normally
