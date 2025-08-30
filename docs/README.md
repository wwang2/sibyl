# Signal Loom - GitHub Pages

This directory contains the GitHub Pages website for the Signal Loom project.

## Files

- `index.html` - Main website page with old-school Times New Roman styling
- `script.js` - Dynamic JavaScript features and interactive elements
- `style.css` - Additional CSS styling for retro/old-school appearance
- `README.md` - This file

## Features

- **Old-School Design**: Times New Roman font, classic styling, retro aesthetics
- **Dynamic Visualizations**: Interactive charts showing system architecture, data flow, and metrics
- **Real-Time Updates**: Simulated system status updates and activity monitoring
- **Interactive Elements**: Clickable code blocks, hover effects, and notifications
- **Responsive Design**: Works on desktop and mobile devices
- **Print-Friendly**: Optimized for printing with clean layouts

## Deployment

The website is automatically deployed to GitHub Pages when changes are pushed to the main branch via the GitHub Actions workflow in `.github/workflows/pages.yml`.

## Local Development

To view the website locally:

1. Open `index.html` in a web browser
2. Or serve it with a local web server:
   ```bash
   # Python 3
   python -m http.server 8000
   
   # Python 2
   python -m SimpleHTTPServer 8000
   
   # Node.js
   npx serve .
   ```

## Customization

- Modify `index.html` for content changes
- Update `script.js` for interactive features
- Adjust `style.css` for styling modifications
- Charts are generated using Chart.js library

## Browser Compatibility

The website is designed to work with modern browsers while maintaining an old-school aesthetic. It uses:
- Chart.js for visualizations
- Modern CSS Grid and Flexbox
- ES6+ JavaScript features
- Progressive enhancement for older browsers
