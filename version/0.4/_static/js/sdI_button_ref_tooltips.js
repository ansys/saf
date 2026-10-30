// _static/sd_button_ref_tooltips.js
document.addEventListener("DOMContentLoaded", () => {
    const buttons = document.querySelectorAll(".onboarding-cards a.sd-btn");

    buttons.forEach((a) => {
        // 1) Look for tooltip text directly on the anchor (varies by theme/version)
        const direct =
            a.getAttribute("title") ||
            a.getAttribute("data-tooltip") ||
            a.getAttribute("data-bs-title") ||
            a.getAttribute("aria-label");

        // 2) If it's not on the anchor, look for it on a nearby wrapper
        const wrapper =
            a.closest(".sd-btn-group, .sd-card, .sd-card-body, .sd-card-footer") ||
            a.parentElement;

        const wrapped =
            wrapper?.getAttribute("data-tooltip") ||
            wrapper?.getAttribute("title") ||
            wrapper?.getAttribute("data-bs-title");

        const tip = direct || wrapped;
        if (!tip) return;

        // Always set native browser tooltip support
        a.setAttribute("title", tip);

        // Only set Bootstrap tooltip attributes if Bootstrap exists
        if (window.bootstrap?.Tooltip) {
            a.setAttribute("data-bs-title", tip);
            a.setAttribute("data-bs-toggle", "tooltip");
        }
    });

    // Optional: initialize Bootstrap tooltips if your theme isn't doing it already
    if (window.bootstrap?.Tooltip) {
        document
            .querySelectorAll('.onboarding-cards [data-bs-toggle="tooltip"]')
            .forEach((el) => new bootstrap.Tooltip(el));
    }
});