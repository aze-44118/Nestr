# 🎙️ Nestr - AI-Powered Podcast Generation Platform

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/your-username/nestr)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-red.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Nestr is an AI-powered platform that generates personalized podcasts on any topic using OpenAI's GPT models and text-to-speech technology. Create custom audio content with simple commands via Telegram or REST API.

## ✨ Features

- **🎯 Multiple Podcast Types**: Wellness, news briefing, and dialogue formats
- **🤖 AI-Powered**: Uses OpenAI GPT-4 for content generation
- **🎵 High-Quality Audio**: OpenAI TTS with multiple voice options
- **📱 Telegram Bot**: Easy-to-use bot interface with onboarding system
- **🔗 RSS Feeds**: Personal RSS feeds for each user
- **☁️ Cloud Storage**: Supabase integration for scalable storage
- **🔐 Secure Access**: User authentication and access control
- **🌍 Multi-language**: Support for French and English

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key
- Supabase account
- Telegram Bot Token (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/nestr.git
   cd nestr
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

5. **Run the application**
   ```bash
   # Development
   python start_dev.py
   
   # Production
   python start_prod.py
   ```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Supabase Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_PODCAST_BUCKET=podcasts

# Telegram Configuration (Optional)
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_SERVICE_ID=your_telegram_user_id

# Application Settings
DEBUG=false
LOG_LEVEL=INFO
DEFAULT_LANG=fr
```

### Supabase Setup

1. Create a new Supabase project
2. Create a `podcasts` storage bucket
3. Set up the following tables:

```sql
-- Users table
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Episodes table
CREATE TABLE episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    intent TEXT NOT NULL,
    language TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    audio_path TEXT NOT NULL,
    audio_url TEXT NOT NULL,
    duration_sec INTEGER NOT NULL,
    published_at TIMESTAMP DEFAULT NOW(),
    raw_meta JSONB
);
```

## 🤖 Telegram Bot Usage

### Setup

1. Create a bot with [@BotFather](https://t.me/botfather)
2. Set the webhook URL: `https://yourdomain.com/telegram/webhook`
3. Configure bot commands using `/setcommands`

### Commands

- `/wellness [topic]` - Generate a wellness podcast
- `/briefing [topic]` - Generate a news briefing podcast
- `/other [topic]` - Generate a dialogue podcast
- `/help` - Show available commands

### Examples

```
/wellness Create a podcast about morning meditation
/briefing Summarize this week's tech news
/other Discuss AI trends in 2024
```

## 🔌 API Usage

### REST Endpoints

#### Generate Podcast
```http
POST /webhooks/generate
Content-Type: application/json

{
    "user_id": "user-123",
    "intent": "wellness",
    "message": "Create a podcast about meditation",
    "lang": "fr"
}
```

#### Health Check
```http
GET /healthz
```

### Response Format

```json
{
    "status": "ok",
    "rss_url": "https://yourdomain.com/rss/user-123.xml",
    "message": "Podcast generated successfully!"
}
```

## 🏗️ Architecture

```
nestr/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── models.py            # Pydantic models
│   ├── deps.py              # Dependency injection
│   ├── pipeline_manager.py  # Podcast generation pipeline
│   ├── pipelines/           # Individual pipeline modules
│   │   ├── wellness_pipeline.py
│   │   ├── briefing_pipeline.py
│   │   └── other_pipeline.py
│   ├── prompts/             # AI prompts and templates
│   ├── supabase_client.py   # Database client
│   ├── openai_client.py     # OpenAI API client
│   └── utils.py             # Utility functions
├── requirements.txt         # Python dependencies
├── start_dev.py            # Development server
├── start_prod.py           # Production server
└── README.md               # This file
```

## 🔧 Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app
```

### Code Quality

```bash
# Format code
black app/

# Lint code
flake8 app/

# Type checking
mypy app/
```

### Adding New Pipelines

1. Create a new pipeline class in `app/pipelines/`
2. Extend `BasePipeline` class
3. Implement required methods
4. Register in `PipelineManager`

## 📦 Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8080

CMD ["python", "start_prod.py"]
```

### Environment Variables

Ensure all required environment variables are set in your deployment environment.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [OpenAI](https://openai.com) for GPT and TTS APIs
- [Supabase](https://supabase.com) for backend services
- [FastAPI](https://fastapi.tiangolo.com) for the web framework
- [Telegram](https://telegram.org) for the bot platform

## 📞 Support

- 📧 Email: support@nestr.app
- 💬 Discord: [Join our community](https://discord.gg/nestr)
- 📖 Documentation: [docs.nestr.app](https://docs.nestr.app)
- 🐛 Issues: [GitHub Issues](https://github.com/your-username/nestr/issues)

---

Made with ❤️ by the Nestr team