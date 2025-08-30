# GitHub Pages Setup Guide

## Manual Setup (Recommended)

If the automatic enablement doesn't work, follow these steps to manually enable GitHub Pages:

### 1. Enable GitHub Pages

1. Go to your repository on GitHub
2. Click on **Settings** (in the repository menu)
3. Scroll down to **Pages** in the left sidebar
4. Under **Source**, select **GitHub Actions**
5. Click **Save**

### 2. Verify Permissions

Make sure your repository has the correct permissions:

1. Go to **Settings** → **Actions** → **General**
2. Under **Workflow permissions**, select:
   - ✅ **Read and write permissions**
   - ✅ **Allow GitHub Actions to create and approve pull requests**

### 3. Push Your Changes

Once Pages is enabled, push your changes to trigger the deployment:

```bash
git add .
git commit -m "Add GitHub Pages website"
git push origin main
```

### 4. Check Deployment Status

1. Go to the **Actions** tab in your repository
2. Look for the "Deploy GitHub Pages" workflow
3. Click on it to see the deployment progress
4. Once complete, your site will be available at:
   `https://yourusername.github.io/sibyl`

## Troubleshooting

### Error: "Get Pages site failed"

This usually means GitHub Pages isn't enabled yet. Follow the manual setup steps above.

### Error: "Missing environment" or "Failed to create deployment"

This means the GitHub Pages environment isn't properly configured. Follow these steps:

1. **Enable GitHub Pages Environment**:
   - Go to your repository Settings → Environments
   - Click "New environment"
   - Name it exactly: `github-pages`
   - Click "Configure environment"

2. **Set Environment Protection Rules** (optional but recommended):
   - Uncheck "Required reviewers" (unless you want manual approval)
   - Uncheck "Wait timer" 
   - Click "Save protection rules"

3. **Verify GitHub Pages Source**:
   - Go to Settings → Pages
   - Under "Source", select "GitHub Actions"
   - Save the settings

4. **Re-run the workflow**:
   - Go to Actions tab
   - Find the failed workflow
   - Click "Re-run all jobs"

### Error: "Permission denied"

Make sure your repository has the correct workflow permissions (step 2 above).

### Error: "No such file or directory: docs"

Make sure the `docs/` directory exists and contains `index.html`.

### Site Not Loading

1. Check the Actions tab for any deployment errors
2. Wait a few minutes for DNS propagation
3. Try accessing the site in an incognito/private browser window

## Alternative: Static Site Hosting

If GitHub Pages continues to have issues, you can also host the site on:

- **Netlify**: Drag and drop the `docs/` folder
- **Vercel**: Connect your GitHub repository
- **GitHub Pages (Legacy)**: Use the `gh-pages` branch method

## Local Testing

To test the website locally before deploying:

```bash
cd docs
python -m http.server 8000
# Then visit http://localhost:8000
```

Or use any other local web server of your choice.
