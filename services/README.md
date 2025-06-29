# Services Module

This module contains all service classes for external API integrations and data processing logic.

## Modules

### openai_service.py
Service for integration with the OpenAI ChatGPT API:

- **API Client Management**: Initializes and manages the AsyncOpenAI Client
- **Factcheck Requests**: Structured prompts for consistent factchecks
- **Error Handling**: Robust handling of rate limits, API errors and timeouts
- **Configurable Parameters**: Uses environment variables for API configuration

#### Main Functions:
- `is_available()`: Checks if the service is available and configured
- `get_factcheck(message_content, user_name)`: Performs factcheck request to ChatGPT
- `_create_factcheck_prompt(message_content, user_name)`: Creates structured prompts

#### Features:
- **Structured Prompts**: Consistent formatting for better AI responses
- **German Localization**: System prompt and responses in German
- **Temperature Optimization**: Low temperature (0.3) for factual responses
- **Token Limiting**: Configurable maximum token count
- **Timeout Handling**: 30-second timeout for API requests

#### Prompt Structure:
```
System: Du bist ein hilfreicher Assistent, der Faktenchecks und ergänzende Informationen bereitstellt...

User: Analysiere folgende Discord-Nachricht auf Fakten und gib ergänzende Informationen:
"[Message Content]"

Bitte antworte kurz und strukturiert mit:
1. 🔍 Faktencheck zu relevanten Aussagen
2. 💡 Ergänzende/interessante Informationen
3. 📚 Kontext oder Hintergrundinformationen
```

## Configuration

The service uses the following environment variables:

- `OPENAI_API_KEY`: API key for OpenAI (required)
- `FACTCHECK_MODEL`: Model to use (default: gpt-3.5-turbo)
- `FACTCHECK_MAX_TOKENS`: Maximum tokens per response (default: 200)
- `FACTCHECK_ENABLED`: Enable/disable feature

## Error Handling

The service handles various error types:

- **RateLimitError**: Warning when rate limits are exceeded
- **APIError**: Logging of API-specific errors
- **TimeoutError**: Handling of connection timeouts
- **General Exceptions**: Logging of unexpected errors

## Integration

The OpenAI Service is used by the `FactcheckHandler` and controlled via configuration in `config.py`.

## Logging

All service operations are logged:
- Successful API calls with response length
- Failed requests with error type
- Availability checks and configuration warnings
