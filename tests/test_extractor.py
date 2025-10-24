"""Tests for TuShare data extractor."""

import pytest
from datetime import datetime
import pandas as pd
from unittest.mock import Mock, patch

from src.stock_datasource.utils.extractor import TuShareExtractor


class TestExtractor:
    """Test TuShare data extractor."""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor instance with mock token."""
        with patch('src.stock_datasource.utils.extractor.settings') as mock_settings:
            mock_settings.TUSHARE_TOKEN = "test_token"
            mock_settings.TUSHARE_RATE_LIMIT = 120
            mock_settings.TUSHARE_MAX_RETRIES = 3
            return TuShareExtractor()
    
    @pytest.fixture
    def mock_tushare_pro(self):
        """Mock TuShare pro API."""
        with patch('tushare.pro_api') as mock_pro:
            yield mock_pro.return_value
    
    def test_extractor_initialization(self, extractor):
        """Test extractor initialization."""
        assert extractor.token == "test_token"
        assert extractor.rate_limit == 120
        assert extractor.max_retries == 3
    
    def test_rate_limiting(self, extractor):
        """Test rate limiting functionality."""
        # Test that rate limiting doesn't sleep when enough time has passed
        extractor._last_call_time = 0  # Long time ago
        start_time = datetime.now().timestamp()
        
        extractor._rate_limit()
        
        end_time = datetime.now().timestamp()
        # Should not sleep much since last call was long ago
        assert end_time - start_time < 0.1
    
    def test_get_trade_calendar(self, extractor, mock_tushare_pro):
        """Test trade calendar extraction."""
        # Mock response
        mock_data = pd.DataFrame({
            'exchange': ['SSE', 'SSE'],
            'cal_date': ['20230101', '20230102'],
            'is_open': [0, 1],
            'pretrade_date': ['20221230', '20230101']
        })
        mock_tushare_pro.trade_cal.return_value = mock_data
        
        result = extractor.get_trade_calendar('20230101', '20230102')
        
        assert len(result) == 2
        assert 'cal_date' in result.columns
        assert 'is_open' in result.columns
        mock_tushare_pro.trade_cal.assert_called_once()
    
    def test_get_stock_basic(self, extractor, mock_tushare_pro):
        """Test stock basic information extraction."""
        # Mock response
        mock_data = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'symbol': ['000001', '000002'],
            'name': ['平安银行', '万科A'],
            'list_date': ['19910403', '19910129'],
            'list_status': ['L', 'L']
        })
        mock_tushare_pro.stock_basic.return_value = mock_data
        
        result = extractor.get_stock_basic()
        
        assert len(result) == 2
        assert 'ts_code' in result.columns
        assert 'name' in result.columns
        mock_tushare_pro.stock_basic.assert_called_once()
    
    def test_get_daily_data(self, extractor, mock_tushare_pro):
        """Test daily data extraction."""
        # Mock response
        mock_data = pd.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20230102'],
            'open': [10.5],
            'high': [11.0],
            'low': [10.2],
            'close': [10.8],
            'pre_close': [10.5],
            'change': [0.3],
            'pct_chg': [2.86],
            'vol': [1000000],
            'amount': [10800000]
        })
        mock_tushare_pro.daily.return_value = mock_data
        
        result = extractor.get_daily_data('20230102')
        
        assert len(result) == 1
        assert 'close' in result.columns
        assert result.iloc[0]['close'] == 10.8
        mock_tushare_pro.daily.assert_called_once_with(trade_date='20230102')
    
    def test_get_adj_factor(self, extractor, mock_tushare_pro):
        """Test adjustment factor extraction."""
        # Mock response
        mock_data = pd.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20230102'],
            'adj_factor': [2.5]
        })
        mock_tushare_pro.adj_factor.return_value = mock_data
        
        result = extractor.get_adj_factor('20230102')
        
        assert len(result) == 1
        assert 'adj_factor' in result.columns
        assert result.iloc[0]['adj_factor'] == 2.5
        mock_tushare_pro.adj_factor.assert_called_once()
    
    def test_get_hk_basic_placeholder(self, extractor):
        """Test HK basic data placeholder (limited API calls)."""
        result = extractor.get_hk_basic()
        
        # Should return empty DataFrame with expected structure
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        expected_columns = ['ts_code', 'symbol', 'name', 'list_date', 'delist_date', 'list_status']
        assert list(result.columns) == expected_columns
    
    def test_get_hk_daily_placeholder(self, extractor):
        """Test HK daily data placeholder (limited API calls)."""
        result = extractor.get_hk_daily('20230102')
        
        # Should return empty DataFrame with expected structure
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        expected_columns = [
            'ts_code', 'trade_date', 'open', 'high', 'low', 'close', 
            'pre_close', 'change', 'pct_chg', 'vol', 'amount'
        ]
        assert list(result.columns) == expected_columns
    
    def test_validate_data_quality_success(self, extractor):
        """Test data quality validation with good data."""
        # Create valid test data
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'trade_date': ['20230102', '20230102'],
            'close': [10.8, 15.2],
            'vol': [1000000, 2000000]
        })
        
        result = extractor.validate_data_quality(test_data, '20230102')
        
        assert result['valid'] is True
        assert result['record_count'] == 2
        assert result['column_count'] == 4
        assert len(result['issues']) == 0
    
    def test_validate_data_quality_empty_data(self, extractor):
        """Test data quality validation with empty data."""
        test_data = pd.DataFrame()
        
        result = extractor.validate_data_quality(test_data, '20230102')
        
        assert result['valid'] is False
        assert 'DataFrame is empty' in result['issues']
    
    def test_validate_data_quality_missing_columns(self, extractor):
        """Test data quality validation with missing required columns."""
        test_data = pd.DataFrame({
            'trade_date': ['20230102', '20230102'],
            'close': [10.8, 15.2]
        })
        
        result = extractor.validate_data_quality(test_data, '20230102')
        
        assert result['valid'] is False
        assert any('Missing required columns' in issue for issue in result['issues'])
    
    def test_validate_data_quality_date_mismatch(self, extractor):
        """Test data quality validation with date mismatch."""
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20230103'],  # Different date
            'close': [10.8]
        })
        
        result = extractor.validate_data_quality(test_data, '20230102')
        
        assert result['valid'] is False
        assert any('Trade date mismatch' in issue for issue in result['issues'])
    
    def test_validate_data_quality_null_codes(self, extractor):
        """Test data quality validation with null ts_code values."""
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ', None],
            'trade_date': ['20230102', '20230102'],
            'close': [10.8, 15.2]
        })
        
        result = extractor.validate_data_quality(test_data, '20230102')
        
        assert result['valid'] is False
        assert any('null ts_code values' in issue for issue in result['issues'])
