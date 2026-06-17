<template>
    <div :data-trigger-key="trigger_key" style="display: none;"></div>
</template>

<script>
module.exports = {
    props: {
        trigger_key: {
            type: String,
            default: "",
        },
    },
    methods: {
        hideIntensityByDefault() {
            if (typeof window === "undefined") {
                return;
            }

            document.querySelectorAll(".leaflet-container").forEach((map) => {
                if (map.dataset.intensityDefaultHandledKey === this.trigger_key) {
                    return;
                }

                const labels = map.querySelectorAll(".leaflet-control-layers-overlays label");
                let handled = false;
                labels.forEach((label) => {
                    const text = (label.textContent || "").trim().toLowerCase();
                    if (text !== "intensity") {
                        return;
                    }

                    const checkbox = label.querySelector("input[type='checkbox']");
                    if (!checkbox) {
                        return;
                    }

                    if (checkbox.checked) {
                        checkbox.click();
                    }

                    handled = true;
                });

                if (handled) {
                    map.dataset.intensityDefaultHandledKey = this.trigger_key;
                }
            });
        },
        scheduleApply() {
            if (typeof window === "undefined") {
                return;
            }

            const delays = [0, 50, 200, 600];
            delays.forEach((delay) => {
                window.setTimeout(() => {
                    window.requestAnimationFrame(() => {
                        this.hideIntensityByDefault();
                    });
                }, delay);
            });
        },
    },
    mounted() {
        this.scheduleApply();
    },
    updated() {
        this.$nextTick(() => {
            this.scheduleApply();
        });
    },
};
</script>
