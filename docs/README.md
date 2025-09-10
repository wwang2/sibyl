# 🔮 Sybil Prediction Dashboard

Interactive dashboard for visualizing AI-powered predictions with structured evidence chains.

## 🚀 Quick Start

1. **Generate prediction data:**
   ```bash
   make run-enhanced-prediction
   ```

2. **Start the local server:**
   ```bash
   make serve-dashboard
   ```

3. **Open the dashboard:**
   - Navigate to: http://localhost:8080
   - The dashboard will automatically load the latest prediction data

## 📊 Features

- **Real-time Data Loading**: Automatically fetches latest predictions and evidence
- **Interactive Charts**: Confidence distribution and activity trends
- **Evidence Chains**: Detailed view of supporting evidence for each prediction
- **Auto-refresh**: Updates every 5 minutes
- **Responsive Design**: Works on desktop and mobile

## 🔧 Technical Details

- **Frontend**: Pure HTML/CSS/JavaScript with Chart.js
- **Data Source**: JSON files exported from the enhanced prediction workflow
- **Server**: Simple Python HTTP server with CORS support
- **Data Format**: Structured JSON with predictions, evidence, and metadata

## 📁 File Structure

```
docs/
├── index.html              # Main dashboard
├── serve.py                # Local HTTP server
├── data/
│   ├── predictions.json    # Detailed prediction data
│   └── prediction_summary.json  # Aggregate statistics
└── README.md               # This file
```

## 🛠️ Troubleshooting

**"Failed to fetch" error:**
- Make sure you're using the local server (`make serve-dashboard`)
- Don't open the HTML file directly in browser (file:// protocol won't work)

**No data showing:**
- Run `make run-enhanced-prediction` first to generate data
- Check that `docs/data/` contains JSON files

**Server won't start:**
- Make sure port 8080 is available
- Try a different port: `cd docs && python3 serve.py 8081`

## 🌐 GitHub Pages Deployment

The dashboard is ready for GitHub Pages deployment:

1. Push the `docs/` folder to your repository
2. Enable GitHub Pages in repository settings
3. Set source to `/docs` folder
4. The dashboard will be available at `https://yourusername.github.io/sybil/`

## 📈 Data Schema

### Prediction Summary
```json
{
  "timestamp": "2025-09-07T19:38:55.263841",
  "total_predictions": 12,
  "average_confidence": 0.85,
  "confidence_distribution": {
    "low": 0,
    "medium": 0,
    "high": 12
  },
  "recent_activity": {
    "predictions_last_7_days": 12,
    "average_confidence_recent": 0.85
  }
}
```

### Predictions Data
```json
{
  "timestamp": "2025-09-07T19:38:55.263841",
  "predictions": [
    {
      "id": "prediction_id",
      "probability": 0.75,
      "rationale": "Detailed reasoning...",
      "evidence_sources": [
        {
          "rank": 1,
          "title": "Evidence Title",
          "url": "https://source.com",
          "relevance_score": 0.88,
          "source_type": "news_article",
          "reliability": "high"
        }
      ]
    }
  ]
}
```