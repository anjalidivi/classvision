
document.addEventListener("DOMContentLoaded", () => {
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
});
