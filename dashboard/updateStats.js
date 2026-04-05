const VM_IP = "172.169.248.121"

const PROCESSING_STATS_API_URL = `http://${VM_IP}:8100/stats`


const HEALTH_CHECK_API_URL = `http://${VM_IP}:8120/healthcheck/health-status`


const ANALYZER_STATS_API_URL = `http://${VM_IP}:5005/analyzer/stats`
const ANALYZER_PERFORMANCE_API_BASE = `http://${VM_IP}:5005/analyzer/performance`
const ANALYZER_ERROR_API_BASE = `http://${VM_IP}:5005/analyzer/error`

/**
 * Generic fetch function to retrieve data from API endpoints
 * @param {string} url - The API endpoint URL
 * @param {function} callback - Function to call with the result
 */
const makeReq = (url, cb) => {
    fetch(url)
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        })
        .then((result) => {
            console.log("Received data from " + url + ": ", result);
            cb(result);
        })
        .catch((error) => {
            console.error("Error fetching from " + url + ":", error);
            updateErrorMessages(error.message);
        });
};

/**
 * Update a code div with formatted JSON
 * @param {object} result - The data to display
 * @param {string} elemId - The element ID to update
 */
const updateCodeDiv = (result, elemId) => {
    document.getElementById(elemId).innerText = JSON.stringify(result, null, 2);
};

/**
 * Get current date and time as a formatted string
 * @returns {string} - Formatted date/time string
 */
const getLocaleDateStr = () => (new Date()).toLocaleString();


/**
 * Format health status for display
 * @param {object} result - The health status object
 * @returns {string} Formatted string with service statuses
 */
const formatHealthStatus = (result) => {
    let display = '';
    
    for (const [service, status] of Object.entries(result)) {
        if (service === 'last_update') continue;
        
        const icon = status === 'Up' ? '✓ ' : '✗ ';
        const displayName = service.charAt(0).toUpperCase() + service.slice(1);
        display += `${icon}${displayName}: ${status}\n`;
    }
    
    if (result.last_update) {
        display += `\nLast checked: ${result.last_update}`;
    }
    
    return display;
};

/**
 * Main function to fetch all statistics and update the dashboard
 */
const getStats = () => {
    console.log("Updating statistics...");
    document.getElementById("last-updated-value").innerText = getLocaleDateStr();
    
    // Fetch Processing Service Stats (UNCHANGED - your original code)
    makeReq(PROCESSING_STATS_API_URL, (result) => {
        updateCodeDiv(result, "processing-stats");
    });
    
  
    makeReq(ANALYZER_STATS_API_URL, (stats) => {
        updateCodeDiv(stats, "analyzer-stats");
        
        // DYNAMIC: Pick random performance event index based on stats
        if (stats.num_performance_events > 0) {
            const randomPerfIndex = Math.floor(
                Math.random() * stats.num_performance_events
            );
            console.log(`Fetching random performance event at index ${randomPerfIndex}`);
            
            // ✨ UPDATE HEADING WITH ACTUAL INDEX (not hardcoded 0)
            document.getElementById("performance-event-heading").innerText = 
                `Performance Event (Index ${randomPerfIndex})`;
            
            const perfUrl = `${ANALYZER_PERFORMANCE_API_BASE}?index=${randomPerfIndex}`;
            makeReq(perfUrl, (result) => {
                updateCodeDiv(result, "event-performance");
            });
        } else {
            document.getElementById("event-performance").innerText = 
                "No performance events available";
            document.getElementById("performance-event-heading").innerText = 
                "Performance Event (No data)";
        }
        
        // DYNAMIC: Pick random error event index based on stats
        if (stats.num_error_events > 0) {
            const randomErrorIndex = Math.floor(
                Math.random() * stats.num_error_events
            );
            console.log(`Fetching random error event at index ${randomErrorIndex}`);
            
            // ✨ UPDATE HEADING WITH ACTUAL INDEX (not hardcoded 0)
            document.getElementById("error-event-heading").innerText = 
                `Error Event (Index ${randomErrorIndex})`;
            
            const errorUrl = `${ANALYZER_ERROR_API_BASE}?index=${randomErrorIndex}`;
            makeReq(errorUrl, (result) => {
                updateCodeDiv(result, "event-error");
            });
        } else {
            document.getElementById("event-error").innerText = 
                "No error events available";
            document.getElementById("error-event-heading").innerText = 
                "Error Event (No data)";
        }
    });
    
    
    makeReq(HEALTH_CHECK_API_URL, (result) => {
        const formatted = formatHealthStatus(result);
        document.getElementById("health-status").innerText = formatted;
        document.getElementById("health-last-update").innerText = 
            `Last check: ${result.last_update || 'N/A'}`;
    });
};

/**
 * Display error messages to the user
 * @param {string} message - The error message to display
 */
const updateErrorMessages = (message) => {
    const id = Date.now();
    console.log("Creating error message:", id);
    
    const msg = document.createElement("div");
    msg.id = `error-${id}`;
    msg.innerHTML = `<p>⚠️ Error occurred at ${getLocaleDateStr()}</p><code>${message}</code>`;
    
    const messagesDiv = document.getElementById("messages");
    messagesDiv.style.display = "block";
    messagesDiv.prepend(msg);
    
    // Auto-remove error message after 7 seconds
    setTimeout(() => {
        const elem = document.getElementById(`error-${id}`);
        if (elem) {
            elem.remove();
        }
        // Hide messages container if empty
        if (messagesDiv.children.length === 0) {
            messagesDiv.style.display = "none";
        }
    }, 7000);
};

/**
 * Initialize the dashboard - called when DOM is fully loaded
 */
const setup = () => {
    console.log("Dashboard initialized");
    // Fetch stats immediately
    getStats();
    // Update every 3 seconds (can adjust between 2-4 as per lab requirements)
    setInterval(() => getStats(), 3000);
};

// Wait for DOM to be fully loaded before setting up
document.addEventListener('DOMContentLoaded', setup);