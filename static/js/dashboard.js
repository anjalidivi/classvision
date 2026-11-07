
document.addEventListener("DOMContentLoaded", () => {

    // ==================================================
    // 1. EXISTING DASHBOARD POPUP FUNCTIONALITY
    // ==================================================

    const cards = document.querySelectorAll(".stat-card");

    const modal = document.createElement("div");
    modal.className = "modal-overlay";
    modal.id = "dashboardModal";

    modal.innerHTML = `
        <div class="modal-box" role="dialog"
             aria-modal="true" aria-labelledby="modalTitle">
            <div class="modal-header">
                <h3 id="modalTitle">Dashboard Details</h3>
                <button class="modal-close" id="closeModal"
                        aria-label="Close popup">&times;</button>
            </div>
            <div id="modalContent"></div>
        </div>
    `;

    document.body.appendChild(modal);

    const title = modal.querySelector("#modalTitle");
    const content = modal.querySelector("#modalContent");
    const closeButton = modal.querySelector("#closeModal");

    function closeModal() {
        modal.classList.remove("active");
    }

    function openModal(heading, description) {
        title.textContent = heading;
        content.textContent = description;
        modal.classList.add("active");
        closeButton.focus();
    }

    cards.forEach((card) => {
        card.setAttribute("role", "button");
        card.setAttribute("tabindex", "0");

        function showDetails() {
            const heading =
                card.querySelector("span")?.textContent.trim()
                || "Dashboard Details";

            const value =
                card.querySelector("h2")?.textContent.trim()
                || "--";

            const description =
                card.querySelector("small")?.textContent.trim()
                || "No additional information available.";

            openModal(
                heading,
                `Current value: ${value}. ${description}`
            );
        }

        card.addEventListener("click", showDetails);

        card.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                showDetails();
            }
        });
    });

    closeButton.addEventListener("click", closeModal);

    modal.addEventListener("click", (event) => {
        if (event.target === modal) {
            closeModal();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && modal.classList.contains("active")) {
            closeModal();
        }
    });


    // ==================================================
    // 2. DASHBOARD ANALYTICS
    // ==================================================

    const dashboardGrid = document.querySelector(".dashboard-grid");

    if (!dashboardGrid) {
        return;
    }

    const analyticsSection = document.createElement("section");
    analyticsSection.id = "liveAnalytics";

    analyticsSection.innerHTML = `
        <style>
            #liveAnalytics {
                margin-top: 28px;
            }

            #liveAnalytics .analytics-heading {
                margin-bottom: 18px;
            }

            #liveAnalytics .analytics-heading h2 {
                margin-bottom: 5px;
            }

            #liveAnalytics .analytics-heading p {
                opacity: 0.7;
            }

            #liveAnalytics .analytics-summary {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 16px;
                margin-bottom: 20px;
            }

            #liveAnalytics .analytics-card,
            #liveAnalytics .analytics-panel {
                padding: 20px;
                border-radius: 14px;
                background: var(--card-bg, #ffffff);
                border: 1px solid var(--border-color, #e5e7eb);
                min-width: 0;
            }

            #liveAnalytics .analytics-card span {
                font-size: 12px;
                opacity: 0.7;
            }

            #liveAnalytics .analytics-card h2 {
                font-size: 28px;
                margin: 10px 0 0;
            }

            #liveAnalytics .analytics-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 18px;
            }

            #liveAnalytics .analytics-panel h3 {
                margin: 0 0 18px;
            }

            #liveAnalytics .chart-container {
                position: relative;
                height: 280px;
            }

            #liveAnalytics table {
                width: 100%;
                border-collapse: collapse;
                font-size: 13px;
            }

            #liveAnalytics th,
            #liveAnalytics td {
                padding: 12px 8px;
                text-align: left;
                border-bottom: 1px solid var(--border-color, #e5e7eb);
            }

            #liveAnalytics .analytics-empty {
                padding: 18px 0;
                opacity: 0.7;
            }

            #liveAnalytics .alert-item {
                padding: 12px;
                margin-bottom: 10px;
                border-radius: 9px;
                background: rgba(220, 38, 38, 0.08);
            }

            #liveAnalytics .analytics-status {
                font-size: 12px;
                margin-bottom: 15px;
                opacity: 0.7;
            }

            @media (max-width: 800px) {
                #liveAnalytics .analytics-grid {
                    grid-template-columns: 1fr;
                }

                #liveAnalytics .analytics-summary {
                    grid-template-columns: 1fr;
                }
            }
        </style>

        <div class="analytics-heading">
            <h2>Classroom Engagement Analytics</h2>
            <a href="/download-engagement-report"
   class="primary-button"
   style="display:inline-block; text-decoration:none; margin:12px 0;">
    Download Engagement Report
</a>
            <p>Live database analytics and student engagement insights</p>
        </div>

        <div id="analyticsStatus" class="analytics-status">
            Loading classroom analytics...
        </div>

        <div class="analytics-summary">
            <div class="analytics-card">
                <span>CLASSROOM AVERAGE ENGAGEMENT</span>
                <h2 id="analyticsAverage">--</h2>
            </div>

            <div class="analytics-card">
                <span>TOTAL ENGAGEMENT RECORDS</span>
                <h2 id="analyticsRecords">--</h2>
            </div>

            <div class="analytics-card">
                <span>STUDENTS MONITORED</span>
                <h2 id="analyticsStudents">--</h2>
            </div>
        </div>

        <div class="analytics-grid">

            <div class="analytics-panel">
                <h3>Engagement Distribution</h3>
                <div class="chart-container">
                    <canvas id="distributionChart"></canvas>
                </div>
            </div>

            <div class="analytics-panel">
                <h3>Engagement Trends</h3>
                <div class="chart-container">
                    <canvas id="trendsChart"></canvas>
                </div>
            </div>

            <div class="analytics-panel">
                <h3>Student-wise Engagement</h3>
                <div class="chart-container">
                    <canvas id="studentsChart"></canvas>
                </div>
            </div>

            <div class="analytics-panel">
                <h3>Low Engagement Alerts</h3>
                <div id="analyticsAlerts">
                    Loading alerts...
                </div>
            </div>

            <div class="analytics-panel">
                <h3>Student Engagement Details</h3>
                <div id="studentAnalyticsTable">
                    Loading student details...
                </div>
            </div>

            <div class="analytics-panel">
                <h3>Engagement Heatmap Data</h3>
                <div id="engagementHeatmap">
                    Loading engagement history...
                </div>
            </div>

        </div>
    `;

    dashboardGrid.insertAdjacentElement("afterend", analyticsSection);


    // ==================================================
    // 3. HELPER FUNCTIONS
    // ==================================================

    function setText(id, value) {
        const element = document.getElementById(id);

        if (element) {
            element.textContent = value;
        }
    }

    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, (character) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        })[character]);
    }

    async function fetchAnalytics(endpoint) {
        const response = await fetch(endpoint);

        if (!response.ok) {
            throw new Error(`Request failed: ${endpoint}`);
        }

        const data = await response.json();

        if (data.success === false) {
            throw new Error(data.message || "Analytics request failed");
        }

        return data;
    }


    // ==================================================
    // 4. CLASSROOM OVERVIEW
    // ==================================================

    async function loadOverview() {
        const data = await fetchAnalytics("/api/analytics/overview");

        setText(
            "analyticsAverage",
            `${Number(data.classroom_average || 0).toFixed(2)}%`
        );

        setText("analyticsRecords", data.total_records ?? 0);
        setText("analyticsStudents", data.students_monitored ?? 0);
    }


    // ==================================================
    // 5. ENGAGEMENT DISTRIBUTION CHART
    // ==================================================

    async function loadDistribution() {
        const data = await fetchAnalytics("/api/analytics/distribution");

        const labels = Object.keys(data.distribution || {});
        const values = Object.values(data.distribution || {});

        const canvas = document.getElementById("distributionChart");

        if (!canvas || typeof Chart === "undefined") {
            throw new Error("Chart.js is unavailable.");
        }
        if (Chart.getChart(canvas)) {
    Chart.getChart(canvas).destroy();
}

        new Chart(canvas, {
            type: "doughnut",
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: [
                        "#16a34a",
                        "#eab308",
                        "#f97316",
                        "#dc2626"
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom"
                    }
                }
            }
        });
    }


    // ==================================================
    // 6. ENGAGEMENT TRENDS CHART
    // ==================================================

    async function loadTrends() {
        const data = await fetchAnalytics("/api/analytics/trends?days=7");

        const trends = data.trends || [];

        const canvas = document.getElementById("trendsChart");

        if (!canvas || typeof Chart === "undefined") {
            throw new Error("Chart.js is unavailable.");
        }

        new Chart(canvas, {
            type: "line",
            data: {
                labels: trends.map(item => item.date),
                datasets: [{
                    label: "Average Engagement",
                    data: trends.map(item => item.average_engagement),
                    borderColor: "#2563eb",
                    backgroundColor: "rgba(37, 99, 235, 0.15)",
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    }


    // ==================================================
    // 7. STUDENT-WISE ENGAGEMENT
    // ==================================================

    async function loadStudents() {
        const data = await fetchAnalytics("/api/analytics/students");

        const students = data.students || [];

        const table = document.getElementById("studentAnalyticsTable");

        if (students.length === 0) {
            table.innerHTML =
                '<p class="analytics-empty">No student engagement data available.</p>';
        } else {
            table.innerHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>Student</th>
                            <th>ID</th>
                            <th>Average</th>
                            <th>Records</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${students.map(student => `
                            <tr>
                                <td>${escapeHTML(student.name)}</td>
                                <td>${escapeHTML(student.student_id)}</td>
                                <td>${Number(student.average_engagement).toFixed(2)}%</td>
                                <td>${student.total_records}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            `;
        }

        const canvas = document.getElementById("studentsChart");

        if (!canvas || typeof Chart === "undefined") {
            throw new Error("Chart.js is unavailable.");
        }

        new Chart(canvas, {
            type: "bar",
            data: {
                labels: students.map(student => student.name),
                datasets: [{
                    label: "Average Engagement",
                    data: students.map(student => student.average_engagement),
                    backgroundColor: "#6366f1"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    }


    // ==================================================
    // 8. LOW ENGAGEMENT ALERTS
    // ==================================================

    async function loadAlerts() {
        const data = await fetchAnalytics("/api/analytics/alerts?threshold=40");

        const container = document.getElementById("analyticsAlerts");
        const alerts = data.alerts || [];

        if (alerts.length === 0) {
            container.innerHTML =
                '<p class="analytics-empty">No low-engagement alerts.</p>';
            return;
        }

        container.innerHTML = alerts.map(alert => `
            <div class="alert-item">
                <strong>${escapeHTML(alert.name)}</strong>
                <p>${escapeHTML(alert.message)}</p>
                <small>
                    Average engagement:
                    ${Number(alert.average_engagement).toFixed(2)}%
                </small>
            </div>
        `).join("");
    }


    // ==================================================
    // 9. ENGAGEMENT HEATMAP DATA
    // ==================================================

    async function loadHeatmap() {
        const data = await fetchAnalytics("/api/analytics/heatmap");

        const container = document.getElementById("engagementHeatmap");
        const records = data.heatmap || [];

        if (records.length === 0) {
            container.innerHTML =
                '<p class="analytics-empty">No engagement history available.</p>';
            return;
        }

        container.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Student</th>
                        <th>Date</th>
                        <th>Engagement</th>
                    </tr>
                </thead>
                <tbody>
                    ${records.map(record => `
                        <tr>
                            <td>${escapeHTML(record.name)}</td>
                            <td>${escapeHTML(record.date)}</td>
                            <td>${Number(record.average_engagement).toFixed(2)}%</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `;
    }


    // ==================================================
    // 10. LOAD ALL ANALYTICS
    // ==================================================

    async function loadDashboardAnalytics() {
        const status = document.getElementById("analyticsStatus");

        const tasks = [
            loadOverview(),
            loadDistribution(),
            loadTrends(),
            loadStudents(),
            loadAlerts(),
            loadHeatmap()
        ];

        const results = await Promise.allSettled(tasks);

        const failed = results.filter(
            result => result.status === "rejected"
        );

        if (failed.length === 0) {
            status.textContent = "Analytics loaded successfully.";
        } else {
            status.textContent =
                `${failed.length} analytics section(s) could not load. Check that Flask and the analytics APIs are running.`;

            console.error("Dashboard analytics errors:", failed);
        }
    }

    loadDashboardAnalytics();
    setInterval(loadDashboardAnalytics, 30000);

});
