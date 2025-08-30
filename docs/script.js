// Signal Loom - Dynamic Website Features
// Old-school JavaScript with modern functionality

class SignalLoomDashboard {
    constructor() {
        this.lastUpdate = new Date();
        this.systemStatus = {
            discoveryAgent: 'active',
            assessorAgent: 'active',
            database: 'connected',
            llmMode: 'offline'
        };
        this.init();
    }

    init() {
        this.updateSystemStatus();
        this.startRealTimeUpdates();
        this.addInteractiveFeatures();
    }

    updateSystemStatus() {
        // Simulate real-time status updates
        const statusElements = document.querySelectorAll('.status');
        statusElements.forEach(element => {
            if (element.textContent.includes('Discovery Agent')) {
                element.className = `status ${this.systemStatus.discoveryAgent}`;
            } else if (element.textContent.includes('Assessor Agent')) {
                element.className = `status ${this.systemStatus.assessorAgent}`;
            } else if (element.textContent.includes('Database')) {
                element.className = `status ${this.systemStatus.database}`;
            } else if (element.textContent.includes('LLM Mode')) {
                element.className = `status ${this.systemStatus.llmMode}`;
            }
        });
    }

    startRealTimeUpdates() {
        // Update every 30 seconds
        setInterval(() => {
            this.simulateSystemActivity();
            this.updateSystemStatus();
            this.updateCharts();
        }, 30000);
    }

    simulateSystemActivity() {
        // Simulate system activity changes
        const activities = ['active', 'inactive', 'testing'];
        const randomActivity = activities[Math.floor(Math.random() * activities.length)];
        
        // Randomly update one system component
        const components = Object.keys(this.systemStatus);
        const randomComponent = components[Math.floor(Math.random() * components.length)];
        this.systemStatus[randomComponent] = randomActivity;
    }

    updateCharts() {
        // Update chart data with new values
        const charts = Chart.instances;
        charts.forEach(chart => {
            if (chart.canvas.id === 'activityChart') {
                // Update activity chart with new data
                const newData = chart.data.datasets[0].data;
                newData.shift(); // Remove first element
                newData.push(Math.floor(Math.random() * 25) + 5); // Add new random value
                chart.update('none');
            }
        });
    }

    addInteractiveFeatures() {
        // Add click handlers for code blocks
        const codeBlocks = document.querySelectorAll('.code-block');
        codeBlocks.forEach(block => {
            block.addEventListener('click', () => {
                this.copyToClipboard(block.textContent);
                this.showNotification('Code copied to clipboard!');
            });
            
            // Add visual feedback
            block.style.cursor = 'pointer';
            block.title = 'Click to copy';
        });

        // Add hover effects for sections
        const sections = document.querySelectorAll('.section');
        sections.forEach(section => {
            section.addEventListener('mouseenter', () => {
                section.style.transform = 'translateY(-2px)';
                section.style.transition = 'transform 0.3s ease';
            });
            
            section.addEventListener('mouseleave', () => {
                section.style.transform = 'translateY(0)';
            });
        });
    }

    copyToClipboard(text) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text);
        } else {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
        }
    }

    showNotification(message) {
        // Create old-school notification
        const notification = document.createElement('div');
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background-color: #ffffcc;
            border: 2px solid #ffcc00;
            padding: 10px 20px;
            font-family: 'Times New Roman', serif;
            font-size: 14px;
            z-index: 1000;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
        `;
        
        document.body.appendChild(notification);
        
        // Remove after 3 seconds
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 3000);
    }

    // Method to simulate API calls
    async fetchSystemMetrics() {
        try {
            // Simulate API call delay
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            return {
                totalRuns: Math.floor(Math.random() * 1000) + 500,
                successRate: Math.floor(Math.random() * 20) + 80,
                avgResponseTime: Math.floor(Math.random() * 500) + 200,
                lastRun: new Date().toISOString()
            };
        } catch (error) {
            console.error('Failed to fetch metrics:', error);
            return null;
        }
    }

    // Method to display system metrics
    async displayMetrics() {
        const metrics = await this.fetchSystemMetrics();
        if (metrics) {
            console.log('System Metrics:', metrics);
            // Could update UI elements with real metrics here
        }
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', function() {
    const dashboard = new SignalLoomDashboard();
    
    // Add some old-school console logging
    console.log('%cSignal Loom Dashboard Initialized', 'color: #000; font-family: Times New Roman; font-size: 16px; font-weight: bold;');
    console.log('%cSystem Status: Online', 'color: #008000; font-family: Times New Roman; font-size: 12px;');
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'r') {
            e.preventDefault();
            dashboard.displayMetrics();
        }
    });
});

// Old-school utility functions
function formatDate(date) {
    return date.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function generateSystemReport() {
    const report = {
        timestamp: formatDate(new Date()),
        status: 'operational',
        components: {
            discovery: 'active',
            assessor: 'active',
            database: 'connected',
            llm: 'offline'
        }
    };
    
    console.log('System Report:', report);
    return report;
}

// Export for potential use in other scripts
window.SignalLoomDashboard = SignalLoomDashboard;
window.generateSystemReport = generateSystemReport;
