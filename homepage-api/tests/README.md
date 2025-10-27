# Homepage API Unit Tests

Comprehensive unit tests for the Homepage Dashboard Backend API.

## Test Structure

```
homepage-api/
├── app.py                    # Main application
├── tests/
│   ├── __init__.py          # Test package marker
│   ├── conftest.py          # Pytest fixtures and configuration
│   ├── test_app.py          # Main test suite
│   └── README.md            # This file
├── pytest.ini               # Pytest configuration
└── requirements.txt         # Includes testing dependencies
```

## Running Tests

### Install Dependencies

```bash
cd homepage-api
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_app.py
```

### Run Specific Test Class

```bash
pytest tests/test_app.py::TestBOMWeatherEndpoint
```

### Run Specific Test Function

```bash
pytest tests/test_app.py::TestBOMWeatherEndpoint::test_bom_weather_success
```

### Run with Coverage Report

```bash
pytest --cov=app --cov-report=term-missing
```

### Run with HTML Coverage Report

```bash
pytest --cov=app --cov-report=html
# Open htmlcov/index.html in browser
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Extra Verbosity (show print statements)

```bash
pytest -vv -s
```

## Test Coverage

The test suite covers:

### ✅ Health Endpoint (`/api/health`)
- Basic health check functionality
- Response format validation

### ✅ BOM Weather Endpoint (`/api/bom/weather`)
- Successful weather data retrieval
- API error handling
- Caching behavior
- Data structure validation
- Mock weather API responses

### ✅ Transport NSW Endpoint (`/api/transport/departures`)
- Successful departure retrieval
- Delay calculation (positive, zero, negative)
- Platform parsing from correct JSON path
- Missing `stopId` parameter handling
- API error handling
- Invalid timestamp handling
- Missing platform data handling

### ✅ Error Handling
- 404 for unknown endpoints
- Generic exception handling
- Graceful degradation

### ✅ CORS Configuration
- CORS headers present on responses

## Test Organization

Tests are organized into classes by endpoint:

- **`TestHealthEndpoint`** - Health check tests
- **`TestBOMWeatherEndpoint`** - BOM weather API tests
- **`TestTransportNSWEndpoint`** - Transport NSW API tests
- **`TestErrorHandling`** - General error handling tests
- **`TestCORSHeaders`** - CORS configuration tests

## Mocking Strategy

The tests use `unittest.mock` to mock external dependencies:

- **`weather_api.get_location`** - Mocked for BOM weather tests
- **`requests.get`** - Mocked for Transport NSW API tests

This ensures:
- Tests run without external API dependencies
- Fast test execution
- Predictable test results
- No API rate limiting issues

## Continuous Integration

These tests can be integrated into CI/CD pipelines:

```bash
# In GitHub Actions, GitLab CI, etc.
pip install -r requirements.txt
pytest --cov=app --cov-report=xml
```

## Writing New Tests

When adding new endpoints to `app.py`:

1. Create new test class in `test_app.py`
2. Mock external dependencies
3. Test success cases
4. Test error cases
5. Test edge cases (missing params, invalid data, etc.)

Example:

```python
class TestNewEndpoint:
    """Tests for /api/new/endpoint"""

    @patch('app.external_api')
    def test_success_case(self, mock_api, client):
        mock_api.return_value = {'data': 'value'}
        response = client.get('/api/new/endpoint')
        assert response.status_code == 200
```

## Troubleshooting

### Import Errors

If you see import errors, ensure you're running pytest from the `homepage-api/` directory:

```bash
cd homepage-api
pytest
```

### Environment Variables

Test fixtures in `conftest.py` automatically set required environment variables.
If you need different values, modify `conftest.py`.

### Module Not Found

Ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```
