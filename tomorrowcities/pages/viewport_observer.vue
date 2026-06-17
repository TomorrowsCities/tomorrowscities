<template>
    <div style="display: none;"></div>
</template>

<script>
module.exports = {
    props: {
        width: {
            type: Number,
            default: 0,
        },
        on_width: {
            type: Function,
            default: null,
        },
    },
    methods: {
        emitWidth() {
            if (typeof window === "undefined" || !this.on_width) {
                return;
            }
            this.on_width(window.innerWidth || 0);
        },
        handleResize() {
            this.emitWidth();
        },
    },
    mounted() {
        this.emitWidth();
        if (typeof window !== "undefined") {
            window.addEventListener("resize", this.handleResize, { passive: true });
        }
    },
    beforeDestroy() {
        if (typeof window !== "undefined") {
            window.removeEventListener("resize", this.handleResize);
        }
    },
};
</script>
