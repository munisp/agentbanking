# NLP Service

Natural Language Processing service for customer support and text analysis.

## Features

- **Sentiment Analysis** - Detect positive, negative, or neutral sentiment
- **Intent Detection** - Understand user intent from text
- **Entity Extraction** - Extract amounts, phone numbers, emails, dates
- **Language Detection** - Detect English, Yoruba, Hausa, Igbo

## API Endpoints

### Health Check
```
GET /health
```

### Sentiment Analysis
```
POST /analyze/sentiment
{
  "text": "I love this service!",
  "language": "en"
}
```

### Intent Detection
```
POST /analyze/intent
{
  "text": "I want to send money to my family",
  "context": {}
}
```

### Entity Extraction
```
POST /analyze/entities
{
  "text": "Transfer ₦50,000 to +2348012345678",
  "language": "en"
}
```

### Language Detection
```
POST /analyze/language
{
  "text": "Bawo ni?"
}
```

### Complete Analysis
```
POST /analyze/all
{
  "text": "I want to check my balance"
}
```

## Running

```bash
pip install -r requirements.txt
python main.py
```

Service runs on port 8010.

## Production

In production, replace rule-based implementations with:
- Transformer models (BERT, GPT) for sentiment and intent
- spaCy or Stanza for entity extraction
- fastText or langdetect for language detection
